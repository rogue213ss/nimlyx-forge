from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from backend.database.db import Base

class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    projects = relationship("Project", back_populates="channel", cascade="all, delete-orphan")
