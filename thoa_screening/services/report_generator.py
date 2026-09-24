import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from thoa_screening.database.models import Case, Document, DocumentType, RelationType, RuleOutcome

def _mask_aadhaar(aadhaar: str) -> str:
    """Masks Aadhaar to show only the last 4 digits."""
    if not aadhaar:
        return "Not Provided"
    aadhaar_clean = ''.join(filter(str.isdigit, aadhaar))
    if len(aadhaar_clean) == 12:
        return f"XXXX-XXXX-{aadhaar_clean[-4:]}"
    return "INVALID FORMAT"

class FooterCanvas(object):
    """Canvas to add an audit trail footer to every page."""
    def __init__(self, canvas, doc, timestamp: str):
        self.canvas = canvas
        self.doc = doc
        self.timestamp = timestamp
        
    def draw_footer(self):
        self.canvas.saveState()
        self.canvas.setFont('Helvetica', 8)
        self.canvas.setStrokeColor(colors.lightgrey)
        self.canvas.line(30, 40, A4[0] - 30, 40)
        
        footer_text = f"THOA Automated Screening System (v0.1.0) | Screened at: {self.timestamp}"
        self.canvas.drawString(30, 25, footer_text)
        
        page_num = f"Page {self.doc.page}"
        self.canvas.drawRightString(A4[0] - 30, 25, page_num)
        
        self.canvas.restoreState()

def _add_page_info(canvas, doc, timestamp):
    footer = FooterCanvas(canvas, doc, timestamp)
    footer.draw_footer()

