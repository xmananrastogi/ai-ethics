"""
SQLAlchemy 2.0 ORM models for the THOA screening system.

Tables (in dependency order):
    1. User          — system operators, committee members, admins
    2. Case          — the transplant screening case (composite root)
    3. Donor         — living organ donor profile
    4. Recipient     — transplant recipient profile
    5. Document      — uploaded legal/medical documents
    6. ExtractedData — structured data extracted from documents
    7. RuleResult    — deterministic rule-engine outputs per case
    8. AuditLog      — immutable, append-only compliance audit trail
    9. Report        — generated committee-facing reports

Design principles:
    - UUID primary keys for non-sequential, distributed-safe IDs.
    - PII columns suffixed ``_enc`` store application-level ciphertext;
      ``_hash`` columns store blind indexes for lookup without decryption.
    - PostgreSQL-native JSONB for flexible audit detail payloads.
    - All THOA-specific logic is in external config, not in DB constraints.

IMPORTANT (Constraint #1):
    CaseStatus values track the SCREENING CASE's workflow state, NOT the
    transplant's clinical approval.  This system is advisory-only.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from thoa_screening.database import Base


# ===================================================================
# ENUMS — PostgreSQL-native enum types
# ===================================================================
# These are DATABASE-LAYER enums, distinct from the Pydantic screening
# enums in schemas/enums.py.  The two layers may share values but
# serve different architectural purposes.
# ===================================================================


class CaseStatus(str, enum.Enum):
    """
    Screening-case workflow lifecycle.

    ┌─────────────────────────────────────────────────────────────────┐
    │  IMPORTANT — ADVISORY ONLY (Constraint #1)                     │
    │                                                                 │
    │  These statuses track the SCREENING CASE's documentation and    │
    │  review workflow.  They do NOT constitute clinical approval or  │
    │  rejection of any transplant procedure.                         │
    │                                                                 │
    │  • AUTO_APPROVE  = all automated screening checks passed;       │
    │    case is auto-forwarded to the committee for their decision.  │
    │  • REJECTED      = screening documentation is insufficient or   │
    │    non-compliant; the case cannot proceed to committee review   │
    │    in its current state.                                        │
    │  • The Authorization Committee retains sole authority over the  │
    │    actual transplant decision.                                  │
    └─────────────────────────────────────────────────────────────────┘
    """

    PENDING = "PENDING"
    """Case created, screening not yet started."""

    UNDER_REVIEW = "UNDER_REVIEW"
    """Active screening / document verification in progress."""

    AUTO_APPROVE = "AUTO_APPROVE"
    """
    All automated checks passed — case auto-forwarded to committee.
    This is NOT transplant approval; the committee still decides.
    """

    COMMITTEE_REVIEW = "COMMITTEE_REVIEW"
    """
    Anomalies detected or relation type mandates explicit committee
    examination before the case can proceed.
    """

    REJECTED = "REJECTED"
    """
    Screening documentation is non-compliant or insufficient.
    The case cannot be forwarded to the committee in this state.
    This is NOT transplant rejection — it is a documentation status.
    """

    NEEDS_INFO = "NEEDS_INFO"
    """Additional information or documents have been requested."""


class UserRole(str, enum.Enum):
    """System user roles with ascending privilege levels."""

    VIEWER = "VIEWER"
    """Read-only access to anonymised case data."""

    DATA_ENTRY = "DATA_ENTRY"
    """Can create and edit cases, upload documents."""

    COMMITTEE_MEMBER = "COMMITTEE_MEMBER"
    """Can review cases, add notes, change case status."""

    ADMIN = "ADMIN"
    """Full access including user management and PII visibility."""


class RelationType(str, enum.Enum):
    """
    Donor–recipient relationship classification (mirrors schemas.enums
    but is independently defined for database-layer independence).
    """

    SPOUSE = "SPOUSE"
    PARENT_CHILD = "PARENT_CHILD"
    SIBLING = "SIBLING"
    GRANDPARENT_GRANDCHILD = "GRANDPARENT_GRANDCHILD"
    NON_RELATIVE = "NON_RELATIVE"
    FOREIGN_NATIONAL = "FOREIGN_NATIONAL"


class DocumentType(str, enum.Enum):
    """Types of documents that can be attached to a case."""

    FORM_1 = "FORM_1"
    """Consent for donation by living near-relative donor."""

    FORM_2 = "FORM_2"
    """Consent for donation by living spousal donor."""

    FORM_3 = "FORM_3"
    """Consent for donation by non-near-relative donor."""

    FORM_4 = "FORM_4"
    """Medical fitness certification of living donor."""

    FORM_5 = "FORM_5"
    """Certification of genetic relationship."""

    FORM_10 = "FORM_10"
    """Brain stem death certification."""

    FORM_11 = "FORM_11"
    """Joint application for transplant approval."""

    FORM_20 = "FORM_20"
    """Domicile verification certificate."""

    FORM_21 = "FORM_21"
    """Relationship certificate for foreign nationals."""

    FINANCIAL_AFFIDAVIT = "FINANCIAL_AFFIDAVIT"
    """Affidavit of no commercial dealing."""

    DNA_REPORT = "DNA_REPORT"
    """DNA test report establishing biological relationship."""

    POLICE_VERIFICATION = "POLICE_VERIFICATION"
    """Police verification report for the donor."""

    IDENTITY_PROOF = "IDENTITY_PROOF"
    """Government-issued photo ID (Aadhaar, passport, etc.)."""

    MEDICAL_REPORT = "MEDICAL_REPORT"
    """Medical fitness / compatibility reports."""

    OTHER = "OTHER"
    """Any supporting document not covered above."""


class ExtractionMethod(str, enum.Enum):
    """How a data field was extracted from a document."""

    MANUAL = "MANUAL"
    """Manually entered by an operator."""

    OCR = "OCR"
    """Optical character recognition (automated)."""

    NLP = "NLP"
    """Natural language processing / information extraction."""


class RuleOutcome(str, enum.Enum):
    """Result of a single rule evaluation."""

    PASS = "PASS"
    """The rule's condition is satisfied."""

    FAIL = "FAIL"
    """The rule's condition is violated — anomaly flagged."""

    WARNING = "WARNING"
    """Condition met but with caveats requiring human attention."""

    SKIPPED = "SKIPPED"
    """Rule was not applicable to this case configuration."""


class AuditAction(str, enum.Enum):
    """Categorised action types for the audit trail."""

    CASE_CREATED = "CASE_CREATED"
    CASE_UPDATED = "CASE_UPDATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    DATA_EXTRACTED = "DATA_EXTRACTED"
    RULES_EVALUATED = "RULES_EVALUATED"
    REPORT_GENERATED = "REPORT_GENERATED"
    CASE_ASSIGNED = "CASE_ASSIGNED"
    NOTE_ADDED = "NOTE_ADDED"
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    PERMISSION_CHANGED = "PERMISSION_CHANGED"


class ReportType(str, enum.Enum):
    """Types of reports generated for committee review."""

    SCREENING_SUMMARY = "SCREENING_SUMMARY"
    """End-to-end screening result summary."""

    COMMITTEE_BRIEF = "COMMITTEE_BRIEF"
    """Concise brief prepared for Authorization Committee meetings."""

    ANOMALY_REPORT = "ANOMALY_REPORT"
    """Detailed breakdown of all detected anomalies."""

    COMPLIANCE_AUDIT = "COMPLIANCE_AUDIT"
    """Regulatory compliance audit report."""


class ReportStatus(str, enum.Enum):
    """Lifecycle status of a generated report."""

    DRAFT = "DRAFT"
    FINAL = "FINAL"
    ARCHIVED = "ARCHIVED"


# ===================================================================
# MIXIN — shared timestamp columns
# ===================================================================


class TimestampMixin:
    """
    Adds ``created_at`` and ``updated_at`` columns to any model.

    Both columns use timezone-aware datetimes and default to the
    database server's ``now()`` function.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Row creation timestamp (server-side UTC).",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Last modification timestamp (auto-updated).",
    )


# ===================================================================
# 1. USER
# ===================================================================


class User(TimestampMixin, Base):
    """
    System user — operators, committee members, and administrators.

    Relationships:
        - ``cases_created`` → Cases this user created (1:N).
        - ``cases_assigned`` → Cases currently assigned to this user (1:N).
        - ``audit_entries`` → Audit log entries for this user's actions (1:N).
        - ``reports_generated`` → Reports this user generated (1:N).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True,
        doc="Unique login email address.",
    )
    full_name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        doc="Display name.",
    )
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_type=True),
        nullable=False,
        doc="Access-control role.",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Bcrypt / argon2 hash — NEVER store plaintext passwords.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        doc="Soft-disable flag (False = account locked).",
    )

    # ---- Relationships ----
    cases_created: Mapped[list["Case"]] = relationship(
        back_populates="created_by",
        foreign_keys="[Case.created_by_id]",
    )
    cases_assigned: Mapped[list["Case"]] = relationship(
        back_populates="assigned_to",
        foreign_keys="[Case.assigned_to_id]",
    )
    audit_entries: Mapped[list["AuditLog"]] = relationship(
        back_populates="user",
    )
    reports_generated: Mapped[list["Report"]] = relationship(
        back_populates="generated_by",
    )

    def __repr__(self) -> str:
        return (
            f"User(id={self.id!s:.8}, email='{self.email}', "
            f"role={self.role.value})"
        )


