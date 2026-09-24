"""
Tests for the database layer (Module 2).

Categories:
    1. Enum completeness and constraint compliance
    2. CaseStatus advisory-only invariant (Constraint #1)
    3. Model instantiation (in-memory, no DB required)
    4. Table metadata & relationship structure (via SQLAlchemy inspector)
    5. Persistence round-trip (in-memory SQLite)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, create_engine
from sqlalchemy.orm import Session

from thoa_screening.database import Base
from thoa_screening.database.models import (
    AuditAction,
    AuditLog,
    Case,
    CaseStatus,
    Document,
    DocumentType,
    Donor,
    ExtractionMethod,
    ExtractedData,
    Recipient,
    RelationType,
    Report,
    ReportStatus,
    ReportType,
    RuleOutcome,
    RuleResult,
    User,
    UserRole,
)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(scope="module")
def engine():
    """
    In-memory SQLite engine for structural and round-trip tests.

    SQLite is used here for speed and zero-dependency testing.
    PostgreSQL-specific features (native ENUMs, JSONB indexes) are
    tested in integration tests against a real PostgreSQL instance.
    """
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """Provide a transactional session that rolls back after each test."""
    with Session(engine) as sess:
        yield sess
        sess.rollback()


def _make_user(**overrides) -> User:
    """Construct a valid User instance (not persisted)."""
    defaults = {
        "id": uuid.uuid4(),
        "email": f"user-{uuid.uuid4().hex[:8]}@hospital.org",
        "full_name": "Dr. Test User",
        "role": UserRole.DATA_ENTRY,
        "password_hash": "$argon2id$fake_hash",
        "is_active": True,
    }
    defaults.update(overrides)
    return User(**defaults)


# ===================================================================
# 1. Enum completeness
# ===================================================================

class TestEnumCompleteness:
    """Verify all enum members are present and correctly typed."""

    def test_case_status_members(self):
        expected = {
            "PENDING", "UNDER_REVIEW", "AUTO_APPROVE",
            "COMMITTEE_REVIEW", "REJECTED", "NEEDS_INFO",
        }
        assert {e.value for e in CaseStatus} == expected

    def test_user_role_members(self):
        expected = {"VIEWER", "DATA_ENTRY", "COMMITTEE_MEMBER", "ADMIN"}
        assert {e.value for e in UserRole} == expected

    def test_relation_type_members(self):
        expected = {
            "SPOUSE", "PARENT_CHILD", "SIBLING",
            "GRANDPARENT_GRANDCHILD", "NON_RELATIVE", "FOREIGN_NATIONAL",
        }
        assert {e.value for e in RelationType} == expected

    def test_document_type_members(self):
        assert len(DocumentType) == 15  # 9 THOA forms + 4 supporting + ID + medical

    def test_rule_outcome_members(self):
        expected = {"PASS", "FAIL", "WARNING", "SKIPPED"}
        assert {e.value for e in RuleOutcome} == expected

    def test_audit_action_has_key_events(self):
        values = {e.value for e in AuditAction}
        for required in [
            "CASE_CREATED", "STATUS_CHANGED",
            "DOCUMENT_UPLOADED", "RULES_EVALUATED",
        ]:
            assert required in values

    def test_report_status_lifecycle(self):
        expected = {"DRAFT", "FINAL", "ARCHIVED"}
        assert {e.value for e in ReportStatus} == expected


# ===================================================================
# 2. Constraint #1 — advisory-only checks
# ===================================================================

class TestAdvisoryOnlyInvariant:
    """
    CaseStatus must NEVER be interpretable as a clinical transplant
    decision.  These tests encode Constraint #1 as assertions.
    """

    def test_no_clinical_approval_status(self):
        """Statuses like APPROVED/TRANSPLANT_APPROVED must never exist."""
        values = {e.value.upper() for e in CaseStatus}
        forbidden = {"APPROVED", "TRANSPLANT_APPROVED", "CLINICALLY_APPROVED"}
        assert values.isdisjoint(forbidden), (
            f"CaseStatus contains forbidden clinical-approval values: "
            f"{values & forbidden}"
        )

    def test_auto_approve_is_documented_as_advisory(self):
        """AUTO_APPROVE docstring must clarify it's not transplant approval."""
        docstring = CaseStatus.AUTO_APPROVE.__doc__ or ""
        assert "not" in docstring.lower(), (
            "AUTO_APPROVE docstring must explicitly state it is NOT "
            "transplant approval."
        )

    def test_rejected_is_documented_as_documentation_status(self):
        """REJECTED docstring must clarify it refers to documentation."""
        docstring = CaseStatus.REJECTED.__doc__ or ""
        assert "documentation" in docstring.lower() or "screening" in docstring.lower(), (
            "REJECTED docstring must clarify it refers to "
            "documentation/screening status, not transplant rejection."
        )

    def test_default_status_is_pending_after_flush(self, session):
        """New cases should default to PENDING after DB insertion."""
        user = _make_user()
        session.add(user)
        session.flush()

        case = Case(
            case_number="DEFAULT-TEST-001",
            relation_type=RelationType.SPOUSE,
            hospital_name="Test Hospital",
            organ_type="kidney",
            created_by_id=user.id,
        )
        session.add(case)
        session.flush()

        assert case.status == CaseStatus.PENDING


