from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.db import Base

class NarrationSegment(Base):
    __tablename__ = "narration_segments"

    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(Integer, ForeignKey("scenes.id"), index=True, nullable=False)
    order_index = Column(Integer, nullable=False)
    text = Column(String, nullable=False)

    is_brief = Column(Integer, default=0)
    purpose = Column(String, nullable=True)
    must_communicate = Column(String, nullable=True)
    must_not_claim = Column(String, nullable=True)
    tone = Column(String, nullable=True)
    estimated_duration_seconds = Column(Integer, nullable=True)
    supporting_claims = Column(String, nullable=True)
    scene = relationship("Scene", back_populates="narration_segments")
    visual_intents = relationship("VisualIntent", back_populates="narration_segment", cascade="all, delete-orphan")

