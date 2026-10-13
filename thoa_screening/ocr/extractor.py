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

def extract_text_and_confidence(image: Image.Image) -> tuple[str, float, list[dict]]:
    """
    Extract text using Tesseract and compute an average confidence score.
    Also returns per-word bounding box data for real highlight positioning.
    Returns (extracted_text, average_confidence, word_data)
    where word_data is a list of dicts: {text, left, top, width, height, conf}
    """
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    
    text_blocks = []
    confidences = []
    word_data = []
    
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        conf = float(data['conf'][i])
        if conf > -1 and text:
            text_blocks.append(text)
            confidences.append(conf)
            word_data.append({
                "text": text,
                "left": int(data['left'][i]),
                "top": int(data['top'][i]),
                "width": int(data['width'][i]),
                "height": int(data['height'][i]),
                "conf": conf
            })
            
    full_text = " ".join(text_blocks)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    
    return full_text, avg_conf, word_data

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
    # 1. First attempt targeted regex for statutory form headers
    name_patterns = [
        r'(?:My full name \(proposed donor\) is|My full name is|Whereas I[,\s]+Shri/Smt/Ms\.?|Whereas I)\s*[\.:]*\s*([A-Z][a-zA-Z\s]{2,30}?)(?:[\.,\n]|\s+and\b|\s+aged\b|\s+S/o|\s+D/o|\s+W/o)',
        r'(?:Name of (?:the )?(?:donor|recipient))\s*[:\-]\s*([A-Z][a-zA-Z\s]{2,30})',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Clean punctuation/dots
            candidate = re.sub(r'[^a-zA-Z\s]', '', candidate).strip()
            if len(candidate) > 2 and candidate.lower() not in ("refer", "doctor", "dr"):
                return candidate, 92.0, None, 0.0

    # 2. Use SpaCy to find PERSON (name) and GPE/LOC (address)
    nlp = get_nlp()
    doc = nlp(text)
    
    names = []
    addresses = []
    
    STOP_PERSONS = {
        "refer", "rules", "rule", "form", "transplantation", "act",
        "doctor", "medical", "practitioner", "notary", "public",
        "delhi", "india", "hospital", "committee", "donor", "recipient",
        "registered medical practitioner", "sections", "driving license",
        "driving", "license", "voter", "passport", "ration", "consumer",
        "card", "permanent", "account", "number", "aadhaar", "tel",
        "signature", "photograph", "affix", "notary public", "state"
    }
    
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            clean_name = re.sub(r'[^a-zA-Z\s\.]', '', ent.text).strip()
            lower_name = clean_name.lower()
            if len(clean_name) > 2 and lower_name not in STOP_PERSONS and not any(term in lower_name for term in ["license", "card", "rules", "notary", "signature"]):
                names.append(clean_name)
        elif ent.label_ in ("GPE", "LOC", "FAC"):
            addresses.append(ent.text)
            
    name = names[0] if names else None
    name_conf = 85.0 if name else 0.0
    
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