# ===================================================================
# 3. Model instantiation (no DB required for these)
# ===================================================================

class TestModelInstantiation:
    """Verify models can be constructed with valid data."""

    def test_user_creation(self):
        user = _make_user()
        assert user.email.endswith("@hospital.org")
        assert user.role == UserRole.DATA_ENTRY
        assert user.is_active is True

    def test_donor_repr_does_not_leak_aadhaar(self):
        """Constraint #6: repr must not contain raw PII."""
        donor = Donor(
            full_name="Arun Kumar",
            age=35,
            nationality="INDIAN",
            case_id=uuid.uuid4(),
        )
        repr_str = repr(donor)
        assert "aadhaar" not in repr_str.lower()

    def test_recipient_has_organ_field(self):
        """Recipient should accept organ_required field."""
        recipient = Recipient(
            full_name="Priya Sharma",
            age=30,
            nationality="INDIAN",
            case_id=uuid.uuid4(),
            organ_required="kidney",
        )
        assert recipient.organ_required == "kidney"

    def test_rule_result_creation(self):
        rr = RuleResult(
            case_id=uuid.uuid4(),
            rule_code="EMBASSY_NOC_REQUIRED",
            result=RuleOutcome.FAIL,
            severity="ERROR",
            message="Embassy NOC missing for foreign donor",
            legal_reference="Rule 20, THO Rules 2014",
            needs_legal_verification=True,
        )
        assert rr.needs_legal_verification is True
        assert rr.result == RuleOutcome.FAIL

    def test_audit_log_case_nullable(self):
        """AuditLog.case_id is nullable for system-level events."""
        log = AuditLog(
            user_id=uuid.uuid4(),
            action=AuditAction.USER_LOGIN,
            ip_address="192.168.1.1",
        )
        assert log.case_id is None

    def test_audit_log_has_no_updated_at(self):
        """AuditLog is append-only — should NOT have updated_at column."""
        columns = {c.name for c in AuditLog.__table__.columns}
        assert "updated_at" not in columns


# ===================================================================
# 4. Table metadata & relationship structure
# ===================================================================

