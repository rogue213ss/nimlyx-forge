import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from backend.services.media.acquisition import AcquisitionOrchestrator
from backend.services.media.processing import MediaProcessingService
from backend.services.media.ytdlp_wrapper import AcquisitionError

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_acq_missing_ytdlp(db_session):
    asset = SourceAsset(id=1, source_url='http://mock', source_platform='yt')
    mapping = AssetMapping(id=1, source_asset_id=1, visual_intent_id=1, state=AssetState.APPROVED_FOR_ACQUISITION)
    db_session.add_all([asset, mapping])
    db_session.commit()
    
    def mock_dl(url, path): raise FileNotFoundError("No yt-dlp executable found")
    orch = AcquisitionOrchestrator(dl_func=mock_dl)
    assert not orch.acquire(db_session, 1)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION

def test_clip_missing_ffmpeg(db_session):
    asset = SourceAsset(id=1, source_url='mock', source_platform='yt', local_file_path='master.mp4', source_duration=10)
    mapping = AssetMapping(id=1, source_asset_id=1, visual_intent_id=1, state=AssetState.DOWNLOADED, start_timestamp=0, end_timestamp=5)
    db_session.add_all([asset, mapping])
    db_session.commit()
    
    def mock_clip(a,b,c,d): raise FileNotFoundError("No ffmpeg")
    proc = MediaProcessingService(clip_func=mock_clip)
    assert not proc.process_clip(db_session, 1)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.DOWNLOADED

def test_probe_missing_ffprobe(db_session):
    asset = SourceAsset(id=2, source_url='mock', source_platform='yt')
    mapping = AssetMapping(id=2, source_asset_id=2, visual_intent_id=2, state=AssetState.APPROVED_FOR_ACQUISITION)
    db_session.add_all([asset, mapping])
    db_session.commit()
    
    def mock_dl(url, path): pass
    def mock_probe(path): raise FileNotFoundError("No ffprobe")
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe)
    assert not orch.acquire(db_session, 2)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION

def test_acq_missing_node(db_session, monkeypatch):
    import shutil
    asset = SourceAsset(id=3, source_url='http://mock', source_platform='yt')
    mapping = AssetMapping(id=3, source_asset_id=3, visual_intent_id=3, state=AssetState.APPROVED_FOR_ACQUISITION)
    db_session.add_all([asset, mapping])
    db_session.commit()
    
    # We test the wrapper directly since Orchestrator swallows it into AcquisitionError
    from backend.services.media.ytdlp_wrapper import download_video
    
    def mock_get_executable(name):
        return 'node'
    monkeypatch.setattr('backend.services.media.ytdlp_wrapper.get_executable_path', mock_get_executable)
    monkeypatch.setattr(shutil, 'which', lambda x: None)
    
    with pytest.raises(EnvironmentError, match="JavaScript runtime \\(node\\) not found"):
        download_video('http://mock', 'out.mp4')
        
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION

def test_binary_resolver_node(monkeypatch):
    import os
    import shutil
    from backend.services.media.binary_resolver import get_executable_path
    
    # Mock exists to true for the explicit path
    original_exists = os.path.exists
    def mock_exists(path):
        if path == 'D:\\nodejs\\node.exe':
            return True
        return original_exists(path)
    
    monkeypatch.setattr(os.path, 'exists', mock_exists)
    
    # It should explicitly prefer the path
    assert get_executable_path('node') == 'D:\\nodejs\\node.exe'
