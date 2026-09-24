from typing import Any
from thoa_screening.schemas.case import TransplantCase
from thoa_screening.rules.engine import RuleEngine
from thoa_screening.schemas.enums import CaseStatus

class THOAScreener:
    """
    Evaluates a TransplantCase against the external JSON configuration.
    
    WARNING: Adheres strictly to the invariant that the system NEVER 
    approves or rejects a transplant. "APPROVED" and "REJECTED" are 
    legally disallowed states in this system.
    """
    def __init__(self, rules_path: str | None = None):
        # We reuse our robust RuleEngine that parses the external JSON
        self.engine = RuleEngine(rules_path)

    def evaluate(self, case: TransplantCase) -> dict[str, Any]:
        """
        Evaluate the case and return a structured dictionary.
        """
        status_enum, results = self.engine.evaluate(case)
        
        # We must never return APPROVED or REJECTED.
        # We map our internal advisory statuses to string outputs.
        status_str = status_enum.value
        
        flags = []
        needs_legal = False
        
        for r in results:
            if r["severity"] in ("WARNING", "ERROR") or r["result"].value == "FAIL":
                flags.append(f"{r['rule_code']}: {r['message']}")
                if r.get("needs_legal_verification"):
                    needs_legal = True
                    
        return {
            "status": status_str,
            "flags": flags,
            "needs_legal_verification": needs_legal
        }
