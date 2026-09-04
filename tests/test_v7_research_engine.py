import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.research_run import ResearchRun
from backend.models.research_source import ResearchSource
from backend.models.research_claim import ResearchClaim
from backend.models.research_evidence import ResearchEvidence
from backend.services.research.engine import ResearchEngine
from backend.services.research.providers import DummyDiscoveryProvider, DummyRetrievalProvider, DummyClaimExtractor
from backend.models.enums import ResearchRunStatus, RetrievalStatus, ClaimStatus, EvidenceType
import sqlalchemy as sa
import urllib.parse
from typing import List, Dict, Any

class MockDiscovery(DummyDiscoveryProvider):
    def discover(self, query: str, **kwargs):
        if query == 'timeout':
            raise Exception("Timeout simulated")
        if query == 'duplicate':
            # returns same canonical url twice but different query params
            return [
                {"url": "http://test.com/a#hash1", "title": "A"},
                {"url": "http://test.com/a#hash2", "title": "B"}
            ]
        if query == 'contradiction':
            return [
                {"url": "http://test.com/source1", "title": "contradiction S1"},
                {"url": "http://test.com/source2", "title": "contradiction S2"}
            ]
        if query == 'unicode':
            return [{"url": "http://test.com/??", "title": "unicode ??\n\t\"'\\"}]
        return super().discover(query, **kwargs)

class MockRetrieval(DummyRetrievalProvider):
    def retrieve(self, url: str):
        if "404" in url:
            return {"status": "NOT_FOUND", "error": "404 Not Found"}
        if "500" in url:
            return {"status": "HTTP_ERROR", "error": "500 Server Error"}
        if "timeout" in url:
            raise Exception("Timeout simulated")
        if "source1" in url:
            return {"status": "SUCCESS", "content_text": "Team was 4 people."}
        if "source2" in url:
            return {"status": "SUCCESS", "content_text": "Team was 5 people."}
        if "??" in url:
            return {"status": "SUCCESS", "content_text": "Unicode text ??"}
        return super().retrieve(url)

class MockExtractor(DummyClaimExtractor):
    def extract(self, text: str, source_tier: str = 'TIER_4', topic: str = ''):
        if text == "Team was 4 people.":
            return [{"claim_text": "Team size", "normalized_claim_text": "Team size_norm", "category": "dev", "confidence": "HIGH", "raw_text": "4 people", "evidence_type": "SUPPORTING"}]
        if text == "Team was 5 people.":
            return [{"claim_text": "Team size", "normalized_claim_text": "Team size_norm", "category": "dev", "confidence": "HIGH", "raw_text": "5 people", "evidence_type": "CONTRADICTING"}]
        if "Unicode" in text:
            return [{"claim_text": "Unicode ??", "normalized_claim_text": "Unicode ??_norm", "category": "test", "confidence": "HIGH", "raw_text": "Unicode text ??"}]
        return super().extract(text)

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    conn = session.connection()
    conn.execute(sa.text("INSERT INTO channels (name) VALUES ('c')"))
    conn.execute(sa.text("INSERT INTO projects (channel_id, name) VALUES (1, 'p')"))
    session.commit()
    yield session
    session.close()

def test_basic_research_flow(db_session):
    engine = ResearchEngine(db_session, MockDiscovery(), MockRetrieval(), MockExtractor())
    run = engine.create_run(1, {"query": "basic"})
    
    engine.discover_and_add_sources(run.id, "basic")
    sources = db_session.query(ResearchSource).filter_by(discovered_in_run_id=run.id).all()
    assert len(sources) == 1
    src = sources[0]
    
    engine.retrieve_source(src.id)
    assert src.retrieval_status == RetrievalStatus.SUCCESS
    
    engine.process_source_claims(run.id, src.id)
    claims = db_session.query(ResearchClaim).filter_by(research_run_id=run.id).all()
    assert len(claims) == 1
    assert claims[0].status == ClaimStatus.SINGLE_SOURCE
    
    evidences = db_session.query(ResearchEvidence).filter_by(claim_id=claims[0].id).all()
    assert len(evidences) == 1
    assert evidences[0].source_id == src.id
    
    engine.complete_run(run.id)
    assert run.status == ResearchRunStatus.COMPLETED

def test_deduplication(db_session):
    engine = ResearchEngine(db_session, MockDiscovery(), MockRetrieval(), MockExtractor())
    run = engine.create_run(1, {"query": "duplicate"})
    
    # Should only insert one source because canonical URL deduplicates
    engine.discover_and_add_sources(run.id, "duplicate")
    sources = db_session.query(ResearchSource).filter_by(discovered_in_run_id=run.id).all()
    assert len(sources) == 1

def test_contradictions(db_session):
    engine = ResearchEngine(db_session, MockDiscovery(), MockRetrieval(), MockExtractor())
    run = engine.create_run(1, {"query": "contradiction"})
    engine.discover_and_add_sources(run.id, "contradiction")
    sources = db_session.query(ResearchSource).filter_by(discovered_in_run_id=run.id).all()
    
    for src in sources:
        engine.retrieve_source(src.id)
        engine.process_source_claims(run.id, src.id)
        
    claims = db_session.query(ResearchClaim).filter_by(research_run_id=run.id).all()
    assert len(claims) == 1 # "Team size" deduplicated!
    claim = claims[0]
    
    evs = db_session.query(ResearchEvidence).filter_by(claim_id=claim.id).all()
    assert len(evs) == 2 # Two pieces of evidence for the same claim
    
    # One should be supporting, one contradicting (based on mock)
    types = [e.evidence_type for e in evs]
    assert EvidenceType.SUPPORTING in types
    assert EvidenceType.CONTRADICTING in types

def test_failure_injection(db_session):
    engine = ResearchEngine(db_session, MockDiscovery(), MockRetrieval(), MockExtractor())
    
    # Discovery failure
    with pytest.raises(Exception):
        run1 = engine.create_run(1, {"query": "timeout"})
        engine.discover_and_add_sources(run1.id, "timeout")
        
    # Retrieval failure
    run2 = engine.create_run(1, {"query": "basic"})
    src = ResearchSource(project_id=1, discovered_in_run_id=run2.id, url="http://404", canonical_url="http://404")
    db_session.add(src)
    db_session.commit()
    
    engine.retrieve_source(src.id)
    assert src.retrieval_status == RetrievalStatus.NOT_FOUND
    assert src.error_info == "404 Not Found"

    src2 = ResearchSource(project_id=1, discovered_in_run_id=run2.id, url="http://timeout", canonical_url="http://timeout")
    db_session.add(src2)
    db_session.commit()
    
    engine.retrieve_source(src2.id)
    assert src2.retrieval_status == RetrievalStatus.HTTP_ERROR
    assert "Timeout" in src2.error_info

def test_adversarial(db_session):
    engine = ResearchEngine(db_session, MockDiscovery(), MockRetrieval(), MockExtractor())
    run = engine.create_run(1, {"query": "unicode"})
    engine.discover_and_add_sources(run.id, "unicode")
    sources = db_session.query(ResearchSource).filter_by(discovered_in_run_id=run.id).all()
    
    assert len(sources) == 1
    src = sources[0]
    assert src.title == "unicode ??\n\t\"'\\"
    
    engine.retrieve_source(src.id)
    engine.process_source_claims(run.id, src.id)
    
    claims = db_session.query(ResearchClaim).filter_by(research_run_id=run.id).all()
    assert claims[0].claim_text == "Unicode ??"








