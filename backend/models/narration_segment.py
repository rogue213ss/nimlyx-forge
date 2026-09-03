from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.db import Base

class NarrationSegment(Base):
    __tablename__ = "narration_segments"

    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(Integer, ForeignKey("scenes.id"), index=True, nullable=False)
    order_index = Column(Integer, nullable=False)
    text = Column(String, nullable=False)

    scene = relationship("Scene", back_populates="narration_segments")
    visual_intents = relationship("VisualIntent", back_populates="narration_segment", cascade="all, delete-orphan")
