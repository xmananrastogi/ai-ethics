import uuid
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from thoa_screening.database import Base
from thoa_screening.database.models import (
    User, Case, Donor, Recipient, Document, DocumentType, UserRole, RelationType,
    CaseStatus, ExtractedData, RuleResult, RuleOutcome
)
from thoa_screening.services.screening import screen_case, ScreeningError

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def setup_db(session):
    user = User(email="test@admin.com", full_name="Admin", role=UserRole.ADMIN, password_hash="hash")
    session.add(user)
    session.commit()
    
    case = Case(
        case_number="THOA-123",
        relation_type=RelationType.NON_RELATIVE,
        hospital_name="Test Hospital",
        organ_type="Kidney",
        created_by_id=user.id
    )
    session.add(case)
    session.commit()
    
    donor = Donor(
        case_id=case.id,
        full_name="John Doe",
        age=30,
        aadhaar_number_enc=b"123456789012",
        monthly_income=Decimal("50000.00")
    )
    recipient = Recipient(
        case_id=case.id,
        full_name="Jane Doe",
        age=40,
        aadhaar_number_enc=b"987654321098",
        monthly_income=Decimal("60000.00")
    )
    session.add(donor)
    session.add(recipient)
    session.commit()
    
    doc = Document(
        case_id=case.id,
        document_type=DocumentType.FORM_11,
        file_path="mock/path.pdf",
        file_hash="hash",
        original_filename="form11.pdf",
        uploaded_by_id=user.id
    )
    session.add(doc)
    session.commit()
    
    return case.id, user.id, doc.id

@patch("thoa_screening.services.screening.process_document")
def test_screen_case_success(mock_process, session, setup_db):
    case_id, user_id, doc_id = setup_db
    
    # Mock OCR output
    mock_process.return_value = {
        "pipeline_metadata": {"pages_processed": 1},
        "extracted_data": {"full_name": "John Doe OCR"},
        "field_confidences": {"full_name": 95.0}
    }
    
    result = screen_case(case_id, session)
    
    # Verify OCR was called since extracted_data was empty
    mock_process.assert_called_once_with("mock/path.pdf")
    
    # Verify ExtractedData was persisted
    extracted = session.query(ExtractedData).filter_by(document_id=doc_id).first()
    assert extracted is not None
    assert extracted.field_name == "full_name"
    assert extracted.field_value == "John Doe OCR"
    
    # Verify RuleResults were persisted
    rules = session.query(RuleResult).filter_by(case_id=case_id).all()
    assert len(rules) > 0
    
    # Verify Case Status was updated
    case = session.query(Case).filter_by(id=case_id).first()
    # Depending on rules, it should be PENDING_COMMITTEE_REVIEW or DOCUMENTATION_INCOMPLETE
    assert case.status in (CaseStatus.COMMITTEE_REVIEW, CaseStatus.REJECTED)
    
    # Verify result dictionary
    assert "status" in result
    assert "flags" in result
    assert "needs_legal_verification" in result

def test_screen_case_invalid_uuid(session):
    with pytest.raises(ScreeningError, match="Invalid UUID format"):
        screen_case("invalid-uuid", session)

def test_screen_case_not_found(session):
    with pytest.raises(ScreeningError, match="not found"):
        screen_case(uuid.uuid4(), session)

@patch("thoa_screening.services.screening.process_document")
def test_screen_case_duplicate_submission_idempotent(mock_process, session, setup_db):
    case_id, user_id, doc_id = setup_db
    
    # Mock OCR output
    mock_process.return_value = {
        "pipeline_metadata": {"pages_processed": 1},
        "extracted_data": {"full_name": "John Doe OCR"},
        "field_confidences": {"full_name": 95.0}
    }
    
    # First execution
    result1 = screen_case(case_id, session)
    rule_count_after_first = session.query(RuleResult).filter_by(case_id=case_id).count()
    
    # Second execution (simulating duplicate submission)
    result2 = screen_case(case_id, session)
    rule_count_after_second = session.query(RuleResult).filter_by(case_id=case_id).count()
    
    # Validates that rules were not duplicated (old rows were cleaned up)
    assert rule_count_after_first > 0
    assert rule_count_after_first == rule_count_after_second
    assert result1["status"] == result2["status"]