# ===================================================================
# 2. CASE
# ===================================================================


class Case(TimestampMixin, Base):
    """
    The transplant screening case — the composite root of the domain.

    A Case links one Donor to one Recipient, collects Documents, runs
    rule evaluations, and produces Reports — all for the Authorization
    Committee's review.

    Relationships:
        - ``donor`` → The living organ donor (1:1, cascade delete).
        - ``recipient`` → The transplant recipient (1:1, cascade delete).
        - ``documents`` → Attached legal/medical documents (1:N, cascade).
        - ``rule_results`` → Deterministic rule-engine outputs (1:N, cascade).
        - ``audit_logs`` → Immutable audit trail (1:N, restrict delete).
        - ``reports`` → Generated committee reports (1:N, cascade).
        - ``created_by`` → User who created the case (N:1).
        - ``assigned_to`` → User currently responsible (N:1, nullable).
    """

    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_status_created", "status", "created_at"),
        {"comment": "Core screening case — one per donor/recipient pair."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    case_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        doc="Human-readable case reference (e.g. 'THOA-2026-00042').",
    )
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, name="case_status", create_type=True),
        default=CaseStatus.PENDING,
        nullable=False,
        index=True,
        doc="Current workflow status (advisory only — see CaseStatus docs).",
    )
    relation_type: Mapped[RelationType] = mapped_column(
        SAEnum(RelationType, name="relation_type", create_type=True),
        nullable=False,
        doc="Donor–recipient relationship classification.",
    )
    hospital_name: Mapped[str] = mapped_column(
        String(300), nullable=False,
        doc="Registered transplant hospital name.",
    )
    hospital_registration_no: Mapped[Optional[str]] = mapped_column(
        String(100),
        doc="Hospital's THOA registration number.",
    )
    organ_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        doc="Organ being transplanted (e.g. 'kidney', 'liver').",
    )
    urgency_level: Mapped[Optional[str]] = mapped_column(
        String(50),
        doc="Clinical urgency (informational; does not affect screening).",
    )

    # ---- Foreign keys ----
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False,
        doc="User who created this case.",
    )
    assigned_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id"),
        doc="User currently responsible for the case (nullable).",
    )

    # ---- Workflow timestamps ----
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        doc="When the case was submitted for screening.",
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        doc="When the committee last reviewed the case.",
    )

    # ---- Free-text notes ----
    committee_decision_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        doc="Committee's notes after review (human-authored, never auto-generated).",
    )

    # ---- Relationships ----
    created_by: Mapped["User"] = relationship(
        back_populates="cases_created",
        foreign_keys=[created_by_id],
    )
    assigned_to: Mapped[Optional["User"]] = relationship(
        back_populates="cases_assigned",
        foreign_keys=[assigned_to_id],
    )
    donor: Mapped[Optional["Donor"]] = relationship(
        back_populates="case",
        uselist=False,
        cascade="all, delete-orphan",
    )
    recipient: Mapped[Optional["Recipient"]] = relationship(
        back_populates="case",
        uselist=False,
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="Document.created_at.desc()",
    )
    rule_results: Mapped[list["RuleResult"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="RuleResult.evaluated_at.desc()",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="case",
        # RESTRICT: audit logs must never be silently deleted.
        passive_deletes="all",
        order_by="AuditLog.created_at.desc()",
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="Report.created_at.desc()",
    )

    def __repr__(self) -> str:
        return (
            f"Case(case_number='{self.case_number}', "
            f"status={self.status.value}, "
            f"relation_type={self.relation_type.value})"
        )


# ===================================================================
# PERSON MIXIN — shared columns for Donor and Recipient
# ===================================================================


class _PersonMixin:
    """
    Shared columns for Donor and Recipient tables.

    PII handling (Constraint #6):
        - ``aadhaar_number_enc``: stores AES-256-GCM ciphertext of the
          12-digit Aadhaar number.  Application-layer encryption is
          REQUIRED before persistence.
        - ``aadhaar_hash``: stores a HMAC-SHA256 blind index for
          lookup-by-Aadhaar without decryption.
        - ``contact_phone_enc``: encrypted phone number.
        - Raw PII is NEVER stored in plaintext columns.
    """

    full_name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        doc="Full legal name as on government ID.",
    )
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        doc="Date of birth (used for age calculation / verification).",
    )
    age: Mapped[int] = mapped_column(
        Integer, nullable=False,
        doc="Age in whole years at time of case creation.",
    )
    gender: Mapped[Optional[str]] = mapped_column(
        String(20),
        doc="Self-declared gender.",
    )

    # ---- PII columns (encrypted at application layer) ----

    aadhaar_number_enc: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary,
        doc=(
            "AES-256-GCM encrypted Aadhaar number.  Decrypt only in "
            "admin-privileged contexts.  NEVER log or serialize raw."
        ),
    )
    aadhaar_hash: Mapped[Optional[str]] = mapped_column(
        String(64), index=True,
        doc=(
            "HMAC-SHA256 blind index of Aadhaar number for lookups "
            "without decryption."
        ),
    )
    contact_phone_enc: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary,
        doc="Encrypted contact phone number.",
    )
    pan_number_enc: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary,
        doc="AES-256-GCM encrypted PAN number. NEVER log or serialize raw.",
    )
    pan_hash: Mapped[Optional[str]] = mapped_column(
        String(64), index=True,
        doc="HMAC-SHA256 blind index of PAN number for lookups.",
    )

    # ---- Non-PII fields ----

    nationality: Mapped[str] = mapped_column(
        String(50), nullable=False, default="INDIAN",
        doc="Nationality classification (INDIAN / FOREIGN / specific country).",
    )
    blood_group: Mapped[Optional[str]] = mapped_column(
        String(10),
        doc="Blood group (e.g. 'A+', 'O-').",
    )
    monthly_income: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=12, scale=2),
        doc="Self-declared monthly income in INR.",
    )
    address: Mapped[Optional[str]] = mapped_column(
        Text,
        doc="Residential address.",
    )


