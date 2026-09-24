"""
OCR Text Extraction and Parsing.

Runs Tesseract on cleaned images and extracts PII fields via Regex and SpaCy NER.
"""
import re
import datetime
import spacy
import pytesseract
from PIL import Image
from typing import Dict, Any

# Load spaCy model lazily
_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp

def extract_text_and_confidence(image: Image.Image) -> tuple[str, float]:
    """
    Extract text using Tesseract and compute an average confidence score.
    Returns (extracted_text, average_confidence)
    """
    # Get detailed data from tesseract
    # PSM 3 is default (fully automatic page segmentation)
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    
    text_blocks = []
    confidences = []
    
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        conf = float(data['conf'][i])
        # conf is -1 if it's a block/paragraph boundary rather than a word
        if conf > -1 and text:
            text_blocks.append(text)
            confidences.append(conf)
            
    full_text = " ".join(text_blocks)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    
    # Normalize OCR artifacts
    # (Tesseract often confuses O and 0 depending on context, we handle that in specific extractors)
    
    return full_text, avg_conf

def _extract_aadhaar(text: str) -> tuple[str | None, float]:
    # Look for 12 digits, possibly separated by spaces or hyphens
    # Normalize common OCR errors (O -> 0, I/l -> 1) in potential Aadhaar numbers
    clean_text = text.replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
    
    # Regex: 4 digits, optional space/hyphen, 4 digits, optional space/hyphen, 4 digits
    match = re.search(r'\b(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})\b', clean_text)
    if match:
        aadhaar = "".join(match.groups())
        return aadhaar, 95.0  # High confidence if regex matches exactly
    return None, 0.0

def _extract_pan(text: str) -> tuple[str | None, float]:
    # PAN format: 5 letters, 4 digits, 1 letter. e.g. ABCDE1234F
    # Normalize OCR errors for letters and numbers
    # We will try to find a 10-char string that looks like PAN.
    words = text.split()
    for word in words:
        clean_word = word.strip().upper()
        # Clean up stray punctuation
        clean_word = re.sub(r'[^A-Z0-9]', '', clean_word)
        if len(clean_word) == 10:
            match = re.match(r'^[A-Z]{5}\d{4}[A-Z]$', clean_word)
            if match:
                return match.group(), 90.0
    return None, 0.0

def _extract_dob(text: str) -> tuple[str | None, float]:
    # Look for dates in common formats: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD
    # We will return YYYY-MM-DD format as per prompt requirements.
    
    # DD/MM/YYYY or DD-MM-YYYY
    match = re.search(r'\b(\d{2})[/\-](\d{2})[/\-](\d{4})\b', text)
    if match:
        dd, mm, yyyy = match.groups()
        try:
            # Validate and convert
            dt = datetime.date(int(yyyy), int(mm), int(dd))
            return dt.isoformat(), 90.0
        except ValueError:
            pass
            
    # YYYY-MM-DD
    match = re.search(r'\b(\d{4})[/\-](\d{2})[/\-](\d{2})\b', text)
    if match:
        yyyy, mm, dd = match.groups()
        try:
            dt = datetime.date(int(yyyy), int(mm), int(dd))
            return dt.isoformat(), 95.0
        except ValueError:
            pass
            
    return None, 0.0

def _extract_name_address(text: str) -> tuple[str | None, float, str | None, float]:
    # Use SpaCy to find PERSON (name) and GPE/LOC (address)
    nlp = get_nlp()
    doc = nlp(text)
    
    names = []
    addresses = []
    
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            # Clean up stray characters
            clean_name = re.sub(r'[^a-zA-Z\s\.]', '', ent.text).strip()
            if len(clean_name) > 2:
                names.append(clean_name)
        elif ent.label_ in ("GPE", "LOC", "FAC"):
            addresses.append(ent.text)
            
    # Naive assumption: first PERSON is the name, all GPEs form the address
    name = names[0] if names else None
    name_conf = 85.0 if name else 0.0
    
    # Address is usually harder, we combine GPEs or just regex for common keywords
    # For a real system we'd use a more robust address regex or BERT model
    address = ", ".join(addresses) if addresses else None
    addr_conf = 70.0 if address else 0.0
    
    return name, name_conf, address, addr_conf

def extract_fields(text: str) -> Dict[str, Any]:
    """
    Extract structural PII fields from OCR text.
    Returns a dict with field names and their extracted values + confidences.
    """
    aadhaar, aadhaar_conf = _extract_aadhaar(text)
    pan, pan_conf = _extract_pan(text)
    dob, dob_conf = _extract_dob(text)
    name, name_conf, address, address_conf = _extract_name_address(text)
    
    return {
        "full_name": {"value": name, "confidence": name_conf},
        "dob": {"value": dob, "confidence": dob_conf},
        "aadhaar_number": {"value": aadhaar, "confidence": aadhaar_conf},
        "pan_number": {"value": pan, "confidence": pan_conf},
        "address": {"value": address, "confidence": address_conf},
    }
