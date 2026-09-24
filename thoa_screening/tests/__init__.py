"""
Unit tests for THOA screening schemas (Module 1).

Test categories:
    1. Enum completeness
    2. PII masking correctness
    3. Profile field validation (age, Aadhaar format)
    4. Document-requirement validation per relation type
    5. Embassy NOC requirement for foreign nationals
    6. TransplantCase status derivation logic
    7. Safe serialisation (PII never leaks in non-admin output)
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from thoa_screening.schemas.enums import CaseStatus, Nationality, RelationType
from thoa_screening.schemas.masking import mask_aadhaar, mask_pan
from thoa_screening.schemas.profiles import DonorProfile, RecipientProfile
from thoa_screening.schemas.documents import DocumentChecklist
from thoa_screening.schemas.case import TransplantCase, ValidationAnomaly


# ===================================================================
# Helpers — reusable test fixtures
# ===================================================================

def _make_donor(**overrides) -> dict:
    """Construct a valid donor dict, applying any overrides."""
    base = {
        "full_name": "Arun Kumar",
        "age": 35,
        "aadhaar_number": "123456789012",
        "nationality": Nationality.INDIAN,
        "monthly_income": Decimal("50000.00"),
    }
    base.update(overrides)
    return base


def _make_recipient(**overrides) -> dict:
    """Construct a valid recipient dict, applying any overrides."""
    base = {
        "full_name": "Priya Sharma",
        "age": 30,
        "aadhaar_number": "987654321098",
        "nationality": Nationality.INDIAN,
        "monthly_income": Decimal("40000.00"),
    }
    base.update(overrides)
    return base


def _make_full_documents(**overrides) -> dict:
    """Construct a document checklist with all flags True."""
    base = {
        "has_form_1": True,
        "has_form_2": True,
        "has_form_3": True,
        "has_form_4": True,
        "has_form_5": True,
        "has_form_10": True,
        "has_form_11": True,
        "has_form_20": True,
        "has_form_21": True,
        "has_financial_affidavit": True,
        "dna_test_match": True,
        "police_verification": True,
        "identity_proof_submitted": True,
        "medical_report_submitted": True,
    }
    base.update(overrides)
    return base


# ===================================================================
# 1. Enum tests
# ===================================================================

class TestEnums:
    """Verify enum members match the specification."""

    def test_relation_type_members(self):
        expected = {
            "SPOUSE", "PARENT_CHILD", "SIBLING",
            "GRANDPARENT_GRANDCHILD", "NON_RELATIVE", "FOREIGN_NATIONAL",
        }
        assert {e.value for e in RelationType} == expected

    def test_case_status_no_approved_or_rejected(self):
        """Constraint #1: system never approves or rejects."""
        values = {e.value for e in CaseStatus}
        assert "APPROVED" not in values
        assert "REJECTED" not in values

    def test_case_status_has_pending_committee_review(self):
        """PENDING_COMMITTEE_REVIEW must be a first-class outcome."""
        assert CaseStatus.PENDING_COMMITTEE_REVIEW in CaseStatus


# ===================================================================
# 2. PII masking tests
# ===================================================================

class TestMasking:

    def test_mask_aadhaar_valid(self):
        assert mask_aadhaar("123456789012") == "XXXX-XXXX-9012"

    def test_mask_aadhaar_all_zeros(self):
        assert mask_aadhaar("000000000000") == "XXXX-XXXX-0000"

    def test_mask_aadhaar_invalid_length(self):
        with pytest.raises(ValueError, match="expected 12 digits"):
            mask_aadhaar("12345")

    def test_mask_aadhaar_non_digits(self):
        with pytest.raises(ValueError):
            mask_aadhaar("12345678901a")

    def test_mask_pan_valid(self):
        assert mask_pan("ABCDE1234F") == "XXXXXX234F"

    def test_mask_pan_invalid(self):
        with pytest.raises(ValueError, match="invalid PAN"):
            mask_pan("INVALID")


# ===================================================================
# 3. Profile validation tests
# ===================================================================

