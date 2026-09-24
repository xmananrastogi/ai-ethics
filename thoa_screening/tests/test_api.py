import io
import uuid
import pytest
from fastapi.testclient import TestClient

import os
os.environ["THOA_DATABASE_URL"] = "sqlite:///:memory:"

# Must import worker before app to avoid Celery broker connection issues
import thoa_screening.worker  # noqa: F401

from thoa_screening.api.main import app
from thoa_screening.database import Base
from thoa_screening.api.deps import get_db
from thoa_screening.database.models import (
    User, Case, Donor, Recipient, Document, DocumentType, UserRole,
    RelationType, RuleResult, RuleOutcome, CaseStatus
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test database with shared cache for memory
engine = create_engine(
    "sqlite:///file:memdb1?mode=memory&cache=shared",
    connect_args={"check_same_thread": False}
)
Base.metadata.create_all(engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def _create_full_case(db=None) -> str:
    """Helper: create a Case with Donor + Recipient (required by the real screening engine)."""
    close_db = False
    if db is None:
        db = TestingSessionLocal()
        close_db = True

    user = User(
        email=f"test_{uuid.uuid4().hex[:8]}@admin.com",
        full_name="Admin",
        role=UserRole.ADMIN,
        password_hash="hash"
    )
    db.add(user)
    db.commit()

    case = Case(
        case_number=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        relation_type=RelationType.NON_RELATIVE,
        hospital_name="Test Hospital",
        organ_type="KIDNEY",
        created_by_id=user.id
    )
    db.add(case)
    db.flush()

    donor = Donor(
        case_id=case.id,
        full_name="Test Donor",
        age=35,
        gender="MALE",
        aadhaar_number_enc=b"123456789012",
        nationality="INDIAN"
    )
    recipient = Recipient(
        case_id=case.id,
        full_name="Test Recipient",
        age=40,
        gender="FEMALE",
        aadhaar_number_enc=b"987654321098",
        nationality="INDIAN"
    )
    db.add(donor)
    db.add(recipient)
    db.commit()

    case_id = str(case.id)
    if close_db:
        db.close()
    return case_id


@pytest.fixture
def test_case_id():
    """Fixture: case WITH donor + recipient (for real screening)."""
    return _create_full_case()


@pytest.fixture
def bare_case_id():
    """Fixture: case WITHOUT donor/recipient (for upload tests that don't need screening)."""
    db = TestingSessionLocal()
    user = User(
        email=f"bare_{uuid.uuid4().hex[:8]}@admin.com",
        full_name="Admin",
        role=UserRole.ADMIN,
        password_hash="hash"
    )
    db.add(user)
    db.commit()

    case = Case(
        case_number=f"BARE-{uuid.uuid4().hex[:8].upper()}",
        relation_type=RelationType.NON_RELATIVE,
        hospital_name="Test Hospital",
        organ_type="KIDNEY",
        created_by_id=user.id
    )
    db.add(case)
    db.commit()
    case_id = str(case.id)
    db.close()
    return case_id


# ================================================================
# Document Upload Tests
# ================================================================

def test_upload_document_success(test_case_id):
    file_content = b"fake pdf content"
    file = io.BytesIO(file_content)

    response = client.post(
        f"/cases/{test_case_id}/documents",
        data={"document_type": "FORM_11"},
        files={"file": ("test.pdf", file, "application/pdf")}
    )

    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert data["original_filename"] == "test.pdf"


def test_upload_document_invalid_type(test_case_id):
    file_content = b"fake text content"
    file = io.BytesIO(file_content)

    response = client.post(
        f"/cases/{test_case_id}/documents",
        data={"document_type": "FORM_11"},
        files={"file": ("test.txt", file, "text/plain")}
    )

    assert response.status_code == 400
    data = response.json()
    assert "Invalid file type" in data["detail"]


# ================================================================
# Screening Tests (Real Engine)
# ================================================================

def test_trigger_screening_success(test_case_id):
    """The real screening engine runs on a case with donor+recipient.
    For a NON_RELATIVE case with NO documents uploaded, we expect flags."""
    response = client.post(f"/cases/{test_case_id}/screen")

    assert response.status_code == 202
    data = response.json()
    # The Pydantic TransplantCase validator catches missing required documents
    # (Form 3, Form 4, Form 11, etc.) and the case ends up REJECTED with
    # SCHEMA_VALIDATION_ERROR flags, OR it goes through the rule engine and
    # gets DOCUMENTATION_INCOMPLETE. Either way, it should NOT be PENDING.
    assert data["status"] in (
        "REJECTED", "COMMITTEE_REVIEW", "DOCUMENTATION_INCOMPLETE",
        "ANOMALIES_DETECTED", "PENDING_COMMITTEE_REVIEW"
    )
    # Should have flags for missing documents
    assert len(data["flags"]) > 0


def test_trigger_screening_not_found():
    response = client.post(f"/cases/{uuid.uuid4()}/screen")
    assert response.status_code == 404


def test_trigger_screening_with_documents(test_case_id):
    """Upload Form 11 and Identity Proof, then screen. Should still flag missing docs."""
    # Upload Form 11
    client.post(
        f"/cases/{test_case_id}/documents",
        data={"document_type": "FORM_11"},
        files={"file": ("form11.pdf", io.BytesIO(b"form11 content"), "application/pdf")}
    )
    # Upload Identity Proof
    client.post(
        f"/cases/{test_case_id}/documents",
        data={"document_type": "IDENTITY_PROOF"},
        files={"file": ("aadhaar.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100), "image/jpeg")}
    )

    response = client.post(f"/cases/{test_case_id}/screen")
    assert response.status_code == 202
    data = response.json()
    # Even with Form 11 and Identity Proof, there are still other required docs
    # missing (Form 3, Form 4, financial affidavit, police verification, etc.)
    assert data["status"] in (
        "REJECTED", "COMMITTEE_REVIEW", "DOCUMENTATION_INCOMPLETE",
        "ANOMALIES_DETECTED", "PENDING_COMMITTEE_REVIEW"
    )


# ================================================================
# Screening Result Retrieval
# ================================================================

def test_get_screening_result(test_case_id):
    db = TestingSessionLocal()
    rule = RuleResult(
        case_id=uuid.UUID(test_case_id),
        rule_code="TEST_RULE",
        result=RuleOutcome.FAIL,
        severity="ERROR",
        message="Test message",
        needs_legal_verification=True
    )

    case = db.query(Case).filter(Case.id == uuid.UUID(test_case_id)).first()
    case.status = CaseStatus.REJECTED

    db.add(rule)
    db.commit()
    db.close()

    response = client.get(f"/cases/{test_case_id}/screening-result")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "REJECTED"
    assert "TEST_RULE: Test message" in data["flags"]
    assert data["needs_legal_verification"] is True


# ================================================================
# Report Generation
# ================================================================

def test_get_report_success(test_case_id):
    response = client.get(f"/cases/{test_case_id}/report")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    # Check it actually has PDF content
    assert response.content[:4] == b"%PDF"


# ================================================================
# Case CRUD via API
# ================================================================

def test_create_case_via_api():
    """Tests the POST /cases endpoint end-to-end."""
    payload = {
        "relation_type": "SPOUSE",
        "hospital_name": "AIIMS Delhi",
        "organ_type": "KIDNEY",
        "donor": {
            "full_name": "API Donor",
            "age": 30,
            "aadhaar_number": "111122223333"
        },
        "recipient": {
            "full_name": "API Recipient",
            "age": 45,
            "aadhaar_number": "444455556666"
        }
    }
    response = client.post("/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["relation_type"] == "SPOUSE"
    assert data["hospital_name"] == "AIIMS Delhi"
    assert data["organ_type"] == "KIDNEY"
    assert data["status"] == "PENDING"
    assert "id" in data
    assert data["case_number"].startswith("THOA-")


def test_list_cases():
    """Tests GET /cases returns a list."""
    response = client.get("/cases")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# ================================================================
# Document List & Serve
# ================================================================

def test_document_list_and_serve(test_case_id):
    """Upload a document, list documents, then serve the file."""
    # Upload
    upload_resp = client.post(
        f"/cases/{test_case_id}/documents",
        data={"document_type": "IDENTITY_PROOF"},
        files={"file": ("id_card.pdf", io.BytesIO(b"fake pdf for serving test"), "application/pdf")}
    )
    assert upload_resp.status_code == 200
    doc_id = upload_resp.json()["document_id"]

    # List
    list_resp = client.get(f"/cases/{test_case_id}/documents")
    assert list_resp.status_code == 200
    docs = list_resp.json()
    assert any(d["id"] == doc_id for d in docs)

    # Serve
    serve_resp = client.get(f"/cases/{test_case_id}/documents/{doc_id}/file")
    assert serve_resp.status_code == 200
    assert serve_resp.content == b"fake pdf for serving test"


# ================================================================
# Committee Decision
# ================================================================

def test_submit_decision(test_case_id):
    """Tests the POST /cases/{id}/decision endpoint."""
    payload = {
        "decision": "APPROVED",
        "comment": "All documents verified by committee.",
        "justification": "Near-relative confirmed via DNA."
    }
    response = client.post(f"/cases/{test_case_id}/decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "AUTO_APPROVE"  # APPROVED maps to AUTO_APPROVE
    assert "Decision submitted" in data["message"]


# ================================================================
# Full E2E Screening Flow
# ================================================================

def test_full_screening_flow():
    """End-to-end: create case via API, upload docs, screen, get result, submit decision."""
    # 1. Create case
    create_resp = client.post("/cases", json={
        "relation_type": "NON_RELATIVE",
        "hospital_name": "Fortis Mumbai",
        "organ_type": "LIVER",
        "donor": {"full_name": "E2E Donor", "age": 28, "aadhaar_number": "999988887777"},
        "recipient": {"full_name": "E2E Recipient", "age": 50, "aadhaar_number": "666655554444"}
    })
    assert create_resp.status_code == 200
    case_id = create_resp.json()["id"]

    # 2. Upload Form 11
    client.post(
        f"/cases/{case_id}/documents",
        data={"document_type": "FORM_11"},
        files={"file": ("form11.pdf", io.BytesIO(b"form 11 pdf content"), "application/pdf")}
    )

    # 3. Screen — the real engine runs OCR (gracefully handles fake PDFs) and rule evaluation
    screen_resp = client.post(f"/cases/{case_id}/screen")
    assert screen_resp.status_code == 202
    screen_data = screen_resp.json()
    assert "status" in screen_data
    assert "flags" in screen_data
    assert "explanations" in screen_data

    # 4. Get screening result
    result_resp = client.get(f"/cases/{case_id}/screening-result")
    assert result_resp.status_code == 200

    # 5. Submit decision (committee overrides to APPROVED)
    decision_resp = client.post(f"/cases/{case_id}/decision", json={
        "decision": "APPROVED",
        "comment": "Committee approved after review."
    })
    assert decision_resp.status_code == 200

    # 6. Verify final status
    details_resp = client.get(f"/cases/{case_id}/details")
    assert details_resp.status_code == 200
    assert details_resp.json()["status"] == "AUTO_APPROVE"


# ================================================================
# Validation Error Handler
# ================================================================

def test_validation_error_handler():
    """Test POST body missing required field `document_type`."""
    file_content = b"fake pdf content"
    file = io.BytesIO(file_content)

    response = client.post(
        f"/cases/{uuid.uuid4()}/documents",
        files={"file": ("test.pdf", file, "application/pdf")}
        # Missing data={"document_type": ...}
    )

    # Custom handler should return 400, not 422
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "Validation failed."
    assert any("document_type" in d["field"] for d in data["details"])
