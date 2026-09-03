import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.visual_intent import VisualIntent
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.services.selection.selector import FootageSelector
from backend.database.db import Base
import sqlalchemy as sa
import time

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

def test_selector_performance(db_session):
    vi = VisualIntent(narration_segment_id=1, description="Intent")
    db_session.add(vi)
    db_session.commit()
    
    for i in range(1000):
        sa = SourceAsset(source_url=f"http://{i}", source_platform="yt", title=f"Test {i}")
        db_session.add(sa)
    db_session.commit()
    
    for i in range(1, 1001):
        m = AssetMapping(visual_intent_id=vi.id, source_asset_id=i, relevance_score=50.0)
        db_session.add(m)
    db_session.commit()
    
    selector = FootageSelector(db_session)
    
    t0 = time.time()
    best = selector.select_best_for_intent(vi.id)
    t1 = time.time()
    
    print(f"\nTime to rank and select 1000 candidates: {t1 - t0:.4f} seconds")
    assert (t1 - t0) < 5.0 # Should be very fast
