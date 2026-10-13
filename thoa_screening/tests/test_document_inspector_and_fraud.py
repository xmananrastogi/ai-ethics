"""
Tests for Document Page Renderer and Computer Vision Fraud Detection Services.
"""
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from thoa_screening.api.main import app
from thoa_screening.api.deps import get_db
from thoa_screening.database import Base
from thoa_screening.database.models import (
    User, Case, Donor, Recipient, Document, DocumentType, RelationType, UserRole
)
from thoa_screening.services.document_renderer import render_document_page
from thoa_screening.services.fraud_detector import analyze_document_fraud

REAL_DOCS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "real_thoa_documents", "test_dossiers"
)

# Shared in-memory test database
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def test_document_renderer_on_real_pdf():
    """Verify high-res page rendering and bounding box location on Form 1."""
    pdf_path = os.path.join(REAL_DOCS_DIR, "case_1_near_relative", "Form_1_Consent_Donor.pdf")
    assert os.path.exists(pdf_path), f"Test file not found: {pdf_path}"

    res = render_document_page(pdf_path, page_number=0)
    assert res["page_count"] >= 1
    assert res["page_image"] is not None
    assert res["page_image"].startswith("data:image/png;base64,")
    assert len(res["bounding_boxes"]) > 0

    # Check for expected statutory bounding boxes
    fields = [b["field"] for b in res["bounding_boxes"]]
    assert "donor_name" in fields or "aadhaar" in fields or "dob" in fields

    # Validate coordinate normalization [0.0 - 1.0]
    for b in res["bounding_boxes"]:
        assert 0.0 <= b["x"] <= 1.0
        assert 0.0 <= b["y"] <= 1.0
        assert 0.0 <= b["w"] <= 1.0
        assert 0.0 <= b["h"] <= 1.0


def test_cv_fraud_detector_on_real_pdf():
    """Verify Computer Vision Error Level Analysis and statutory signature check."""
    pdf_path = os.path.join(REAL_DOCS_DIR, "case_1_near_relative", "Form_1_Consent_Donor.pdf")
    assert os.path.exists(pdf_path)

    res = analyze_document_fraud(pdf_path, doc_type="FORM_1")
    assert "fraud_risk_score" in res
    assert 0.0 <= res["fraud_risk_score"] <= 100.0
    assert res["verdict"] in ("AUTHENTIC", "SUSPICIOUS_ARTIFACTS", "HIGH_TAMPERING_RISK")
    assert "signature_verification" in res
    assert res["signature_verification"]["signature_zone_checked"] is True
    assert "heatmap_image" in res
    assert res["heatmap_image"].startswith("data:image/jpeg;base64,")


def test_rendered_and_fraud_api_endpoints():
    """Verify HTTP API endpoints for document rendering and fraud forensics."""
    db = TestingSessionLocal()
    user = User(
        id=uuid.uuid4(), email=f"test_{uuid.uuid4().hex[:6]}@thoa.gov.in",
        full_name="Tester", role=UserRole.ADMIN, password_hash="hash"
    )
    db.add(user)
    db.commit()

    case = Case(
        case_number=f"TEST-INSPECT-{uuid.uuid4().hex[:6]}",
        relation_type=RelationType.SIBLING,
        hospital_name="AIIMS",
        organ_type="Kidney",
        created_by_id=user.id
    )
    db.add(case)
    db.commit()

    pdf_path = os.path.join(REAL_DOCS_DIR, "case_1_near_relative", "Form_1_Consent_Donor.pdf")
    doc = Document(
        case_id=case.id,
        uploaded_by_id=user.id,
        document_type=DocumentType.FORM_1,
        original_filename="Form_1_Consent_Donor.pdf",
        file_path=pdf_path,
        file_hash="test_hash",
        mime_type="application/pdf",
        file_size_bytes=os.path.getsize(pdf_path),
        is_verified=True
    )
    db.add(doc)
    db.commit()
    case_id = str(case.id)
    doc_id = str(doc.id)
    db.close()

    # 1. Test rendered page endpoint
    render_url = f"/cases/{case_id}/documents/{doc_id}/rendered?page=0"
    r_render = client.get(render_url)
    assert r_render.status_code == 200
    data_render = r_render.json()
    assert data_render["page_image"] is not None
    assert len(data_render["bounding_boxes"]) > 0

    # 2. Test fraud check endpoint
    fraud_url = f"/cases/{case_id}/documents/{doc_id}/fraud-check"
    r_fraud = client.get(fraud_url)
    assert r_fraud.status_code == 200
    data_fraud = r_fraud.json()
    assert "fraud_risk_score" in data_fraud
    assert "heatmap_image" in data_fraud
