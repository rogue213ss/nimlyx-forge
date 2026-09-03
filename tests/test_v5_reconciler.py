import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from backend.services.media.reconciler import FilesystemReconciler
from backend.services.media.ffmpeg_wrapper import MediaValidationError

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_reconcile_missing_master(db_session):
    asset = SourceAsset(id=1, source_url='url', source_platform='yt', local_file_path='missing.mp4')
    m = AssetMapping(id=1, source_asset_id=1, visual_intent_id=1, state=AssetState.DOWNLOADED)
    db_session.add_all([asset, m])
    db_session.commit()
    
    rec = FilesystemReconciler()
    rec.reconcile(db_session)
    assert m.state == AssetState.APPROVED_FOR_ACQUISITION

def test_reconcile_corrupt_master(db_session):
    with open('corrupt_m.mp4', 'w') as f: f.write('bad')
    asset = SourceAsset(id=2, source_url='url2', source_platform='yt', local_file_path='corrupt_m.mp4')
    m = AssetMapping(id=2, source_asset_id=2, visual_intent_id=2, state=AssetState.DOWNLOADED)
    db_session.add_all([asset, m])
    db_session.commit()
    
    def mock_probe(p): raise MediaValidationError('Bad')
    rec = FilesystemReconciler(probe_func=mock_probe)
    rec.reconcile(db_session)
    assert m.state == AssetState.APPROVED_FOR_ACQUISITION
    os.remove('corrupt_m.mp4')

def test_reconcile_missing_clip(db_session):
    asset = SourceAsset(id=3, source_url='url3', source_platform='yt', local_file_path='good.mp4')
    m = AssetMapping(id=3, source_asset_id=3, visual_intent_id=3, state=AssetState.READY)
    db_session.add_all([asset, m])
    db_session.commit()
    
    rec = FilesystemReconciler()
    rec.reconcile(db_session)
    assert m.state == AssetState.DOWNLOADED

def test_reconcile_corrupt_clip(db_session):
    if not os.path.exists('downloads/clips'): os.makedirs('downloads/clips', exist_ok=True)
    with open('downloads/clips/4.mp4', 'w') as f: f.write('bad_clip')
    asset = SourceAsset(id=4, source_url='url4', source_platform='yt', local_file_path='good.mp4')
    m = AssetMapping(id=4, source_asset_id=4, visual_intent_id=4, state=AssetState.READY)
    db_session.add_all([asset, m])
    db_session.commit()
    
    def mock_probe(p):
        if '4.mp4' in p: raise MediaValidationError('Bad')
        return True
    rec = FilesystemReconciler(probe_func=mock_probe)
    rec.reconcile(db_session)
    assert m.state == AssetState.DOWNLOADED
    os.remove('downloads/clips/4.mp4')