class TestDonorProfile:

    def test_valid_donor(self):
        donor = DonorProfile(**_make_donor())
        assert donor.age == 35
        assert donor.full_name == "Arun Kumar"

    def test_minor_donor_raises(self):
        """Constraint: donor must be >= 18 (from config)."""
        with pytest.raises(ValueError, match="at least 18"):
            DonorProfile(**_make_donor(age=17))

    def test_donor_age_exactly_18(self):
        """Boundary: exactly 18 should pass."""
        donor = DonorProfile(**_make_donor(age=18))
        assert donor.age == 18

    def test_invalid_aadhaar_format(self):
        """Aadhaar must be exactly 12 digits."""
        with pytest.raises(ValueError):
            DonorProfile(**_make_donor(aadhaar_number="1234"))

    def test_invalid_aadhaar_with_letters(self):
        with pytest.raises(ValueError):
            DonorProfile(**_make_donor(aadhaar_number="12345678901X"))

    def test_negative_income_rejected(self):
        with pytest.raises(ValueError):
            DonorProfile(**_make_donor(monthly_income=Decimal("-100")))

    def test_zero_income_accepted(self):
        donor = DonorProfile(**_make_donor(monthly_income=Decimal("0")))
        assert donor.monthly_income == 0


class TestRecipientProfile:

    def test_valid_recipient(self):
        recipient = RecipientProfile(**_make_recipient())
        assert recipient.full_name == "Priya Sharma"

    def test_recipient_minor_allowed(self):
        """Minors can receive organs (with guardian consent)."""
        recipient = RecipientProfile(**_make_recipient(age=5))
        assert recipient.age == 5

    def test_recipient_age_zero_rejected(self):
        """Age must be > 0."""
        with pytest.raises(ValueError):
            RecipientProfile(**_make_recipient(age=0))


# ===================================================================
# 4. Document requirement tests
# ===================================================================

class TestDocumentValidation:
    """
    These tests verify that the model validator correctly raises
    ValueError when required documents are missing, based on the
    external config's ``required_documents_by_relation`` mapping.
    """

    def test_near_relative_with_all_docs_passes(self):
        """SPOUSE only needs Form 2 + Form 4 + ID + Medical."""
        case = TransplantCase(
            relation_type=RelationType.SPOUSE,
            donor=DonorProfile(**_make_donor()),
            recipient=RecipientProfile(**_make_recipient()),
            documents=DocumentChecklist(
                has_form_2=True,
                has_form_4=True,
                identity_proof_submitted=True,
                medical_report_submitted=True,
            ),
        )
        # Should not raise — SPOUSE needs only Form 2, 4, ID, Medical
        assert case.screening_status in {
            CaseStatus.PENDING_COMMITTEE_REVIEW,
            CaseStatus.ANOMALIES_DETECTED,
        }

    def test_spouse_missing_form_2_raises(self):
        with pytest.raises(ValueError, match="Required documents missing"):
            TransplantCase(
                relation_type=RelationType.SPOUSE,
                donor=DonorProfile(**_make_donor()),
                recipient=RecipientProfile(**_make_recipient()),
                documents=DocumentChecklist(
                    has_form_2=False,  # Missing
                    has_form_4=True,
                    identity_proof_submitted=True,
                    medical_report_submitted=True,
                ),
            )

    def test_non_relative_missing_form_11_raises(self):
        with pytest.raises(ValueError, match="Required documents missing"):
            TransplantCase(
                relation_type=RelationType.NON_RELATIVE,
                donor=DonorProfile(**_make_donor()),
                recipient=RecipientProfile(**_make_recipient()),
                documents=DocumentChecklist(
                    has_form_3=True,
                    has_form_4=True,
                    has_form_11=False,  # Missing
                    has_financial_affidavit=True,
                    police_verification=True,
                    identity_proof_submitted=True,
                    medical_report_submitted=True,
                ),
            )

    def test_non_relative_all_docs_passes(self):
        case = TransplantCase(
            relation_type=RelationType.NON_RELATIVE,
            donor=DonorProfile(**_make_donor()),
            recipient=RecipientProfile(**_make_recipient()),
            documents=DocumentChecklist(
                has_form_3=True,
                has_form_4=True,
                has_form_11=True,
                has_financial_affidavit=True,
                police_verification=True,
                identity_proof_submitted=True,
                medical_report_submitted=True,
            ),
        )
        # NON_RELATIVE always forces committee review (WARNING)
        assert case.screening_status == CaseStatus.ANOMALIES_DETECTED


# ===================================================================
# 5. Embassy NOC tests
# ===================================================================

