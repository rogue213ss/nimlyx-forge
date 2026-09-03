import pytest
from backend.services.discovery.search_plan import SearchPlanGenerator
from backend.services.discovery.relevance import RelevanceScorer
from backend.services.discovery.models import NormalizedCandidate

# Test 1: No Man's Sky the impossible dream gameplay -> "No Man's Sky" gameplay
def test_search_plan_gameplay_dream():
    gen = SearchPlanGenerator()
    queries = gen.generate_queries("No Man's Sky the impossible dream gameplay")
    # Should contain "No Man's Sky" gameplay
    assert '"No Man\'s Sky" gameplay' in queries
    # Should not contain the full narrative phrase
    assert not any("impossible dream" in q for q in queries)
    assert not any("dream" in q for q in queries if "dream" not in ["dream"])

# Test 2: No Man's Sky the impossible dream trailer -> official trailer, etc.
def test_search_plan_trailer():
    gen = SearchPlanGenerator()
    queries = gen.generate_queries("No Man's Sky the impossible dream trailer")
    assert '"No Man\'s Sky" official trailer' in queries
    assert '"No Man\'s Sky" PlayStation trailer' in queries
    assert not any("impossible dream" in q for q in queries)

# Test 3: Ensure "dream" doesn't become retrieval keyword
def test_search_plan_ambiguous_keyword():
    gen = SearchPlanGenerator()
    queries = gen.generate_queries("No Man's Sky dream survival")
    # defaults to gameplay since no trailer specified
    assert '"No Man\'s Sky" gameplay' in queries
    assert not any("dream" in q for q in queries)

# Test 4: Multiple word game titles
def test_search_plan_multiple_word_titles():
    gen = SearchPlanGenerator()
    queries = gen.generate_queries("Red Dead Redemption 2 horse riding")
    assert '"Red Dead Redemption 2" gameplay' in queries

# Test 5: Relevance Scorer
def test_relevance_scorer():
    gen = SearchPlanGenerator()
    scorer = RelevanceScorer(plan_generator=gen)
    
    intent = "No Man's Sky gameplay"
    
    # Candidate 1: Minecraft Ultra RTX Cave Loop -> REJECTED
    c1 = NormalizedCandidate(source_url="c1", source_platform="yt", title="Minecraft Ultra RTX Cave Loop")
    score, reason, src, is_short = scorer.score_candidate(intent, c1)
    assert reason is not None
    assert "completely absent" in reason
    
    # Candidate 2: No Man's Sky Official Trailer -> HIGH SCORE
    c2 = NormalizedCandidate(source_url="c2", source_platform="yt", title="No Man's Sky Official Trailer", source_channel="Hello Games")
    score2, reason2, src2, is_short2 = scorer.score_candidate("No Man's Sky trailer", c2)
    assert reason2 is None
    assert score2 >= 75 # 50 (title) + 25 (dev) + 15 (trailer) -> 90
    assert src2 == "OFFICIAL_DEVELOPER"
    
    # Candidate 3: Skyfall Official Trailer -> REJECTED
    c3 = NormalizedCandidate(source_url="c3", source_platform="yt", title="Skyfall Official Trailer")
    score3, reason3, src3, is_short3 = scorer.score_candidate("No Man's Sky trailer", c3)
    assert reason3 is not None
    
    # Candidate 4: A Massive Surprise In No Man's Sky -> MEDIUM SCORE
    c4 = NormalizedCandidate(source_url="c4", source_platform="yt", title="A Massive Surprise In No Man's Sky", source_channel="RandomGamer")
    score4, reason4, src4, is_short4 = scorer.score_candidate(intent, c4)
    assert reason4 is None
    assert score4 == 50 # title match
    
    # Candidate 5: Shorts rejection
    c5 = NormalizedCandidate(source_url="c5", source_platform="yt", title="No Man's Sky #shorts", duration=30)
    score5, reason5, src5, is_short5 = scorer.score_candidate(intent, c5)
    assert reason5 is None
    assert is_short5 is True
    assert score5 == 20 # 50 (title) - 30 (short penalty)
