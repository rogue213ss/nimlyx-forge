import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from backend.services.media.acquisition import AcquisitionOrchestrator, TMP_DIR
from backend.services.media.ytdlp_wrapper import AcquisitionUnavailableError, AcquisitionError

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

def mock_probe_success(p):
    return True

def test_acq_timeout(db_session):
    asset, mapping = setup_mock_asset(db_session)
    def mock_dl(url, path):
        raise AcquisitionError("Timeout error")
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe_success)
    assert not orch.acquire(db_session, asset.id)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION # Remains approved for retry

def test_acq_http_429(db_session):
    asset, mapping = setup_mock_asset(db_session)
    def mock_dl(url, path):
        raise AcquisitionError("HTTP Error 429: Too Many Requests")
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe_success)
    assert not orch.acquire(db_session, asset.id)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION # Retryable

def test_acq_http_403(db_session):
    asset, mapping = setup_mock_asset(db_session)
    def mock_dl(url, path):
        raise AcquisitionUnavailableError("HTTP Error 403: Forbidden")
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe_success)
    assert not orch.acquire(db_session, asset.id)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.REJECTED # Unretryable

def test_acq_http_404(db_session):
    asset, mapping = setup_mock_asset(db_session)
    def mock_dl(url, path):
        raise AcquisitionUnavailableError("HTTP Error 404: Not Found")
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe_success)
    assert not orch.acquire(db_session, asset.id)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.REJECTED # Unretryable

def test_acq_http_5xx(db_session):
    asset, mapping = setup_mock_asset(db_session)
    def mock_dl(url, path):
        raise AcquisitionError("HTTP Error 500: Internal Server Error")
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe_success)
    assert not orch.acquire(db_session, asset.id)
    db_session.refresh(mapping)
    assert mapping.state == AssetState.APPROVED_FOR_ACQUISITION # Retryable
