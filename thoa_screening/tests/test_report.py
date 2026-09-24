import pytest
import uuid
import os
from datetime import datetime

os.environ["THOA_DATABASE_URL"] = "sqlite:///:memory:"

from thoa_screening.database.models import Case, Document, DocumentType, RelationType, User, UserRole
from thoa_screening.services.report_generator import generate_report
from thoa_screening.api.deps import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# DB Setup
engine = create_engine("sqlite:///file:memdb_rep?mode=memory&cache=shared", connect_args={"check_same_thread": False})
from thoa_screening.database import Base
Base.metadata.create_all(engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def mock_case(db_session):
    user = User(email=f"report_{uuid.uuid4()}@test.com", full_name="Admin", role=UserRole.ADMIN, password_hash="hash")
    db_session.add(user)
    db_session.commit()
    
    case = Case(
        case_number=f"THOA-2026-{uuid.uuid4().hex[:4]}",
        relation_type=RelationType.NON_RELATIVE,
        hospital_name="AIIMS",
        organ_type="Kidney",
        created_by_id=user.id
    )
    db_session.add(case)
    db_session.commit()
    
    # Add documents
    docs = [
        Document(case_id=case.id, uploaded_by_id=user.id, document_type=DocumentType.FORM_1, file_path="x.pdf", file_hash="hash1", original_filename="x.pdf"),
        Document(case_id=case.id, uploaded_by_id=user.id, document_type=DocumentType.FINANCIAL_AFFIDAVIT, file_path="y.pdf", file_hash="hash2", original_filename="y.pdf"),
    ]
    db_session.add_all(docs)
    db_session.commit()
    
    return case

def test_generate_report_pdf(mock_case):
    screening_result = {
        "status": "PENDING_COMMITTEE_REVIEW",
        "flags": ["Missing Form 11"],
        "needs_legal_verification": True,
        "explanations": [
            {
                "rule_code": "NON_RELATIVE_NO_FORM_11",
                "rule_description": "Missing Form 11 for non-relative donation.",
                "thoa_reference": "Rule 19",
                "evidence": "Form 11 not found in document inventory.",
                "next_step": "Request Form 11 from hospital.",
                "needs_legal_verification": True
            }
        ]
    }
    
    pdf_bytes = generate_report(mock_case, screening_result)
    
    assert pdf_bytes is not None
    assert pdf_bytes.startswith(b"%PDF-1.")
    assert len(pdf_bytes) > 1000  # Ensure it has substantial content
