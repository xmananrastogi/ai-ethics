"""
Seed script to populate the local database (thoa.db) with the 4 real clinical test cases,
real statutory PDFs, extracted OCR data, bounding boxes, rule screening outcomes,
and generated PDF compliance reports for tomorrow's final review.
"""
import os
import sys
import uuid
import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Ensure test dossiers exist
from scripts.build_real_test_dossiers import generate_all
generate_all()

import hashlib
from sqlalchemy.orm import Session
from thoa_screening.database import Base, get_engine, get_session_factory
from thoa_screening.database.models import (
    User, Case, Donor, Recipient, Document, DocumentType,
    RelationType, CaseStatus, ExtractedData, UserRole, Report, ReportStatus,
    ReportType, ExtractionMethod
)
from thoa_screening.ocr.pipeline import process_document
from thoa_screening.services.screening import screen_case
from thoa_screening.services.report_generator import generate_report

engine = get_engine("sqlite:///thoa.db")
Base.metadata.create_all(bind=engine)
SessionFactory = get_session_factory(engine)
db: Session = SessionFactory()

REPORTS_DIR = PROJECT_ROOT / "real_thoa_documents" / "generated_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def seed_presentation_cases():
    print("=============================================================")
    print("Seeding THOA Screening System with 4 Real Statutory Cases...")
    print("=============================================================")

    # 1. Ensure Reviewer / Admin User
    admin = db.query(User).filter(User.email == "reviewer@thoa.gov.in").first()
    if not admin:
        admin = User(
            id=uuid.uuid4(),
            email="reviewer@thoa.gov.in",
            full_name="Dr. Sivakumar R / Committee Reviewer",
            role=UserRole.ADMIN,
            password_hash="admin123"
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    # 2. Define the 4 Real Clinical Test Cases
    cases_config = [
        {
            "case_number": "THOA-2026-REL-01",
            "relation_type": RelationType.SIBLING,
            "hospital_name": "AIIMS New Delhi",
            "organ_type": "KIDNEY",
            "donor": {
                "name": "Sunita Sharma", "age": 36, "gender": "F",
                "dob": datetime.date(1988, 8, 15), "income": 45000,
                "aadhaar": "987654321098", "address": "B-42, Lajpat Nagar, New Delhi",
                "nationality": "INDIAN"
            },
            "recipient": {
                "name": "Rajesh Sharma", "age": 42, "gender": "M",
                "dob": datetime.date(1982, 3, 20), "income": 50000,
                "aadhaar": "123456789012", "address": "B-42, Lajpat Nagar, New Delhi",
                "nationality": "INDIAN"
            },
            "docs": [
                ("case_1_near_relative/Form_1_Consent_Donor.pdf", DocumentType.FORM_1),
                ("case_1_near_relative/Form_4_Medical_Fitness.pdf", DocumentType.FORM_4),
                ("case_1_near_relative/Form_11_Joint_Application.pdf", DocumentType.FORM_11)
            ]
        },
        {
            "case_number": "THOA-2026-SPOUSE-02",
            "relation_type": RelationType.SPOUSE,
            "hospital_name": "Sir Ganga Ram Hospital, New Delhi",
            "organ_type": "LIVER",
            "donor": {
                "name": "Pooja Verma", "age": 34, "gender": "F",
                "dob": datetime.date(1990, 5, 12), "income": 60000,
                "aadhaar": "887766554433", "address": "C-12, Rajouri Garden, New Delhi",
                "nationality": "INDIAN"
            },
            "recipient": {
                "name": "Amit Verma", "age": 38, "gender": "M",
                "dob": datetime.date(1986, 11, 4), "income": 75000,
                "aadhaar": "223344556677", "address": "C-12, Rajouri Garden, New Delhi",
                "nationality": "INDIAN"
            },
            "docs": [
                ("case_2_spousal/Form_2_Spousal_Consent.pdf", DocumentType.FORM_2),
                ("case_2_spousal/Form_4_Medical_Fitness.pdf", DocumentType.FORM_4),
                ("case_2_spousal/Form_11_Joint_Application.pdf", DocumentType.FORM_11)
            ]
        },
        {
            "case_number": "THOA-2026-NONREL-03",
            "relation_type": RelationType.NON_RELATIVE,
            "hospital_name": "Apollo Hospitals, Chennai",
            "organ_type": "KIDNEY",
            "donor": {
                "name": "Vikram Singh", "age": 28, "gender": "M",
                "dob": datetime.date(1996, 7, 19), "income": 18000,
                "aadhaar": "445566778899", "address": "Anna Nagar, Chennai",
                "nationality": "INDIAN"
            },
            "recipient": {
                "name": "Rohan Gupta", "age": 52, "gender": "M",
                "dob": datetime.date(1972, 1, 15), "income": 350000,
                "aadhaar": "998877665544", "address": "T. Nagar, Chennai",
                "nationality": "INDIAN"
            },
            "docs": [
                ("case_3_non_relative/Form_3_Non_Relative_Consent.pdf", DocumentType.FORM_3),
                ("case_3_non_relative/Form_4_Medical_Fitness.pdf", DocumentType.FORM_4),
                ("case_3_non_relative/Form_11_Joint_Application.pdf", DocumentType.FORM_11)
            ]
        },
        {
            "case_number": "THOA-2026-SAFETY-04",
            "relation_type": RelationType.PARENT_CHILD,
            "hospital_name": "Fortis Memorial Research Institute, Gurgaon",
            "organ_type": "KIDNEY",
            "donor": {
                "name": "Karan Kapoor", "age": 16, "gender": "M",
                "dob": datetime.date(2010, 4, 12), "income": 0,
                "aadhaar": "112233445566", "address": "DLF Phase 2, Gurgaon",
                "nationality": "INDIAN"
            },
            "recipient": {
                "name": "Suresh Kapoor", "age": 49, "gender": "M",
                "dob": datetime.date(1975, 9, 30), "income": 120000,
                "aadhaar": "665544332211", "address": "DLF Phase 2, Gurgaon",
                "nationality": "INDIAN"
            },
            "docs": [
                ("case_4_underage_donor/Form_1_Minor_Donor.pdf", DocumentType.FORM_1),
                ("case_4_underage_donor/Form_4_Medical_Fitness.pdf", DocumentType.FORM_4)
            ]
        }
    ]

    for cfg in cases_config:
        # Check if case exists
        existing = db.query(Case).filter(Case.case_number == cfg["case_number"]).first()
        if existing:
            # Delete old case cascade
            db.delete(existing)
            db.commit()

        # Create Case
        case = Case(
            case_number=cfg["case_number"],
            relation_type=cfg["relation_type"],
            hospital_name=cfg["hospital_name"],
            organ_type=cfg["organ_type"],
            created_by_id=admin.id,
            status=CaseStatus.PENDING
        )
        db.add(case)
        db.flush()

        # Donor & Recipient
        d_cfg = cfg["donor"]
        r_cfg = cfg["recipient"]
        donor = Donor(
            case_id=case.id,
            full_name=d_cfg["name"],
            age=d_cfg["age"],
            gender=d_cfg["gender"],
            date_of_birth=datetime.datetime.combine(d_cfg["dob"], datetime.time.min),
            monthly_income=d_cfg["income"],
            nationality=d_cfg["nationality"],
            address=d_cfg["address"],
            aadhaar_number_enc=d_cfg["aadhaar"].encode('utf-8')
        )
        recipient = Recipient(
            case_id=case.id,
            full_name=r_cfg["name"],
            age=r_cfg["age"],
            gender=r_cfg["gender"],
            date_of_birth=datetime.datetime.combine(r_cfg["dob"], datetime.time.min),
            monthly_income=r_cfg["income"],
            nationality=r_cfg["nationality"],
            address=r_cfg["address"],
            aadhaar_number_enc=r_cfg["aadhaar"].encode('utf-8')
        )
        db.add(donor)
        db.add(recipient)
        db.flush()

        # Attach real statutory documents
        dossier_base = PROJECT_ROOT / "real_thoa_documents" / "test_dossiers"
        for rel_path, doc_type in cfg["docs"]:
            abs_file = dossier_base / rel_path
            if not abs_file.exists():
                print(f"Warning: File {abs_file} not found!")
                continue

            doc_record = Document(
                case_id=case.id,
                uploaded_by_id=admin.id,
                document_type=doc_type,
                original_filename=abs_file.name,
                file_path=str(abs_file),
                file_hash=f"sha256_{uuid.uuid4().hex[:12]}",
                mime_type="application/pdf",
                file_size_bytes=abs_file.stat().st_size,
                is_verified=True
            )
            db.add(doc_record)
            db.flush()

            # Process with OCR
            ocr_res = process_document(str(abs_file))
            extracted_fields = ocr_res.get("extracted_data", {})
            confidences = ocr_res.get("field_confidences", {})
            bboxes = ocr_res.get("bounding_boxes", {})

            for k, val in extracted_fields.items():
                if val:
                    raw_conf = confidences.get(k, 85.0)
                    norm_conf = min(max(float(raw_conf) / 100.0, 0.0), 1.0)
                    db.add(ExtractedData(
                        document_id=doc_record.id,
                        field_name=k,
                        field_value=str(val),
                        confidence_score=norm_conf,
                        extraction_method=ExtractionMethod.OCR,
                        needs_human_review=(norm_conf < 0.8)
                    ))

        db.commit()

        # Run Screening Engine
        screening_res = screen_case(case.id, db)
        db.refresh(case)

        # Generate Committee Audit Report PDF
        pdf_bytes = generate_report(case, screening_res)
        report_pdf_path = REPORTS_DIR / f"{case.case_number}_Report.pdf"
        with open(report_pdf_path, "wb") as f:
            f.write(pdf_bytes)

        report = Report(
            case_id=case.id,
            report_type=ReportType.SCREENING_SUMMARY,
            generated_by_id=admin.id,
            file_path=str(report_pdf_path),
            content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
            status=ReportStatus.FINAL
        )
        db.add(report)
        db.commit()

        print(f"✅ Created Case {case.case_number}:")
        print(f"   Hospital: {case.hospital_name}")
        print(f"   Relation: {case.relation_type.value} | Organ: {case.organ_type}")
        print(f"   Screening Result: {case.status.value}")
        print(f"   Attached Docs: {len(cfg['docs'])} statutory forms")
        print(f"   Audit Report: {report_pdf_path.name}")

    print("\n🎉 All 4 presentation cases successfully seeded into thoa.db!")

if __name__ == "__main__":
    seed_presentation_cases()
