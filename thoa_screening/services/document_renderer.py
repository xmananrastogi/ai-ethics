"""
Document Page Renderer and Bounding Box Locator Service.

Renders document pages (PDF/Image) to high-resolution web-ready images and locates
normalized bounding box coordinates for key statutory clinical and legal fields.
"""

import os
import base64
import re
from typing import Dict, Any, List
import fitz  # PyMuPDF
from PIL import Image


def render_document_page(file_path: str, page_number: int = 0) -> Dict[str, Any]:
    """
    Renders a page of a document to base64 PNG and returns all detected statutory
    field bounding boxes (normalized between 0.0 and 1.0).
    """
    if not os.path.exists(file_path):
        return {
            "error": "File not found on disk",
            "page_count": 0,
            "page_image": None,
            "bounding_boxes": []
        }

    is_pdf = file_path.lower().endswith(".pdf")
    bounding_boxes: List[Dict[str, Any]] = []

    if is_pdf:
        doc = fitz.open(file_path)
        page_count = len(doc)
        if page_count == 0 or page_number >= page_count:
            doc.close()
            return {"error": "Invalid page number", "page_count": page_count, "page_image": None, "bounding_boxes": []}

        page = doc[page_number]
        pw, ph = page.rect.width, page.rect.height

        # Render at 150 DPI for crystal clear text
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")
        page_b64 = f"data:image/png;base64,{base64.b64encode(png_bytes).decode('utf-8')}"

        # 1. Search for statutory labels & stamped values
        search_targets = [
            ("aadhaar", r"\b\d{4}\s?\d{4}\s?\d{4}\b", "Aadhaar Card Number"),
            ("dob", r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", "Date of Birth"),
            ("pan", r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", "PAN Number"),
            ("organ", r"\b(Kidney|Liver|Cornea|Heart|Lungs)\b", "Organ Type"),
            ("doctor_reg", r"\b(DMC|MCI|REG|Reg)[-\s]?[0-9]{4,6}\b", "Doctor Registration No"),
        ]

        # Extract text page
        text_page = page.get_text("text")

        # Specific statutory labels in THOA forms
        thoa_prompts = [
            ("donor_name", "My full name (proposed donor) is", 200),
            ("recipient_name", "whose particulars are as follows and name is", 180),
            ("relation", "to my relative", 90),
            ("fitness_statement", "certify that I have examined", 180),
            ("doctor_sig", "Signature of Registered Medical Practitioner", 200),
            ("donor_sig", "Signature of the prospective donor", 180),
        ]

        for field_key, label_text, val_offset in thoa_prompts:
            rects = page.search_for(label_text)
            if rects:
                r = rects[0]
                # Bounding box of the filled value right next to the label
                val_x = r.x1 + 2
                val_y = r.y0 - 2
                val_w = min(val_offset, pw - val_x - 5)
                val_h = r.height + 6
                bounding_boxes.append({
                    "field": field_key,
                    "label": label_text,
                    "x": round(max(val_x, 0) / pw, 4),
                    "y": round(max(val_y, 0) / ph, 4),
                    "w": round(val_w / pw, 4),
                    "h": round(val_h / ph, 4),
                    "confidence": 0.95
                })

        # Regex searches on page
        for field_key, pattern, label in search_targets:
            for match in re.finditer(pattern, text_page, re.IGNORECASE):
                match_str = match.group(0)
                m_rects = page.search_for(match_str)
                for mr in m_rects:
                    bounding_boxes.append({
                        "field": field_key,
                        "label": f"{label}: {match_str}",
                        "x": round(mr.x0 / pw, 4),
                        "y": round(mr.y0 / ph, 4),
                        "w": round(mr.width / pw, 4),
                        "h": round(mr.height / ph, 4),
                        "confidence": 0.92
                    })

        doc.close()
    else:
        # Image file
        pil_img = Image.open(file_path)
        pw, ph = pil_img.size
        buffer = io.BytesIO()
        pil_img.save(buffer, format="PNG")
        page_b64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
        page_count = 1

    return {
        "page_number": page_number,
        "page_count": page_count,
        "page_image": page_b64,
        "bounding_boxes": bounding_boxes
    }
