from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from backend.database.db import Base
from .enums import RetrievalStatus

class ResearchSource(Base):
    __tablename__ = 'research_sources'

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), index=True, nullable=False)
    discovered_in_run_id = Column(Integer, ForeignKey('research_runs.id'), nullable=True)
    url = Column(String, nullable=False)
    canonical_url = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    publisher = Column(String, nullable=True)
    source_type = Column(String, nullable=True)
    reliability_tier = Column(String, nullable=True)
    scope = Column(String, nullable=True)
    published_date = Column(DateTime, nullable=True)
    retrieved_at = Column(DateTime, nullable=True)
    retrieval_status = Column(Enum(RetrievalStatus), default=RetrievalStatus.PENDING, nullable=False)
    error_info = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    content_text = Column(String, nullable=True)
    is_syndicated = Column(Boolean, default=False, nullable=False)

    project = relationship('Project')
    evidence = relationship('ResearchEvidence', back_populates='source', cascade='all, delete-orphan')
