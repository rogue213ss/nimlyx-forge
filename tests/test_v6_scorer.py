import pytest
import json
from backend.services.selection.scorer import SelectionScorer

class DummyAsset:
    def __init__(self, title=None, description=None, source_channel=None, published_date=None, is_short=False):
        self.title = title
        self.description = description
        self.source_channel = source_channel
        self.published_date = published_date
        self.is_short = is_short
        
class DummyIntent:
    def __init__(self, desc=None, pref_types='[]', avoid_types='[]', pref_chans='[]', pref_year=None):
        self.description = desc
        self.preferred_content_types = pref_types
        self.avoid_content_types = avoid_types
        self.preferred_channels = pref_chans
        self.preferred_year = pref_year

class DummyMapping:
    def __init__(self, relevance_score=0.0):
        self.relevance_score = relevance_score

def test_hard_rejection():
    scorer = SelectionScorer()
    mapping = DummyMapping(relevance_score=80.0)
    intent = DummyIntent()
    source = DummyAsset(title="", description="") # Missing both
    
    score, reason_json, is_hard = scorer.score_candidate(mapping, intent, source)
    assert is_hard == True
    assert score == 0.0
    
    reason = json.loads(reason_json)
    assert reason["hard_rejection"] == True
    assert "Missing both title and description" in reason["rejection_reasons"]
    assert scorer.determine_confidence(score, is_hard) == "REJECTED"

def test_score_clamping():
    scorer = SelectionScorer()
    mapping = DummyMapping(relevance_score=90.0)
    intent = DummyIntent(pref_types='["trailer"]', pref_chans='["playstation"]')
    source = DummyAsset(title="trailer", source_channel="playstation")
    
    score, reason_json, is_hard = scorer.score_candidate(mapping, intent, source)
    assert is_hard == False
    assert score == 100.0 # Clamped from 90 + 15 + 20 + 10 (official) = 135
    assert scorer.determine_confidence(score, is_hard) == "HIGH"

def test_soft_penalties():
    scorer = SelectionScorer()
    mapping = DummyMapping(relevance_score=50.0)
    intent = DummyIntent(avoid_types='["review"]')
    source = DummyAsset(title="game review", is_short=True)
    
    score, reason_json, is_hard = scorer.score_candidate(mapping, intent, source)
    assert is_hard == False
    assert score == 5.0 # 50 - 20 (review) - 25 (short)
    assert scorer.determine_confidence(score, is_hard) == "REJECTED"
    
def test_json_canonical_ordering():
    scorer = SelectionScorer()
    mapping = DummyMapping(relevance_score=50.0)
    intent = DummyIntent(pref_types='["trailer"]', pref_chans='["xbox"]')
    source = DummyAsset(title="trailer", source_channel="xbox")
    
    score, reason_json1, _ = scorer.score_candidate(mapping, intent, source)
    score, reason_json2, _ = scorer.score_candidate(mapping, intent, source)
    
    assert reason_json1 == reason_json2 # Exact byte-for-byte serialization
     # Compact separators
    assert '{"base_relevance":50.0,"final_score":95.0' in reason_json1
