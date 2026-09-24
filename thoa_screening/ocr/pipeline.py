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
    
    Returns:
        JSON structure matching TransplantCase schema fields (partial).
        Unmatched fields default to null.
    """
    file_path = str(file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document not found: {file_path}")
        
    images = []
    if file_path.lower().endswith('.pdf'):
        if convert_from_path is None:
            raise RuntimeError("pdf2image is not installed. Cannot process PDF.")
        logger.info(f"Converting PDF to images: {file_path}")
        # Convert PDF pages to PIL images
        # We can limit to first 3 pages to save time for this MVP
        try:
            images = convert_from_path(file_path, first_page=1, last_page=3)
        except Exception as e:
            logger.error(f"Failed to convert PDF: {e}")
            raise
    else:
        logger.info(f"Loading image: {file_path}")
        try:
            img = Image.open(file_path)
            # Ensure image is loaded and not just a reference
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
    
    for i, img in enumerate(images):
        logger.info(f"Processing page {i+1}...")
        try:
            # 1. Preprocess
            clean_img = preprocess_for_ocr(img)
            
            # 2. Extract raw text
            text, avg_conf = extract_text_and_confidence(clean_img)
            
            all_text += text + "\n"
            global_conf_sum += avg_conf
            valid_pages += 1
        except Exception as e:
            logger.error(f"Error processing page {i+1}: {e}")
            continue
            
    if valid_pages == 0:
        return _empty_result()
        
    # 3. Parse fields using NLP/Regex on the aggregated text
    extracted = extract_fields(all_text)
    
    # 4. Construct response JSON matching schema
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
        }
    }

def _empty_result() -> Dict[str, Any]:
    return {
        "pipeline_metadata": {
            "pages_processed": 0,
            "average_ocr_confidence": 0.0
        },
        "extracted_data": {
            "full_name": None,
            "dob": None,
            "aadhaar_number": None,
            "pan_number": None,
            "address": None,
        },
        "field_confidences": {
            "full_name": 0.0,
            "dob": 0.0,
            "aadhaar_number": 0.0,
            "pan_number": 0.0,
            "address": 0.0,
        }
    }
