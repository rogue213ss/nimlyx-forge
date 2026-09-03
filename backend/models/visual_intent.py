from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.db import Base

class VisualIntent(Base):
    __tablename__ = "visual_intents"

    id = Column(Integer, primary_key=True, index=True)
    narration_segment_id = Column(Integer, ForeignKey("narration_segments.id"), index=True, nullable=False)
    description = Column(String, nullable=False)
    search_query = Column(String, nullable=True)

    narration_segment = relationship("NarrationSegment", back_populates="visual_intents")
    asset_mappings = relationship("AssetMapping", back_populates="visual_intent", cascade="all, delete-orphan")