# ===================================================================
# 3. DONOR
# ===================================================================


class Donor(_PersonMixin, TimestampMixin, Base):
    """
    Living organ donor profile.

    One-to-one with Case.  The ``case_id`` column has a unique
    constraint ensuring each case has at most one donor.

    Note: the donor minimum-age constraint (18 under THOA Section 3)
    is enforced at the APPLICATION layer (Pydantic validators + rule
    engine) rather than as a DB CHECK, because the threshold is
    configurable via external rules config.

    Relationship:
        - ``case`` → Parent screening case (N:1, unique = effectively 1:1).
    """

    __tablename__ = "donors"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_donors_case_id"),
        {"comment": "Living organ donor — one per screening case."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        doc="Parent case (unique — 1:1 relationship).",
    )

    # ---- Relationship ----
    case: Mapped["Case"] = relationship(back_populates="donor")

    def __repr__(self) -> str:
        return (
            f"Donor(id={self.id!s:.8}, name='{self.full_name}', "
            f"age={self.age})"
        )


# ===================================================================
# 4. RECIPIENT
# ===================================================================


class Recipient(_PersonMixin, TimestampMixin, Base):
    """
    Transplant recipient profile.

    One-to-one with Case.  Unlike Donor, there is no minimum-age
    constraint — minors can receive organs with guardian consent
    (handled by the Authorization Committee, not auto-screened).

    Additional fields:
        - ``organ_required``: the organ the recipient needs.
        - ``medical_urgency_notes``: clinical context for the committee.

    Relationship:
        - ``case`` → Parent screening case (1:1 via unique constraint).
    """

    __tablename__ = "recipients"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_recipients_case_id"),
        {"comment": "Transplant recipient — one per screening case."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        doc="Parent case (unique — 1:1 relationship).",
    )
    organ_required: Mapped[Optional[str]] = mapped_column(
        String(100),
        doc="Organ the recipient requires.",
    )
    medical_urgency_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        doc="Clinical urgency notes for committee reference.",
    )

    # ---- Relationship ----
    case: Mapped["Case"] = relationship(back_populates="recipient")

    def __repr__(self) -> str:
        return (
            f"Recipient(id={self.id!s:.8}, name='{self.full_name}', "
            f"age={self.age})"
        )


