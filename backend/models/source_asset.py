from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
import datetime
from backend.database.db import Base
from .enums import CopyrightStatus

class SourceAsset(Base):
    __tablename__ = "source_assets"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String, nullable=False, unique=True, index=True)
    source_platform = Column(String, nullable=False)
    source_id = Column(String, nullable=True) # e.g. youtube video id
    source_channel = Column(String, nullable=True)
    title = Column(String, nullable=True)
    description = Column(String, nullable=True)
    source_duration = Column(Float, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    published_date = Column(DateTime, nullable=True)
    is_short = Column(Boolean, default=False)
    retrieved_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    local_file_path = Column(String, nullable=True)
    local_file_hash = Column(String, nullable=True)

    copyright_status = Column(Enum(CopyrightStatus), default=CopyrightStatus.UNKNOWN, nullable=False)
    usage_notes = Column(String, nullable=True)
    copyright_notes = Column(String, nullable=True)
    
    # We might just use string for approved_by right now
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    asset_mappings = relationship("AssetMapping", back_populates="source_asset")
