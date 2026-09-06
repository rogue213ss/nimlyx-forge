import pytest
import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models import (
    Project, Channel, ResearchRun, ResearchSource, ResearchClaim, 
    ResearchEvidence, Episode, StoryRun, Scene, NarrationSegment,
    ScriptRun, ScriptSentence, ClaimReference
)
from backend.models.enums import ClaimStatus, SentenceType, ReviewStatus, ScriptRunStatus
from backend.services.script.llm_writer import LLMScriptWriter
from backend.services.llm.provider import LLMProvider, MockProvider
from backend.services.script.validator import FactualValidator

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def setup_base(db):
    c = Channel(name="c1")
    db.add(c)
    p = Project(channel=c, name="p1")
    db.add(p)
    db.flush()
    rr = ResearchRun(project_id=p.id)
    db.add(rr)
    db.flush()
    e = Episode(project_id=p.id, name="e1")
    db.add(e)
    db.flush()
    sr = StoryRun(project_id=p.id, episode_id=e.id, research_run_id=rr.id, status="COMPLETED")
    db.add(sr)
    db.flush()
    return p, rr, sr

def create_claim(db, p, rr, text, status=ClaimStatus.CORROBORATED.value, quality="HIGH_QUALITY"):
    src = ResearchSource(project_id=p.id, discovered_in_run_id=rr.id, url="http", canonical_url="http", title="t", reliability_tier="TIER_1")
    db.add(src)
    db.flush()
    c = ResearchClaim(project_id=p.id, research_run_id=rr.id, claim_text=text, status=status)
    c.quality_classification = quality
    db.add(c)
    db.flush()
    ev = ResearchEvidence(claim_id=c.id, source_id=src.id, raw_text=text)
    db.add(ev)
    db.flush()
    return c, src, ev

def add_scene(db, sr, claims, purpose="P", is_brief=1, must_not_claim=None):
    scene = Scene(episode_id=sr.episode_id, story_run_id=sr.id, order_index=1, title="S1", purpose=purpose)
    db.add(scene)
    db.flush()
    mnc = json.dumps(must_not_claim) if must_not_claim else "[]"
    seg = NarrationSegment(scene_id=scene.id, order_index=1, text="N", purpose="P", is_brief=is_brief, supporting_claims=json.dumps([c.id for c in claims]), must_not_claim=mnc)
    db.add(seg)
    db.commit()
    return scene, seg

class MaliciousProvider(LLMProvider):
    def generate_script(self, prompt_package, config):
        return {
            "sentences": [
                {
                    "text": "The game sold 5 million copies in 2021.", # Mutation of 2.3
                    "type": "FACTUAL",
                    "claim_ids": [prompt_package["verified_claims"][0]["id"]]
                }
            ],
            "usage": {"total_tokens": 10}, "model": "malicious-1"
        }

class HallucinatedIDProvider(LLMProvider):
    def generate_script(self, prompt_package, config):
        return {
            "sentences": [
                {
                    "text": "Valid text.",
                    "type": "FACTUAL",
                    "claim_ids": [9999] # Hallucinated
                }
            ],
            "usage": {"total_tokens": 10}, "model": "hallucinated-1"
        }

class MalformedProvider(LLMProvider):
    def generate_script(self, prompt_package, config):
        raise Exception("API Timeout")

class MustNotClaimProvider(LLMProvider):
    def generate_script(self, prompt_package, config):
        return {
            "sentences": [
                {
                    "text": "Player reaction was furious.", 
                    "type": "FACTUAL",
                    "claim_ids": [prompt_package["verified_claims"][0]["id"]]
                }
            ],
            "usage": {"total_tokens": 10}, "model": "mnc-1"
        }

def test_v10_basic_mock_generation(db_session):
    p, rr, sr = setup_base(db_session)
    c, _, _ = create_claim(db_session, p, rr, "The game released in 2018.")
    add_scene(db_session, sr, [c])
    
    writer = LLMScriptWriter(db_session) # Uses MockProvider by default
    s_id = writer.generate_script(sr.id)
    
    sentences = db_session.query(ScriptSentence).filter_by(script_run_id=s_id).all()
    assert len(sentences) == 1
    assert sentences[0].review_status == ReviewStatus.DRAFT.value
    
    run = db_session.query(ScriptRun).get(s_id)
    assert run.provider_name == "MockProvider"
    assert "total_tokens" in run.token_usage

def test_v10_numerical_mutation_detected(db_session):
    p, rr, sr = setup_base(db_session)
    c, _, _ = create_claim(db_session, p, rr, "The game sold 2.3 million copies.")
    add_scene(db_session, sr, [c])
    
    writer = LLMScriptWriter(db_session, provider=MaliciousProvider()) 
    s_id = writer.generate_script(sr.id)
    
    # Sentence has 5 million, claim has 2.3 million
    # Validator should set it to NEEDS_REVIEW
    s = db_session.query(ScriptSentence).filter_by(script_run_id=s_id).first()
    assert s.review_status == ReviewStatus.NEEDS_REVIEW.value

def test_v10_hallucinated_claim_id(db_session):
    p, rr, sr = setup_base(db_session)
    c, _, _ = create_claim(db_session, p, rr, "Safe.")
    add_scene(db_session, sr, [c])
    
    writer = LLMScriptWriter(db_session, provider=HallucinatedIDProvider()) 
    s_id = writer.generate_script(sr.id)
    
    s = db_session.query(ScriptSentence).filter_by(script_run_id=s_id).first()
    assert s.review_status == ReviewStatus.REJECTED.value

def test_v10_must_not_claim_enforced(db_session):
    p, rr, sr = setup_base(db_session)
    c, _, _ = create_claim(db_session, p, rr, "Safe.")
    add_scene(db_session, sr, [c], must_not_claim=["player reaction"])
    
    writer = LLMScriptWriter(db_session, provider=MustNotClaimProvider()) 
    s_id = writer.generate_script(sr.id)
    
    s = db_session.query(ScriptSentence).filter_by(script_run_id=s_id).first()
    assert s.review_status == ReviewStatus.NEEDS_REVIEW.value

def test_v10_api_failure_handling(db_session):
    p, rr, sr = setup_base(db_session)
    c, _, _ = create_claim(db_session, p, rr, "Safe.")
    add_scene(db_session, sr, [c])
    
    writer = LLMScriptWriter(db_session, provider=MalformedProvider()) 
    try:
        writer.generate_script(sr.id)
    except Exception:
        pass
    
    # Ensure ScriptRun is FAILED
    run = db_session.query(ScriptRun).filter_by(story_run_id=sr.id).order_by(ScriptRun.id.desc()).first()
    assert run.status == ScriptRunStatus.FAILED.value
    assert "API Timeout" in run.error_message
    
    # Ensure no orphan sentences
    assert db_session.query(ScriptSentence).filter_by(script_run_id=run.id).count() == 0