# ===================================================================
# 5. DOCUMENT
# ===================================================================


class Document(TimestampMixin, Base):
    """
    A legal or medical document attached to a screening case.

    Multiple documents of the same type are allowed per case to support
    re-submissions (e.g. a corrected Form 1).  The ``is_active`` flag
    identifies the current version; historical documents are retained
    for audit purposes.

    Relationships:
        - ``case`` → Parent screening case (N:1).
        - ``uploaded_by`` → User who uploaded the document (N:1).
        - ``verified_by_user`` → User who verified the document (N:1, nullable).
        - ``extracted_data`` → Structured data extracted from this doc (1:N).
    """

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_case_type", "case_id", "document_type"),
        {"comment": "Legal/medical documents attached to screening cases."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Parent screening case.",
    )
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type", create_type=True),
        nullable=False,
        doc="Categorisation per THOA form numbering.",
    )
    file_path: Mapped[str] = mapped_column(
        String(500), nullable=False,
        doc="Storage path (S3 key, local path, etc.).",
    )
    file_hash: Mapped[str] = mapped_column(
        String(64), nullable=False,
        doc="SHA-256 hash for integrity verification.",
    )
    original_filename: Mapped[str] = mapped_column(
        String(255), nullable=False,
        doc="Original uploaded filename (for display only).",
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        doc="MIME type (e.g. 'application/pdf').",
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        doc="File size in bytes.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        doc="True = current version; False = superseded by re-upload.",
    )

    # ---- Verification fields ----
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        doc="True if a human has verified this document's authenticity.",
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
        doc="User who uploaded this document.",
    )
    verified_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        doc="User who verified this document (null if unverified).",
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        doc="Timestamp of verification.",
    )

    # ---- Relationships ----
    case: Mapped["Case"] = relationship(back_populates="documents")
    uploaded_by: Mapped["User"] = relationship(foreign_keys=[uploaded_by_id])
    verified_by_user: Mapped[Optional["User"]] = relationship(
        foreign_keys=[verified_by_id],
    )
    extracted_data: Mapped[list["ExtractedData"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"Document(id={self.id!s:.8}, type={self.document_type.value}, "
            f"verified={self.is_verified})"
        )


# ===================================================================
# 6. EXTRACTED DATA
# ===================================================================


class ExtractedData(TimestampMixin, Base):
    """
    Structured data field extracted from a document (via OCR, NLP, or
    manual entry).

    Each row is a single key–value pair extracted from a specific
    document.  Low-confidence extractions are flagged for human review.

    Relationships:
        - ``document`` → Source document (N:1).
        - ``reviewed_by_user`` → User who reviewed the extraction (N:1, nullable).
    """

    __tablename__ = "extracted_data"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_extracted_data_confidence_range",
        ),
        Index("ix_extracted_data_document", "document_id"),
        {"comment": "Key-value pairs extracted from uploaded documents."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        doc="Source document.",
    )
    field_name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        doc="Name of the extracted field (e.g. 'donor_name', 'date_signed').",
    )
    field_value: Mapped[Optional[str]] = mapped_column(
        Text,
        doc="Extracted value as text.",
    )
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=4, scale=3),
        doc="Extraction confidence [0.0–1.0]; null for manual entries.",
    )
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        SAEnum(ExtractionMethod, name="extraction_method", create_type=True),
        nullable=False,
        default=ExtractionMethod.MANUAL,
        doc="How this field was extracted.",
    )
    needs_human_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        doc="True if the extraction confidence is below threshold.",
    )

    # ---- Review tracking ----
    reviewed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id"),
        doc="User who reviewed this extracted value.",
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        doc="Timestamp of human review.",
    )

    # ---- Relationships ----
    document: Mapped["Document"] = relationship(
        back_populates="extracted_data",
    )
    reviewed_by_user: Mapped[Optional["User"]] = relationship(
        foreign_keys=[reviewed_by_id],
    )

    def __repr__(self) -> str:
        return (
            f"ExtractedData(field='{self.field_name}', "
            f"method={self.extraction_method.value}, "
            f"review={self.needs_human_review})"
        )


