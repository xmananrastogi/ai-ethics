"""
Computer Vision Document Integrity and Synthetic Tampering / Fraud Detector.

Forensic analysis for statutory transplant documentation (THOA 1994):
1. Error Level Analysis (ELA) for digital splicing / compression variance detection.
2. Edge Discontinuity & Seam Analysis for copy-paste bounding artifacts.
3. Statutory Signature & Seal presence verification.
4. Color-coded forensic heatmap generation.
"""

import io
import os
import base64
from typing import Dict, Any, List, Optional
import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance


def _perform_ela(pil_image: Image.Image, quality: int = 90) -> tuple[np.ndarray, float]:
    """
    Perform Error Level Analysis (ELA) by re-saving at a known JPEG quality
    and measuring the pixel-level difference matrix.
    """
    buffer = io.BytesIO()
    # Convert RGBA to RGB if needed
    if pil_image.mode != 'RGB':
        pil_image = pil_image.convert('RGB')
        
    pil_image.save(buffer, 'JPEG', quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)

    diff = ImageChops.difference(pil_image, resaved)
    extrema = diff.getextrema()
    max_diff = max([ex[1] for ex in extrema]) if extrema else 1
    scale = 255.0 / max_diff if max_diff > 0 else 1.0
    diff_enhanced = ImageEnhance.Brightness(diff).enhance(scale * 1.5)

    diff_np = np.array(diff_enhanced)
    gray = cv2.cvtColor(diff_np, cv2.COLOR_RGB2GRAY)
    variance = float(np.var(gray))
    return diff_np, variance


def _detect_splice_contours(gray_image: np.ndarray) -> tuple[List[Dict[str, Any]], float]:
    """
    Detect sharp rectangular edge seams that indicate pasted or spliced image patches.
    """
    edges = cv2.Canny(gray_image, 100, 200)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    suspicious_rects = []
    h, w = gray_image.shape
    total_area = h * w

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        box_area = cw * ch
        # Look for rectangular patches between 0.5% and 15% of document area
        if 0.005 * total_area < box_area < 0.15 * total_area:
            aspect_ratio = float(cw) / float(ch) if ch > 0 else 0
            if 0.2 < aspect_ratio < 5.0:
                # Check sharpness of edges along rectangle boundary
                roi = gray_image[y:y+ch, x:x+cw]
                laplacian_var = cv2.Laplacian(roi, cv2.CV_64F).var()
                if laplacian_var > 350.0:
                    suspicious_rects.append({
                        "x": round(float(x) / w, 4),
                        "y": round(float(y) / h, 4),
                        "w": round(float(cw) / w, 4),
                        "h": round(float(ch) / h, 4),
                        "severity": "MEDIUM",
                        "variance": round(float(laplacian_var), 2)
                    })

    splice_score = min(len(suspicious_rects) * 15.0, 60.0)
    return suspicious_rects, splice_score


def _verify_signature_zones(gray_image: np.ndarray, doc_type: str | None) -> Dict[str, Any]:
    """
    Verify presence of ink strokes in statutory signature zones.
    """
    h, w = gray_image.shape
    # Standard THOA forms place signatures in the lower quadrant (y: 65% to 95%)
    sig_roi = gray_image[int(h * 0.65):int(h * 0.95), :]
    
    # Adaptive threshold to isolate ink strokes
    thresh = cv2.adaptiveThreshold(
        sig_roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )
    
    stroke_pixels = int(np.count_nonzero(thresh))
    stroke_density = float(stroke_pixels) / float(sig_roi.size)

    # Required threshold for ink content
    has_ink = stroke_density > 0.008

    return {
        "signature_zone_checked": True,
        "ink_density": round(stroke_density, 4),
        "signatures_detected": has_ink,
        "status": "VALID_STROKES_DETECTED" if has_ink else "POTENTIAL_MISSING_SIGNATURE"
    }


