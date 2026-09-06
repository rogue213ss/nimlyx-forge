import pytest
import os
import json
from unittest.mock import patch, MagicMock
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
from backend.services.llm.gemini_provider import GeminiProvider

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

class MockGeminiClient:
    def __init__(self, response_text):
        self.response_text = response_text
    
    class Models:
        def __init__(self, response_text):
            self.response_text = response_text
        def generate_content(self, model, contents, config):
            class Response:
                def __init__(self, text):
                    self.text = text
                    self.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=20, total_token_count=30)
            return Response(self.response_text)
            
    @property
    def models(self):
        return self.Models(self.response_text)


@patch("backend.services.llm.gemini_provider.genai.Client")
@patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "LLM_PROVIDER": "gemini"})
def test_gemini_structured_response(mock_client, db_session):
    # Mocking Gemini SDK response
    mock_client.return_value = MockGeminiClient('{"sentences": [{"text": "The game sold 2.3 million copies.", "type": "FACTUAL", "claim_ids": [1]}]}')
    
    p, rr, sr = setup_base(db_session)
    c, _, _ = create_claim(db_session, p, rr, "The game sold 2.3 million copies.")
    assert c.id == 1
    add_scene(db_session, sr, [c])
    
    writer = LLMScriptWriter(db_session)
    s_id = writer.generate_script(sr.id)
    
    # Assert
    s = db_session.query(ScriptSentence).filter_by(script_run_id=s_id).first()
    assert s.text == "The game sold 2.3 million copies."
    assert s.review_status == ReviewStatus.DRAFT.value
    
    run = db_session.query(ScriptRun).get(s_id)
    assert run.provider_name == "GeminiProvider"
    assert "total_tokens" in run.token_usage

@patch("backend.services.llm.gemini_provider.genai.Client")
@patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "LLM_PROVIDER": "gemini"})
def test_gemini_api_failure(mock_client, db_session):
    def raise_error(*args, **kwargs):
        raise Exception("API Timeout")
        
    client_instance = MagicMock()
    client_instance.models.generate_content.side_effect = raise_error
    mock_client.return_value = client_instance

    p, rr, sr = setup_base(db_session)
    c, _, _ = create_claim(db_session, p, rr, "Safe.")
    add_scene(db_session, sr, [c])
    
    writer = LLMScriptWriter(db_session) 
    try:
        writer.generate_script(sr.id)
    except Exception:
        pass
    
    run = db_session.query(ScriptRun).filter_by(story_run_id=sr.id).order_by(ScriptRun.id.desc()).first()
    assert run.status == ScriptRunStatus.FAILED.value
    assert "API Timeout" in run.error_message
    assert db_session.query(ScriptSentence).filter_by(script_run_id=run.id).count() == 0

@patch("backend.services.llm.gemini_provider.genai.Client")
@patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "LLM_PROVIDER": "gemini"})
def test_gemini_factual_validator_still_applies(mock_client, db_session):
    # Test that V10 validators intercept bad output from Gemini
    mock_client.return_value = MockGeminiClient('{"sentences": [{"text": "The game sold 5 million copies.", "type": "FACTUAL", "claim_ids": [1]}]}')
    
    p, rr, sr = setup_base(db_session)
    c, _, _ = create_claim(db_session, p, rr, "The game sold 2.3 million copies.")
    assert c.id == 1
    add_scene(db_session, sr, [c])
    
    writer = LLMScriptWriter(db_session)
    s_id = writer.generate_script(sr.id)
    
    s = db_session.query(ScriptSentence).filter_by(script_run_id=s_id).first()
    assert s.review_status == ReviewStatus.NEEDS_REVIEW.value

@patch("backend.services.llm.gemini_provider.genai.Client")
@patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "LLM_PROVIDER": "gemini"})
def test_gemini_idempotency(mock_client, db_session):
    mock_client.return_value = MockGeminiClient('{"sentences": [{"text": "Text.", "type": "FACTUAL", "claim_ids": [1]}]}')
    
    p, rr, sr = setup_base(db_session)
    c, _, _ = create_claim(db_session, p, rr, "Text.")
    assert c.id == 1
    add_scene(db_session, sr, [c])
    
    writer = LLMScriptWriter(db_session)
    s_id1 = writer.generate_script(sr.id)
    s_id2 = writer.generate_script(sr.id)
    
    assert s_id1 != s_id2

@patch("backend.services.llm.gemini_provider.genai.Client")
@patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "LLM_PROVIDER": "gemini"})
def test_gemini_human_approval_protected(mock_client, db_session):
    mock_client.return_value = MockGeminiClient('{"sentences": [{"text": "Text.", "type": "FACTUAL", "claim_ids": [1]}]}')
    
    p, rr, sr = setup_base(db_session)
    c, _, _ = create_claim(db_session, p, rr, "Text.")
    add_scene(db_session, sr, [c])
    
    writer = LLMScriptWriter(db_session)
    s_id1 = writer.generate_script(sr.id)
    
    s1 = db_session.query(ScriptSentence).filter_by(script_run_id=s_id1).first()
    s1.review_status = ReviewStatus.APPROVED.value
    db_session.commit()
    
    s_id2 = writer.generate_script(sr.id)
    
    db_session.refresh(s1)
    assert s1.review_status == ReviewStatus.APPROVED.value

