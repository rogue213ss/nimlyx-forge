from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import datetime
from backend.database.db import Base
from .enums import ClaimStatus

class ResearchClaim(Base):
    __tablename__ = 'research_claims'

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), index=True, nullable=False)
    research_run_id = Column(Integer, ForeignKey('research_runs.id'), index=True, nullable=False)
    claim_text = Column(String, nullable=False)
    category = Column(String, nullable=True)
    confidence = Column(String, nullable=True)
    confidence_reason = Column(String, nullable=True)
    confidence_signals = Column(String, nullable=True)
    temporal_context = Column(String, nullable=True)
    normalized_claim_text = Column(String, nullable=True)
    quality_classification = Column(String, nullable=True)
    status = Column(Enum(ClaimStatus), default=ClaimStatus.UNVERIFIED, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    research_run = relationship('ResearchRun', back_populates='claims')
    evidence = relationship('ResearchEvidence', back_populates='claim', cascade='all, delete-orphan')
