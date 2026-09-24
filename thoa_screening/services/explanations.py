from typing import List, Dict, Any
from thoa_screening.database.models import RuleResult, Case, RuleOutcome
from thoa_screening.api.schemas import ExplanationModel

class ExplanationGenerator:
    """
    Generates human-readable explanations for flagged screening rules.
    This operates strictly on facts, extracting evidence directly from
    the Case/Profile and assigning next steps deterministically based
    on the rule ID.
    """
    
    @classmethod
    def generate(cls, case: Case, rule_results: List[RuleResult]) -> List[ExplanationModel]:
        explanations = []
        for result in rule_results:
            if result.result in (RuleOutcome.FAIL, RuleOutcome.WARNING):
                evidence = cls._extract_evidence(case, result.rule_code)
                next_step = cls._get_next_step(result.rule_code)
                
                explanations.append(
                    ExplanationModel(
                        rule_code=result.rule_code,
                        rule_description=result.rule_description or "Unknown Rule",
                        thoa_reference=result.legal_reference,
                        evidence=evidence,
                        next_step=next_step,
                        needs_legal_verification=result.needs_legal_verification
                    )
                )
        return explanations
        
    @classmethod
    def _extract_evidence(cls, case: Case, rule_code: str) -> str:
        """Deterministically extracts factual evidence based on the rule code."""
        if rule_code == "ID-01":
            return f"Living donor is {case.donor.age} years old (under 18 limit)."
        elif rule_code == "ID-03":
            return "No government-issued identity proof document was uploaded."
        elif rule_code == "ID-04":
            return f"Donor nationality is {case.donor.nationality}, Recipient nationality is {case.recipient.nationality}. Form 21 is missing."
        elif rule_code == "REL-02":
            return f"Relationship is {case.relation_type}, but near-relative Form 1 or Form 2 is missing."
        elif rule_code == "REL-03":
            return f"Relationship is {case.relation_type}, but no Form 5 (genetic testing) or DNA match is present."
        elif rule_code == "REL-04":
            return f"Relationship is {case.relation_type}, which is categorized as non-relative."
        elif rule_code == "REL-05":
            return f"Relationship is {case.relation_type}. Required Form 3 and/or Form 11 are missing."
        elif rule_code == "REL-06":
            return f"Donor nationality: {case.donor.nationality}, Recipient nationality: {case.recipient.nationality}, Relationship: {case.relation_type}."
        elif rule_code == "SPEC-03":
            return f"Recipient is {case.recipient.age} years old (under 18 limit) and guardian consent may be missing."
        elif rule_code == "SPEC-04":
            return "Form 4 (Medical fitness certification) is missing."
        elif rule_code == "COM-01":
            return f"Relationship is {case.relation_type}. Financial affidavit is missing."
        elif rule_code == "COM-02":
            return f"Relationship is {case.relation_type}. Police verification report is missing."
        elif rule_code == "COM-03":
            ratio = 0
            if case.donor.monthly_income and case.donor.monthly_income > 0:
                ratio = (case.recipient.monthly_income or 0) / case.donor.monthly_income
            return f"Donor income: {case.donor.monthly_income}, Recipient income: {case.recipient.monthly_income}. Disparity ratio: {ratio:.1f}x."
        elif rule_code == "COM-05":
            return "No primary consent form (Form 1, 2, or 3) was detected in the submitted documents."
        elif rule_code == "SCHEMA_VALIDATION_ERROR":
            return "The initial case data or document checklist failed fundamental schema validation."
            
        return "Review the submitted documents and patient profiles for anomalies."
        
    @classmethod
    def _get_next_step(cls, rule_code: str) -> str:
        """Static mapping of suggested next steps."""
        steps = {
            "ID-01": "Reject case. Living donor must be >= 18.",
            "ID-03": "Request submission of Aadhaar card, Passport, or other valid identity proof.",
            "ID-04": "Request submission of Form 21 (Embassy NOC) for the foreign national.",
            "REL-02": "Request submission of Form 1 or Form 2 to verify near-relative status.",
            "REL-03": "Request submission of Form 5 or a valid DNA test report.",
            "REL-04": "Route case directly to the Authorization Committee for review.",
            "REL-05": "Request submission of Form 3 and Form 11 for non-relative donation.",
            "REL-06": "Route case to the Authorization Committee due to foreign national involvement.",
            "SPEC-03": "Request formal guardian consent document for the minor recipient.",
            "SPEC-04": "Request submission of Form 4 (Medical Fitness Certificate).",
            "COM-01": "Request submission of a sworn financial affidavit.",
            "COM-02": "Request submission of a valid police verification report.",
            "COM-03": "Authorization Committee to conduct thorough interview regarding financial coercion.",
            "COM-05": "Request immediate submission of primary consent forms (Form 1, 2, or 3).",
            "SCHEMA_VALIDATION_ERROR": "Correct the data entry errors and ensure all mandatory baseline documents are uploaded."
        }
        return steps.get(rule_code, "Authorization Committee review required.")
