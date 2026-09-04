from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.db import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    topic = Column(String, nullable=True)

    channel = relationship("Channel", back_populates="projects")
    episodes = relationship("Episode", back_populates="project", cascade="all, delete-orphan")
