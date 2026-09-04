import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.project import Project
from backend.models.research_run import ResearchRun
from backend.models.research_source import ResearchSource
from backend.models.research_claim import ResearchClaim
from backend.models.research_evidence import ResearchEvidence
from backend.services.research.engine import ResearchEngine, classify_scope
from backend.services.research.providers import DummyDiscoveryProvider, DummyRetrievalProvider, DummyClaimExtractor
from backend.services.research.plan import ResearchPlanner
from backend.models.enums import ResearchRunStatus
import sqlalchemy as sa
import json

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    conn = session.connection()
    conn.execute(sa.text("INSERT INTO channels (name) VALUES ('c')"))
    conn.execute(sa.text("INSERT INTO projects (channel_id, name, topic) VALUES (1, 'p', 'Test Topic')"))
    session.commit()
    yield session
    session.close()

def test_research_planner():
    planner = ResearchPlanner()
    plan = planner.generate_plan("Test Topic")
    assert len(plan) == 15
    assert plan[0]["category"] == "development"
    assert plan[0]["query"] == "Test Topic development"

def test_scope_classifier():
    assert classify_scope("Test Topic", "Test Topic") == "PRIMARY"
    assert classify_scope("test topic", "Test Topic") == "PRIMARY"
    assert classify_scope("Test Topic Development", "Test Topic") == "PRIMARY"
    assert classify_scope("Completely different game", "Test Topic") == "REJECTED"
    assert classify_scope("Test", "Test Topic") == "REJECTED"
    assert classify_scope("Review of test Topic", "Test Topic") == "PRIMARY"
    
    # Rejected
    assert classify_scope("Completely Unrelated", "Test Topic") == "REJECTED"

def test_v7_2_idempotency_and_determinism(db_session):
    engine = ResearchEngine(db_session, [DummyDiscoveryProvider()], DummyRetrievalProvider(), DummyClaimExtractor())
    
    # Run 1
    run1 = engine.create_run(1, {"query": "Test Topic"})
    engine.execute_plan(run1.id)
    sources1 = db_session.query(ResearchSource).filter_by(discovered_in_run_id=run1.id).all()
    # Dummy returns 1 result per query (15 queries)
    assert len(sources1) == 15
    for s in sources1:
        engine.retrieve_source(s.id)
        engine.process_source_claims(run1.id, s.id)
    
    # Run 2
    run2 = engine.create_run(1, {"query": "Test Topic"})
    engine.execute_plan(run2.id)
    sources2 = db_session.query(ResearchSource).filter_by(discovered_in_run_id=run2.id).all()
    # Should be 0 new sources due to exact deduplication of canonical_urls!
    assert len(sources2) == 0

def test_v7_2_failure_handling(db_session):
    class FailingDiscoveryProvider(DummyDiscoveryProvider):
        def discover(self, query, **kwargs):
            raise Exception("Failure injection")
            
    engine = ResearchEngine(db_session, [FailingDiscoveryProvider()], DummyRetrievalProvider(), DummyClaimExtractor())
    run = engine.create_run(1, {"query": "Test Topic"})
    
    # execute_plan should swallow the exception and not crash
    engine.execute_plan(run.id)
    
    sources = db_session.query(ResearchSource).filter_by(discovered_in_run_id=run.id).all()
    assert len(sources) == 0