class TestTableMetadata:
    """Verify tables, foreign keys, and indexes via SQLAlchemy metadata."""

    def test_all_tables_created(self, engine):
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {
            "users", "cases", "donors", "recipients", "documents",
            "extracted_data", "rule_results", "audit_logs", "reports",
        }
        assert expected.issubset(tables), (
            f"Missing tables: {expected - tables}"
        )

    def test_cases_foreign_keys(self, engine):
        """Cases should have FKs to users (created_by, assigned_to)."""
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("cases")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "users" in referred_tables

    def test_donors_fk_to_cases(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("donors")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "cases" in referred_tables

    def test_recipients_fk_to_cases(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("recipients")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "cases" in referred_tables

    def test_documents_fk_to_cases_and_users(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("documents")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "cases" in referred_tables
        assert "users" in referred_tables

    def test_extracted_data_fk_to_documents(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("extracted_data")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "documents" in referred_tables

    def test_rule_results_fk_to_cases(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("rule_results")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "cases" in referred_tables

    def test_audit_logs_fk_to_cases_and_users(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("audit_logs")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "cases" in referred_tables
        assert "users" in referred_tables

    def test_reports_fk_to_cases_and_users(self, engine):
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("reports")
        referred_tables = {fk["referred_table"] for fk in fks}
        assert "cases" in referred_tables
        assert "users" in referred_tables

    def test_donor_case_id_unique(self, engine):
        """donors.case_id should have a unique constraint (1:1 with Case)."""
        inspector = inspect(engine)
        uniques = inspector.get_unique_constraints("donors")
        unique_cols = {
            col
            for uc in uniques
            for col in uc["column_names"]
        }
        assert "case_id" in unique_cols

    def test_recipient_case_id_unique(self, engine):
        """recipients.case_id should have a unique constraint (1:1 with Case)."""
        inspector = inspect(engine)
        uniques = inspector.get_unique_constraints("recipients")
        unique_cols = {
            col
            for uc in uniques
            for col in uc["column_names"]
        }
        assert "case_id" in unique_cols


# ===================================================================
# 5. Persistence round-trip (in-memory SQLite)
# ===================================================================

class TestPersistenceRoundTrip:
    """Basic insert/query tests using in-memory SQLite."""

    def test_user_insert_and_query(self, session):
        user = _make_user()
        session.add(user)
        session.flush()

        queried = session.get(User, user.id)
        assert queried is not None
        assert queried.email == user.email
        assert queried.role == UserRole.DATA_ENTRY

    def test_case_with_donor_and_recipient(self, session):
        user = _make_user()
        session.add(user)
        session.flush()

        case = Case(
            case_number=f"THOA-{uuid.uuid4().hex[:8]}",
            relation_type=RelationType.SPOUSE,
            hospital_name="AIIMS Delhi",
            organ_type="kidney",
            created_by_id=user.id,
        )
        session.add(case)
        session.flush()

        donor = Donor(
            case_id=case.id,
            full_name="Arun Kumar",
            age=35,
            nationality="INDIAN",
        )
        recipient = Recipient(
            case_id=case.id,
            full_name="Priya Kumar",
            age=30,
            nationality="INDIAN",
            organ_required="kidney",
        )
        session.add_all([donor, recipient])
        session.flush()

        # Verify relationships
        loaded_case = session.get(Case, case.id)
        assert loaded_case.donor is not None
        assert loaded_case.donor.full_name == "Arun Kumar"
        assert loaded_case.recipient is not None
        assert loaded_case.recipient.full_name == "Priya Kumar"

    def test_document_with_extracted_data(self, session):
        user = _make_user()
        session.add(user)
        session.flush()

        case = Case(
            case_number=f"THOA-{uuid.uuid4().hex[:8]}",
            relation_type=RelationType.NON_RELATIVE,
            hospital_name="Medanta",
            organ_type="liver",
            created_by_id=user.id,
        )
        session.add(case)
        session.flush()

        doc = Document(
            case_id=case.id,
            document_type=DocumentType.FORM_5,
            file_path="/uploads/form_5.pdf",
            file_hash="b" * 64,
            original_filename="form_5_scan.pdf",
            uploaded_by_id=user.id,
        )
        session.add(doc)
        session.flush()

        extracted = ExtractedData(
            document_id=doc.id,
            field_name="donor_name",
            field_value="Vikram Singh",
            confidence_score=0.95,
            extraction_method=ExtractionMethod.OCR,
            needs_human_review=False,
        )
        session.add(extracted)
        session.flush()

        loaded_doc = session.get(Document, doc.id)
        assert len(loaded_doc.extracted_data) == 1
        assert loaded_doc.extracted_data[0].field_name == "donor_name"

    def test_case_status_defaults_to_pending(self, session):
        """Verify DB-level default: status = PENDING after insert."""
        user = _make_user()
        session.add(user)
        session.flush()

        case = Case(
            case_number=f"THOA-{uuid.uuid4().hex[:8]}",
            relation_type=RelationType.SIBLING,
            hospital_name="Fortis",
            organ_type="kidney",
            created_by_id=user.id,
        )
        session.add(case)
        session.flush()

        assert case.status == CaseStatus.PENDING

    def test_report_status_defaults_to_draft(self, session):
        """Verify DB-level default: report status = DRAFT after insert."""
        user = _make_user()
        session.add(user)
        session.flush()

        case = Case(
            case_number=f"THOA-{uuid.uuid4().hex[:8]}",
            relation_type=RelationType.SPOUSE,
            hospital_name="Apollo",
            organ_type="liver",
            created_by_id=user.id,
        )
        session.add(case)
        session.flush()

        report = Report(
            case_id=case.id,
            report_type=ReportType.SCREENING_SUMMARY,
            generated_by_id=user.id,
        )
        session.add(report)
        session.flush()

        assert report.status == ReportStatus.DRAFT

    def test_document_defaults_after_flush(self, session):
        """Document.is_verified and .is_active should default correctly."""
        user = _make_user()
        session.add(user)
        session.flush()

        case = Case(
            case_number=f"THOA-{uuid.uuid4().hex[:8]}",
            relation_type=RelationType.SPOUSE,
            hospital_name="CMC Vellore",
            organ_type="kidney",
            created_by_id=user.id,
        )
        session.add(case)
        session.flush()

        doc = Document(
            case_id=case.id,
            document_type=DocumentType.FORM_1,
            file_path="/uploads/form_1.pdf",
            file_hash="a" * 64,
            original_filename="form_1.pdf",
            uploaded_by_id=user.id,
        )
        session.add(doc)
        session.flush()

        assert doc.is_verified is False
        assert doc.is_active is True

    def test_audit_log_persists_without_case(self, session):
        """System-level audit events (no case_id) should persist."""
        user = _make_user()
        session.add(user)
        session.flush()

        log = AuditLog(
            user_id=user.id,
            action=AuditAction.USER_LOGIN,
            ip_address="10.0.0.1",
        )
        session.add(log)
        session.flush()

        loaded = session.get(AuditLog, log.id)
        assert loaded is not None
        assert loaded.case_id is None
        assert loaded.action == AuditAction.USER_LOGIN

    def test_rule_results_persist(self, session):
        user = _make_user()
        session.add(user)
        session.flush()

        case = Case(
            case_number=f"THOA-{uuid.uuid4().hex[:8]}",
            relation_type=RelationType.FOREIGN_NATIONAL,
            hospital_name="Max Hospital",
            organ_type="kidney",
            created_by_id=user.id,
        )
        session.add(case)
        session.flush()

        rr = RuleResult(
            case_id=case.id,
            rule_code="EMBASSY_NOC_REQUIRED",
            result=RuleOutcome.FAIL,
            severity="ERROR",
            message="Embassy NOC missing for foreign donor",
            legal_reference="Rule 20, THO Rules 2014",
            needs_legal_verification=True,
        )
        session.add(rr)
        session.flush()

        loaded_case = session.get(Case, case.id)
        assert len(loaded_case.rule_results) == 1
        assert loaded_case.rule_results[0].rule_code == "EMBASSY_NOC_REQUIRED"
