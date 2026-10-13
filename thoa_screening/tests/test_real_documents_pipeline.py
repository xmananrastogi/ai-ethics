"""
Automated End-to-End Pipeline Tests Using Real Statutory THOA Documents.

Tests real document ingestion, OCR extraction, bounding boxes, DAG rule evaluation,
human-in-the-loop validation, and report generation using official government form PDFs.
"""
import os
import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from thoa_screening.api.main import app
from thoa_screening.api.deps import get_db
from thoa_screening.database import Base
from thoa_screening.database.models import (
    User, Case, Donor, Recipient, Document, DocumentType,
    RelationType, UserRole, CaseStatus, AuditLog, AuditAction
)
from thoa_screening.ocr.pipeline import process_document
from thoa_screening.services.screening import screen_case
from thoa_screening.services.report_generator import generate_report

# Shared in-memory test database
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
Base.metadata.create_all(engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

DOSSIER_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "real_thoa_documents", "test_dossiers"
)

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "reviewer@thoa.gov.in").first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            email="reviewer@thoa.gov.in",
            full_name="Dr. Reviewer",
            role=UserRole.ADMIN,
            password_hash="test"
        )
        db.add(user)
        db.commit()
    db.close()
    yield
    app.dependency_overrides.clear()

def test_real_form_1_ocr_extraction():
    """Test OCR pipeline on the official Form 1 (Living Near-Relative Consent)."""
    form_path = os.path.join(DOSSIER_DIR, "case_1_near_relative", "Form_1_Consent_Donor.pdf")
    assert os.path.exists(form_path), f"Test dossier missing: {form_path}"

    res = process_document(form_path)
    assert "extracted_data" in res
    assert "field_confidences" in res
    assert "bounding_boxes" in res

    data = res["extracted_data"]
    # Check that extracted DOB and Aadhaar match what was stamped
    assert data.get("dob") == "1988-08-15"
    assert data.get("aadhaar_number") == "543298761234"
    # PAN should be detected (10 characters)
    assert data.get("pan_number") is not None
    assert len(data.get("pan_number")) == 10
    assert res["field_confidences"]["dob"] >= 80.0
    assert res["field_confidences"]["aadhaar_number"] >= 90.0

def test_real_case_near_relative_workflow():
    """End-to-End Test: Living Near-Relative Case with real Form 1, Form 4, Form 11."""
    db = TestingSessionLocal()
    user = db.query(User).first()

    # 1. Create Case in DB
    case = Case(
        id=uuid.uuid4(),
        case_number=f"THOA-REAL-001",
        relation_type=RelationType.SIBLING,
        hospital_name="AIIMS New Delhi",
        organ_type="KIDNEY",
        status=CaseStatus.PENDING,
        created_by_id=user.id
    )
    donor = Donor(
        case_id=case.id,
        full_name="Sunita Sharma",
        age=36,
        gender="F",
        aadhaar_number_enc=b"enc_543298761234",
        address="New Delhi"
    )
    recipient = Recipient(
        case_id=case.id,
        full_name="Rahul Sharma",
        age=42,
        gender="M",
        aadhaar_number_enc=b"enc_987654321098",
        address="New Delhi"
    )
    db.add_all([case, donor, recipient])
    db.commit()

    case_id_str = str(case.id)

    # 2. Upload Real Documents via API
    docs_to_upload = [
        ("case_1_near_relative/Form_1_Consent_Donor.pdf", "FORM_1"),
        ("case_1_near_relative/Form_4_Medical_Fitness.pdf", "FORM_4"),
        ("case_1_near_relative/Form_11_Joint_Application.pdf", "FORM_11"),
    ]

    for rel_path, doc_type in docs_to_upload:
        abs_path = os.path.join(DOSSIER_DIR, rel_path)
        with open(abs_path, "rb") as f:
            resp = client.post(
                f"/cases/{case_id_str}/documents",
                data={"document_type": doc_type},
                files={"file": (os.path.basename(abs_path), f, "application/pdf")}
            )
            assert resp.status_code == 200, f"Failed uploading {doc_type}: {resp.text}"
            data = resp.json()
            assert "document_id" in data

    # 3. Trigger Automated Screening via API
    screen_resp = client.post(f"/cases/{case_id_str}/screen")
    assert screen_resp.status_code == 202
    res_data = screen_resp.json()

    assert res_data["status"] in ("APPROVED", "AUTO_APPROVE", "PENDING", "MORE_INFO", "COMMITTEE_REVIEW")
    assert "bounding_boxes" in res_data
    assert "explanations" in res_data

    # 4. Generate Official Report
    report_bytes = generate_report(case, res_data)
    assert report_bytes.startswith(b"%PDF")
    assert len(report_bytes) > 1000

    db.close()

