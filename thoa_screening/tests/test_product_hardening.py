"""
Additional tests covering gaps identified in the product hardening audit:
- HITL corrections endpoint
- Audit log created during screening
- DAG branching verification (skipped branches)
- OCR extractor with real text content
- Bounding box field locator
- WebSocket manager unit behaviour
"""
import io
import uuid
import pytest

import os
os.environ["THOA_DATABASE_URL"] = "sqlite:///:memory:"

import thoa_screening.worker  # noqa: F401

from fastapi.testclient import TestClient
from thoa_screening.api.main import app
from thoa_screening.database import Base
from thoa_screening.api.deps import get_db
from thoa_screening.database.models import (
    User, Case, Donor, Recipient, AuditLog, AuditAction,
    RelationType, UserRole, CaseStatus
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

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


@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def _make_full_case(relation="SPOUSE") -> str:
    db = TestingSessionLocal()
    user = User(
        email=f"u_{uuid.uuid4().hex[:6]}@test.com",
        full_name="Test",
        role=UserRole.ADMIN,
        password_hash="x"
    )
    db.add(user)
    db.commit()
    case = Case(
        case_number=f"TC-{uuid.uuid4().hex[:6].upper()}",
        relation_type=RelationType[relation],
        hospital_name="Test Hospital",
        organ_type="KIDNEY",
        created_by_id=user.id
    )
    db.add(case)
    db.flush()
    db.add(Donor(
        case_id=case.id, full_name="Donor A", age=30, gender="MALE",
        aadhaar_number_enc=b"111122223333", nationality="INDIAN"
    ))
    db.add(Recipient(
        case_id=case.id, full_name="Recipient B", age=40, gender="FEMALE",
        aadhaar_number_enc=b"444455556666", nationality="INDIAN"
    ))
    db.commit()
    cid = str(case.id)
    db.close()
    return cid


# ================================================================
# 1. HITL Corrections endpoint
# ================================================================

def test_hitl_correction_saves_to_db():
    """POST /cases/{id}/corrections should persist the correction."""
    case_id = _make_full_case()
    payload = {
        "field_name": "aadhaar_number",
        "original_text": "111122223333",
        "corrected_text": "111122229999"
    }
    resp = client.post(f"/cases/{case_id}/corrections", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["field_name"] == "aadhaar_number"
    assert data["corrected_text"] == "111122229999"
    assert "id" in data
    assert "created_at" in data


def test_hitl_correction_404_for_unknown_case():
    resp = client.post(f"/cases/{uuid.uuid4()}/corrections", json={
        "field_name": "full_name",
        "original_text": "Wrong",
        "corrected_text": "Right"
    })
    assert resp.status_code == 404


# ================================================================
# 2. Audit log created on screening
# ================================================================

def test_screening_creates_audit_log():
    """Running screening should create an audit log entry."""
    case_id = _make_full_case()
    # Trigger screening
    client.post(f"/cases/{case_id}/screen")

    db = TestingSessionLocal()
    logs = db.query(AuditLog).filter(
        AuditLog.case_id == uuid.UUID(case_id),
        AuditLog.action == AuditAction.RULES_EVALUATED
    ).all()
    db.close()

    assert len(logs) >= 1, "Expected at least one RULES_EVALUATED audit log after screening"


# ================================================================
# 3. DAG branching — near-relative skips non-relative branches
# ================================================================

from thoa_screening.rules.engine import RuleEngine
from thoa_screening.schemas.case import TransplantCase
from thoa_screening.schemas.documents import DocumentChecklist
from thoa_screening.schemas.enums import Nationality, RelationType as RT
from thoa_screening.schemas.profiles import DonorProfile, RecipientProfile
from thoa_screening.database.models import RuleOutcome
from decimal import Decimal

@pytest.fixture
def engine_inst():
    return RuleEngine()

def _base_donor():
    return {"full_name": "Ravi K", "age": 34, "aadhaar_number": "123456789012",
            "nationality": Nationality.INDIAN, "monthly_income": Decimal("40000")}

def _base_recipient():
    return {"full_name": "Sunita K", "age": 32, "aadhaar_number": "987654321098",
            "nationality": Nationality.INDIAN, "monthly_income": Decimal("40000")}


def test_dag_skips_nonrelative_rules_for_spouse(engine_inst):
    """Near-relative (SPOUSE) must skip REL-04, REL-05, COM-02, COM-03."""
    case = TransplantCase(
        relation_type=RT.SPOUSE,
        donor=DonorProfile(**_base_donor()),
        recipient=RecipientProfile(**_base_recipient()),
        documents=DocumentChecklist(
            has_form_2=True, has_form_4=True,
            identity_proof_submitted=True, medical_report_submitted=True,
            has_financial_affidavit=True
        )
    )
    _, results = engine_inst.evaluate(case)
    should_be_skipped = ["REL-04", "REL-05", "COM-02", "COM-03"]
    for code in should_be_skipped:
        result = next((r for r in results if r["rule_code"] == code), None)
        if result:
            assert result["result"] == RuleOutcome.SKIPPED, (
                f"Rule {code} should be SKIPPED for SPOUSE but was {result['result']}"
            )


def test_dag_skips_near_relative_rules_for_nonrelative(engine_inst):
    """Non-relative case must skip REL-01, REL-02, REL-03 (near-rel branches)."""
    case = TransplantCase(
        relation_type=RT.NON_RELATIVE,
        donor=DonorProfile(**_base_donor()),
        recipient=RecipientProfile(**_base_recipient()),
        documents=DocumentChecklist(
            has_form_3=True, has_form_11=True, has_form_4=True,
            has_financial_affidavit=True, police_verification=True,
            identity_proof_submitted=True, medical_report_submitted=True,
        )
    )
    _, results = engine_inst.evaluate(case)
    for code in ["REL-01", "REL-02", "REL-03"]:
        result = next((r for r in results if r["rule_code"] == code), None)
        if result:
            assert result["result"] == RuleOutcome.SKIPPED, (
                f"Rule {code} should be SKIPPED for NON_RELATIVE but was {result['result']}"
            )


# ================================================================
# 4. OCR regex extractor with real text
# ================================================================

from thoa_screening.ocr.extractor import extract_fields

def test_ocr_extract_aadhaar_from_text():
    text = "Patient Aadhaar: 1234 5678 9012 DOB: 15/08/1995"
    result = extract_fields(text)
    assert result["aadhaar_number"]["value"] == "123456789012"
    assert result["aadhaar_number"]["confidence"] == 95.0


def test_ocr_extract_dob_from_text():
    text = "Date of Birth: 01/05/1980 PAN: ABCDE1234F"
    result = extract_fields(text)
    assert result["dob"]["value"] == "1980-05-01"
    assert result["pan_number"]["value"] == "ABCDE1234F"


def test_ocr_extract_pan_from_text():
    text = "PAN Card: ZXYWV9876A issued in 2010"
    result = extract_fields(text)
    assert result["pan_number"]["value"] == "ZXYWV9876A"


# ================================================================
# 5. Pipeline bounding box locator
# ================================================================

from thoa_screening.ocr.pipeline import _locate_fields_in_words

def test_bounding_box_locator_finds_aadhaar():
    """_locate_fields_in_words should return correct normalised bbox for aadhaar."""
    extracted = {
        "aadhaar_number": {"value": "123456789012", "confidence": 95.0}
    }
    word_data = [
        {"text": "Name:", "left": 10, "top": 10, "width": 50, "height": 20, "conf": 90.0},
        {"text": "123456789012", "left": 70, "top": 50, "width": 100, "height": 20, "conf": 95.0},
    ]
    boxes = _locate_fields_in_words(extracted, word_data, page_width=400, page_height=300)
    assert boxes["aadhaar_number"] is not None
    bbox = boxes["aadhaar_number"]
    assert bbox["x"] == round(70 / 400, 4)
    assert bbox["y"] == round(50 / 300, 4)
    assert bbox["w"] == round(100 / 400, 4)


def test_bounding_box_locator_returns_none_if_not_found():
    extracted = {
        "pan_number": {"value": "ABCDE1234F", "confidence": 90.0}
    }
    word_data = [
        {"text": "Hello", "left": 0, "top": 0, "width": 50, "height": 20, "conf": 80.0},
    ]
    boxes = _locate_fields_in_words(extracted, word_data, 500, 400)
    assert boxes["pan_number"] is None
