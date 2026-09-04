import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models import (
    Project, Channel, ResearchRun, ResearchSource, ResearchClaim, 
    ResearchEvidence, Episode, StoryRun, StoryEvent, StoryBeat, Scene,
    StoryAct, NarrationSegment, VisualIntent
)
from backend.models.enums import ClaimStatus, DatePrecision, NarrativeRole
from backend.services.story.builder import StoryBuilder

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_v8_story_build(db_session):
    c = Channel(name="c")
    db_session.add(c)
    p = Project(channel=c, name="p", topic="test")
    db_session.add(p)
    e = Episode(project=p, name="e")
    db_session.add(e)
    r = ResearchRun(project=p)
    db_session.add(r)
    db_session.commit()
    
    src = ResearchSource(project_id=p.id, discovered_in_run_id=r.id, url="http", canonical_url="http", title="t", reliability_tier="TIER_1")
    db_session.add(src)
    db_session.commit()
    
    # Add claims that trigger heuristics
    c1 = ResearchClaim(project_id=p.id, research_run_id=r.id, claim_text="The game released in 2018.", status=ClaimStatus.CORROBORATED.value, quality_classification="STORY_READY")
    c2 = ResearchClaim(project_id=p.id, research_run_id=r.id, claim_text="It sold 5 million copies.", status=ClaimStatus.CORROBORATED.value, quality_classification="STORY_READY")
    # Low quality
    c3 = ResearchClaim(project_id=p.id, research_run_id=r.id, claim_text="Random thing.", status=ClaimStatus.SINGLE_SOURCE.value, quality_classification="LOW_QUALITY")
    
    db_session.add_all([c1, c2, c3])
    db_session.commit()
    
    builder = StoryBuilder(db_session)
    run_id = builder.build_story(p.id, e.id, r.id)
    
    run = db_session.query(StoryRun).get(run_id)
    assert run.status == "COMPLETED"
    
    events = db_session.query(StoryEvent).filter_by(story_run_id=run.id).all()
    assert len(events) == 2 # c1 and c2 selected, c3 dropped
    
    # Check date extraction
    e1 = next(ev for ev in events if "2018" in ev.summary)
    assert e1.date_precision == "YEAR"
    assert e1.event_date == "2018"
    
    beats = db_session.query(StoryBeat).filter_by(story_run_id=run.id).all()
    assert len(beats) == 2
    
    acts = db_session.query(StoryAct).filter_by(story_run_id=run.id).all()
    assert len(acts) == 3
    
    scenes = db_session.query(Scene).filter_by(story_run_id=run.id).all()
    assert len(scenes) == 2
    
    # Check graph provenance
    scene = scenes[0]
    seg = db_session.query(NarrationSegment).filter_by(scene_id=scene.id).first()
    assert seg.is_brief == 1
    
    vi = db_session.query(VisualIntent).filter_by(narration_segment_id=seg.id).first()
    assert vi is not None
