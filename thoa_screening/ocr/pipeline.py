"""
OCR Pipeline Orchestrator.

Accepts an image or PDF, converts to images if needed, runs preprocessing, 
extracts text via OCR, and parses structured fields into a JSON payload.
"""
import os
import logging
from pathlib import Path
from typing import Any, Dict

from PIL import Image
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

from .preprocess import preprocess_for_ocr
from .extractor import extract_text_and_confidence, extract_fields

logger = logging.getLogger(__name__)

def process_document(file_path: str | Path) -> Dict[str, Any]:
    """
    Process an uploaded document (Image or PDF) through the OCR pipeline.
    
    Returns a dict with:
    - extracted_data: field values (name, aadhaar, dob, etc.)
    - field_confidences: per-field OCR confidence scores
    - bounding_boxes: real pixel-normalised coordinates from Tesseract for each field
    """
    file_path = str(file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document not found: {file_path}")
        
    images = []
    if file_path.lower().endswith('.pdf'):
        if convert_from_path is None:
            raise RuntimeError("pdf2image is not installed. Cannot process PDF.")
        logger.info(f"Converting PDF to images: {file_path}")
        try:
            images = convert_from_path(file_path, first_page=1, last_page=3, dpi=200)
        except Exception as e:
            logger.error(f"Failed to convert PDF: {e}")
            raise
    else:
        logger.info(f"Loading image: {file_path}")
        try:
            img = Image.open(file_path)
            img.load()
            images.append(img)
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            raise
            
    if not images:
        logger.warning("No pages to process.")
        return _empty_result()
        
    all_text = ""
    global_conf_sum = 0.0
    valid_pages = 0
    all_word_data: list[Dict] = []
    page_width, page_height = 1, 1
    
    for i, img in enumerate(images):
        logger.info(f"Processing page {i+1}...")
        try:
            clean_img = preprocess_for_ocr(img)
            page_width, page_height = clean_img.width, clean_img.height
            
            # extract_text_and_confidence now returns: text, confidence, word_data
            text, avg_conf, word_data = extract_text_and_confidence(clean_img)
            
            all_text += text + "\n"
            global_conf_sum += avg_conf
            valid_pages += 1
            for wd in word_data:
                wd["page"] = i + 1
            all_word_data.extend(word_data)
        except Exception as e:
            logger.error(f"Error processing page {i+1}: {e}")
            continue
            
    if valid_pages == 0:
        return _empty_result()
        
    extracted = extract_fields(all_text)
    bounding_boxes = _locate_fields_in_words(extracted, all_word_data, page_width, page_height)
    
    return {
        "pipeline_metadata": {
            "pages_processed": valid_pages,
            "average_ocr_confidence": round(global_conf_sum / valid_pages, 2)
        },
        "extracted_data": {
            "full_name": extracted["full_name"]["value"],
            "dob": extracted["dob"]["value"],
            "aadhaar_number": extracted["aadhaar_number"]["value"],
            "pan_number": extracted["pan_number"]["value"],
            "address": extracted["address"]["value"],
        },
        "field_confidences": {
            "full_name": extracted["full_name"]["confidence"],
            "dob": extracted["dob"]["confidence"],
            "aadhaar_number": extracted["aadhaar_number"]["confidence"],
            "pan_number": extracted["pan_number"]["confidence"],
            "address": extracted["address"]["confidence"],
        },
        "bounding_boxes": bounding_boxes
    }


def _locate_fields_in_words(
    extracted: Dict[str, Any],
    word_data: list[Dict],
    page_width: int,
    page_height: int
) -> Dict[str, Any]:
    """
    For each extracted field value, scan Tesseract's word-level output to find
    the actual position of that text on the page.
    Returns normalised coordinates (0.0–1.0) so the frontend can scale them to 
    any zoom level.
    """
    boxes = {}
    
    for field_name, info in extracted.items():
        value = info.get("value")
        if not value:
            boxes[field_name] = None
            continue
        
        value_tokens = str(value).replace("-", " ").split()
        best_match = None
        
        for i, word in enumerate(word_data):
            word_text = word.get("text", "").strip()
            if not word_text:
                continue
            
            match_count = 0
            for j, token in enumerate(value_tokens):
                if i + j < len(word_data):
                    candidate = word_data[i + j].get("text", "").replace("-", "").strip()
                    clean_token = token.replace("-", "")
                    if candidate.upper() == clean_token.upper():
                        match_count += 1
            
            if match_count == len(value_tokens) and match_count > 0:
                first_word = word_data[i]
                last_word = word_data[i + match_count - 1]
                
                x1 = first_word["left"]
                y1 = first_word["top"]
                x2 = last_word["left"] + last_word["width"]
                y2 = last_word["top"] + last_word["height"]
                
                best_match = {
                    "x": round(x1 / page_width, 4) if page_width > 0 else 0,
                    "y": round(y1 / page_height, 4) if page_height > 0 else 0,
                    "w": round((x2 - x1) / page_width, 4) if page_width > 0 else 0,
                    "h": round((y2 - y1) / page_height, 4) if page_height > 0 else 0,
                    "page": first_word.get("page", 1)
                }
                break
        
        boxes[field_name] = best_match
    
    return boxes


def _empty_result() -> Dict[str, Any]:
    return {
        "pipeline_metadata": {"pages_processed": 0, "average_ocr_confidence": 0.0},
        "extracted_data": {
            "full_name": None, "dob": None,
            "aadhaar_number": None, "pan_number": None, "address": None,
        },
        "field_confidences": {
            "full_name": 0.0, "dob": 0.0,
            "aadhaar_number": 0.0, "pan_number": 0.0, "address": 0.0,
        },
        "bounding_boxes": {}
    }