# ===================================================================
# 7. RULE RESULT
# ===================================================================


class RuleResult(Base):
    """
    Output of a single deterministic rule evaluation against a case.

    Each row records one rule from the external THOA config
    (``config/document_rules.json``) applied to a specific case.
    The rule engine is deterministic — no LLM calls, no stochastic
    behaviour.

    Relationships:
        - ``case`` → Screening case this rule was evaluated against (N:1).
    """

    __tablename__ = "rule_results"
    __table_args__ = (
        Index("ix_rule_results_case_rule", "case_id", "rule_code"),
        {"comment": "Deterministic rule-engine evaluation outputs."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Screening case.",
    )
    rule_code: Mapped[str] = mapped_column(
        String(100), nullable=False,
        doc=(
            "Rule identifier from external config "
            "(e.g. 'DONOR_AGE_CHECK', 'EMBASSY_NOC_REQUIRED')."
        ),
    )
    rule_description: Mapped[Optional[str]] = mapped_column(
        Text,
        doc="Human-readable description of what the rule checks.",
    )
    result: Mapped[RuleOutcome] = mapped_column(
        SAEnum(RuleOutcome, name="rule_outcome", create_type=True),
        nullable=False,
        doc="Outcome of the evaluation.",
    )
    severity: Mapped[Optional[str]] = mapped_column(
        String(20),
        doc="Severity level (ERROR, WARNING, INFO).",
    )
    message: Mapped[Optional[str]] = mapped_column(
        Text,
        doc="Detailed explanation of the result.",
    )
    legal_reference: Mapped[Optional[str]] = mapped_column(
        String(200),
        doc="THOA section/rule reference (from config).",
    )
    needs_legal_verification: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        doc=(
            "True if the legal_reference has not been verified by a "
            "qualified legal professional (Constraint #2)."
        ),
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the rule was evaluated.",
    )

    # ---- Relationship ----
    case: Mapped["Case"] = relationship(back_populates="rule_results")

    def __repr__(self) -> str:
        return (
            f"RuleResult(rule='{self.rule_code}', "
            f"result={self.result.value})"
        )


