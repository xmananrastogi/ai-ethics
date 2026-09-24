import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from thoa_screening.api.deps import SessionFactory, engine
from thoa_screening.database import Base
from thoa_screening.database.models import User, Case, Donor, Recipient, CaseStatus, RelationType
import uuid
import datetime

def populate():
    # 1. Create tables
    Base.metadata.create_all(bind=engine)
    db = SessionFactory()

    # 2. Add System Admin
    dummy_user = db.query(User).filter(User.email == "admin@thoa.gov.in").first()
    if not dummy_user:
        dummy_user = User(email="admin@thoa.gov.in", full_name="System Admin", role="ADMIN", password_hash="dummy")
        db.add(dummy_user)
        db.commit()
        db.refresh(dummy_user)

    # 3. Create Case 1: Spouse (Clean)
    case1_id = uuid.uuid4()
    case1 = Case(
        id=case1_id,
        case_number=f"THOA-{case1_id.hex[:6].upper()}",
        relation_type=RelationType.SPOUSE,
        hospital_name="AIIMS Delhi",
        organ_type="KIDNEY",
        status=CaseStatus.PENDING,
        created_by_id=dummy_user.id
    )
    donor1 = Donor(
        case_id=case1.id, full_name="Rahul Sharma", age=45, gender="M",
        aadhaar_number_enc=b"encrypted_aadhaar_1", address="New Delhi"
    )
    recipient1 = Recipient(
        case_id=case1.id, full_name="Priya Sharma", age=42, gender="F",
        aadhaar_number_enc=b"encrypted_aadhaar_2", address="New Delhi"
    )

    # 4. Create Case 2: Non-Relative (Flagged)
    case2_id = uuid.uuid4()
    case2 = Case(
        id=case2_id,
        case_number=f"THOA-{case2_id.hex[:6].upper()}",
        relation_type=RelationType.NON_RELATIVE,
        hospital_name="Apollo Chennai",
        organ_type="LIVER",
        status=CaseStatus.COMMITTEE_REVIEW,
        created_by_id=dummy_user.id,
        created_at=datetime.datetime.now() - datetime.timedelta(days=1)
    )
    donor2 = Donor(
        case_id=case2.id, full_name="Vikram Singh", age=29, gender="M",
        aadhaar_number_enc=b"encrypted_aadhaar_3", address="Chennai"
    )
    recipient2 = Recipient(
        case_id=case2.id, full_name="Arun Kumar", age=55, gender="M",
        aadhaar_number_enc=b"encrypted_aadhaar_4", address="Mumbai"
    )

    db.add_all([case1, donor1, recipient1, case2, donor2, recipient2])
    db.commit()
    
    print("Database successfully populated with synthetic cases for the presentation!")
    print(f"Case 1: {case1.case_number} (Spouse)")
    print(f"Case 2: {case2.case_number} (Non-Relative)")

if __name__ == "__main__":
    populate()
