import os
import logging
from sqlalchemy.orm import Session
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState
from .acquisition import DOWNLOAD_DIR
from .processing import CLIPS_DIR
from .ffmpeg_wrapper import probe_video, MediaValidationError

logger = logging.getLogger(__name__)

class FilesystemReconciler:
    def __init__(self, probe_func=probe_video):
        self.probe_func = probe_func

    def reconcile(self, db: Session):
        """
        Scans DB records and downgrades states if filesystem is missing/corrupt.
        """
        # Case A & B: DB = DOWNLOADED, but master file missing or corrupt
        mappings = db.query(AssetMapping).filter(AssetMapping.state == AssetState.DOWNLOADED).all()
        for m in mappings:
            asset = m.source_asset
            if not asset or not asset.local_file_path or not os.path.exists(asset.local_file_path):
                logger.warning(f"Reconciler: Mapping {m.id} DOWNLOADED but master missing. Downgrading.")
                m.state = AssetState.APPROVED_FOR_ACQUISITION
                if asset: asset.local_file_path = None
                continue
                
            try:
                self.probe_func(asset.local_file_path)
            except MediaValidationError:
                logger.warning(f"Reconciler: Mapping {m.id} master is corrupt. Downgrading.")
                m.state = AssetState.APPROVED_FOR_ACQUISITION
                asset.local_file_path = None

        # Case D & E: DB = READY, but clip file missing or corrupt
        ready_mappings = db.query(AssetMapping).filter(AssetMapping.state == AssetState.READY).all()
        for m in ready_mappings:
            clip_path = os.path.join(CLIPS_DIR, f"{m.id}.mp4")
            if not os.path.exists(clip_path):
                logger.warning(f"Reconciler: Mapping {m.id} READY but clip missing. Downgrading.")
                m.state = AssetState.DOWNLOADED
                continue
                
            try:
                self.probe_func(clip_path)
            except MediaValidationError:
                logger.warning(f"Reconciler: Mapping {m.id} READY but clip corrupt. Downgrading.")
                m.state = AssetState.DOWNLOADED
                
        db.commit()
