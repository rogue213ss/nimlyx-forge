import pytest
import os
import threading
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from backend.services.media.processing import MediaProcessingService

def test_concurrent_clipping():
    import os
    if os.path.exists('v5_concurrent_test.db'): os.remove('v5_concurrent_test.db')
    if os.path.exists('downloads/clips/1.mp4'): os.remove('downloads/clips/1.mp4')
    import uuid
    db_name = f'v5_concurrent_{uuid.uuid4().hex}.db'
    engine = create_engine(f'sqlite:///{db_name}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    asset = SourceAsset(id=1, source_url='mock', source_platform='yt', local_file_path='master.mp4', source_duration=100)
    mapping = AssetMapping(id=1, source_asset_id=1, visual_intent_id=1, state=AssetState.DOWNLOADED, start_timestamp=0, end_timestamp=10)
    db.add_all([asset, mapping])
    db.commit()
    
    def mock_clip(a, b, c, d):
        import time
        time.sleep(1.0)
        with open(b, 'w') as f: f.write('data')
        
    def mock_probe(p):
        return {"duration": 10.0}
        
    def worker(results, index):
        s = Session()
        proc = MediaProcessingService(clip_func=mock_clip, probe_func=mock_probe)
        results[index] = proc.process_clip(s, 1)
        s.close()
        
    results = [None, None]
    t1 = threading.Thread(target=worker, args=(results, 0))
    t2 = threading.Thread(target=worker, args=(results, 1))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    # One should succeed, one should gracefully fail/skip
    assert results.count(True) == 1
    assert results.count(False) == 1
    
    db.refresh(mapping)
    assert mapping.state == AssetState.READY
    db.close()
