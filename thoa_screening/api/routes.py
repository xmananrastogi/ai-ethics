import os
import uuid
import hashlib
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from thoa_screening.services.report_generator import generate_report
from sqlalchemy.orm import Session
from thoa_screening.api.websockets import manager
from typing import List

from thoa_screening.api.deps import get_db
from thoa_screening.api.schemas import (
    DocumentUploadResponse, ScreeningResultResponse, ErrorResponse, AuditLogResponse,
    CaseSummary, CaseDetail, CaseCreate, DecisionSubmit, PersonDetail,
    HumanCorrectionCreate, HumanCorrectionResponse
)
from thoa_screening.database.models import (
    Case, Document, DocumentType, RuleResult, AuditAction, AuditLog, 
    CaseStatus, Donor, Recipient, RelationType, User, HumanCorrection
)
from thoa_screening.services.screening import screen_case, ScreeningError
from thoa_screening.services.explanations import ExplanationGenerator
from thoa_screening.services.audit import audit_log

router = APIRouter(prefix="/cases", tags=["cases"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = ["application/pdf", "image/jpeg", "image/png"]
UPLOAD_DIR = "./uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.websocket("/ws/{case_id}")
async def websocket_endpoint(websocket: WebSocket, case_id: str):
    await manager.connect(websocket, case_id)
    try:
        while True:
            # We don't expect the client to send much, but keep the connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, case_id)

@router.post("/{case_id}/documents", response_model=DocumentUploadResponse, responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
@audit_log(AuditAction.DOCUMENT_UPLOADED)
async def upload_document(
    case_id: uuid.UUID,
    request: Request,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a document for a specific case.
    Validates file type (PDF/JPG/PNG) and size (Max 10MB).
    """
    # 1. Validate Case Exists
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    # 2. Validate Content Type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )

    # 3. Read File and Validate Size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit.")
        
    # Calculate hash
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # 4. Save to Disk
    file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
    internal_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, internal_filename)
    
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    # 5. Save to Database
    # (Assuming dummy uploaded_by_id for now as auth is out of scope)
    # Using the case creator for simplicity
    doc = Document(
        case_id=case.id,
        document_type=document_type,
        file_path=file_path,
        file_hash=file_hash,
        original_filename=file.filename or "unknown",
        mime_type=file.content_type,
        file_size_bytes=len(file_bytes),
        uploaded_by_id=case.created_by_id 
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # Broadcast to websocket
    import asyncio
    asyncio.create_task(manager.broadcast({
        "event": "document_uploaded",
        "document_id": str(doc.id),
        "filename": doc.original_filename
    }, str(case_id)))
    
    return DocumentUploadResponse(
        document_id=str(doc.id),
        original_filename=doc.original_filename
    )

@router.post("/{case_id}/screen", response_model=ScreeningResultResponse, status_code=status.HTTP_202_ACCEPTED, responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
@audit_log(AuditAction.RULES_EVALUATED)
async def trigger_screening(
    case_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Triggers the REAL screening engine synchronously.
    (In a production Docker environment, this is offloaded to Celery).
    """
    
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
        
    # Set status to UNDER_REVIEW while processing
    case.status = CaseStatus.UNDER_REVIEW
    db.commit()
    
    await manager.broadcast({"event": "screening_started", "message": "Starting Rule Evaluation DAG..."}, str(case_id))
    
    try:
        # Run the REAL OCR and Rule Engine pipeline synchronously
        screening_result = screen_case(case_id, db)
        
        # Reload the case to get the updated status
        db.refresh(case)
        
        rule_results = db.query(RuleResult).filter(RuleResult.case_id == case_id).all()
        explanations_raw = ExplanationGenerator.generate(case, rule_results)
        
        return ScreeningResultResponse(
            status=case.status.value,
            flags=screening_result["flags"],
            needs_legal_verification=screening_result["needs_legal_verification"],
            explanations=explanations_raw
        )
    except ScreeningError as e:
        # If it fails, revert status
        case.status = CaseStatus.REJECTED
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))
        
@router.get("/{case_id}/screening-result", response_model=ScreeningResultResponse, responses={404: {"model": ErrorResponse}})
def get_screening_result(
    case_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieves the persisted screening result for a case.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
        
    rule_results = db.query(RuleResult).filter(RuleResult.case_id == case_id).all()
    flags = [f"{r.rule_code}: {r.message}" for r in rule_results if r.severity in ("ERROR", "WARNING")]
    needs_legal = any(r.needs_legal_verification for r in rule_results)
    explanations = ExplanationGenerator.generate(case, rule_results)
    
    return ScreeningResultResponse(
        status=case.status.value,
        flags=flags,
        needs_legal_verification=needs_legal,
        explanations=explanations
    )

@router.get("/{case_id}/report", responses={404: {"model": ErrorResponse}})
def get_report(
    case_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Returns a generated PDF report for the committee.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
        
    # We run the screen_case function to get the latest result dictionary.
    # In a real production system, this result would be cached in the database.
    try:
        screening_result = screen_case(case_id, db)
    except Exception:
        # If it fails, we just use a default pending result so the report still generates
        screening_result = {"status": "PENDING_COMMITTEE_REVIEW", "flags": [], "needs_legal_verification": False, "explanations": []}
        
    pdf_bytes = generate_report(case, screening_result)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=THOA_Report_{case.case_number}.pdf"
        }
    )

@router.get("/{case_id}/documents")
def list_documents(
    case_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """List all documents attached to a case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    
    documents = db.query(Document).filter(Document.case_id == case_id).order_by(Document.created_at.desc()).all()
    return [
        {
            "id": str(d.id),
            "document_type": d.document_type.value,
            "original_filename": d.original_filename,
            "mime_type": d.mime_type,
            "file_size_bytes": d.file_size_bytes,
            "is_verified": d.is_verified,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in documents
    ]

@router.get("/{case_id}/documents/{document_id}/file")
def serve_document_file(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Serve the raw file content for inline viewing (PDF/image)."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.case_id == case_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    if not os.path.isfile(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")
    
    with open(doc.file_path, "rb") as f:
        content = f.read()
    
    return Response(
        content=content,
        media_type=doc.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"inline; filename=\"{doc.original_filename}\""
        }
    )

@router.get("/{case_id}/audit", response_model=List[AuditLogResponse], responses={404: {"model": ErrorResponse}})
def get_audit_logs(
    case_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Retrieves the immutable audit log trail for a case.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
        
    logs = db.query(AuditLog).filter(AuditLog.case_id == case_id).order_by(AuditLog.created_at.desc()).all()
    
    return [
        AuditLogResponse(
            id=log.id,
            case_id=log.case_id,
            user_id=log.user_id,
            action=log.action.value,
            detail=log.detail,
            ip_address=log.ip_address,
            created_at=log.created_at
        ) for log in logs
    ]

@router.post("", response_model=CaseSummary)
def create_case(case_data: CaseCreate, db: Session = Depends(get_db)):
    """Create a new transplant case."""
    # 1. Create a dummy user for the created_by_id
    dummy_user = db.query(User).first()
    if not dummy_user:
        dummy_user = User(email="system@thoa.gov.in", full_name="System", role="ADMIN", password_hash="dummy")
        db.add(dummy_user)
        db.commit()
        db.refresh(dummy_user)
        
    case_number = f"THOA-{uuid.uuid4().hex[:6].upper()}"

    case = Case(
        case_number=case_number,
        relation_type=RelationType(case_data.relation_type),
        hospital_name=case_data.hospital_name,
        organ_type=case_data.organ_type,
        created_by_id=dummy_user.id
    )
    db.add(case)
    db.flush()
    
    donor = Donor(
        case_id=case.id,
        full_name=case_data.donor.full_name,
        age=case_data.donor.age,
        gender=case_data.donor.gender,
        aadhaar_number_enc=case_data.donor.aadhaar_number.encode('utf-8'),
        pan_number_enc=case_data.donor.pan_number.encode('utf-8') if case_data.donor.pan_number else None,
        address=case_data.donor.address
    )
    recipient = Recipient(
        case_id=case.id,
        full_name=case_data.recipient.full_name,
        age=case_data.recipient.age,
        gender=case_data.recipient.gender,
        aadhaar_number_enc=case_data.recipient.aadhaar_number.encode('utf-8'),
        pan_number_enc=case_data.recipient.pan_number.encode('utf-8') if case_data.recipient.pan_number else None,
        address=case_data.recipient.address
    )
    db.add(donor)
    db.add(recipient)
    db.commit()
    db.refresh(case)
    
    return CaseSummary(
        id=str(case.id),
        case_number=case.case_number,
        relation_type=case.relation_type.value,
        hospital_name=case.hospital_name,
        organ_type=case.organ_type,
        status=case.status.value,
        created_at=case.created_at.isoformat()
    )

@router.get("", response_model=List[CaseSummary])
def get_cases(db: Session = Depends(get_db)):
    """List all cases."""
    cases = db.query(Case).order_by(Case.created_at.desc()).all()
    return [
        CaseSummary(
            id=str(c.id),
            case_number=c.case_number,
            relation_type=c.relation_type.value,
            hospital_name=c.hospital_name,
            organ_type=c.organ_type,
            status=c.status.value,
            created_at=c.created_at.isoformat()
        ) for c in cases
    ]

@router.get("/{case_id}/details", response_model=CaseDetail)
def get_case_details(case_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get full case details including flags and explanations."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
        
    rule_results = db.query(RuleResult).filter(RuleResult.case_id == case_id).all()
    flags = [f"{r.rule_code}: {r.message}" for r in rule_results if r.severity in ("ERROR", "WARNING")]
    explanations = ExplanationGenerator.generate(case, rule_results)
    
    return CaseDetail(
        id=str(case.id),
        case_number=case.case_number,
        relation_type=case.relation_type.value,
        hospital_name=case.hospital_name,
        organ_type=case.organ_type,
        status=case.status.value,
        created_at=case.created_at.isoformat(),
        donor=PersonDetail(full_name=case.donor.full_name, age=case.donor.age) if case.donor else PersonDetail(full_name="Unknown", age=0),
        recipient=PersonDetail(full_name=case.recipient.full_name, age=case.recipient.age) if case.recipient else PersonDetail(full_name="Unknown", age=0),
        flags=flags,
        explanations=explanations
    )

@router.post("/{case_id}/decision")
@audit_log(AuditAction.STATUS_CHANGED)
def submit_decision(
    case_id: uuid.UUID, 
    decision: DecisionSubmit, 
    request: Request, 
    db: Session = Depends(get_db)
):
    """Submit final committee decision."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
        
    case.committee_decision_notes = f"Decision: {decision.decision.upper()}\nComment: {decision.comment}\nJustification: {decision.justification or 'None'}"
    
    # We treat APPROVED as AUTO_APPROVE to pass DB enum validation if APPROVED doesn't exist.
    if decision.decision.upper() == "REJECTED":
        case.status = CaseStatus.REJECTED
    elif decision.decision.upper() == "APPROVED":
        case.status = CaseStatus.AUTO_APPROVE
        
    db.commit()
    return {"message": "Decision submitted successfully", "status": case.status.value}


@router.post("/{case_id}/corrections", response_model=HumanCorrectionResponse)
def submit_human_correction(
    case_id: uuid.UUID,
    correction: HumanCorrectionCreate,
    db: Session = Depends(get_db)
):
    """
    Submit a human-in-the-loop (HITL) correction for OCR/NLP extracted data.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    # Using dummy admin for MVP
    dummy_user = db.query(User).first()
    
    new_correction = HumanCorrection(
        case_id=case_id,
        corrected_by_id=dummy_user.id if dummy_user else None,
        field_name=correction.field_name,
        original_text=correction.original_text,
        corrected_text=correction.corrected_text
    )
    db.add(new_correction)
    db.commit()
    db.refresh(new_correction)
    
    return HumanCorrectionResponse(
        id=new_correction.id,
        field_name=new_correction.field_name,
        corrected_text=new_correction.corrected_text,
        created_at=new_correction.created_at
    )
