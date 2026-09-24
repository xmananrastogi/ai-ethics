from typing import List, Optional, Any
import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class DocumentUploadResponse(BaseModel):
    """Response returned upon successful document upload."""
    document_id: str
    original_filename: str
    message: str = "Document uploaded successfully."

class ErrorDetail(BaseModel):
    """Detailed error object, used for Pydantic validation failures or screening errors."""
    field: Optional[str] = None
    message: str
    type: str

class ErrorResponse(BaseModel):
    """Standardized error response format."""
    error: str
    details: Optional[List[ErrorDetail]] = None

class ExplanationModel(BaseModel):
    """Human-readable explanation of a flagged rule."""
    rule_code: str
    rule_description: str
    thoa_reference: Optional[str] = None
    evidence: str
    next_step: str
    needs_legal_verification: bool

class AuditLogResponse(BaseModel):
    """Schema for a single audit log entry."""
    id: uuid.UUID
    case_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    action: str
    detail: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

class ScreeningResultResponse(BaseModel):
    """Response containing the screening decision, flags, and detailed explanations."""
    status: str
    flags: List[str]
    needs_legal_verification: bool
    explanations: List[ExplanationModel] = Field(default_factory=list)

class PersonCreate(BaseModel):
    full_name: str
    age: int
    gender: Optional[str] = None
    aadhaar_number: str
    pan_number: Optional[str] = None
    address: Optional[str] = None

class CaseCreate(BaseModel):
    relation_type: str
    hospital_name: str
    organ_type: str
    donor: PersonCreate
    recipient: PersonCreate

class CaseSummary(BaseModel):
    id: str
    case_number: str
    relation_type: str
    hospital_name: str
    organ_type: str
    status: str
    created_at: str

class PersonDetail(BaseModel):
    full_name: str
    age: int

class CaseDetail(BaseModel):
    id: str
    case_number: str
    relation_type: str
    hospital_name: str
    organ_type: str
    status: str
    created_at: str
    donor: PersonDetail
    recipient: PersonDetail
    flags: List[str]
    explanations: List[ExplanationModel]

class DecisionSubmit(BaseModel):
    decision: str
    comment: str
    justification: Optional[str] = None