def generate_report(case: Case, screening_result: dict) -> bytes:
    """
    Generates a PDF compliance report for the Authorization Committee.
    """
    buffer = io.BytesIO()
    from datetime import UTC
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=50,
        bottomMargin=60
    )
    
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading1_style = styles['Heading1']
    heading2_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Custom styles
    danger_style = ParagraphStyle(
        'Danger', parent=normal_style, textColor=colors.red, fontName='Helvetica-Bold'
    )
    warning_style = ParagraphStyle(
        'Warning', parent=normal_style, textColor=colors.orange, fontName='Helvetica-Bold'
    )
    success_style = ParagraphStyle(
        'Success', parent=normal_style, textColor=colors.green, fontName='Helvetica-Bold'
    )
    
    elements = []
    
    # ---------------------------------------------------------
    # 1. Cover Page / Header
    # ---------------------------------------------------------
    elements.append(Paragraph("THOA Authorization Committee", title_style))
    elements.append(Paragraph("Automated Compliance Screening Report", styles['Heading2']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(f"<b>Case ID:</b> {case.case_number}", normal_style))
    elements.append(Paragraph(f"<b>Date Generated:</b> {timestamp}", normal_style))
    elements.append(Paragraph(f"<b>Hospital:</b> {case.hospital_name}", normal_style))
    elements.append(Paragraph(f"<b>Organ Type:</b> {case.organ_type.replace('_', ' ').title() if case.organ_type else 'N/A'}", normal_style))
    elements.append(Paragraph(f"<b>Relation:</b> {case.relation_type.value.replace('_', ' ').title() if case.relation_type else 'N/A'}", normal_style))
    
    elements.append(Spacer(1, 30))
    
    # Overall Recommendation Box
    rec_status = screening_result.get("status", "PENDING_COMMITTEE_REVIEW")
    if rec_status == "REJECTED":
        rec_text = "RECOMMENDATION: REJECT (Documentation Critically Incomplete)"
        rec_style = danger_style
    elif rec_status == "APPROVED":
        rec_text = "RECOMMENDATION: READY FOR REVIEW (No Anomalies Detected)"
        rec_style = success_style
    else:
        rec_text = "RECOMMENDATION: PENDING COMMITTEE REVIEW (Anomalies Flagged)"
        rec_style = warning_style
        
    elements.append(Paragraph(rec_text, rec_style))
    elements.append(Spacer(1, 20))
    
    # ---------------------------------------------------------
    # 2. Donor/Recipient Summary
    # ---------------------------------------------------------
    elements.append(Paragraph("Demographics", heading1_style))
    
    donor = case.donor
    recipient = case.recipient
    
    d_name = donor.full_name if donor else "N/A"
    d_age = str(donor.age) if donor and donor.age else "N/A"
    d_aadhaar = _mask_aadhaar(donor.aadhaar_number_enc.decode('utf-8') if donor and donor.aadhaar_number_enc else "") if donor else "N/A"
    
    r_name = recipient.full_name if recipient else "N/A"
    r_age = str(recipient.age) if recipient and recipient.age else "N/A"
    r_aadhaar = _mask_aadhaar(recipient.aadhaar_number_enc.decode('utf-8') if recipient and recipient.aadhaar_number_enc else "") if recipient else "N/A"
    
    demo_data = [
        ["Field", "Donor", "Recipient"],
        ["Name", d_name, r_name],
        ["Age", d_age, r_age],
        ["Aadhaar", d_aadhaar, r_aadhaar]
    ]
    
    demo_table = Table(demo_data, colWidths=[100, 200, 200])
    demo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 6)
    ]))
    
    elements.append(demo_table)
    elements.append(Spacer(1, 30))
    
    # ---------------------------------------------------------
    # 3. Document Inventory Table
    # ---------------------------------------------------------
    elements.append(Paragraph("Document Inventory", heading1_style))
    
    # Determine expected docs based on relation type
    expected_docs = [DocumentType.FORM_1, DocumentType.FORM_2, DocumentType.FORM_3]
    if case.relation_type == RelationType.NON_RELATIVE:
        expected_docs.append(DocumentType.FORM_11)
        expected_docs.append(DocumentType.FINANCIAL_AFFIDAVIT)
        
    actual_docs = {doc.document_type for doc in case.documents}
    
    doc_data = [["Document Type", "Status"]]
    for doc_type in expected_docs:
        if doc_type in actual_docs:
            status = "PRESENT"
        else:
            status = "MISSING"
        doc_data.append([doc_type.name.replace('_', ' '), status])
        
    doc_table = Table(doc_data, colWidths=[300, 200])
    # Highlight missing docs in red
    doc_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]
    for i, row in enumerate(doc_data):
        if row[1] == "MISSING":
            doc_style.append(('TEXTCOLOR', (1, i), (1, i), colors.red))
            doc_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))
        elif row[1] == "PRESENT":
            doc_style.append(('TEXTCOLOR', (1, i), (1, i), colors.green))
            
    doc_table.setStyle(TableStyle(doc_style))
    elements.append(doc_table)
    
    elements.append(Spacer(1, 30))
    
    # ---------------------------------------------------------
    # 4. Anomalies / Flags Section
    # ---------------------------------------------------------
    elements.append(Paragraph("Compliance Anomalies & Flags", heading1_style))
    
    explanations = screening_result.get("explanations", [])
    
    if not explanations:
        elements.append(Paragraph("No anomalies were detected by the system.", success_style))
    else:
        elements.append(Paragraph("The system has flagged the following issues that require committee attention:", normal_style))
        elements.append(Spacer(1, 10))
        
        flag_data = [["Rule", "Description & Evidence", "Severity"]]
        
        for exp in explanations:
            # Wrap text in Paragraphs to handle wrapping in table cells
            desc = Paragraph(f"<b>{exp['rule_description']}</b><br/>Evidence: {exp['evidence']}<br/><font color='blue'>Recommendation: {exp['next_step']}</font>", normal_style)
            severity = "CRITICAL" if exp['needs_legal_verification'] else "WARNING"
            flag_data.append([exp['rule_code'], desc, severity])
            
        flag_table = Table(flag_data, colWidths=[100, 320, 80])
        f_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]
        
        for i, row in enumerate(flag_data):
            if row[2] == "CRITICAL":
                f_style.append(('TEXTCOLOR', (2, i), (2, i), colors.red))
                f_style.append(('FONTNAME', (2, i), (2, i), 'Helvetica-Bold'))
            elif row[2] == "WARNING":
                f_style.append(('TEXTCOLOR', (2, i), (2, i), colors.orange))
                
        flag_table.setStyle(TableStyle(f_style))
        elements.append(flag_table)
    
    # Build PDF
    doc.build(
        elements, 
        onFirstPage=lambda canvas, doc: _add_page_info(canvas, doc, timestamp), 
        onLaterPages=lambda canvas, doc: _add_page_info(canvas, doc, timestamp)
    )
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
