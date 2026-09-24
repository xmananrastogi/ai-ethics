"""
Enumerated types for the THOA screening system.

These enums model the finite, well-defined categories used across
transplant case processing. Values are string-backed for JSON
serialisation readability.
"""

from enum import StrEnum, unique


@unique
class RelationType(StrEnum):
    """
    Relationship between donor and recipient as defined under THOA.

    Near relatives (Section 2(i), THOA 1994):
        SPOUSE, PARENT_CHILD, SIBLING, GRANDPARENT_GRANDCHILD

    Non-near-relative / unrelated donors require Authorization Committee
    approval under Section 9(3) of the 2011 Amendment.

    FOREIGN_NATIONAL triggers additional embassy NOC requirements
    under the 2014 Rules.
    """

    SPOUSE = "SPOUSE"
    PARENT_CHILD = "PARENT_CHILD"
    SIBLING = "SIBLING"
    GRANDPARENT_GRANDCHILD = "GRANDPARENT_GRANDCHILD"
    NON_RELATIVE = "NON_RELATIVE"
    FOREIGN_NATIONAL = "FOREIGN_NATIONAL"


@unique
class CaseStatus(StrEnum):
    """
    Screening outcome produced by this system.

    CRITICAL: This system is advisory-only.  No status here constitutes
    an approval or rejection of a transplant.  Every status is an input
    to the human Authorization Committee's deliberation.

    - PENDING_COMMITTEE_REVIEW: Default and most common outcome.
      Indicates the case is ready (or must go) to the committee.
    - DOCUMENTATION_INCOMPLETE: One or more legally required documents
      are missing. The case cannot proceed to the committee yet.
    - ANOMALIES_DETECTED: Rule-engine checks have found issues that
      the committee must specifically examine.
    """

    PENDING_COMMITTEE_REVIEW = "PENDING_COMMITTEE_REVIEW"
    DOCUMENTATION_INCOMPLETE = "DOCUMENTATION_INCOMPLETE"
    ANOMALIES_DETECTED = "ANOMALIES_DETECTED"


@unique
class Nationality(StrEnum):
    """
    Donor / recipient nationality classification.

    THOA's 2014 Rules impose additional requirements on foreign nationals
    (embassy NOC, etc.).  Only the broad classification matters for
    screening; the exact country is captured separately.
    """

    INDIAN = "INDIAN"
    FOREIGN = "FOREIGN"
