"""
PII masking utilities for THOA screening outputs.

All non-admin-facing serialisations must use these helpers to ensure
sensitive identifiers (Aadhaar, PAN, etc.) are never exposed in logs,
API responses, or reports meant for non-privileged consumers.
"""

import re


# ---------------------------------------------------------------------------
# Aadhaar masking
# ---------------------------------------------------------------------------

# Aadhaar is a 12-digit number.  We reveal only the last 4 digits.
_AADHAAR_PATTERN = re.compile(r"^\d{12}$")


def mask_aadhaar(raw: str) -> str:
    """
    Mask an Aadhaar number, revealing only the last 4 digits.

    Args:
        raw: The 12-digit Aadhaar number string.

    Returns:
        Masked string in the format ``XXXX-XXXX-1234``.

    Raises:
        ValueError: If ``raw`` is not a valid 12-digit string.

    Examples:
        >>> mask_aadhaar("123456789012")
        'XXXX-XXXX-9012'
    """
    if not _AADHAAR_PATTERN.match(raw):
        raise ValueError(
            f"Cannot mask invalid Aadhaar number (expected 12 digits, "
            f"got {len(raw)} chars)."
        )
    return f"XXXX-XXXX-{raw[-4:]}"


# ---------------------------------------------------------------------------
# PAN masking
# ---------------------------------------------------------------------------

# PAN format: 5 letters + 4 digits + 1 letter  (e.g. ABCDE1234F)
_PAN_PATTERN = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")


def mask_pan(raw: str) -> str:
    """
    Mask a PAN card number, revealing only the last 4 characters.

    Args:
        raw: The 10-character PAN string (e.g. ``ABCDE1234F``).

    Returns:
        Masked string in the format ``XXXXXX234F``.

    Raises:
        ValueError: If ``raw`` does not match the PAN format.

    Examples:
        >>> mask_pan("ABCDE1234F")
        'XXXXXX234F'
    """
    if not _PAN_PATTERN.match(raw.upper()):
        raise ValueError(
            f"Cannot mask invalid PAN number (expected format ABCDE1234F, "
            f"got '{raw}')."
        )
    return f"XXXXXX{raw[-4:]}"


# ---------------------------------------------------------------------------
# Generic redaction helper
# ---------------------------------------------------------------------------

def redact_field(value: str, *, visible_suffix: int = 4) -> str:
    """
    Generic redaction: replaces all but the last ``visible_suffix``
    characters with 'X'.

    This is a fallback for identifiers that don't have a specific masker.
    """
    if len(value) <= visible_suffix:
        return "X" * len(value)
    masked_length = len(value) - visible_suffix
    return ("X" * masked_length) + value[-visible_suffix:]
