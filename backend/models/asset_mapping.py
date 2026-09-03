from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship
from backend.database.db import Base
from .enums import AssetState

class AssetMapping(Base):
    __tablename__ = "asset_mappings"

    id = Column(Integer, primary_key=True, index=True)
    visual_intent_id = Column(Integer, ForeignKey("visual_intents.id"), index=True, nullable=False)
    source_asset_id = Column(Integer, ForeignKey("source_assets.id"), index=True, nullable=False)
    
    start_timestamp = Column(Float, nullable=True)
    end_timestamp = Column(Float, nullable=True)
    
    state = Column(Enum(AssetState), default=AssetState.DISCOVERED, nullable=False)
    relevance_score = Column(Float, nullable=True)

    visual_intent = relationship("VisualIntent", back_populates="asset_mappings")
    source_asset = relationship("SourceAsset", back_populates="asset_mappings")
