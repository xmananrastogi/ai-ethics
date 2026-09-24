"""
TransplantCase — the top-level composite model for a screening case.

This is the primary data structure that flows through the THOA screening
pipeline.  It aggregates donor/recipient profiles, the document
checklist, and the screening engine's output (anomalies + status).

IMPORTANT (Constraint #1):
    The ``screening_status`` field is NEVER "APPROVED" or "REJECTED".
    This system only surfaces anomalies for the human Authorization
    Committee.  ``PENDING_COMMITTEE_REVIEW`` is the default and most
    common outcome — it is a first-class status, not an edge case.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator

from thoa_screening.config import (
    get_force_committee_review_relations,
    get_legal_reference,
    get_required_documents,
)
from thoa_screening.schemas.documents import DocumentChecklist
from thoa_screening.schemas.enums import CaseStatus, Nationality, RelationType
from thoa_screening.schemas.profiles import DonorProfile, RecipientProfile


# ---------------------------------------------------------------------------
# Supporting model: anomalies surfaced during validation
# ---------------------------------------------------------------------------

class ValidationAnomaly(BaseModel):
    """
    A single anomaly detected during case screening.

    Anomalies are *observations*, not *decisions*.  They exist to help
    the Authorization Committee focus their review.

    Attributes:
        field: The schema field or document flag that triggered the anomaly.
        severity: ``"ERROR"`` (blocks committee submission) or
            ``"WARNING"`` (informational, committee should review).
        message: Human-readable description of the issue.
        legal_reference: The THOA section/rule reference, if known.
        needs_legal_verification: ``True`` if the cited section has not
            been verified by a legal professional.
    """

    field: str = Field(
        ..., description="Schema field or document that caused the anomaly."
    )
    severity: str = Field(
        ...,
        pattern=r"^(ERROR|WARNING)$",
        description="ERROR blocks submission; WARNING is informational.",
    )
    message: str = Field(
        ..., description="Human-readable anomaly description."
    )
    legal_reference: str | None = Field(
        default=None,
        description="THOA section/rule reference, if available.",
    )
    needs_legal_verification: bool = Field(
        default=False,
        description=(
            "True if the legal_reference has not been verified by a "
            "qualified legal professional."
        ),
    )


# ---------------------------------------------------------------------------
# TransplantCase — composite root
# ---------------------------------------------------------------------------

def _generate_case_id() -> str:
    """Generate a unique case identifier (UUID4 hex)."""
    return uuid.uuid4().hex


class TransplantCase(BaseModel):
    """
    Top-level transplant screening case.

    Aggregates all parties, documents, and screening outputs into a
    single validated structure.  Model-level validators enforce
    cross-field THOA rules read from external config.

    Usage::

        case = TransplantCase(
            relation_type=RelationType.NON_RELATIVE,
            donor=DonorProfile(...),
            recipient=RecipientProfile(...),
            documents=DocumentChecklist(has_form_1=True, ...),
        )
        # After construction, check:
        #   case.screening_status   → CaseStatus enum
        #   case.anomalies          → list[ValidationAnomaly]
        #   case.to_safe_dict()     → PII-masked dict for reports
    """

    # ---- Identity ----
    case_id: str = Field(
        default_factory=_generate_case_id,
        description="Unique case identifier (auto-generated UUID4 hex).",
    )

    # ---- Core data ----
    relation_type: RelationType = Field(
        ..., description="Donor–recipient relationship classification."
    )
    donor: DonorProfile
    recipient: RecipientProfile
    documents: DocumentChecklist = Field(
        default_factory=DocumentChecklist,
        description="Submitted document checklist.",
    )

    # ---- Screening outputs (populated by validators) ----
    screening_status: CaseStatus = Field(
        default=CaseStatus.PENDING_COMMITTEE_REVIEW,
        description=(
            "Screening outcome — advisory only. Defaults to "
            "PENDING_COMMITTEE_REVIEW."
        ),
    )
    anomalies: list[ValidationAnomaly] = Field(
        default_factory=list,
        description="Anomalies detected during validation.",
    )

    # ---- Metadata ----
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of case creation (UTC).",
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Free-text notes for the committee.",
    )

    # ==================================================================
    # MODEL VALIDATORS — cross-field THOA compliance checks
    # ==================================================================

    @model_validator(mode="after")
    def _run_screening_checks(self) -> "TransplantCase":
        """
        Master validation pipeline — runs all cross-field checks and
        populates ``anomalies`` and ``screening_status``.

        This method is deterministic: it reads rules from external
        config and applies boolean logic.  No LLM calls, no scoring.
        """
        anomalies: list[ValidationAnomaly] = []

        # 1. Embassy NOC check for foreign nationals
        anomalies.extend(self._check_form_21())

        # 2. Required documents for the stated relation type
        anomalies.extend(self._check_required_documents())

        # 3. Nationality consistency between donor and relation type
        anomalies.extend(self._check_nationality_consistency())

        # 4. Force committee review for certain relation types
        anomalies.extend(self._check_forced_committee_review())

        # Persist anomalies
        self.anomalies = anomalies

        # Derive screening status from anomalies
        self.screening_status = self._derive_status(anomalies)

        return self

    # ---- Individual check methods ----

    def _check_form_21(self) -> list[ValidationAnomaly]:
        """
        THOA 2014 Rules — foreign-national donors require Form 21 (relationship certificate).

        Raises a ValueError during construction (strict mode) AND records
        an anomaly so the committee sees it even if the error is caught.
        """
        anomalies: list[ValidationAnomaly] = []

        if (
            self.donor.nationality != Nationality.INDIAN
            and not self.documents.has_form_21
        ):
            ref = get_legal_reference("form_21")
            anomaly = ValidationAnomaly(
                field="documents.has_form_21",
                severity="ERROR",
                message=(
                    "Form 21 (Relationship certificate for foreign nationals) is missing for a "
                    "foreign-national donor."
                ),
                legal_reference=ref["section"] if ref else "THO Rules 2014",
                needs_legal_verification=(
                    ref.get("needs_legal_verification", True) if ref else True
                ),
            )
            anomalies.append(anomaly)
            raise ValueError(anomaly.message)

        return anomalies

    def _check_required_documents(self) -> list[ValidationAnomaly]:
        """
        Check that all documents required for the stated ``relation_type``
        are present, per the external config.
        """
        anomalies: list[ValidationAnomaly] = []
        required = get_required_documents(self.relation_type.value)

        for doc_flag in required:
            # Access the flag on the DocumentChecklist
            value = getattr(self.documents, doc_flag, None)
            if value is None:
                # Flag doesn't exist on the model — config mismatch
                anomalies.append(
                    ValidationAnomaly(
                        field=f"documents.{doc_flag}",
                        severity="WARNING",
                        message=(
                            f"Config references document flag '{doc_flag}' "
                            f"which does not exist on DocumentChecklist. "
                            f"This may indicate a config/schema mismatch."
                        ),
                    )
                )
                continue

            if not value:
                ref = get_legal_reference(
                    doc_flag.removeprefix("has_")
                    if doc_flag.startswith("has_")
                    else doc_flag
                )

                anomaly = ValidationAnomaly(
                    field=f"documents.{doc_flag}",
                    severity="ERROR",
                    message=(
                        f"Required document '{doc_flag}' is not submitted "
                        f"for relation type {self.relation_type.value}."
                    ),
                    legal_reference=ref["section"] if ref else None,
                    needs_legal_verification=(
                        ref.get("needs_legal_verification", True)
                        if ref
                        else True
                    ),
                )
                anomalies.append(anomaly)

        if anomalies:
            missing_flags = [a.field for a in anomalies if a.severity == "ERROR"]
            raise ValueError(
                f"Required documents missing for relation type "
                f"'{self.relation_type.value}': {missing_flags}. "
                f"Please submit all required documents before proceeding."
            )

        return anomalies

    def _check_nationality_consistency(self) -> list[ValidationAnomaly]:
        """
        Warn if the donor is foreign but relation_type is not
        FOREIGN_NATIONAL — the case may need re-classification.
        """
        anomalies: list[ValidationAnomaly] = []

        if (
            self.donor.nationality == Nationality.FOREIGN
            and self.relation_type != RelationType.FOREIGN_NATIONAL
        ):
            anomalies.append(
                ValidationAnomaly(
                    field="relation_type",
                    severity="WARNING",
                    message=(
                        f"Donor nationality is FOREIGN but relation_type is "
                        f"'{self.relation_type.value}', not FOREIGN_NATIONAL. "
                        f"Verify the classification is intentional."
                    ),
                )
            )

        return anomalies

    def _check_forced_committee_review(self) -> list[ValidationAnomaly]:
        """
        Certain relation types (e.g. NON_RELATIVE, FOREIGN_NATIONAL) must
        ALWAYS go through committee review per THOA Section 9.

        This is informational — PENDING_COMMITTEE_REVIEW is already the
        default, but this makes the *reason* explicit in the anomaly log.
        """
        anomalies: list[ValidationAnomaly] = []
        forced_relations = get_force_committee_review_relations()

        if self.relation_type.value in forced_relations:
            anomalies.append(
                ValidationAnomaly(
                    field="relation_type",
                    severity="WARNING",
                    message=(
                        f"Relation type '{self.relation_type.value}' "
                        f"mandates Authorization Committee review under "
                        f"THOA Section 9."
                    ),
                    legal_reference="Section 9, THOA 2011 Amendment",
                    needs_legal_verification=False,
                ),
            )

        return anomalies

    # ---- Status derivation ----

    @staticmethod
    def _derive_status(anomalies: list[ValidationAnomaly]) -> CaseStatus:
        """
        Derive the screening status from the collected anomalies.

        Logic:
            - Any ERROR-severity anomaly  → DOCUMENTATION_INCOMPLETE
            - Any WARNING-severity anomaly → ANOMALIES_DETECTED
            - No anomalies at all         → PENDING_COMMITTEE_REVIEW

        Note: PENDING_COMMITTEE_REVIEW is the *best possible* outcome.
        This system never produces "APPROVED".
        """
        has_errors = any(a.severity == "ERROR" for a in anomalies)
        has_warnings = any(a.severity == "WARNING" for a in anomalies)

        if has_errors:
            return CaseStatus.DOCUMENTATION_INCOMPLETE
        if has_warnings:
            return CaseStatus.ANOMALIES_DETECTED
        return CaseStatus.PENDING_COMMITTEE_REVIEW

    # ---- Safe serialisation (Constraint #6) ----

    def to_safe_dict(self) -> dict[str, Any]:
        """
        Serialise the case with all PII masked.

        Use this for committee-facing reports, logs, and API responses.
        Never use ``model_dump()`` directly for non-admin outputs.
        """
        data = self.model_dump(mode="json")
        data["donor"] = self.donor.to_safe_dict()
        data["recipient"] = self.recipient.to_safe_dict()
        return data
