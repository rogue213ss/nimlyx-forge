import pytest
from backend.services.discovery.search_plan import SearchPlanGenerator
from backend.services.discovery.relevance import RelevanceScorer
from backend.services.discovery.models import NormalizedCandidate

def test_v4_brutal_search_gen():
    gen = SearchPlanGenerator()
    
    # 1. Punctuation, apostrophes, subtitles
    q1 = gen.generate_queries("No Man's Sky: NEXT - The Impossible Dream trailer")
    assert '"No Man\'s Sky"' in q1[0]
    
    # 2. Missing game title, empty intent, malformed intent
    q_empty = gen.generate_queries("")
    assert q_empty == []
    
    # Random text with dangerous words
    q_ambig = gen.generate_queries("dream fall war gameplay")
    assert "gameplay" in q_ambig
    assert "dream" not in q_ambig[0].split()

def test_v4_brutal_relevance_scorer():
    gen = SearchPlanGenerator()
    scorer = RelevanceScorer(plan_generator=gen)
    
    intent = "No Man's Sky official trailer"
    
    # Official source boost shouldn't override semantic mismatch (e.g. PlayStation uploads an unrelated game trailer)
    # PlayStation uploads "Star Wars Trailer"
    c_mismatch = NormalizedCandidate(
        source_url="url1", source_platform="yt", 
        title="Star Wars Outlaws Official Trailer", 
        source_channel="PlayStation"
    )
    score, reason, source, is_short = scorer.score_candidate(intent, c_mismatch)
    assert reason is not None
    assert "absent" in reason
    
    # PlayStation uploads No Man's Sky trailer
    c_match = NormalizedCandidate(
        source_url="url2", source_platform="yt", 
        title="No Man's Sky NEXT Trailer", 
        source_channel="PlayStation"
    )
    score2, reason2, source2, is_short2 = scorer.score_candidate(intent, c_match)
    assert reason2 is None
    assert score2 > 0
    assert source2 == "OFFICIAL_PLATFORM"

    # Game title in description but NOT title
    c_desc_only = NormalizedCandidate(
        source_url="url3", source_platform="yt",
        title="A Huge Space Update!",
        description="The new No Man's Sky update is here.",
        source_channel="Random"
    )
    score3, reason3, source3, is_short3 = scorer.score_candidate(intent, c_desc_only)
    assert reason3 is None  # Since it's in description, it passes the hard rejection
    assert score3 > 0

    # Game title NOT in title, NOT in description
    c_missing = NormalizedCandidate(
        source_url="url4", source_platform="yt",
        title="Space Game Update",
        description="A huge space update",
        source_channel="Random"
    )
    score4, reason4, source4, is_short4 = scorer.score_candidate(intent, c_missing)
    assert reason4 is not None

    # Shorts Penalty
    c_short = NormalizedCandidate(
        source_url="url5", source_platform="yt",
        title="No Man's Sky update #shorts",
        duration=30
    )
    score5, reason5, source5, is_short5 = scorer.score_candidate(intent, c_short)
    assert is_short5 is True
    # Base score = 50 (title) - 30 (short penalty) = 20
    assert score5 == 20