# ===================================================================
# 8. AUDIT LOG
# ===================================================================


class AuditLog(Base):
    """
    Immutable, append-only audit trail for compliance.

    Every significant action in the system is recorded here.  Audit
    logs are NEVER updated or deleted — the FK to ``cases`` uses
    ``RESTRICT`` to prevent accidental cascade deletion.

    Design decisions:
        - No ``updated_at`` column (immutable rows).
        - ``detail`` is JSONB for flexible, structured payloads without
          schema migrations.
        - ``case_id`` is nullable to allow system-level events (e.g.
          user login) that aren't tied to a specific case.

    Relationships:
        - ``case`` → Related screening case, if any (N:1, nullable).
        - ``user`` → User who performed the action (N:1).
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_case_time", "case_id", "created_at"),
        Index("ix_audit_user_time", "user_id", "created_at"),
        {"comment": "Immutable compliance audit trail."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("cases.id", ondelete="RESTRICT"),
        index=True,
        doc="Related case (nullable for system-level events).",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        doc="User who performed the action.",
    )
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, name="audit_action", create_type=True),
        nullable=False,
        doc="Categorised action type.",
    )
    detail: Mapped[Optional[dict]] = mapped_column(
        JSON,
        doc=(
            "Structured action payload (e.g. old/new values, document IDs). "
            "Uses native JSONB on PostgreSQL, JSON on other backends."
        ),
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        doc="Client IP address (IPv4 or IPv6).",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        doc="Client user-agent string.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        doc="Event timestamp (server-side, immutable).",
    )

    # ---- Relationships ----
    case: Mapped[Optional["Case"]] = relationship(
        back_populates="audit_logs",
    )
    user: Mapped["User"] = relationship(back_populates="audit_entries")

    def __repr__(self) -> str:
        return (
            f"AuditLog(action={self.action.value}, "
            f"user={self.user_id!s:.8}, "
            f"at={self.created_at})"
        )


# ===================================================================
# 9. REPORT
# ===================================================================


class Report(TimestampMixin, Base):
    """
    Generated screening report for the Authorization Committee.

    Reports are created by the system or by a user and go through a
    DRAFT → FINAL → ARCHIVED lifecycle.  Content is stored as a file
    (PDF, HTML, etc.) referenced by ``file_path``, with ``content_hash``
    for integrity.

    Relationships:
        - ``case`` → Screening case this report covers (N:1).
        - ``generated_by`` → User (or system account) that created it (N:1).
    """

    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_case", "case_id"),
        {"comment": "Committee-facing screening reports."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        doc="Screening case this report covers.",
    )
    report_type: Mapped[ReportType] = mapped_column(
        SAEnum(ReportType, name="report_type", create_type=True),
        nullable=False,
        doc="Report category.",
    )
    generated_by_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
        doc="User or system account that generated the report.",
    )
    file_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        doc="Storage path to the rendered report file.",
    )
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        doc="SHA-256 hash of the report content for tamper detection.",
    )
    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus, name="report_status", create_type=True),
        default=ReportStatus.DRAFT,
        nullable=False,
        doc="Report lifecycle status.",
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        doc="Brief text summary of the report's findings.",
    )

    # ---- Relationships ----
    case: Mapped["Case"] = relationship(back_populates="reports")
    generated_by: Mapped["User"] = relationship(
        back_populates="reports_generated",
    )

    def __repr__(self) -> str:
        return (
            f"Report(id={self.id!s:.8}, type={self.report_type.value}, "
            f"status={self.status.value})"
        )

# ===================================================================
# IMMUTABILITY EVENT LISTENERS
# ===================================================================
from sqlalchemy import event

@event.listens_for(AuditLog, "before_update")
def receive_before_update(mapper, connection, target):
    raise NotImplementedError("AuditLog records are strictly immutable and cannot be updated.")

@event.listens_for(AuditLog, "before_delete")
def receive_before_delete(mapper, connection, target):
    raise NotImplementedError("AuditLog records are strictly immutable and cannot be deleted.")
