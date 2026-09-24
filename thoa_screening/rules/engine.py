import json
from pathlib import Path
from typing import Any

from thoa_screening.schemas.case import TransplantCase
from thoa_screening.schemas.enums import CaseStatus, Nationality, RelationType
from thoa_screening.database.models import RuleOutcome


class RuleEngine:
    """
    Evaluates a TransplantCase against THOA rule definitions.
    """

    def __init__(self, rules_path: Path | str | None = None):
        if rules_path is None:
            rules_path = Path(__file__).parent / "rule_definitions.json"
        
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.rules = data.get("rules", [])

    def evaluate(self, case: TransplantCase) -> tuple[CaseStatus, list[dict[str, Any]]]:
        """
        Evaluate all rules against the case.

        Returns:
            tuple[CaseStatus, list[dict]]: The derived case status and the list
            of rule results (structured for RuleResult DB ingestion).
        """
        results: list[dict[str, Any]] = []

        # We map methods to rule IDs if they are automatable
        for rule_def in self.rules:
            rule_code = rule_def["rule_id"]
            
            method_name = f"_evaluate_{rule_code.replace('-', '_').lower()}"
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                outcome, severity, message = method(case)
                results.append(self._build_result(
                    rule_code=rule_code,
                    rule_def=rule_def,
                    outcome=outcome,
                    severity=severity,
                    message=message,
                ))
            else:
                # Rule is not automated or not implemented yet
                results.append(self._build_result(
                    rule_code=rule_code,
                    rule_def=rule_def,
                    outcome=RuleOutcome.SKIPPED,
                    severity="INFO",
                    message="Rule is inherently subjective, requires human assessment, or is not automated.",
                ))

        # Re-derive status based on engine rules + pydantic anomalies
        status = self._derive_overall_status(case, results)

        return status, results

    def _build_result(
        self,
        rule_code: str,
        rule_def: dict[str, Any],
        outcome: RuleOutcome,
        severity: str,
        message: str,
    ) -> dict[str, Any]:
        """Construct a standardized result dictionary for DB ingestion."""
        return {
            "rule_code": rule_code,
            "rule_description": rule_def.get("logic_description"),
            "result": outcome,
            "severity": severity,
            "message": message,
            "legal_reference": rule_def.get("thoa_reference"),
            "needs_legal_verification": rule_def.get("needs_legal_verification", True),
        }

    def _derive_overall_status(self, case: TransplantCase, results: list[dict[str, Any]]) -> CaseStatus:
        """
        Derive the final CaseStatus based on both Pydantic anomalies and Rule Engine results.
        """
        has_error = False
        has_warning = False

        # 1. Check rule engine results
        for r in results:
            if r["severity"] == "ERROR":
                has_error = True
            elif r["severity"] == "WARNING":
                has_warning = True

        # 2. Include Pydantic anomalies (they represent document gaps)
        if case.screening_status == CaseStatus.DOCUMENTATION_INCOMPLETE:
            has_error = True
        elif case.screening_status == CaseStatus.ANOMALIES_DETECTED:
            has_warning = True

        if has_error:
            return CaseStatus.DOCUMENTATION_INCOMPLETE
        if has_warning:
            return CaseStatus.ANOMALIES_DETECTED
        
        return CaseStatus.PENDING_COMMITTEE_REVIEW

    # --- Rule Implementations ---

    def _evaluate_id_01(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Donor Minimum Age Check"""
        if case.donor.age < 18:
            return RuleOutcome.FAIL, "ERROR", "Living donor is a minor (under 18)."
        return RuleOutcome.PASS, "INFO", "Donor age requirement met."

    def _evaluate_id_03(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Aadhaar / Identity Document Verification"""
        if not case.documents.identity_proof_submitted:
            return RuleOutcome.FAIL, "ERROR", "Identity proof documents missing."
        return RuleOutcome.PASS, "INFO", "Identity proof documents submitted."

    def _evaluate_id_04(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Foreign National Embassy Certificate"""
        has_foreign = (
            case.donor.nationality == Nationality.FOREIGN 
            or case.recipient.nationality == Nationality.FOREIGN
        )
        if has_foreign and not case.documents.has_form_21:
            return RuleOutcome.FAIL, "ERROR", "Foreign national involved but Form 21 is missing."
        if has_foreign:
            return RuleOutcome.PASS, "INFO", "Form 21 present for foreign national."
        return RuleOutcome.SKIPPED, "INFO", "No foreign nationals involved."

    def _evaluate_id_05(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Domicile Verification for Cross-State Cases"""
        # We don't have hospital state or residence in the current profile yet, so we skip
        # It's marked automatable, but profile schemas need extending.
        return RuleOutcome.SKIPPED, "INFO", "State residence data not available in profile."

    def _evaluate_rel_01(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Near Relative Enumeration Check"""
        near_relatives = {
            RelationType.SPOUSE, RelationType.PARENT_CHILD,
            RelationType.SIBLING, RelationType.GRANDPARENT_GRANDCHILD
        }
        if case.relation_type in near_relatives:
            return RuleOutcome.PASS, "INFO", "Relationship is a recognized near-relative."
        return RuleOutcome.SKIPPED, "INFO", "Relationship is not a near-relative."

    def _evaluate_rel_02(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Near Relative Documentation"""
        if case.relation_type == RelationType.SPOUSE:
            if not case.documents.has_form_2:
                return RuleOutcome.FAIL, "ERROR", "Spousal donor missing Form 2."
        elif case.relation_type in {RelationType.PARENT_CHILD, RelationType.SIBLING, RelationType.GRANDPARENT_GRANDCHILD}:
            if not case.documents.has_form_1:
                return RuleOutcome.FAIL, "ERROR", "Near-relative donor missing Form 1."
        return RuleOutcome.PASS, "INFO", "Near-relative documentation requirements met."

    def _evaluate_rel_03(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Genetic Relationship Certification"""
        bio_rels = {RelationType.PARENT_CHILD, RelationType.SIBLING, RelationType.GRANDPARENT_GRANDCHILD}
        if case.relation_type in bio_rels:
            if not case.documents.has_form_5 and not case.documents.dna_test_match:
                return RuleOutcome.WARNING, "WARNING", "Biological relationship claimed but Form 5 / DNA test not submitted."
            return RuleOutcome.PASS, "INFO", "Biological relationship certification present."
        return RuleOutcome.SKIPPED, "INFO", "Not a biological near-relative case."

    def _evaluate_rel_04(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Non-Relative Requires Authorization Committee"""
        if case.relation_type in {RelationType.NON_RELATIVE, RelationType.FOREIGN_NATIONAL}:
            return RuleOutcome.WARNING, "WARNING", "Non-near relative donation mandates Authorization Committee review."
        return RuleOutcome.SKIPPED, "INFO", "Near-relative case."

    def _evaluate_rel_05(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Non-Relative Consent Form"""
        if case.relation_type == RelationType.NON_RELATIVE:
            if not case.documents.has_form_3 or not case.documents.has_form_11:
                return RuleOutcome.FAIL, "ERROR", "Non-relative donor missing Form 3 or Form 11."
            return RuleOutcome.PASS, "INFO", "Non-relative forms submitted."
        return RuleOutcome.SKIPPED, "INFO", "Not a non-relative case."

    def _evaluate_rel_06(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Foreign National Near-Relative Requires Committee"""
        has_foreign = (
            case.donor.nationality == Nationality.FOREIGN 
            or case.recipient.nationality == Nationality.FOREIGN
        )
        if has_foreign:
            near_rels = {RelationType.SPOUSE, RelationType.PARENT_CHILD, RelationType.SIBLING, RelationType.GRANDPARENT_GRANDCHILD}
            if case.recipient.nationality == Nationality.FOREIGN and case.donor.nationality == Nationality.INDIAN:
                if case.relation_type not in near_rels:
                    return RuleOutcome.FAIL, "ERROR", "Indian donor cannot donate to foreign recipient unless near-relatives."
            return RuleOutcome.WARNING, "WARNING", "Foreign national involvement mandates Authorization Committee review."
        return RuleOutcome.SKIPPED, "INFO", "No foreign nationals involved."

    def _evaluate_spec_03(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Minor Recipient Guardian Consent"""
        if case.recipient.age < 18:
            return RuleOutcome.WARNING, "WARNING", "Minor recipient requires guardian consent. Manual check needed."
        return RuleOutcome.PASS, "INFO", "Recipient is not a minor."

    def _evaluate_spec_04(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Medical Fitness Certification"""
        if not case.documents.has_form_4:
            return RuleOutcome.FAIL, "ERROR", "Medical fitness certification (Form 4) missing."
        return RuleOutcome.PASS, "INFO", "Medical fitness certification present."

    def _evaluate_com_01(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Financial Affidavit"""
        if case.relation_type in {RelationType.NON_RELATIVE, RelationType.FOREIGN_NATIONAL}:
            if not case.documents.has_financial_affidavit:
                return RuleOutcome.FAIL, "ERROR", "Financial affidavit missing for non-relative/foreign case."
        elif not case.documents.has_financial_affidavit:
            return RuleOutcome.WARNING, "WARNING", "Financial affidavit missing (recommended for near-relatives)."
        return RuleOutcome.PASS, "INFO", "Financial affidavit present."

    def _evaluate_com_02(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Police Verification Report"""
        if case.relation_type in {RelationType.NON_RELATIVE, RelationType.FOREIGN_NATIONAL}:
            if not case.documents.police_verification:
                return RuleOutcome.FAIL, "ERROR", "Police verification missing for non-relative/foreign case."
            return RuleOutcome.PASS, "INFO", "Police verification present."
        return RuleOutcome.SKIPPED, "INFO", "Police verification not typically required for near-relatives."

    def _evaluate_com_03(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Income Disparity Anomaly Detection"""
        if case.relation_type in {RelationType.NON_RELATIVE, RelationType.FOREIGN_NATIONAL}:
            if case.donor.monthly_income > 0:
                ratio = case.recipient.monthly_income / case.donor.monthly_income
                if ratio > 10:
                    return RuleOutcome.WARNING, "WARNING", f"High income disparity detected (Recipient income is {ratio:.1f}x Donor income)."
            elif case.recipient.monthly_income > 0:
                return RuleOutcome.WARNING, "WARNING", "Donor has zero income while recipient has income (possible disparity)."
        return RuleOutcome.PASS, "INFO", "No significant income disparity flagged."

    def _evaluate_com_05(self, case: TransplantCase) -> tuple[RuleOutcome, str, str]:
        """Section 18 Unauthorized Removal"""
        if not case.documents.has_form_1 and not case.documents.has_form_2 and not case.documents.has_form_3:
            return RuleOutcome.FAIL, "ERROR", "No primary consent form present (Form 1, 2, or 3). Potential unauthorized removal risk."
        return RuleOutcome.PASS, "INFO", "Primary consent forms present."
