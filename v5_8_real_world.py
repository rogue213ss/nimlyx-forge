import os
import sys
import json
import argparse
import urllib.parse
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from backend.services.media.acquisition import AcquisitionOrchestrator
from backend.services.media.processing import MediaProcessingService
from backend.services.media.ffmpeg_wrapper import probe_video
from backend.services.media.reconciler import FilesystemReconciler

def is_valid_youtube_url(url: str) -> bool:
    if not url:
        return False
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        return False
    if parsed.netloc not in ("www.youtube.com", "youtube.com", "youtu.be"):
        return False
    if parsed.netloc in ("www.youtube.com", "youtube.com"):
        query = urllib.parse.parse_qs(parsed.query)
        if "v" not in query or not query["v"]:
            return False
    return True

def get_hash(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def dump_ffprobe(path):
    try:
        return probe_video(path)
    except Exception as e:
        return str(e)

def setup_source(db, src_id, url, title, channel, copyright_status):
    src = db.query(SourceAsset).filter(SourceAsset.id == src_id).first()
    if not src:
        src = SourceAsset(
            id=src_id,
            source_url=url,
            source_platform='yt',
            title=title,
            source_channel=channel,
            copyright_status=copyright_status,
            retrieved_at=datetime.now(timezone.utc)
        )
        db.add(src)
    else:
        if src.source_url != url or src.copyright_status != copyright_status:
            raise ValueError(
                f"Existing SourceAsset {src_id} provenance conflict! "
                f"Expected: {url}, Found: {src.source_url}. "
                f"(Hint: Delete v5_8_real_world.db to start fresh)"
            )
            
    mapping = db.query(AssetMapping).filter(AssetMapping.id == src_id).first()
    if not mapping:
        mapping = AssetMapping(
            id=src_id,
            source_asset_id=src_id,
            visual_intent_id=src_id,
            state=AssetState.APPROVED_FOR_ACQUISITION
        )
        db.add(mapping)
    else:
        mapping.state = AssetState.APPROVED_FOR_ACQUISITION
        
    db.commit()
    return src, mapping

def get_urls(args_list=None):
    parser = argparse.ArgumentParser(description="V5 Real World Validation Runner")
    parser.add_argument('--source-a-url', type=str, help='YouTube URL for Source A (Official Trailer)')
    parser.add_argument('--source-b-url', type=str, help='YouTube URL for Source B (Gameplay)')
    args = parser.parse_args(args_list)

    url_a = args.source_a_url or os.environ.get('V5_SOURCE_A_URL') or "https://www.youtube.com/watch?v=n0E96p_MFRA"
    url_b = args.source_b_url or os.environ.get('V5_SOURCE_B_URL') or "https://www.youtube.com/watch?v=0hWbkz3661U"

    if not is_valid_youtube_url(url_a):
        raise ValueError(f"Invalid YouTube URL for Source A: {url_a}")
    if not is_valid_youtube_url(url_b):
        raise ValueError(f"Invalid YouTube URL for Source B: {url_b}")
    
    return url_a, url_b

def run():
    try:
        url_a, url_b = get_urls()
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print("--- 1. PRE-FLIGHT ---")
    print(f"Python: {sys.version}")
    print(f"Source A URL: {url_a}")
    print(f"Source B URL: {url_b}")
    
    engine = create_engine('sqlite:///v5_8_real_world.db')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    title_a = "Provided Source A (Trailer)" if url_a != "https://www.youtube.com/watch?v=n0E96p_MFRA" else "No Man's Sky - E3 2014 Trailer"
    channel_a = "Provided Channel A" if url_a != "https://www.youtube.com/watch?v=n0E96p_MFRA" else "PlayStation"
    
    title_b = "Provided Source B (Gameplay)" if url_b != "https://www.youtube.com/watch?v=0hWbkz3661U" else "No Man's Sky - Launch Trailer"
    channel_b = "Provided Channel B" if url_b != "https://www.youtube.com/watch?v=0hWbkz3661U" else "IGN"
    
    setup_source(db, 101, url_a, title_a, channel_a, "OFFICIAL_PUBLIC")
    setup_source(db, 102, url_b, title_b, channel_b, "FAIR_USE_CANDIDATE")

    map_a = db.query(AssetMapping).filter_by(id=101).one()
    map_b = db.query(AssetMapping).filter_by(id=102).one()

    print("\n--- PROVENANCE AUDIT ---")
    src_a = db.query(SourceAsset).filter_by(id=101).one()
    print(f"ID: {src_a.id} | Title: {src_a.title} | Channel: {src_a.source_channel} | Copyright: {src_a.copyright_status}")
    src_b = db.query(SourceAsset).filter_by(id=102).one()
    print(f"ID: {src_b.id} | Title: {src_b.title} | Channel: {src_b.source_channel} | Copyright: {src_b.copyright_status}")

    print("\n--- 3/4. REAL ACQUISITION ---")
    orch = AcquisitionOrchestrator()
    print(f"Acquiring Source A ({url_a})...")
    res_a = orch.acquire(db, 101)
    print(f"Result A: {res_a}")
    db.refresh(map_a)
    print(f"DB State A: {map_a.state}")
    
    print(f"\nAcquiring Source B ({url_b})...")
    res_b = orch.acquire(db, 102)
    print(f"Result B: {res_b}")
    db.refresh(map_b)
    print(f"DB State B: {map_b.state}")

    print("\n--- 5. REAL FFPROBE VALIDATION ---")
    path_a = f"downloads/masters/101.mp4"
    if os.path.exists(path_a):
        print(f"Master A Size: {os.path.getsize(path_a)}")
        print(f"Master A Hash: {get_hash(path_a)}")
        print(f"Master A Probe: {json.dumps(dump_ffprobe(path_a), indent=2)}")

    path_b = f"downloads/masters/102.mp4"
    if os.path.exists(path_b):
        print(f"Master B Size: {os.path.getsize(path_b)}")
        print(f"Master B Hash: {get_hash(path_b)}")
        print(f"Master B Probe: {json.dumps(dump_ffprobe(path_b), indent=2)}")

    print("\n--- 6/7. REAL CLIPPING ---")
    proc = MediaProcessingService()
    if res_a or os.path.exists(path_a):
        map_a.start_timestamp = 10.0
        map_a.end_timestamp = 25.0
        db.commit()
        print("Clipping A (10s - 25s)...")
        clip_res_a = proc.process_clip(db, 101)
        print(f"Clip A Result: {clip_res_a}")
        db.refresh(map_a)
        print(f"DB State A: {map_a.state}")
        
        path_clip_a = f"downloads/clips/101.mp4"
        if os.path.exists(path_clip_a):
            print(f"Clip A Size: {os.path.getsize(path_clip_a)}")
            print(f"Clip A Hash: {get_hash(path_clip_a)}")
            print(f"Clip A Probe: {json.dumps(dump_ffprobe(path_clip_a), indent=2)}")

    print("\n--- 9. DB FILESYSTEM AUDIT (RECONCILIATION) ---")
    path_clip_a = f"downloads/clips/101.mp4"
    if os.path.exists(path_clip_a):
        print("Removing Clip A to test Reconciler...")
        os.remove(path_clip_a)
        rec = FilesystemReconciler()
        rec.reconcile(db)
        db.refresh(map_a)
        print(f"State after Reconcile (Missing Clip): {map_a.state}")
        
        print("Restoring Clip A...")
        proc.process_clip(db, 101)
        db.refresh(map_a)
        print(f"State after Restore (READY expected): {map_a.state}")

    print("\n--- 10. IDEMPOTENCY ---")
    if os.path.exists(path_a):
        print("Re-acquiring Source A (Valid Master Exists)...")
        idem_acq = orch.acquire(db, 101)
        db.refresh(map_a)
        if idem_acq:
            print("Idempotent Acquire A: WORK PERFORMED (Unexpected)")
        elif map_a.state == AssetState.DOWNLOADED:
            print("Idempotent Acquire A: NO-OP / ALREADY SATISFIED")
        else:
            print("Idempotent Acquire A: FAILURE")
            
    if os.path.exists(path_clip_a):
        print("Re-clipping Source A (Valid Clip Exists)...")
        idem_clip = proc.process_clip(db, 101)
        db.refresh(map_a)
        if idem_clip:
            print("Idempotent Clip A: WORK PERFORMED (Unexpected)")
        elif map_a.state == AssetState.READY:
            print("Idempotent Clip A: NO-OP / ALREADY SATISFIED")
        else:
            print("Idempotent Clip A: FAILURE")

if __name__ == '__main__':
    run()
