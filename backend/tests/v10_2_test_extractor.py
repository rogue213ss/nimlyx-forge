from backend.services.research.extractor import AdvancedHeuristicExtractor
import pytest

def test_extractor_topic_normalization():
    extractor = AdvancedHeuristicExtractor()
    text = "The game Fallout New Vegas was released in 2010."
    
    # Should match despite missing colon
    claims = extractor.extract(text, topic="Fallout: New Vegas")
    
    found_entity = False
    for c in claims:
        if "Contains target entity" in c['evidence_quality_reason']:
            found_entity = True
            break
            
    assert found_entity, "Failed to match target entity with different punctuation"

def test_extractor_topic_case_whitespace():
    extractor = AdvancedHeuristicExtractor()
    text = "In fallout   new   vegas, the game was released in 2010."
    
    # Should match despite case and weird spaces
    claims = extractor.extract(text, topic="Fallout New Vegas")
    
    found_entity = False
    for c in claims:
        if "Contains target entity" in c['evidence_quality_reason']:
            found_entity = True
            break
            
    assert found_entity, "Failed to match target entity with different casing/whitespace"

def test_extractor_topic_unrelated():
    extractor = AdvancedHeuristicExtractor()
    text = "The game Fallout 3 was released in 2008."
    
    # Should NOT match Fallout 3 when searching for Fallout New Vegas
    claims = extractor.extract(text, topic="Fallout New Vegas")
    
    found_entity = False
    for c in claims:
        if "Contains target entity" in c['evidence_quality_reason']:
            found_entity = True
            break
            
    assert not found_entity, "Falsely matched target entity for unrelated game"

if __name__ == '__main__':
    pytest.main(["-v", __file__])
