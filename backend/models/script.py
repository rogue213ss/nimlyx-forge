import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from backend.database.db import Base
from backend.models.enums import ScriptRunStatus, SentenceType, ReviewStatus

class ScriptRun(Base):
    __tablename__ = "script_runs"
    id = Column(Integer, primary_key=True, index=True)
    story_run_id = Column(Integer, ForeignKey("story_runs.id", name="fk_script_run_story_run"), nullable=False)
    status = Column(SQLEnum(ScriptRunStatus), default=ScriptRunStatus.PENDING)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    provider_name = Column(String(50), nullable=True)
    model_name = Column(String(50), nullable=True)
    configuration = Column(Text, nullable=True)
    prompt_version = Column(String(50), nullable=True)
    token_usage = Column(Text, nullable=True)

class ScriptSentence(Base):
    __tablename__ = "script_sentences"
    id = Column(Integer, primary_key=True, index=True)
    script_run_id = Column(Integer, ForeignKey("script_runs.id", name="fk_sentence_script_run"), nullable=False)
    narration_segment_id = Column(Integer, ForeignKey("narration_segments.id", name="fk_sentence_narration"), nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    text = Column(Text, nullable=False)
    original_text = Column(Text, nullable=False)
    sentence_type = Column(SQLEnum(SentenceType), default=SentenceType.FACTUAL)
    review_status = Column(SQLEnum(ReviewStatus), default=ReviewStatus.DRAFT)

class ClaimReference(Base):
    __tablename__ = "claim_references"
    id = Column(Integer, primary_key=True, index=True)
    script_sentence_id = Column(Integer, ForeignKey("script_sentences.id", name="fk_claimref_sentence"), nullable=False)
    research_claim_id = Column(Integer, ForeignKey("research_claims.id", name="fk_claimref_claim"), nullable=False)

