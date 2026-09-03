import pytest
import os
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from backend.services.media.acquisition import AcquisitionOrchestrator, TMP_DIR, DOWNLOAD_DIR

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def setup_mock_asset(db_session, asset_id=1):
    asset = SourceAsset(id=asset_id, source_url='http://mock', source_platform='yt')
    mapping = AssetMapping(id=asset_id, source_asset_id=asset_id, visual_intent_id=asset_id, state=AssetState.APPROVED_FOR_ACQUISITION)
    db_session.add_all([asset, mapping])
    db_session.commit()
    return asset, mapping

def mock_probe_success(p): return True

def test_acq_permission_denied(db_session):
    asset, mapping = setup_mock_asset(db_session)
    def mock_dl(url, path):
        raise PermissionError("Permission denied")
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe_success)
    assert not orch.acquire(db_session, asset.id)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION

def test_acq_missing_dest_dir(db_session, monkeypatch):
    asset, mapping = setup_mock_asset(db_session)
    def mock_dl(url, path):
        with open(path, 'w') as f: f.write('data')
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe_success)
    # Simulate missing dest dir by patching os.replace to throw FileNotFoundError
    def mock_replace(src, dst): raise FileNotFoundError("Dest dir missing")
    monkeypatch.setattr(os, 'replace', mock_replace)
    assert not orch.acquire(db_session, asset.id)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION
    assert not os.path.exists(os.path.join(TMP_DIR, f"{asset.id}.mp4")) # Cleanup works

def test_acq_dest_disappearing(db_session, monkeypatch):
    # If the destination dir is removed between checks
    asset, mapping = setup_mock_asset(db_session)
    def mock_dl(url, path):
        with open(path, 'w') as f: f.write('data')
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe_success)
    def mock_replace(src, dst): raise OSError("Disappeared")
    monkeypatch.setattr(os, 'replace', mock_replace)
    assert not orch.acquire(db_session, asset.id)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION
    assert not os.path.exists(os.path.join(TMP_DIR, f"{asset.id}.mp4"))
