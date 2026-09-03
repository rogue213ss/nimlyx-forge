import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.visual_intent import VisualIntent
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
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

from backend.models.channel import Channel
from backend.models.project import Project
from backend.models.episode import Episode
from backend.models.scene import Scene
from backend.models.narration_segment import NarrationSegment

import sqlalchemy as sa
def get_dummy_narr_id(db):
    conn = db.connection()
    # just insert 1 of each to avoid fk errors
    conn.execute(sa.text("INSERT INTO channels (name) VALUES ('c')"))
    conn.execute(sa.text("INSERT INTO projects (channel_id, name) VALUES (1, 'p')"))
    conn.execute(sa.text("INSERT INTO episodes (project_id, name) VALUES (1, 'e')"))
    conn.execute(sa.text("INSERT INTO scenes (episode_id, order_index, title) VALUES (1, 1, 's')"))
    conn.execute(sa.text("INSERT INTO narration_segments (scene_id, order_index, text) VALUES (1, 1, 'n')"))
    return 1

def _unused(db):
    ch = Channel(name="c")
    pr = Project(name="p", channel=ch)
    ep = Episode(name="e", project=pr, order_index=1)
    sc = Scene(title="s", episode=ep, order_index=1)
    na = NarrationSegment(text="n", scene=sc, order_index=1)
    db.add_all([ch, pr, ep, sc, na])
    db.commit()
    return na.id

def setup_nms_assets(db):
    assets = [
        # 1. Old E3 trailer
        SourceAsset(id=1, source_url="1", source_platform="yt", title="No Man's Sky - E3 2014 Gameplay", description="Early concept universe", published_date=datetime.datetime(2014, 6, 1), source_channel="playstation"),
        # 2. 2016 Launch Hype
        SourceAsset(id=2, source_url="2", source_platform="yt", title="No Man's Sky Launch Trailer", description="Explore the universe on launch day", published_date=datetime.datetime(2016, 8, 8), source_channel="hellogamestube"),
        # 3. Disappointment Review
        SourceAsset(id=3, source_url="3", source_platform="yt", title="Why No Man's Sky Failed", description="Launch day disaster", published_date=datetime.datetime(2016, 8, 20), source_channel="ign"),
        # 4. Foundation Update
        SourceAsset(id=4, source_url="4", source_platform="yt", title="No Man's Sky Foundation Update", description="Base building", published_date=datetime.datetime(2016, 11, 27), source_channel="hellogamestube"),
        # 5. Modern 2024 Worlds Part 1 Update
        SourceAsset(id=5, source_url="5", source_platform="yt", title="No Man's Sky Worlds Part 1 Update Trailer", description="New planetary generation", published_date=datetime.datetime(2024, 7, 17), source_channel="hellogamestube"),
        # 6. Unrelated
        SourceAsset(id=6, source_url="6", source_platform="yt", title="Minecraft Gameplay", description="Building a house", published_date=datetime.datetime(2015, 1, 1), source_channel="ign")
    ]
    for a in assets:
        db.add(a)
    db.commit()

def test_intent_a_early_concept(db_session):
    setup_nms_assets(db_session)
    vi = VisualIntent(narration_segment_id=get_dummy_narr_id(db_session), description="The impossible scale of the dream", preferred_year=2014)
    db_session.add(vi)
    db_session.commit()
    
    # Map all
    for i in range(1, 7):
        db_session.add(AssetMapping(visual_intent_id=vi.id, source_asset_id=i, relevance_score=50.0))
    db_session.commit()
    
    best = FootageSelector(db_session).select_best_for_intent(vi.id)
    assert best.source_asset_id == 1 # E3 2014

def test_intent_b_launch_hype(db_session):
    setup_nms_assets(db_session)
    vi = VisualIntent(narration_segment_id=get_dummy_narr_id(db_session), description="Launch day hype", preferred_year=2016, preferred_content_types='["trailer"]')
    db_session.add(vi)
    db_session.commit()
    
    for i in range(1, 7):
        db_session.add(AssetMapping(visual_intent_id=vi.id, source_asset_id=i, relevance_score=50.0))
    db_session.commit()
    
    best = FootageSelector(db_session).select_best_for_intent(vi.id)
    assert best.source_asset_id == 2 # 2016 Launch Trailer

def test_intent_c_post_launch_rebuilding(db_session):
    setup_nms_assets(db_session)
    vi = VisualIntent(narration_segment_id=get_dummy_narr_id(db_session), description="Hello Games quietly went to work on rebuilding", preferred_content_types='["update"]')
    db_session.add(vi)
    db_session.commit()
    
    for i in range(1, 7):
        db_session.add(AssetMapping(visual_intent_id=vi.id, source_asset_id=i, relevance_score=50.0))
    db_session.commit()
    
    # Needs to prefer Update over regular gameplay or launch trailer
    best = FootageSelector(db_session).select_best_for_intent(vi.id)
    # Could be Foundation or Worlds. Let's see which has higher date or score. 
    # Since they both have "update", they both get the bonus. 2024 has higher pub_date.
    assert best.source_asset_id == 5

def test_intent_d_modern(db_session):
    setup_nms_assets(db_session)
    vi = VisualIntent(narration_segment_id=get_dummy_narr_id(db_session), description="Modern generation", preferred_year=2024)
    db_session.add(vi)
    db_session.commit()
    
    for i in range(1, 7):
        db_session.add(AssetMapping(visual_intent_id=vi.id, source_asset_id=i, relevance_score=50.0))
    db_session.commit()
    
    best = FootageSelector(db_session).select_best_for_intent(vi.id)
    assert best.source_asset_id == 5 # Worlds Update
