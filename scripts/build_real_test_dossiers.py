"""
Build Real Test Dossiers from Official Government THOA Form PDFs.

Takes the statutory forms downloaded from the Delhi Government / NOTTO portal
and populates them with realistic, high-fidelity patient and clinical data
for automated end-to-end pipeline testing.
"""
import os
import fitz  # PyMuPDF

REAL_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "real_thoa_documents")
OUT_DIR = os.path.join(REAL_DOCS_DIR, "test_dossiers")

os.makedirs(OUT_DIR, exist_ok=True)

def fill_form_1(donor_name: str, donor_dob: str, donor_aadhaar: str, donor_pan: str, 
                recipient_name: str, recipient_dob: str, relation: str, organ: str, out_path: str):
    """Fill statutory Form 1 (Living Near-Relative Consent)."""
    src_path = os.path.join(REAL_DOCS_DIR, "Form_1_Near_Relative.pdf")
    doc = fitz.open(src_path)
    page = doc[0]

    stamps = [
        ("My full name (proposed donor) is", donor_name, 200),
        ("Date of birth", f"  {donor_dob}  ", 120),
        ("Permanent Account Number (PAN)", f"  {donor_pan}  ", 150),
        ("AADHAAR No.", f"  {donor_aadhaar}  ", 160),
        ("consent to donate my", f" {organ} ", 100),
        ("to my relative", f" {relation} ", 80),
        ("whose particulars are as follows and name is", f" {recipient_name} ", 180),
        ("and who was born on", f" {recipient_dob} ", 100),
        ("Signature of the prospective donor", f" {donor_name} ", 140)
    ]

    for label, val, width in stamps:
        rects = page.search_for(label)
        if rects:
            r = rects[0]
            # White out the dotted line
            box = fitz.Rect(r.x1 + 2, r.y0 - 2, r.x1 + width, r.y1 + 4)
            page.draw_rect(box, color=(1, 1, 1), fill=(1, 1, 1))
            page.insert_text(fitz.Point(r.x1 + 6, r.y1), val, fontsize=9.5, color=(0, 0, 0.6))

    doc.save(out_path)
    doc.close()
    print(f"Generated: {out_path}")

def fill_form_2(donor_name: str, donor_dob: str, donor_aadhaar: str, recipient_name: str, organ: str, out_path: str):
    """Fill statutory Form 2 (Living Spousal Consent)."""
    src_path = os.path.join(REAL_DOCS_DIR, "Form_2_Spousal.pdf")
    doc = fitz.open(src_path)
    page = doc[0]

    stamps = [
        ("My full name (proposed donor) is", donor_name, 200),
        ("Date of birth", f"  {donor_dob}  ", 120),
        ("AADHAAR No.", f"  {donor_aadhaar}  ", 160),
        ("consent to donate my", f" {organ} ", 100),
        ("Signature of the prospective donor", f" {donor_name} ", 140)
    ]

    for label, val, width in stamps:
        rects = page.search_for(label)
        if rects:
            r = rects[0]
            box = fitz.Rect(r.x1 + 2, r.y0 - 2, r.x1 + width, r.y1 + 4)
            page.draw_rect(box, color=(1, 1, 1), fill=(1, 1, 1))
            page.insert_text(fitz.Point(r.x1 + 6, r.y1), val, fontsize=9.5, color=(0, 0, 0.6))

    doc.save(out_path)
    doc.close()
    print(f"Generated: {out_path}")

