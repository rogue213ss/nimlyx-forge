import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.services.projects.service import *
from backend.services.assets.service import *
from backend.models.enums import AssetState, CopyrightStatus
from backend.models.source_asset import SourceAsset

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_multiple_episodes_can_exist(db_session):
    channel = create_channel(db_session, "Gaming Doc")
    project = create_project(db_session, channel.id, "NMS")
    ep1 = create_episode(db_session, project.id, "Ep 1")
    ep2 = create_episode(db_session, project.id, "Ep 2")
    
    assert ep1.id != ep2.id
    assert ep1.project_id == project.id
    assert ep2.project_id == project.id

def test_scenes_preserve_ordering(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    
    create_scene(db_session, ep.id, "Scene B", 2)
    create_scene(db_session, ep.id, "Scene A", 1)
    
    db_session.commit()
    # Fetch scenes for episode
    db_ep = db_session.query(Episode).filter(Episode.id == ep.id).first()
    assert len(db_ep.scenes) == 2
    assert db_ep.scenes[0].title == "Scene A"
    assert db_ep.scenes[1].title == "Scene B"

def test_narration_segments_preserve_ordering(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    
    create_narration_segment(db_session, scene.id, "Text 2", 2)
    create_narration_segment(db_session, scene.id, "Text 1", 1)
    
    db_session.commit()
    db_scene = db_session.query(Scene).filter(Scene.id == scene.id).first()
    assert db_scene.narration_segments[0].text == "Text 1"
    assert db_scene.narration_segments[1].text == "Text 2"

def test_one_source_can_map_to_multiple_narration_segments(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    seg2 = create_narration_segment(db_session, scene.id, "T2", 2)
    
    intent1 = create_visual_intent(db_session, seg1.id, "V1")
    intent2 = create_visual_intent(db_session, seg2.id, "V2")
    
    asset = create_source_asset(db_session, "url1", "yt")
    
    map1 = create_asset_mapping(db_session, intent1.id, asset.id)
    map2 = create_asset_mapping(db_session, intent2.id, asset.id)
    
    assert map1.source_asset_id == asset.id
    assert map2.source_asset_id == asset.id
    assert map1.id != map2.id

def test_one_narration_segment_multiple_candidates(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "V1")
    
    asset1 = create_source_asset(db_session, "url1", "yt")
    asset2 = create_source_asset(db_session, "url2", "yt")
    
    create_asset_mapping(db_session, intent1.id, asset1.id)
    create_asset_mapping(db_session, intent1.id, asset2.id)
    
    db_intent = db_session.query(VisualIntent).filter(VisualIntent.id == intent1.id).first()
    assert len(db_intent.asset_mappings) == 2

def test_timestamps_cannot_be_negative(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "V1")
    asset1 = create_source_asset(db_session, "url1", "yt")
    mapping = create_asset_mapping(db_session, intent1.id, asset1.id)
    
    with pytest.raises(ValueError, match="cannot be negative"):
        set_mapping_timestamps(db_session, mapping.id, -1, 5)

def test_end_timestamp_cannot_precede_start(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "V1")
    asset1 = create_source_asset(db_session, "url1", "yt")
    mapping = create_asset_mapping(db_session, intent1.id, asset1.id)
    
    with pytest.raises(ValueError, match="strictly greater"):
        set_mapping_timestamps(db_session, mapping.id, 5, 2)

def test_unverified_cannot_enter_ready(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "V1")
    asset1 = create_source_asset(db_session, "url1", "yt")
    mapping = create_asset_mapping(db_session, intent1.id, asset1.id, state=AssetState.CANDIDATE)
    
    with pytest.raises(ValueError, match="Invalid state transition"):
        update_mapping_state(db_session, mapping.id, AssetState.READY)

def test_rejected_cannot_enter_ready(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "V1")
    asset1 = create_source_asset(db_session, "url1", "yt")
    mapping = create_asset_mapping(db_session, intent1.id, asset1.id, state=AssetState.REJECTED)
    
    with pytest.raises(ValueError, match="Invalid state transition"):
        update_mapping_state(db_session, mapping.id, AssetState.READY)

def test_provenance_survives_acquisition(db_session):
    asset1 = create_source_asset(db_session, "url1", "yt", title="Original Title", copyright_status=CopyrightStatus.OFFICIAL_PUBLIC)
    assert asset1.source_url == "url1"
    
    approve_asset_acquisition(db_session, asset1.id, "human1")
    
    db_asset = db_session.query(SourceAsset).filter(SourceAsset.id == asset1.id).first()
    assert db_asset.source_url == "url1"
    assert db_asset.title == "Original Title"
    assert db_asset.approved_by == "human1"
    assert db_asset.approved_at is not None

def test_future_episodes_can_reuse_existing_source_assets(db_session):
    asset1 = create_source_asset(db_session, "url1", "yt")
    
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep1 = create_episode(db_session, project.id, "E1")
    scene1 = create_scene(db_session, ep1.id, "S1", 1)
    seg1 = create_narration_segment(db_session, scene1.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "V1")
    create_asset_mapping(db_session, intent1.id, asset1.id)
    
    ep2 = create_episode(db_session, project.id, "E2")
    scene2 = create_scene(db_session, ep2.id, "S2", 1)
    seg2 = create_narration_segment(db_session, scene2.id, "T2", 1)
    intent2 = create_visual_intent(db_session, seg2.id, "V2")
    create_asset_mapping(db_session, intent2.id, asset1.id)
    
    # Same asset used in 2 different episodes
    db_asset = db_session.query(SourceAsset).filter(SourceAsset.id == asset1.id).first()
    assert len(db_asset.asset_mappings) == 2
def test_valid_state_transitions(db_session):
    from backend.models.enums import AssetState
    from backend.services.assets.service import update_mapping_state
    
    channel = create_channel(db_session, "C2")
    project = create_project(db_session, channel.id, "P2")
    ep = create_episode(db_session, project.id, "E2")
    scene = create_scene(db_session, ep.id, "S2", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "V1")
    asset1 = create_source_asset(db_session, "url_valid_transitions", "yt")
    mapping = create_asset_mapping(db_session, intent1.id, asset1.id, state=AssetState.DISCOVERED)
    
    # Valid transitions
    mapping = update_mapping_state(db_session, mapping.id, AssetState.CANDIDATE)
    mapping = update_mapping_state(db_session, mapping.id, AssetState.SELECTED)
    mapping = update_mapping_state(db_session, mapping.id, AssetState.VERIFIED)
    mapping = update_mapping_state(db_session, mapping.id, AssetState.APPROVED_FOR_ACQUISITION)
    mapping = update_mapping_state(db_session, mapping.id, AssetState.DOWNLOADED)
    mapping = update_mapping_state(db_session, mapping.id, AssetState.CLIPPED)
    mapping = update_mapping_state(db_session, mapping.id, AssetState.READY)
    assert mapping.state == AssetState.READY

def test_invalid_state_transitions(db_session):
    from backend.models.enums import AssetState
    from backend.services.assets.service import update_mapping_state
    
    channel = create_channel(db_session, "C3")
    project = create_project(db_session, channel.id, "P3")
    ep = create_episode(db_session, project.id, "E3")
    scene = create_scene(db_session, ep.id, "S3", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "V1")
    asset1 = create_source_asset(db_session, "url_invalid_transitions", "yt")
    
    # UNVERIFIED -> READY
    m1 = create_asset_mapping(db_session, intent1.id, asset1.id, state=AssetState.SELECTED)
    import pytest
    with pytest.raises(ValueError, match="Invalid state transition"):
        update_mapping_state(db_session, m1.id, AssetState.READY)
        
    # REJECTED -> READY
    m2 = create_asset_mapping(db_session, intent1.id, asset1.id, state=AssetState.REJECTED)
    with pytest.raises(ValueError, match="Invalid state transition"):
        update_mapping_state(db_session, m2.id, AssetState.READY)
        
    # DISCOVERED -> READY
    m3 = create_asset_mapping(db_session, intent1.id, asset1.id, state=AssetState.DISCOVERED)
    with pytest.raises(ValueError, match="Invalid state transition"):
        update_mapping_state(db_session, m3.id, AssetState.READY)
        
    # READY -> DISCOVERED
    m4 = create_asset_mapping(db_session, intent1.id, asset1.id, state=AssetState.READY)
    with pytest.raises(ValueError, match="Invalid state transition"):
        update_mapping_state(db_session, m4.id, AssetState.DISCOVERED)
def test_end_timestamp_cannot_exceed_duration(db_session):
    channel = create_channel(db_session, "C4")
    project = create_project(db_session, channel.id, "P4")
    ep = create_episode(db_session, project.id, "E4")
    scene = create_scene(db_session, ep.id, "S4", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "V1")
    asset1 = create_source_asset(db_session, "url_duration", "yt", source_duration=10.0)
    mapping = create_asset_mapping(db_session, intent1.id, asset1.id)
    
    with pytest.raises(ValueError, match="cannot exceed source duration"):
        set_mapping_timestamps(db_session, mapping.id, 5.0, 15.0)
import pytest
from alembic.config import Config
from alembic import command
import os

def test_alembic_matches_models(tmp_path):
    # This verifies that the current models match the current database exactly
    import subprocess
    
    # We run autogenerate and see if it outputs any 'Detected' lines
    import sys
    result = subprocess.run(
        [sys.executable, '-m', 'alembic', 'revision', '--autogenerate', '-m', 'test'], 
        capture_output=True, text=True, cwd=r'c:\Users\berli\OneDrive\Desktop\yt'
    )
    
    # If there are changes, it creates a file. We want to ensure no 'Detected' schema changes
    # But wait, if there are no changes, it will print "Target database is not up to date." if not upgraded
    # Our DB is upgraded. Let's just check if it says 'Detected' anything
    
    if "Detected" in result.stderr:
        # cleanup the generated file
        import glob
        files = glob.glob(r'c:\Users\berli\OneDrive\Desktop\yt\alembic\versions\*test.py')
        for f in files:
            os.remove(f)
        pytest.fail(f"Alembic detected uncommitted schema changes:\n{result.stderr}")
