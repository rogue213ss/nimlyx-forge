import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from backend.services.media.acquisition import AcquisitionOrchestrator

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_acq_path_safety(db_session, monkeypatch):
    # Attempt to inject adversarial characters into title and url
    # Ensure local path is strictly based on asset.id
    asset = SourceAsset(id=999, source_url='http://mock?param=../../evil', source_platform='yt', title='../../evil')
    mapping = AssetMapping(id=999, source_asset_id=999, visual_intent_id=999, state=AssetState.APPROVED_FOR_ACQUISITION)
    db_session.add_all([asset, mapping])
    db_session.commit()
    
    captured_paths = []
    def mock_dl(url, path):
        captured_paths.append(path)
        with open(path, 'w') as f: f.write('d')
    def mock_probe(p): return True
    def mock_replace(src, dst): captured_paths.append(dst)
    
    monkeypatch.setattr(os, 'replace', mock_replace)
    orch = AcquisitionOrchestrator(dl_func=mock_dl, probe_func=mock_probe)
    orch.acquire(db_session, 999)
    
    for p in captured_paths:
        # None of the paths should contain 'evil' or traversing structures from the metadata
        assert 'evil' not in p
        assert '999.mp4' in p
