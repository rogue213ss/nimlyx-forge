import os
import shutil
import logging
import time
from sqlalchemy.orm import Session
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from .ytdlp_wrapper import download_video, AcquisitionError, AcquisitionUnavailableError
from .ffmpeg_wrapper import probe_video, MediaValidationError

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../downloads/masters"))
TMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../downloads/tmp"))

class AcquisitionOrchestrator:
    def __init__(self, dl_func=download_video, probe_func=probe_video):
        self.dl_func = dl_func
        self.probe_func = probe_func
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(TMP_DIR, exist_ok=True)

    def _clean_tmp(self, asset_id: int):
        base_path = os.path.join(TMP_DIR, f"{asset_id}.mp4")
        for ext in ["", ".part", ".ytdl"]:
            p = base_path + ext
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

    def acquire(self, db: Session, asset_id: int) -> bool:
        asset = db.query(SourceAsset).filter(SourceAsset.id == asset_id).first()
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")

        mappings = db.query(AssetMapping).filter(
            AssetMapping.source_asset_id == asset_id,
            AssetMapping.state == AssetState.APPROVED_FOR_ACQUISITION
        ).all()
        
        if not mappings:
            return False

        final_path = os.path.join(DOWNLOAD_DIR, f"{asset.id}.mp4")
        tmp_path = os.path.join(TMP_DIR, f"{asset.id}.mp4")

        # Idempotency
        if os.path.exists(final_path):
            try:
                self.probe_func(final_path)
                asset_locked = db.query(SourceAsset).with_for_update().filter(SourceAsset.id == asset_id).first()
                for m in mappings:
                    m.state = AssetState.DOWNLOADED
                db.commit()
                return True
            except MediaValidationError:
                os.remove(final_path)

        # File-based Concurrency Lock
        lock_file = os.path.join(TMP_DIR, f"{asset.id}.lock")
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.close(fd)
        except FileExistsError:
            logger.info(f"Asset {asset.id} locked by another process.")
            return False

        try:
            self._clean_tmp(asset.id)
            self.dl_func(asset.source_url, tmp_path)
            self.probe_func(tmp_path)
            os.replace(tmp_path, final_path)

            asset_locked = db.query(SourceAsset).with_for_update().filter(SourceAsset.id == asset_id).first()
            asset_locked.local_file_path = final_path
            for m in mappings:
                m.state = AssetState.DOWNLOADED
            db.commit()
            self._clean_tmp(asset.id)
            return True
            
        except AcquisitionUnavailableError as e:
            logger.error(f"Asset {asset.id} unavailable: {e}")
            asset_locked = db.query(SourceAsset).with_for_update().filter(SourceAsset.id == asset_id).first()
            for m in mappings:
                m.state = AssetState.REJECTED
            db.commit()
            self._clean_tmp(asset.id)
            return False
            
        except MediaValidationError as e:
            logger.error(f"Asset {asset.id} corrupted: {e}")
            asset_locked = db.query(SourceAsset).with_for_update().filter(SourceAsset.id == asset_id).first()
            for m in mappings:
                m.state = AssetState.REJECTED
            db.commit()
            self._clean_tmp(asset.id)
            return False
            
        except Exception as e:
            logger.error(f"Asset {asset.id} failed: {e}")
            self._clean_tmp(asset.id)
            return False
            
        finally:
            if os.path.exists(lock_file):
                os.remove(lock_file)
