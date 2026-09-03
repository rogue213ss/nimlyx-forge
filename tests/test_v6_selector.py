import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.visual_intent import VisualIntent
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import SelectionStatus, AssetState
from backend.services.selection.selector import FootageSelector
from backend.database.db import Base

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def setup_data(db):
    vi = VisualIntent(description="Test intent", narration_segment_id=1)
    db.add(vi)
    
    # Add sources with various properties for tie-breaking
    # 1. High score
    sa1 = SourceAsset(title="test", source_url="http://1", source_platform="yt", source_channel="playstation", published_date=datetime.datetime(2020, 1, 1))
    # 2. Same score, earlier date
    sa2 = SourceAsset(title="test", source_url="http://2", source_platform="yt", source_channel="playstation", published_date=datetime.datetime(2019, 1, 1))
    # 3. Low score
    sa3 = SourceAsset(title="test", source_url="http://3", source_platform="yt", source_channel="random", published_date=datetime.datetime(2021, 1, 1))
    
    db.add_all([sa1, sa2, sa3])
    db.commit()
    
    # Assuming V4 gives base scores
    m1 = AssetMapping(visual_intent_id=vi.id, source_asset_id=sa1.id, relevance_score=90.0, state=AssetState.CANDIDATE)
    m2 = AssetMapping(visual_intent_id=vi.id, source_asset_id=sa2.id, relevance_score=90.0, state=AssetState.CANDIDATE)
    m3 = AssetMapping(visual_intent_id=vi.id, source_asset_id=sa3.id, relevance_score=20.0, state=AssetState.CANDIDATE)
    
    db.add_all([m1, m2, m3])
    db.commit()
    return vi.id, [m1.id, m2.id, m3.id]

def test_selector_ranking_and_tie_breaking(db_session):
    vi_id, _ = setup_data(db_session)
    selector = FootageSelector(db_session)
    
    best = selector.select_best_for_intent(vi_id)
    assert best is not None
    assert best.selection_status == SelectionStatus.AUTO_SELECTED
    assert best.confidence_level == "HIGH"
    
    # Tie breaking: sa1 vs sa2. They both have 90 base + 10 official. 
    # sa1 is 2020, sa2 is 2019. Sort is pub_date DESC, so 2020 should win.
    assert best.source_asset.source_url == "http://1"
    
def test_selector_idempotency(db_session):
    vi_id, mapping_ids = setup_data(db_session)
    selector = FootageSelector(db_session)
    
    best1 = selector.select_best_for_intent(vi_id)
    score1 = best1.selection_score
    reason1 = best1.selection_reason
    
    best2 = selector.select_best_for_intent(vi_id)
    
    assert best1.id == best2.id
    assert score1 == best2.selection_score
    assert reason1 == best2.selection_reason
    
    # Ensure others were rejected
    all_mappings = db_session.query(AssetMapping).filter(AssetMapping.visual_intent_id == vi_id).all()
    for m in all_mappings:
        if m.id == best1.id:
            assert m.selection_status == SelectionStatus.AUTO_SELECTED
        elif m.source_asset.source_url == "http://2":
            assert m.selection_status == SelectionStatus.NEEDS_REVIEW # Still HIGH/MEDIUM
        elif m.source_asset.source_url == "http://3":
            assert m.selection_status == SelectionStatus.REJECTED # LOW
            
        assert m.state == AssetState.CANDIDATE # V1-V5 state machine remains completely independent!
