from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from backend.database.db import Base
from backend.models.enums import StoryRunStatus, DatePrecision, NarrativeRole
import datetime

class StoryRun(Base):
    __tablename__ = "story_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True, nullable=False)
    episode_id = Column(Integer, ForeignKey("episodes.id"), index=True, nullable=False)
    research_run_id = Column(Integer, ForeignKey("research_runs.id"), index=True, nullable=False)
    status = Column(String, nullable=False, default=StoryRunStatus.RUNNING.value)
    
    central_question = Column(String, nullable=True)
    story_promise = Column(String, nullable=True)
    emotional_arc = Column(String, nullable=True)
    
    stats = Column(String, nullable=True) # JSON
    configuration = Column(String, nullable=True) # JSON
    quality_score = Column(String, nullable=True) # JSON
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    acts = relationship("StoryAct", back_populates="story_run", cascade="all, delete-orphan", order_by="StoryAct.order_index")
    events = relationship("StoryEvent", back_populates="story_run", cascade="all, delete-orphan")
    beats = relationship("StoryBeat", back_populates="story_run", cascade="all, delete-orphan")

class StoryAct(Base):
    __tablename__ = "story_acts"

    id = Column(Integer, primary_key=True, index=True)
    story_run_id = Column(Integer, ForeignKey("story_runs.id"), index=True, nullable=False)
    order_index = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    narrative_question = Column(String, nullable=True)

    story_run = relationship("StoryRun", back_populates="acts")
    beats = relationship("StoryBeat", back_populates="act", order_by="StoryBeat.order_index")

class StoryEvent(Base):
    __tablename__ = "story_events"

    id = Column(Integer, primary_key=True, index=True)
    story_run_id = Column(Integer, ForeignKey("story_runs.id"), index=True, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(String, nullable=True)
    event_date = Column(String, nullable=True)
    date_precision = Column(String, nullable=False, default=DatePrecision.UNKNOWN.value)
    importance_score = Column(Integer, nullable=False, default=0)
    category = Column(String, nullable=True)
    
    story_run = relationship("StoryRun", back_populates="events")

class StoryBeat(Base):
    __tablename__ = "story_beats"

    id = Column(Integer, primary_key=True, index=True)
    story_run_id = Column(Integer, ForeignKey("story_runs.id"), index=True, nullable=False)
    act_id = Column(Integer, ForeignKey("story_acts.id"), nullable=True)
    order_index = Column(Integer, nullable=False)
    
    title = Column(String, nullable=False)
    summary = Column(String, nullable=True)
    narrative_role = Column(String, nullable=False)
    emotional_state = Column(String, nullable=True)
    dramatic_intensity = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="ACTIVE")
    
    story_run = relationship("StoryRun", back_populates="beats")
    act = relationship("StoryAct", back_populates="beats")

class StoryEventClaim(Base):
    __tablename__ = "story_event_claims"
    event_id = Column(Integer, ForeignKey("story_events.id"), primary_key=True)
    claim_id = Column(Integer, ForeignKey("research_claims.id"), primary_key=True)

class StoryBeatClaim(Base):
    __tablename__ = "story_beat_claims"
    beat_id = Column(Integer, ForeignKey("story_beats.id"), primary_key=True)
    claim_id = Column(Integer, ForeignKey("research_claims.id"), primary_key=True)
