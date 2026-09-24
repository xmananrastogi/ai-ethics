import pytest
from unittest.mock import patch, MagicMock
from thoa_screening.ocr.extractor import _extract_aadhaar, _extract_pan, _extract_dob, extract_fields

def test_extract_aadhaar_clean():
    text = "Name: John Doe Aadhaar: 1234 5678 9012 Address: Some street"
    val, conf = _extract_aadhaar(text)
    assert val == "123456789012"
    assert conf == 95.0

def test_extract_aadhaar_ocr_error():
    # 'O' instead of '0', 'l' instead of '1'
    text = "Aadhaar: l234 5678 9O12"
    val, conf = _extract_aadhaar(text)
    assert val == "123456789012"
    assert conf == 95.0

def test_extract_pan():
    text = "Income Tax Dept PAN Card ABCDE1234F Signature"
    val, conf = _extract_pan(text)
    assert val == "ABCDE1234F"
    assert conf == 90.0

def test_extract_pan_with_noise():
    text = "Income Tax Dept PAN Card ABCDE1234F, Signature"
    val, conf = _extract_pan(text)
    assert val == "ABCDE1234F"
    assert conf == 90.0

def test_extract_dob_dd_mm_yyyy():
    text = "Date of Birth: 15/08/1990 Place of Birth"
    val, conf = _extract_dob(text)
    assert val == "1990-08-15"
    assert conf == 90.0

def test_extract_dob_yyyy_mm_dd():
    text = "DOB: 1985-12-01"
    val, conf = _extract_dob(text)
    assert val == "1985-12-01"
    assert conf == 95.0

@patch("thoa_screening.ocr.extractor._extract_name_address")
def test_extract_fields(mock_name_addr):
    mock_name_addr.return_value = ("John Doe", 85.0, "Mumbai, India", 70.0)
    
    text = "John Doe born on 15/08/1990 living in Mumbai, India. PAN: ABCDE1234F Aadhaar 123456789012."
    result = extract_fields(text)
    
    assert result["full_name"]["value"] == "John Doe"
    assert result["dob"]["value"] == "1990-08-15"
    assert result["aadhaar_number"]["value"] == "123456789012"
    assert result["pan_number"]["value"] == "ABCDE1234F"
    assert result["address"]["value"] == "Mumbai, India"

def test_extract_dob_malformed():
    text = "Date of Birth: 32/13/1990"
    val, conf = _extract_dob(text)
    # The regex might parse it, but if it's an invalid date, let's see what happens.
    # Our simple regex handles \d{2}/\d{2}/\d{4}. We might just get it back as is, or none.
    # The requirement is to test the edge case.
    assert val is None

def test_extraction_failures():
    text = "This is a random document without any PII."
    val, conf = _extract_aadhaar(text)
    assert val is None
    
    val, conf = _extract_pan(text)
    assert val is None
    
    val, conf = _extract_dob(text)
    assert val is None
