import pytest
import uuid
import os

os.environ["THOA_DATABASE_URL"] = "sqlite:///:memory:"

from thoa_screening.database.models import Case, AuditLog, AuditAction, User, UserRole, RelationType
from thoa_screening.api.main import app
from thoa_screening.api.deps import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# DB Setup
engine = create_engine("sqlite:///file:memdb2?mode=memory&cache=shared", connect_args={"check_same_thread": False})
from thoa_screening.database import Base
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

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def test_case_id(db_session):
    user = User(email=f"audit_{uuid.uuid4()}@test.com", full_name="Admin", role=UserRole.ADMIN, password_hash="hash")
    db_session.add(user)
    db_session.commit()
    
    case = Case(
        case_number=f"AUDIT-TEST-{uuid.uuid4().hex[:8]}",
        relation_type=RelationType.NON_RELATIVE,
        hospital_name="Audit Hospital",
        organ_type="Liver",
        created_by_id=user.id
    )
    db_session.add(case)
    db_session.commit()
    return str(case.id)

def test_audit_immutability(db_session, test_case_id):
    # Create an audit log
    log = AuditLog(
        case_id=uuid.UUID(test_case_id),
        user_id=db_session.query(User).first().id,
        action=AuditAction.CASE_CREATED,
        detail={"status": "SUCCESS"},
        ip_address="127.0.0.1"
    )
    db_session.add(log)
    db_session.commit()
    
    # Attempt to update it
    log.detail = {"status": "TAMPERED"}
    with pytest.raises(NotImplementedError) as exc_info:
        db_session.commit()
    assert "strictly immutable and cannot be updated" in str(exc_info.value)
    
    db_session.rollback() # clear the failed transaction
    
    # Attempt to delete it
    db_session.delete(log)
    with pytest.raises(NotImplementedError) as exc_info:
        db_session.commit()
    assert "strictly immutable and cannot be deleted" in str(exc_info.value)
    
    db_session.rollback()

def test_audit_decorator_and_endpoint(test_case_id):
    import io
    file_content = b"fake document"
    file = io.BytesIO(file_content)
    
    # Trigger an action that is decorated (upload document)
    res = client.post(
        f"/cases/{test_case_id}/documents",
        data={"document_type": "FORM_3"},
        files={"file": ("test.pdf", file, "application/pdf")}
    )
    assert res.status_code == 200
    
    # Fetch audit logs using the new endpoint
    audit_res = client.get(f"/cases/{test_case_id}/audit")
    assert audit_res.status_code == 200
    
    logs = audit_res.json()
    assert len(logs) > 0
    # The first item should be our upload action (descending order)
    upload_log = logs[0]
    assert upload_log["action"] == "DOCUMENT_UPLOADED"
    assert upload_log["detail"]["status"] == "SUCCESS"
    assert upload_log["case_id"] == test_case_id
