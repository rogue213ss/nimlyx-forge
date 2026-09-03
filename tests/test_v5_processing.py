import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from backend.services.media.processing import MediaProcessingService, CLIPS_DIR, TMP_DIR
from backend.services.media.ffmpeg_wrapper import MediaProcessingError, MediaValidationError

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def setup_mock_db(db_session, mapping_id=1):
    asset = SourceAsset(id=mapping_id, source_url="http://test", source_platform="yt", local_file_path="src.mp4", source_duration=100)
    mapping = AssetMapping(id=mapping_id, source_asset_id=mapping_id, visual_intent_id=mapping_id, state=AssetState.DOWNLOADED, start_timestamp=10.0, end_timestamp=20.0)
    db_session.add_all([asset, mapping])
    db_session.commit()
    return asset, mapping

def clean_file(path):
    if os.path.exists(path):
        os.remove(path)

def test_clip_invalid_timestamps(db_session):
    asset, mapping = setup_mock_db(db_session, 1)
    mapping.start_timestamp = 20.0
    mapping.end_timestamp = 10.0 # Invalid
    db_session.commit()

    svc = MediaProcessingService()
    assert not svc.process_clip(db_session, mapping.id)

def test_clip_ffmpeg_crash(db_session):
    asset, mapping = setup_mock_db(db_session, 2)
    clean_file(os.path.join(CLIPS_DIR, "2.mp4"))
    
    def mock_clip(src, dst, st, en):
        with open(dst, "w") as f: f.write("part")
        raise MediaProcessingError("Crash")

    svc = MediaProcessingService(clip_func=mock_clip, probe_func=lambda p: {"duration": 10})
    success = svc.process_clip(db_session, mapping.id)

    assert not success
    db_session.refresh(mapping)
    assert mapping.state == AssetState.DOWNLOADED # Remains downloaded for retry
    assert not os.path.exists(os.path.join(TMP_DIR, "clip_2.mp4"))

def test_clip_zero_duration(db_session):
    asset, mapping = setup_mock_db(db_session, 3)
    clean_file(os.path.join(CLIPS_DIR, "3.mp4"))
    
    def mock_clip(src, dst, st, en):
        with open(dst, "w") as f: f.write("empty")

    def mock_probe(p):
        raise MediaValidationError("Zero duration")

    svc = MediaProcessingService(clip_func=mock_clip, probe_func=mock_probe)
    success = svc.process_clip(db_session, mapping.id)

    assert not success
    db_session.refresh(mapping)
    assert mapping.state == AssetState.REJECTED
    assert not os.path.exists(os.path.join(TMP_DIR, "clip_3.mp4"))

def test_clip_idempotent(db_session):
    asset, mapping = setup_mock_db(db_session, 4)
    final_path = os.path.join(CLIPS_DIR, "4.mp4")
    with open(final_path, "w") as f: f.write("valid_clip")

    def mock_clip(src, dst, st, en):
        raise AssertionError("Should not be called")

    svc = MediaProcessingService(clip_func=mock_clip, probe_func=lambda p: {"duration": 10.0}) # 20 - 10 = 10
    success = svc.process_clip(db_session, mapping.id)

    assert success
    db_session.refresh(mapping)
    assert mapping.state == AssetState.READY
    clean_file(final_path)
