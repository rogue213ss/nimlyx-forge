from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.db import Base

class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=False)
    order_index = Column(Integer, nullable=False)
    title = Column(String, nullable=False)

    episode = relationship("Episode", back_populates="scenes")
    narration_segments = relationship("NarrationSegment", back_populates="scene", cascade="all, delete-orphan", order_by="NarrationSegment.order_index")
