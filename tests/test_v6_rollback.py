import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.visual_intent import VisualIntent
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.services.selection.selector import FootageSelector
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

def test_selector_rollback(db_session):
    vi = VisualIntent(narration_segment_id=1, description="Intent")
    sa1 = SourceAsset(source_url="1", source_platform="yt")
    sa2 = SourceAsset(source_url="2", source_platform="yt")
    db_session.add_all([vi, sa1, sa2])
    db_session.commit()
    
    m1 = AssetMapping(visual_intent_id=vi.id, source_asset_id=sa1.id)
    m2 = AssetMapping(visual_intent_id=vi.id, source_asset_id=sa2.id)
    db_session.add_all([m1, m2])
    db_session.commit()
    
    selector = FootageSelector(db_session)
    
    with patch.object(db_session, 'commit', side_effect=Exception("Database write failure")):
        with pytest.raises(Exception):
            selector.select_best_for_intent(vi.id)
            
    # Check that nothing was written (it should be rolled back or uncommitted)
    db_session.rollback()
    
    m1_refreshed = db_session.query(AssetMapping).get(m1.id)
    assert m1_refreshed.selection_score is None
    assert m1_refreshed.selection_status.name == "UNSCORED"