def fill_form_3(donor_name: str, donor_dob: str, recipient_name: str, reason: str, organ: str, out_path: str):
    """Fill statutory Form 3 (Non-Near Relative Consent)."""
    src_path = os.path.join(REAL_DOCS_DIR, "Form_3_Non_Relative.pdf")
    doc = fitz.open(src_path)
    page = doc[0]

    stamps = [
        ("My full name is", donor_name, 220),
        ("Date of birth", f"  {donor_dob}  ", 120),
        ("consent to donate my", f" {organ} ", 100),
    ]

    for label, val, width in stamps:
        rects = page.search_for(label)
        if rects:
            r = rects[0]
            box = fitz.Rect(r.x1 + 2, r.y0 - 2, r.x1 + width, r.y1 + 4)
            page.draw_rect(box, color=(1, 1, 1), fill=(1, 1, 1))
            page.insert_text(fitz.Point(r.x1 + 6, r.y1), val, fontsize=9.5, color=(0, 0, 0.6))

    doc.save(out_path)
    doc.close()
    print(f"Generated: {out_path}")

def fill_form_4(doctor_name: str, hospital_name: str, donor_name: str, recipient_name: str, organ: str, out_path: str):
    """Fill statutory Form 4 (Medical Fitness Certification)."""
    src_path = os.path.join(REAL_DOCS_DIR, "Form_4_Medical_Fitness.pdf")
    doc = fitz.open(src_path)
    page = doc[0]

    stamps = [
        ("I, Dr", f" {doctor_name}, MBBS, MD, {hospital_name} ", 260),
        ("certify that I have examined Shri / Smt. / Km", f" {donor_name} ", 180),
        ("is fit to donate his / her", f" {organ} ", 100),
        ("to Shri / Smt.", f" {recipient_name} ", 180),
    ]

    for label, val, width in stamps:
        rects = page.search_for(label)
        if rects:
            r = rects[0]
            box = fitz.Rect(r.x1 + 2, r.y0 - 2, r.x1 + width, r.y1 + 4)
            page.draw_rect(box, color=(1, 1, 1), fill=(1, 1, 1))
            page.insert_text(fitz.Point(r.x1 + 6, r.y1), val, fontsize=9.5, color=(0, 0, 0.6))

    doc.save(out_path)
    doc.close()
    print(f"Generated: {out_path}")

def fill_form_11(donor_name: str, donor_age: int, recipient_name: str, recipient_age: int, 
                 hospital_name: str, organ: str, relation_desc: str, out_path: str):
    """Fill statutory Form 11 (Joint Application for Approval of Transplantation)."""
    src_path = os.path.join(REAL_DOCS_DIR, "Form_11_Joint_Application.pdf")
    doc = fitz.open(src_path)
    page = doc[0]

    stamps = [
        ("Whereas I", f" {recipient_name} ", 140),
        ("aged", f" {recipient_age} ", 50),
        ("benefited by transplantation of", f" {organ} ", 100),
        ("And whereas I", f" {donor_name} ", 140),
        ("by virtue of being a near relative i.e.", f" {relation_desc} ", 150),
        ("like to donate my (name of the organ)", f" {organ} ", 80),
        ("Signature of the Prospective Donor", f" {donor_name} ", 120),
        ("Signature of Prospective Recipient", f" {recipient_name} ", 120),
    ]

    for label, val, width in stamps:
        rects = page.search_for(label)
        if rects:
            r = rects[0]
            box = fitz.Rect(r.x1 + 2, r.y0 - 2, r.x1 + width, r.y1 + 4)
            page.draw_rect(box, color=(1, 1, 1), fill=(1, 1, 1))
            page.insert_text(fitz.Point(r.x1 + 6, r.y1), val, fontsize=9.5, color=(0, 0, 0.6))

    doc.save(out_path)
    doc.close()
    print(f"Generated: {out_path}")

