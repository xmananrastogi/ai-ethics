import pytest
from thoa_screening.ocr.form3_extractor import extract_form3_facts

def test_extract_form3_facts():
    text = (
        "I, John Smith, state that I have known Mary Johnson for ten years. "
        "We met in college at Harvard University in Boston in 2014. "
        "We are close childhood friends and have lived together as roommates. "
        "I love her dearly. I am donating my kidney out of pure affection."
    )
    
    result = extract_form3_facts(text)
    
    # Check entities
    assert "John Smith" in result["entities"]["persons"]
    assert "Mary Johnson" in result["entities"]["persons"]
    assert "Harvard University" in result["entities"]["organizations"]
    assert "Boston" in result["entities"]["locations"]
    assert "2014" in result["entities"]["dates"]
    
    # Check duration
    assert result["relationship_duration_stated"] == "ten years"
    
    # Check events (should capture sentences with 'college', 'friends', 'lived')
    assert any("college" in e for e in result["key_events_mentioned"])
    assert any("childhood friends" in e for e in result["key_events_mentioned"])
    
    # Should NOT compute sentiment
    assert "sentiment" not in result
    assert "score" not in result
    
    # Check metadata warning
    assert "purely factual extraction" in result["metadata"]["warning"]
