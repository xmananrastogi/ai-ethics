"""
Form 3 (Affection and Attachment Affidavit) NLP Extractor.

This module is designed strictly to extract factual information for the Authorization
Committee. In compliance with core system constraints, it performs NO sentiment
analysis, computes NO affection scores, and makes NO judgments regarding the
legitimacy of the relationship. It outputs a plain factual summary object.
"""

import re
from typing import Dict, List, Any
from thoa_screening.ocr.extractor import get_nlp

# Keywords that commonly denote relationship events/facts in an affidavit
_EVENT_KEYWORDS = {
    "business", "childhood", "school", "college", "friends", "met", 
    "introduced", "worked", "colleagues", "lived", "together", "neighbor",
    "marriage", "wedding", "family"
}

def extract_form3_facts(text: str) -> Dict[str, Any]:
    """
    Extract factual elements from a Form 3 affidavit.
    
    Args:
        text: The raw text of the affidavit.
        
    Returns:
        A dictionary containing extracted named entities, stated relationship
        duration, and explicit event sentences. No numeric scoring is included.
    """
    nlp = get_nlp()
    doc = nlp(text)
    
    entities = {
        "persons": set(),
        "dates": set(),
        "locations": set(),
        "organizations": set()
    }
    
    events: List[str] = []
    
    # Extract entities
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            # Clean up obvious OCR errors
            clean = re.sub(r'[^a-zA-Z\s\.]', '', ent.text).strip()
            if len(clean) > 2:
                entities["persons"].add(clean)
        elif ent.label_ == "DATE":
            entities["dates"].add(ent.text.strip())
        elif ent.label_ in ("GPE", "LOC"):
            entities["locations"].add(ent.text.strip())
        elif ent.label_ == "ORG":
            entities["organizations"].add(ent.text.strip())
            
    # Extract events and duration
    # We iterate over sentences to find factual statements about the relationship
    duration = None
    duration_pattern = re.compile(r'(?:known.*?|friends.*?|together.*?) for ((?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:years|months|decades))', re.IGNORECASE)
    
    for sent in doc.sents:
        sent_text = sent.text.strip()
        
        # Look for duration
        if not duration:
            match = duration_pattern.search(sent_text)
            if match:
                duration = match.group(1).lower()
                
        # Look for key events based on keywords
        words = {token.text.lower() for token in sent if token.is_alpha}
        if words.intersection(_EVENT_KEYWORDS):
            # Clean up the sentence (remove excessive whitespace/newlines)
            clean_sent = re.sub(r'\s+', ' ', sent_text)
            events.append(clean_sent)
            
    # Remove duplicates while preserving order for events
    unique_events = list(dict.fromkeys(events))
    
    return {
        "entities": {
            "persons": sorted(list(entities["persons"])),
            "dates": sorted(list(entities["dates"])),
            "locations": sorted(list(entities["locations"])),
            "organizations": sorted(list(entities["organizations"]))
        },
        "relationship_duration_stated": duration,
        "key_events_mentioned": unique_events,
        "metadata": {
            "warning": "This is a purely factual extraction. The Authorization Committee must independently verify the legitimacy of affection and attachment."
        }
    }