def generate_all():
    print("Building realistic test dossiers from official government forms...")
    
    # 1. Dossier A: Near-Relative (Sister donating Kidney to Brother at AIIMS Delhi)
    dossier_a = os.path.join(OUT_DIR, "case_1_near_relative")
    os.makedirs(dossier_a, exist_ok=True)
    fill_form_1(
        donor_name="Sunita Sharma", donor_dob="15/08/1988", donor_aadhaar="5432 9876 1234", donor_pan="ABCPS1234F",
        recipient_name="Rahul Sharma", recipient_dob="10/04/1982", relation="sister", organ="Kidney",
        out_path=os.path.join(dossier_a, "Form_1_Consent_Donor.pdf")
    )
    fill_form_4(
        doctor_name="Dr. Ananya Roy", hospital_name="AIIMS New Delhi",
        donor_name="Sunita Sharma", recipient_name="Rahul Sharma", organ="Kidney",
        out_path=os.path.join(dossier_a, "Form_4_Medical_Fitness.pdf")
    )
    fill_form_11(
        donor_name="Sunita Sharma", donor_age=36, recipient_name="Rahul Sharma", recipient_age=42,
        hospital_name="AIIMS New Delhi", organ="Kidney", relation_desc="Sister (Near Relative)",
        out_path=os.path.join(dossier_a, "Form_11_Joint_Application.pdf")
    )

    # 2. Dossier B: Spousal Living Donor (Wife donating Liver to Husband at Apollo Chennai)
    dossier_b = os.path.join(OUT_DIR, "case_2_spousal")
    os.makedirs(dossier_b, exist_ok=True)
    fill_form_2(
        donor_name="Priya Verma", donor_dob="22/11/1986", donor_aadhaar="7712 3456 9012",
        recipient_name="Amit Verma", organ="Liver",
        out_path=os.path.join(dossier_b, "Form_2_Spousal_Consent.pdf")
    )
    fill_form_4(
        doctor_name="Dr. K. Venkataraman", hospital_name="Apollo Hospitals Chennai",
        donor_name="Priya Verma", recipient_name="Amit Verma", organ="Liver",
        out_path=os.path.join(dossier_b, "Form_4_Medical_Fitness.pdf")
    )
    fill_form_11(
        donor_name="Priya Verma", donor_age=38, recipient_name="Amit Verma", recipient_age=41,
        hospital_name="Apollo Chennai", organ="Liver", relation_desc="Spouse (Wife)",
        out_path=os.path.join(dossier_b, "Form_11_Joint_Application.pdf")
    )

    # 3. Dossier C: Non-Near Relative / Unrelated Donor (Altruistic Friend at Sir Ganga Ram Hospital)
    dossier_c = os.path.join(OUT_DIR, "case_3_non_relative")
    os.makedirs(dossier_c, exist_ok=True)
    fill_form_3(
        donor_name="Vikram Malhotra", donor_dob="18/06/1995",
        recipient_name="Suresh Gupta", reason="Close family friendship of 15 years", organ="Kidney",
        out_path=os.path.join(dossier_c, "Form_3_Non_Relative_Consent.pdf")
    )
    fill_form_4(
        doctor_name="Dr. Rajiv Mehta", hospital_name="Sir Ganga Ram Hospital",
        donor_name="Vikram Malhotra", recipient_name="Suresh Gupta", organ="Kidney",
        out_path=os.path.join(dossier_c, "Form_4_Medical_Fitness.pdf")
    )
    fill_form_11(
        donor_name="Vikram Malhotra", donor_age=29, recipient_name="Suresh Gupta", recipient_age=52,
        hospital_name="Sir Ganga Ram Hospital", organ="Kidney", relation_desc="Friend (Other than near relative)",
        out_path=os.path.join(dossier_c, "Form_11_Joint_Application.pdf")
    )

    # 4. Dossier D: Underage Minor Donor (< 18 years old) — Red Flag Test
    dossier_d = os.path.join(OUT_DIR, "case_4_underage_donor")
    os.makedirs(dossier_d, exist_ok=True)
    fill_form_1(
        donor_name="Ankit Patel", donor_dob="10/01/2008", donor_aadhaar="1234 5678 9900", donor_pan="PATEL1234F",
        recipient_name="Rajesh Patel", recipient_dob="05/03/1976", relation="son", organ="Kidney",
        out_path=os.path.join(dossier_d, "Form_1_Minor_Donor.pdf")
    )

    print("All real test dossiers successfully generated!")

if __name__ == "__main__":
    generate_all()
