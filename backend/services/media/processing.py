import os
import logging
from sqlalchemy.orm import Session
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from .ffmpeg_wrapper import clip_video, probe_video, MediaProcessingError, MediaValidationError

logger = logging.getLogger(__name__)

CLIPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../downloads/clips"))
TMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../downloads/tmp"))

class MediaProcessingService:
    def __init__(self, clip_func=clip_video, probe_func=probe_video):
        self.clip_func = clip_func
        self.probe_func = probe_func
        os.makedirs(CLIPS_DIR, exist_ok=True)
        os.makedirs(TMP_DIR, exist_ok=True)

    def _clean_tmp(self, mapping_id: int):
        p = os.path.join(TMP_DIR, f"clip_{mapping_id}.mp4")
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

    def process_clip(self, db: Session, mapping_id: int) -> bool:
        mapping = db.query(AssetMapping).filter(AssetMapping.id == mapping_id).first()
        if not mapping or mapping.state != AssetState.DOWNLOADED:
            return False
            
        asset = mapping.source_asset
        if not asset or not asset.local_file_path:
            return False

        if mapping.start_timestamp is None or mapping.end_timestamp is None:
            return False
        if mapping.start_timestamp < 0 or mapping.start_timestamp >= mapping.end_timestamp:
            return False
        if asset.source_duration and mapping.end_timestamp > asset.source_duration:
            return False

        final_path = os.path.join(CLIPS_DIR, f"{mapping.id}.mp4")
        tmp_path = os.path.join(TMP_DIR, f"clip_{mapping.id}.mp4")
        expected_dur = mapping.end_timestamp - mapping.start_timestamp

        if os.path.exists(final_path):
            try:
                probe = self.probe_func(final_path)
                if abs(probe["duration"] - expected_dur) < 0.1:
                    locked = db.query(AssetMapping).with_for_update().filter(AssetMapping.id == mapping_id).first()
                    locked.state = AssetState.READY
                    db.commit()
                    return True
            except MediaValidationError:
                os.remove(final_path)

        lock_file = os.path.join(TMP_DIR, f"clip_{mapping.id}.lock")
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
        except FileExistsError:
            return False

        try:
            self._clean_tmp(mapping.id)
            self.clip_func(asset.local_file_path, tmp_path, mapping.start_timestamp, mapping.end_timestamp)
            self.probe_func(tmp_path)
            os.replace(tmp_path, final_path)

            locked = db.query(AssetMapping).with_for_update().filter(AssetMapping.id == mapping_id).first()
            locked.state = AssetState.READY
            db.commit()
            return True
            
        except MediaValidationError as e:
            logger.error(f"Produced clip validation failed: {e}")
            locked = db.query(AssetMapping).with_for_update().filter(AssetMapping.id == mapping_id).first()
            locked.state = AssetState.REJECTED
            db.commit()
            self._clean_tmp(mapping.id)
            return False
            
        except Exception as e:
            logger.error(f"Clipping failure: {e}")
            self._clean_tmp(mapping.id)
            return False
            
        finally:
            if os.path.exists(lock_file):
                os.remove(lock_file)
