"""
Core Workflow Orchestrator.

Ties together Database ORM, OCR pipeline, Pydantic schemas, and Rule Engine.
Implements the `screen_case` workflow.
"""
import uuid
import logging
from typing import Any, Dict

from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from thoa_screening.database.models import (
    Case, Document, ExtractedData, RuleResult, CaseStatus, 
    ExtractionMethod, RuleOutcome
)
from thoa_screening.schemas.case import TransplantCase
from thoa_screening.schemas.profiles import DonorProfile, RecipientProfile
from thoa_screening.schemas.documents import DocumentChecklist
from thoa_screening.rules.screener import THOAScreener
from thoa_screening.ocr.pipeline import process_document

logger = logging.getLogger(__name__)

class ScreeningError(Exception):
    """Custom exception raised during the screening workflow."""
    pass

# Mock decryption functions until the KMS layer is built
def _mock_decrypt(enc_value: bytes | None) -> str:
    if not enc_value:
        return "123456789012"  # fallback mock
    return enc_value.decode('utf-8')

def screen_case(case_id: uuid.UUID | str, session: Session) -> Dict[str, Any]:
    """
    Main orchestrator for case screening.
    
    1. Loads Case, Donor, Recipient, and Documents from the DB.
    2. Runs OCR for unprocessed Documents.
    3. Aggregates data into a Pydantic TransplantCase.
    4. Evaluates rules via THOAScreener.
    5. Persists RuleResult rows and updates Case status.
    6. Returns the final screening dictionary.
    
    The entire operation uses the provided SQLAlchemy session. It rolls back
    and raises ScreeningError if anything fails.
    """
    if isinstance(case_id, str):
        try:
            case_id = uuid.UUID(case_id)
        except ValueError:
            raise ScreeningError(f"Invalid UUID format: {case_id}")
            
    try:
        logger.info(f"Starting screening workflow for Case: {case_id}")
        
        # 1. Load Case
        case = session.query(Case).options(
            joinedload(Case.donor),
            joinedload(Case.recipient),
            joinedload(Case.documents).joinedload(Document.extracted_data)
        ).filter(Case.id == case_id).first()
        
        if not case:
            raise ScreeningError(f"Case {case_id} not found.")
            
        if not case.donor or not case.recipient:
            raise ScreeningError(f"Case {case_id} is missing Donor or Recipient.")
            
        # 2. Extract Data via OCR (best-effort: invalid files don't abort screening)
        for doc in case.documents:
            # Check if this document already has extracted data
            if not doc.extracted_data and doc.file_path:
                logger.info(f"Running OCR pipeline on document {doc.id} ({doc.original_filename})")
                try:
                    ocr_result = process_document(doc.file_path)
                except Exception as ocr_err:
                    logger.warning(f"OCR failed for document {doc.id}: {ocr_err}. Skipping extraction.")
                    continue
                
                # Persist ExtractedData
                for field_name, value in ocr_result.get("extracted_data", {}).items():
                    if value is not None:
                        conf = ocr_result["field_confidences"].get(field_name, 0.0)
                        extracted = ExtractedData(
                            document_id=doc.id,
                            field_name=field_name,
                            field_value=str(value),
                            confidence_score=conf / 100.0,
                            extraction_method=ExtractionMethod.OCR,
                            needs_human_review=(conf < 80.0)
                        )
                        session.add(extracted)
                        doc.extracted_data.append(extracted)
                session.flush() # Ensure ExtractedData gets IDs
                
        # 3. Aggregate Data into Pydantic TransplantCase
        # Determine boolean document flags based on attached document types
        doc_types = {doc.document_type.value for doc in case.documents}
        checklist = DocumentChecklist(
            has_form_1="FORM_1" in doc_types,
            has_form_2="FORM_2" in doc_types,
            has_form_3="FORM_3" in doc_types,
            has_form_4="FORM_4" in doc_types,
            has_form_5="FORM_5" in doc_types,
            has_form_11="FORM_11" in doc_types,
            has_form_21="FORM_21" in doc_types,
            has_financial_affidavit="FINANCIAL_AFFIDAVIT" in doc_types,
            dna_test_match="DNA_REPORT" in doc_types,
            police_verification="POLICE_VERIFICATION" in doc_types,
            embassy_noc="FORM_21" in doc_types, # Assuming Form 21 implies NOC
            medical_fitness="MEDICAL_REPORT" in doc_types,
            identity_proof="IDENTITY_PROOF" in doc_types
        )
        
        donor_profile = DonorProfile(
            full_name=case.donor.full_name,
            age=case.donor.age,
            dob=case.donor.date_of_birth.date() if case.donor.date_of_birth else None,
            aadhaar_number=_mock_decrypt(case.donor.aadhaar_number_enc),
            pan_number=_mock_decrypt(case.donor.pan_number_enc) if case.donor.pan_number_enc else None,
            nationality=case.donor.nationality,
            monthly_income=case.donor.monthly_income or 0,
            address=case.donor.address
        )
        
        recipient_profile = RecipientProfile(
            full_name=case.recipient.full_name,
            age=case.recipient.age,
            dob=case.recipient.date_of_birth.date() if case.recipient.date_of_birth else None,
            aadhaar_number=_mock_decrypt(case.recipient.aadhaar_number_enc),
            pan_number=_mock_decrypt(case.recipient.pan_number_enc) if case.recipient.pan_number_enc else None,
            nationality=case.recipient.nationality,
            monthly_income=case.recipient.monthly_income or 0,
            address=case.recipient.address
        )
        
        from pydantic import ValidationError
        try:
            pydantic_case = TransplantCase(
                relation_type=case.relation_type.value,
                donor=donor_profile,
                recipient=recipient_profile,
                documents=checklist
            )
            
            # 4. Evaluate via THOAScreener
            screener = THOAScreener()
            status_enum, rule_results = screener.engine.evaluate(pydantic_case)
            
        except ValidationError as ve:
            logger.warning(f"Case {case_id} failed basic schema validation: {ve}")
            status_enum = CaseStatus.REJECTED
            # Extract error messages from Pydantic to store as RuleResult
            rule_results = []
            for error in ve.errors():
                rule_results.append({
                    "rule_code": "SCHEMA_VALIDATION_ERROR",
                    "rule_description": "Initial data validation failed",
                    "result": RuleOutcome.FAIL,
                    "severity": "ERROR",
                    "message": error.get("msg", str(error)),
                    "legal_reference": None,
                    "needs_legal_verification": False
                })

        # 5. Persist RuleResult rows
        # First, clear old rule results for this case if any exist (idempotency)
        session.query(RuleResult).filter(RuleResult.case_id == case.id).delete()

        for r in rule_results:
            db_result = RuleResult(
                case_id=case.id,
                rule_code=r["rule_code"],
                rule_description=r.get("rule_description"),
                result=RuleOutcome(r.get("result", RuleOutcome.FAIL)),
                severity=r.get("severity"),
                message=r.get("message"),
                legal_reference=r.get("legal_reference"),
                needs_legal_verification=r.get("needs_legal_verification", False)
            )
            session.add(db_result)

        # Update Case Status (Advisory Only mapping)
        case.status = CaseStatus(status_enum.value) if hasattr(status_enum, 'value') else status_enum

        # 6. Commit and Return
        session.commit()
        logger.info(f"Screening completed for Case {case_id}. Status: {case.status.value}")
        
        flags = [f"{r['rule_code']}: {r['message']}" for r in rule_results if r.get("severity") in ("ERROR", "WARNING")]
        return {
            "status": case.status.value,
            "flags": flags,
            "needs_legal_verification": any(r.get("needs_legal_verification") for r in rule_results)
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Screening failed for Case {case_id}: {str(e)}", exc_info=True)
        raise ScreeningError(f"Screening failed: {str(e)}") from e