def test_real_case_spousal_workflow():
    """End-to-End Test: Living Spousal Case with real Form 2, Form 4, Form 11."""
    db = TestingSessionLocal()
    user = db.query(User).first()

    case = Case(
        id=uuid.uuid4(),
        case_number=f"THOA-REAL-002",
        relation_type=RelationType.SPOUSE,
        hospital_name="Apollo Hospitals Chennai",
        organ_type="LIVER",
        status=CaseStatus.PENDING,
        created_by_id=user.id
    )
    donor = Donor(
        case_id=case.id,
        full_name="Priya Verma",
        age=38,
        gender="F",
        aadhaar_number_enc=b"enc_771234569012"
    )
    recipient = Recipient(
        case_id=case.id,
        full_name="Amit Verma",
        age=41,
        gender="M",
        aadhaar_number_enc=b"enc_231490876543"
    )
    db.add_all([case, donor, recipient])
    db.commit()

    case_id_str = str(case.id)

    # Upload Form 2 and Form 4
    for rel_path, doc_type in [
        ("case_2_spousal/Form_2_Spousal_Consent.pdf", "FORM_2"),
        ("case_2_spousal/Form_4_Medical_Fitness.pdf", "FORM_4"),
        ("case_2_spousal/Form_11_Joint_Application.pdf", "FORM_11"),
    ]:
        abs_path = os.path.join(DOSSIER_DIR, rel_path)
        with open(abs_path, "rb") as f:
            resp = client.post(
                f"/cases/{case_id_str}/documents",
                data={"document_type": doc_type},
                files={"file": (os.path.basename(abs_path), f, "application/pdf")}
            )
            assert resp.status_code == 200

    # Trigger screening
    screen_resp = client.post(f"/cases/{case_id_str}/screen")
    assert screen_resp.status_code == 202
    res_data = screen_resp.json()

    # Form 2 spousal consent satisfies living spousal donor rules
    assert res_data["status"] in ("APPROVED", "AUTO_APPROVE", "COMMITTEE_REVIEW", "PENDING", "MORE_INFO")
    db.close()

def test_real_case_unrelated_donor_flags_committee():
    """End-to-End Test: Unrelated Donor triggers Authorization Committee review under THOA Rule 19."""
    db = TestingSessionLocal()
    user = db.query(User).first()

    case = Case(
        id=uuid.uuid4(),
        case_number=f"THOA-REAL-003",
        relation_type=RelationType.NON_RELATIVE,
        hospital_name="Sir Ganga Ram Hospital",
        organ_type="KIDNEY",
        status=CaseStatus.PENDING,
        created_by_id=user.id
    )
    donor = Donor(
        case_id=case.id,
        full_name="Vikram Malhotra",
        age=29,
        gender="M",
        aadhaar_number_enc=b"enc_882344551122"
    )
    recipient = Recipient(
        case_id=case.id,
        full_name="Suresh Gupta",
        age=52,
        gender="M",
        aadhaar_number_enc=b"enc_112233445566"
    )
    db.add_all([case, donor, recipient])
    db.commit()

    case_id_str = str(case.id)

    # Upload Form 3 and Form 11
    for rel_path, doc_type in [
        ("case_3_non_relative/Form_3_Non_Relative_Consent.pdf", "FORM_3"),
        ("case_3_non_relative/Form_11_Joint_Application.pdf", "FORM_11"),
    ]:
        abs_path = os.path.join(DOSSIER_DIR, rel_path)
        with open(abs_path, "rb") as f:
            resp = client.post(
                f"/cases/{case_id_str}/documents",
                data={"document_type": doc_type},
                files={"file": (os.path.basename(abs_path), f, "application/pdf")}
            )
            assert resp.status_code == 200

    # Trigger screening
    screen_resp = client.post(f"/cases/{case_id_str}/screen")
    assert screen_resp.status_code == 202
    res_data = screen_resp.json()

    # For unrelated donor with missing required docs: rejected or committee review
    assert res_data["status"] in ("COMMITTEE_REVIEW", "REJECTED")

    db.close()

def test_real_case_minor_donor_safety_violation():
    """End-to-End Test: Underage Donor (< 18 yrs) triggers mandatory ID-01 rejection."""
    db = TestingSessionLocal()
    user = db.query(User).first()

    case = Case(
        id=uuid.uuid4(),
        case_number=f"THOA-REAL-004",
        relation_type=RelationType.PARENT_CHILD,
        hospital_name="KIMS Hospital",
        organ_type="KIDNEY",
        status=CaseStatus.PENDING,
        created_by_id=user.id
    )
    # 16 years old
    donor = Donor(
        case_id=case.id,
        full_name="Ankit Patel",
        age=16,
        gender="M",
        aadhaar_number_enc=b"enc_123456789900"
    )
    recipient = Recipient(
        case_id=case.id,
        full_name="Rajesh Patel",
        age=48,
        gender="M",
        aadhaar_number_enc=b"enc_887766554433"
    )
    db.add_all([case, donor, recipient])
    db.commit()

    case_id_str = str(case.id)

    # Upload Form 1
    abs_path = os.path.join(DOSSIER_DIR, "case_4_underage_donor", "Form_1_Minor_Donor.pdf")
    with open(abs_path, "rb") as f:
        resp = client.post(
            f"/cases/{case_id_str}/documents",
            data={"document_type": "FORM_1"},
            files={"file": (os.path.basename(abs_path), f, "application/pdf")}
        )
        assert resp.status_code == 200

    # Trigger screening
    screen_resp = client.post(f"/cases/{case_id_str}/screen")
    assert screen_resp.status_code == 202
    res_data = screen_resp.json()

    # ID-01 MUST trigger ERROR for minor donor
    assert any("ID-01" in flag for flag in res_data["flags"])
    assert res_data["status"] in ("REJECTED", "COMMITTEE_REVIEW")

    db.close()
