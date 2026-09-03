import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.visual_intent import VisualIntent
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import SelectionStatus
from backend.services.selection.selector import FootageSelector
from backend.services.selection.scorer import SelectionScorer
from backend.database.db import Base
import sqlalchemy as sa
import json

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # insert dummy fk tree
    conn = session.connection()
    conn.execute(sa.text("INSERT INTO channels (name) VALUES ('c')"))
    conn.execute(sa.text("INSERT INTO projects (channel_id, name) VALUES (1, 'p')"))
    conn.execute(sa.text("INSERT INTO episodes (project_id, name) VALUES (1, 'e')"))
    conn.execute(sa.text("INSERT INTO scenes (episode_id, order_index, title) VALUES (1, 1, 's')"))
    conn.execute(sa.text("INSERT INTO narration_segments (scene_id, order_index, text) VALUES (1, 1, 'n')"))
    
    yield session
    session.close()

def test_adversarial_scorer_json(db_session):
    vi = VisualIntent(narration_segment_id=1, description="Intent")
    db_session.add(vi)
    db_session.commit()
    
    sa1 = SourceAsset(source_url="http://x", source_platform="yt", title="?? \n \t \\\" '", description='{"this": "is not a real json"}')
    db_session.add(sa1)
    db_session.commit()
    
    m = AssetMapping(visual_intent_id=vi.id, source_asset_id=sa1.id, relevance_score=float('inf'))
    db_session.add(m)
    db_session.commit()
    
    selector = FootageSelector(db_session)
    best = selector.select_best_for_intent(vi.id)
    
    assert best is not None
    assert best.selection_score == 100.0 # Clamped
    assert best.selection_status == SelectionStatus.AUTO_SELECTED
    
    reason = json.loads(best.selection_reason)
    assert reason["final_score"] == 100.0
    
def test_adversarial_planner(db_session):
    vi = VisualIntent(narration_segment_id=1, description="Intent")
    sa1 = SourceAsset(source_url="http://y", source_platform="yt", title="Test", source_duration=0.0)
    db_session.add_all([vi, sa1])
    db_session.commit()
    
    m1 = AssetMapping(visual_intent_id=vi.id, source_asset_id=sa1.id, start_timestamp=50.0, end_timestamp=10.0)
    db_session.add(m1)
    db_session.commit()
    
    selector = FootageSelector(db_session)
    best = selector.select_best_for_intent(vi.id)
    assert best.timestamp_confidence == "UNKNOWN"
    assert "strictly greater" in best.timestamp_reason
