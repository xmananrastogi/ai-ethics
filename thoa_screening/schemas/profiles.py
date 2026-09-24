"""
Donor and Recipient profile models.

Pydantic v2 schemas with field-level validation for PII fields, age
constraints, and income.  Masking is applied via ``to_safe_dict()`` —
the raw model retains full data for admin-only use.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, Field, field_validator

from thoa_screening.config import get_donor_minimum_age
from thoa_screening.schemas.enums import Nationality
from thoa_screening.schemas.masking import mask_aadhaar


# ---------------------------------------------------------------------------
# Reusable annotated types
# ---------------------------------------------------------------------------

AadhaarStr = Annotated[
    str,
    Field(
        pattern=r"^\d{12}$",
        description="12-digit Aadhaar number (no spaces or hyphens).",
        examples=["123456789012"],
    ),
]

PositiveAge = Annotated[
    int,
    Field(gt=0, description="Age in whole years, must be positive."),
]

NonNegativeIncome = Annotated[
    Decimal,
    Field(
        ge=0,
        decimal_places=2,
        description="Monthly income in INR.",
    ),
]


# ---------------------------------------------------------------------------
# Base person model (shared fields)
# ---------------------------------------------------------------------------

class _PersonProfileBase(BaseModel):
    """
    Shared fields for any person involved in a transplant case.

    Not exported directly — use ``DonorProfile`` or ``RecipientProfile``.
    """

    full_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Full legal name as it appears on government ID.",
    )
    age: PositiveAge
    dob: Optional[date] = Field(
        default=None,
        description="Date of birth in YYYY-MM-DD format.",
    )
    aadhaar_number: AadhaarStr
    pan_number: Optional[str] = Field(
        default=None,
        pattern=r"^[A-Z]{5}\d{4}[A-Z]$",
        description="10-character PAN number.",
    )
    nationality: Nationality = Field(
        default=Nationality.INDIAN,
        description="Nationality classification (INDIAN or FOREIGN).",
    )
    monthly_income: NonNegativeIncome = Field(
        ...,
        description="Self-declared monthly income in INR.",
    )
    address: Optional[str] = Field(
        default=None,
        description="Full residential address.",
    )

    # ---- Masking support (Constraint #6) ----

    def to_safe_dict(self) -> dict:
        """
        Return a dictionary with sensitive fields masked.

        Use this for all non-admin outputs: API responses, logs,
        committee-facing reports, etc.
        """
        data = self.model_dump(mode="json")
        data["aadhaar_number"] = mask_aadhaar(self.aadhaar_number)
        if self.pan_number:
            from thoa_screening.schemas.masking import mask_pan
            data["pan_number"] = mask_pan(self.pan_number)
        return data

    def __repr__(self) -> str:
        """Repr always masks PII to prevent accidental log leakage."""
        masked_aadhaar = mask_aadhaar(self.aadhaar_number)
        return (
            f"{self.__class__.__name__}("
            f"full_name='{self.full_name}', "
            f"age={self.age}, "
            f"aadhaar='{masked_aadhaar}', "
            f"nationality={self.nationality.value})"
        )


# ---------------------------------------------------------------------------
# Donor profile
# ---------------------------------------------------------------------------

class DonorProfile(_PersonProfileBase):
    """
    Living organ donor's profile.

    Validation:
        - ``age`` must be >= the minimum legal donor age defined in the
          THOA rules config (default 18 under Section 3, THOA 1994).
    """

    @field_validator("age")
    @classmethod
    def validate_donor_age(cls, value: int) -> int:
        """
        Ensure the donor meets the minimum legal age requirement.

        The threshold is read from external config, not hardcoded.

        Raises:
            ValueError: If the donor is below the minimum legal age.
        """
        min_age = get_donor_minimum_age()
        if value < min_age:
            raise ValueError(
                f"Donor must be at least {min_age} years old "
                f"(Section 3, THOA 1994). Received age: {value}."
            )
        return value


# ---------------------------------------------------------------------------
# Recipient profile
# ---------------------------------------------------------------------------

class RecipientProfile(_PersonProfileBase):
    """
    Transplant recipient's profile.

    No additional age restriction beyond positivity — minors can receive
    organs with guardian consent (handled separately by the Authorization
    Committee, not auto-screened here).
    """

    pass