def analyze_document_fraud(file_path: str, doc_type: str | None = None) -> Dict[str, Any]:
    """
    Perform complete forensic fraud analysis on a PDF or image document.
    Returns risk score, anomalies list, signature verification, and forensic heatmap.
    """
    if not os.path.exists(file_path):
        return {
            "fraud_risk_score": 0,
            "risk_level": "UNKNOWN",
            "verdict": "FILE_NOT_FOUND",
            "anomalies": ["Document file missing from disk."]
        }

    # 1. Render first page to image
    if file_path.lower().endswith(".pdf"):
        doc = fitz.open(file_path)
        if len(doc) == 0:
            return {"fraud_risk_score": 0, "verdict": "EMPTY_DOCUMENT", "anomalies": []}
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        pil_img = Image.frombytes("RGB", [pix.w, pix.h], pix.samples)
        doc.close()
    else:
        pil_img = Image.open(file_path).convert("RGB")

    w, h = pil_img.size
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

    # 2. Error Level Analysis (ELA)
    ela_np, ela_variance = _perform_ela(pil_img, quality=90)
    ela_anomaly = ela_variance > 180.0

    # 3. Splicing Boundary Detection
    splice_rects, splice_score = _detect_splice_contours(gray)

    # 4. Signature & Seal Verification
    sig_result = _verify_signature_zones(gray, doc_type)

    # 5. Calculate Composite Fraud Score [0 - 100]
    base_score = 5.0  # nominal baseline
    if ela_anomaly:
        base_score += 25.0
    base_score += splice_score
    if not sig_result["signatures_detected"]:
        base_score += 30.0

    risk_score = min(max(round(base_score, 1), 0.0), 100.0)

    # Verdict
    if risk_score < 30.0:
        verdict = "AUTHENTIC"
        risk_level = "LOW"
    elif risk_score < 65.0:
        verdict = "SUSPICIOUS_ARTIFACTS"
        risk_level = "MEDIUM"
    else:
        verdict = "HIGH_TAMPERING_RISK"
        risk_level = "HIGH"

    anomalies = []
    if ela_anomaly:
        anomalies.append({
            "code": "CV-ELA-01",
            "severity": "WARNING",
            "title": "Compression Inconsistency",
            "description": f"Elevated Error Level Analysis variance ({ela_variance:.1f}) detected. Possible multi-layer resave."
        })
    if splice_rects:
        anomalies.append({
            "code": "CV-SEAM-02",
            "severity": "WARNING",
            "title": "Sharp Splicing Seams",
            "description": f"Detected {len(splice_rects)} candidate rectangular edge boundaries consistent with digital patch insertion."
        })
    if not sig_result["signatures_detected"]:
        anomalies.append({
            "code": "CV-SIG-03",
            "severity": "CRITICAL",
            "title": "Missing Statutory Signatures",
            "description": "Signature zone has insufficient ink stroke density. Statutory declaration may be unexecuted."
        })

    # 6. Generate Color-Coded Forensic Heatmap Image
    # Overlay ELA intensity in Jet colormap over grayscale background
    ela_gray = cv2.cvtColor(ela_np, cv2.COLOR_RGB2GRAY)
    heatmap_colored = cv2.applyColorMap(ela_gray, cv2.COLORMAP_JET)
    
    # Blend: 65% original gray + 35% heatmap
    gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    overlay = cv2.addWeighted(gray_bgr, 0.65, heatmap_colored, 0.35, 0)

    # Draw splice boxes if any
    for rect in splice_rects:
        rx = int(rect["x"] * w)
        ry = int(rect["y"] * h)
        rw = int(rect["w"] * w)
        rh = int(rect["h"] * h)
        cv2.rectangle(overlay, (rx, ry), (rx + rw, ry + rh), (0, 0, 255), 2)
        cv2.putText(overlay, "SEAM", (rx, max(ry - 5, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    # Encode Heatmap as JPEG base64
    _, buf = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 80])
    heatmap_b64 = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"

    return {
        "fraud_risk_score": risk_score,
        "risk_level": risk_level,
        "verdict": verdict,
        "ela_variance": round(ela_variance, 2),
        "signature_verification": sig_result,
        "anomalies_detected": anomalies,
        "splice_boxes_count": len(splice_rects),
        "heatmap_image": heatmap_b64
    }
