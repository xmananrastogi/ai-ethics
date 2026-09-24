"""
Configuration loader for THOA screening rules.

Loads the externalised document-requirement rules from JSON config.
All THOA-specific logic reads from this config — nothing is hardcoded
in application code (Constraint #3).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


# Default config path — resolved relative to this file's package.
_DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent / "document_rules.json"
)


class ConfigLoadError(RuntimeError):
    """Raised when the THOA rules config cannot be loaded or parsed."""


@lru_cache(maxsize=1)
def load_document_rules(
    config_path: Path | str | None = None,
) -> dict[str, Any]:
    """
    Load and cache the THOA document-requirement rules.

    Args:
        config_path: Optional override for the JSON config file path.
            Defaults to ``config/document_rules.json`` within this package.

    Returns:
        Parsed config dictionary.

    Raises:
        ConfigLoadError: If the file is missing, unreadable, or invalid JSON.
    """
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

    if not path.is_file():
        raise ConfigLoadError(
            f"THOA rules config not found at: {path}. "
            "Ensure the config file exists before starting the system."
        )

    try:
        with open(path, encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ConfigLoadError(
            f"Invalid JSON in THOA rules config ({path}): {exc}"
        ) from exc

    # Minimal structural validation
    required_keys = {"required_documents_by_relation", "donor_minimum_age"}
    missing = required_keys - data.keys()
    if missing:
        raise ConfigLoadError(
            f"THOA rules config is missing required keys: {missing}"
        )

    return data


def get_required_documents(relation_type: str) -> list[str]:
    """
    Return the list of required document flags for a given relation type.

    Args:
        relation_type: The ``RelationType`` value (e.g. ``"NON_RELATIVE"``).

    Returns:
        List of document flag field names (e.g.
        ``["has_form_1", "has_form_3", ...]``).
    """
    config = load_document_rules()
    docs_by_relation = config["required_documents_by_relation"]
    return docs_by_relation.get(relation_type, [])


def get_donor_minimum_age() -> int:
    """Return the minimum legal donor age from config."""
    config = load_document_rules()
    return int(config["donor_minimum_age"])


def get_force_committee_review_relations() -> list[str]:
    """Return relation types that always require committee review."""
    config = load_document_rules()
    return config.get("force_committee_review", [])


def get_legal_reference(document_key: str) -> dict[str, Any] | None:
    """
    Look up the legal reference metadata for a document/form.

    Returns:
        Dict with ``description``, ``section``, and
        ``needs_legal_verification`` keys, or ``None`` if the key
        is not in the config.
    """
    config = load_document_rules()
    return config.get("legal_references", {}).get(document_key)
