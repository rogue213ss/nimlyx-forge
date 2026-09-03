import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.visual_intent import VisualIntent
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import SelectionStatus, AssetState
from backend.services.selection.selector import FootageSelector
from backend.services.selection.planner import ClipPlanner
from backend.database.db import Base
import sqlalchemy as sa
from unittest.mock import patch

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    conn = session.connection()
    conn.execute(sa.text("INSERT INTO channels (name) VALUES ('c')"))
    conn.execute(sa.text("INSERT INTO projects (channel_id, name) VALUES (1, 'p')"))
    conn.execute(sa.text("INSERT INTO episodes (project_id, name) VALUES (1, 'e')"))
    conn.execute(sa.text("INSERT INTO scenes (episode_id, order_index, title) VALUES (1, 1, 's')"))
    conn.execute(sa.text("INSERT INTO narration_segments (scene_id, order_index, text) VALUES (1, 1, 'n')"))
    
    yield session
    session.close()

def test_v6_to_v5_integration(db_session):
    vi = VisualIntent(narration_segment_id=1, description="Intent")
    sa1 = SourceAsset(source_url="http://real.url", source_platform="yt", title="Test Trailer")
    db_session.add_all([vi, sa1])
    db_session.commit()
    
    m1 = AssetMapping(visual_intent_id=vi.id, source_asset_id=sa1.id, relevance_score=90.0, state=AssetState.CANDIDATE, start_timestamp=10.0, end_timestamp=25.0)
    db_session.add(m1)
    db_session.commit()
    
    # 1. V6 Selection
    selector = FootageSelector(db_session)
    best = selector.select_best_for_intent(vi.id)
    
    assert best.selection_status == SelectionStatus.AUTO_SELECTED
    assert best.timestamp_confidence == "HUMAN_PROVIDED" # Because planner worked
    assert best.start_timestamp == 10.0
    
    # 2. Handoff to V5 (simulate human approval logic which bridges V6 selection to V5 acquisition)
    # The rule is AUTO_SELECTED != APPROVED. Human approval is an explicit action.
    # So we manually approve it.
    best.selection_status = SelectionStatus.APPROVED
    best.state = AssetState.APPROVED_FOR_ACQUISITION
    db_session.commit()
    
    # Assert V5 pre-conditions are met
    assert best.state == AssetState.APPROVED_FOR_ACQUISITION
    assert best.source_asset.source_url == "http://real.url"
    assert best.start_timestamp == 10.0
    assert best.end_timestamp == 25.0
