"""
Document checklist model for transplant case screening.

Each boolean flag indicates whether a specific legal document has been
submitted.  The *meaning* and *requirement logic* of each flag lives in
the external config (``config/document_rules.json``) or the rule engine,
not here.
"""

from pydantic import BaseModel, Field


class DocumentChecklist(BaseModel):
    """
    Boolean checklist of documents required under THOA.

    This model is purely structural — it records what has been submitted.
    Which documents are *required* for a given ``RelationType`` is
    determined by the rule engine reading from external config.

    Flag naming convention: ``has_form_<N>`` mirrors the official THOA
    form numbering (2014 Rules). Non-form documents use descriptive names.
    """

    # --- THOA statutory forms (2014 Rules) ---

    has_form_1: bool = Field(
        default=False,
        description="Form 1: Consent for donation by living near-relative donor.",
    )
    has_form_2: bool = Field(
        default=False,
        description="Form 2: Consent for donation by living spousal donor.",
    )
    has_form_3: bool = Field(
        default=False,
        description="Form 3: Consent for donation by non-near-relative donor.",
    )
    has_form_4: bool = Field(
        default=False,
        description="Form 4: Medical fitness certification of living donor.",
    )
    has_form_5: bool = Field(
        default=False,
        description="Form 5: Certification of genetic relationship.",
    )
    has_form_10: bool = Field(
        default=False,
        description="Form 10: Brain stem death certification.",
    )
    has_form_11: bool = Field(
        default=False,
        description="Form 11: Joint application for transplant approval.",
    )
    has_form_20: bool = Field(
        default=False,
        description="Form 20: Domicile verification certificate.",
    )
    has_form_21: bool = Field(
        default=False,
        description="Form 21: Relationship certificate for foreign nationals.",
    )

    # --- Supporting documents ---

    has_financial_affidavit: bool = Field(
        default=False,
        description=(
            "Sworn affidavit declaring no commercial dealing between "
            "donor and recipient."
        ),
    )
    dna_test_match: bool = Field(
        default=False,
        description=(
            "DNA test report confirming biological relationship. "
            "May be requested by the Authorization Committee for "
            "near-relative cases."
        ),
    )
    police_verification: bool = Field(
        default=False,
        description=(
            "Police verification report for the donor, typically "
            "required for non-relative and foreign-national cases."
        ),
    )
    identity_proof_submitted: bool = Field(
        default=False,
        description="Government-issued photo ID submitted for both donor and recipient.",
    )
    medical_report_submitted: bool = Field(
        default=False,
        description="Medical fitness / compatibility reports submitted.",
    )
