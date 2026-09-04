from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import datetime
from backend.database.db import Base
from .enums import ResearchRunStatus

class ResearchRun(Base):
    __tablename__ = 'research_runs'

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), index=True, nullable=False)
    status = Column(Enum(ResearchRunStatus), default=ResearchRunStatus.RUNNING, nullable=False)
    configuration = Column(String, nullable=True) # Canonical JSON
    stats = Column(String, nullable=True) # Canonical JSON
    started_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    project = relationship('Project')
    claims = relationship('ResearchClaim', back_populates='research_run', cascade='all, delete-orphan')
