import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from backend.services.media.acquisition import AcquisitionOrchestrator, TMP_DIR, DOWNLOAD_DIR
from backend.services.media.ytdlp_wrapper import AcquisitionUnavailableError, AcquisitionError
from backend.services.media.ffmpeg_wrapper import MediaValidationError

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def setup_mock_db(db):
    asset = SourceAsset(id=1, source_url="http://test", source_platform="yt")
    db.add(asset)
    db.commit()
    mapping = AssetMapping(id=1, source_asset_id=1, visual_intent_id=1, state=AssetState.APPROVED_FOR_ACQUISITION)
    db.add(mapping)
    db.commit()
    return asset, mapping

def test_acq_deleted_url(db_session):
    asset, mapping = setup_mock_db(db_session)
    def mock_dl(url, path): raise AcquisitionUnavailableError("Private video")
    
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=lambda p: {"duration": 10})
    success = orch.acquire(db_session, asset.id)
    
    assert not success
    db_session.refresh(mapping)
    assert mapping.state == AssetState.REJECTED

def test_acq_process_crash(db_session):
    asset, mapping = setup_mock_db(db_session)
    def mock_dl(url, path): 
        with open(path + ".part", "w") as f: f.write("partial data")
        raise AcquisitionError("Process crashed")
        
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=lambda p: {"duration": 10})
    success = orch.acquire(db_session, asset.id)
    
    assert not success
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION # Unchanged
    assert not os.path.exists(os.path.join(TMP_DIR, "1.mp4.part")) # Cleaned up

def test_acq_disk_full_on_move(db_session, monkeypatch):
    asset, mapping = setup_mock_db(db_session)
    def mock_dl(url, path):
        with open(path, "w") as f: f.write("data")
    
    def mock_probe(path): return {"duration": 10}
    
    def mock_replace(src, dst): raise OSError("No space left on device")
    monkeypatch.setattr(os, "replace", mock_replace)
    
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe)
    success = orch.acquire(db_session, asset.id)
    
    assert not success
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION
    assert not os.path.exists(os.path.join(TMP_DIR, "1.mp4"))

def test_acq_existing_valid_file(db_session):
    asset, mapping = setup_mock_db(db_session)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    final_path = os.path.join(DOWNLOAD_DIR, "1.mp4")
    with open(final_path, "w") as f: f.write("good data")
    
    called_dl = False
    def mock_dl(url, path):
        nonlocal called_dl
        called_dl = True
        
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=lambda p: {"duration": 10})
    success = orch.acquire(db_session, asset.id)
    
    assert success
    assert not called_dl # Skipped download
    db_session.refresh(mapping)
    assert mapping.state == AssetState.DOWNLOADED
    os.remove(final_path)

def test_acq_existing_corrupt_file(db_session):
    asset, mapping = setup_mock_db(db_session)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    final_path = os.path.join(DOWNLOAD_DIR, "1.mp4")
    with open(final_path, "w") as f: f.write("corrupt data")
    
    def mock_probe(path):
        if path == final_path:
            raise MediaValidationError("Corrupt file")
        return {"duration": 10} # tmp is good
        
    def mock_dl(url, path):
        with open(path, "w") as f: f.write("new good data")
        
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe)
    success = orch.acquire(db_session, asset.id)
    
    assert success
    db_session.refresh(mapping)
    assert mapping.state == AssetState.DOWNLOADED
    os.remove(final_path)

def test_acq_corrupt_download(db_session):
    asset, mapping = setup_mock_db(db_session)
    def mock_dl(url, path):
        with open(path, "w") as f: f.write("bad data")
    
    def mock_probe(path):
        raise MediaValidationError("Zero duration")
        
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe)
    success = orch.acquire(db_session, asset.id)
    
    assert not success
    db_session.refresh(mapping)
    assert mapping.state == AssetState.REJECTED # Failed validation after DL
    assert not os.path.exists(os.path.join(TMP_DIR, "1.mp4"))
