from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.db import Base

class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=False)
    order_index = Column(Integer, nullable=False)
    title = Column(String, nullable=False)

    story_run_id = Column(Integer, ForeignKey("story_runs.id"), nullable=True)
    story_beat_id = Column(Integer, ForeignKey("story_beats.id"), nullable=True)
    act_id = Column(Integer, ForeignKey("story_acts.id"), nullable=True)
    
    purpose = Column(String, nullable=True)
    emotional_intent = Column(String, nullable=True)
    visual_purpose = Column(String, nullable=True)
    estimated_duration_seconds = Column(Integer, nullable=True)
    episode = relationship("Episode", back_populates="scenes")
    narration_segments = relationship("NarrationSegment", back_populates="scene", cascade="all, delete-orphan", order_by="NarrationSegment.order_index")

