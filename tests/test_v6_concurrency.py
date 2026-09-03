import pytest
import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.visual_intent import VisualIntent
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.services.selection.selector import FootageSelector
from backend.database.db import Base
import sqlalchemy as sa

@pytest.fixture
def db_engine():
    from sqlalchemy.pool import StaticPool
    import os
    db_path = 'test_v6_concurrency.db'
    if os.path.exists(db_path):
        os.remove(db_path)
    engine = create_engine(f'sqlite:///{db_path}', connect_args={'check_same_thread': False, 'timeout': 15})
    Base.metadata.create_all(engine)
    return engine

def setup_data(engine):
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # insert dummy fk tree
    conn = db.connection()
    conn.execute(sa.text("INSERT INTO channels (name) VALUES ('c')"))
    conn.execute(sa.text("INSERT INTO projects (channel_id, name) VALUES (1, 'p')"))
    conn.execute(sa.text("INSERT INTO episodes (project_id, name) VALUES (1, 'e')"))
    conn.execute(sa.text("INSERT INTO scenes (episode_id, order_index, title) VALUES (1, 1, 's')"))
    conn.execute(sa.text("INSERT INTO narration_segments (scene_id, order_index, text) VALUES (1, 1, 'n')"))
    
    vi = VisualIntent(narration_segment_id=1, description="Test intent")
    db.add(vi)
    db.commit()
    
    sa1 = SourceAsset(source_url="http://1", source_platform="yt", title="A")
    sa2 = SourceAsset(source_url="http://2", source_platform="yt", title="B")
    
    db.add_all([sa1, sa2])
    db.commit()
    
    m1 = AssetMapping(visual_intent_id=vi.id, source_asset_id=sa1.id, relevance_score=90.0)
    m2 = AssetMapping(visual_intent_id=vi.id, source_asset_id=sa2.id, relevance_score=20.0)
    
    db.add_all([m1, m2])
    db.commit()
    return vi.id

def test_selector_concurrency(db_engine):
    vi_id = setup_data(db_engine)
    
    def run_selection():
        Session = sessionmaker(bind=db_engine)
        db = Session()
        selector = FootageSelector(db)
        selector.select_best_for_intent(vi_id)
        db.close()
        
    threads = []
    for _ in range(10):
        t = threading.Thread(target=run_selection)
        threads.append(t)
        
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    # Check consistency
    Session = sessionmaker(bind=db_engine)
    db = Session()
    mappings = db.query(AssetMapping).filter(AssetMapping.visual_intent_id == vi_id).all()
    
    assert len(mappings) == 2
    
    best = next(m for m in mappings if m.source_asset.source_url == "http://1")
    worst = next(m for m in mappings if m.source_asset.source_url == "http://2")
    
    assert best.selection_status.name == "AUTO_SELECTED"
    assert worst.selection_status.name == "REJECTED"
    
    assert best.selection_score > 0
    assert best.selection_reason is not None
