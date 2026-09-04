from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import datetime
from backend.database.db import Base
from .enums import EvidenceType

class ResearchEvidence(Base):
    __tablename__ = 'research_evidence'

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey('research_claims.id'), index=True, nullable=False)
    source_id = Column(Integer, ForeignKey('research_sources.id'), index=True, nullable=False)
    raw_text = Column(String, nullable=False)
    evidence_type = Column(Enum(EvidenceType), default=EvidenceType.SUPPORTING, nullable=False)
    evidence_quality = Column(String, nullable=True)
    evidence_quality_reason = Column(String, nullable=True)
    extracted_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    claim = relationship('ResearchClaim', back_populates='evidence')
    source = relationship('ResearchSource', back_populates='evidence')
