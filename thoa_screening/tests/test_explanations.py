import os
os.environ["THOA_DATABASE_URL"] = "sqlite:///:memory:"

import pytest
import uuid
from thoa_screening.database.models import Case, RuleResult, RuleOutcome, RelationType, Donor, Recipient
from thoa_screening.schemas.enums import Nationality
from thoa_screening.services.explanations import ExplanationGenerator

def test_explanation_generator():
    case = Case(
        id=uuid.uuid4(),
        case_number="TEST-EXP-01",
        relation_type=RelationType.NON_RELATIVE,
    )
    
    case.donor = Donor(age=17, nationality=Nationality.INDIAN, monthly_income=50000)
    case.recipient = Recipient(age=45, nationality=Nationality.INDIAN, monthly_income=50000)
    
    rule_results = [
        RuleResult(
            case_id=case.id,
            rule_code="ID-01",
            rule_description="Donor Minimum Age Check",
            result=RuleOutcome.FAIL,
            severity="ERROR",
            legal_reference="Section 3, THOA",
            needs_legal_verification=False
        ),
        RuleResult(
            case_id=case.id,
            rule_code="REL-05",
            rule_description="Non-Relative Consent Form",
            result=RuleOutcome.FAIL,
            severity="ERROR",
            legal_reference="Form 3 and 11",
            needs_legal_verification=False
        )
    ]
    
    explanations = ExplanationGenerator.generate(case, rule_results)
    
    assert len(explanations) == 2
    
    exp1 = explanations[0]
    assert exp1.rule_code == "ID-01"
    assert "17" in exp1.evidence
    assert "Reject" in exp1.next_step
    
    exp2 = explanations[1]
    assert exp2.rule_code == "REL-05"
    assert "NON_RELATIVE" in exp2.evidence
    assert "Form 3 and Form 11" in exp2.next_step