class TestEmbassyNoc:

    def test_foreign_donor_missing_form_21_raises(self):
        """Constraint: Form 21 required when nationality != INDIAN."""
        with pytest.raises(ValueError, match="Form 21"):
            TransplantCase(
                relation_type=RelationType.FOREIGN_NATIONAL,
                donor=DonorProfile(**_make_donor(nationality=Nationality.FOREIGN)),
                recipient=RecipientProfile(**_make_recipient()),
                documents=DocumentChecklist(
                    has_form_4=True,
                    has_form_11=True,
                    has_form_21=False,  # Missing!
                    has_financial_affidavit=True,
                    police_verification=True,
                    identity_proof_submitted=True,
                    medical_report_submitted=True,
                ),
            )

    def test_foreign_donor_with_embassy_noc_passes(self):
        case = TransplantCase(
            relation_type=RelationType.FOREIGN_NATIONAL,
            donor=DonorProfile(**_make_donor(nationality=Nationality.FOREIGN)),
            recipient=RecipientProfile(**_make_recipient()),
            documents=DocumentChecklist(**_make_full_documents()),
        )
        assert case.screening_status in {
            CaseStatus.PENDING_COMMITTEE_REVIEW,
            CaseStatus.ANOMALIES_DETECTED,
        }

    def test_indian_donor_no_form_21_is_fine(self):
        """Indian donors should not need Form 21."""
        case = TransplantCase(
            relation_type=RelationType.SPOUSE,
            donor=DonorProfile(**_make_donor(nationality=Nationality.INDIAN)),
            recipient=RecipientProfile(**_make_recipient()),
            documents=DocumentChecklist(
                has_form_2=True,
                has_form_4=True,
                identity_proof_submitted=True,
                medical_report_submitted=True,
            ),
        )
        assert case.donor.nationality == Nationality.INDIAN


# ===================================================================
# 6. Status derivation tests
# ===================================================================

class TestStatusDerivation:

    def test_no_anomalies_gives_pending_review(self):
        """Best-case outcome is PENDING_COMMITTEE_REVIEW, never APPROVED."""
        status = TransplantCase._derive_status([])
        assert status == CaseStatus.PENDING_COMMITTEE_REVIEW

    def test_warning_only_gives_anomalies_detected(self):
        warning = ValidationAnomaly(
            field="test",
            severity="WARNING",
            message="Test warning",
        )
        status = TransplantCase._derive_status([warning])
        assert status == CaseStatus.ANOMALIES_DETECTED

    def test_error_gives_documentation_incomplete(self):
        error = ValidationAnomaly(
            field="test",
            severity="ERROR",
            message="Test error",
        )
        status = TransplantCase._derive_status([error])
        assert status == CaseStatus.DOCUMENTATION_INCOMPLETE

    def test_error_takes_precedence_over_warning(self):
        items = [
            ValidationAnomaly(field="a", severity="WARNING", message="w"),
            ValidationAnomaly(field="b", severity="ERROR", message="e"),
        ]
        status = TransplantCase._derive_status(items)
        assert status == CaseStatus.DOCUMENTATION_INCOMPLETE


# ===================================================================
# 7. Safe serialisation tests (Constraint #6)
# ===================================================================

class TestSafeSerialization:

    def test_donor_safe_dict_masks_aadhaar(self):
        donor = DonorProfile(**_make_donor())
        safe = donor.to_safe_dict()
        assert safe["aadhaar_number"] == "XXXX-XXXX-9012"
        # Raw model still has the full number
        assert donor.aadhaar_number == "123456789012"

    def test_recipient_safe_dict_masks_aadhaar(self):
        recipient = RecipientProfile(**_make_recipient())
        safe = recipient.to_safe_dict()
        assert safe["aadhaar_number"] == "XXXX-XXXX-1098"

    def test_case_safe_dict_masks_both_profiles(self):
        case = TransplantCase(
            relation_type=RelationType.SPOUSE,
            donor=DonorProfile(**_make_donor()),
            recipient=RecipientProfile(**_make_recipient()),
            documents=DocumentChecklist(
                has_form_2=True,
                has_form_4=True,
                identity_proof_submitted=True,
                medical_report_submitted=True,
            ),
        )
        safe = case.to_safe_dict()
        assert safe["donor"]["aadhaar_number"].startswith("XXXX")
        assert safe["recipient"]["aadhaar_number"].startswith("XXXX")

    def test_repr_masks_aadhaar(self):
        donor = DonorProfile(**_make_donor())
        repr_str = repr(donor)
        assert "123456789012" not in repr_str
        assert "XXXX-XXXX-9012" in repr_str
