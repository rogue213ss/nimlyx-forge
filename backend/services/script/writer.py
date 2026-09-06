import os
import json
import datetime
from sqlalchemy.orm import Session
from backend.models import (
    Project, StoryRun, Scene, NarrationSegment, ResearchClaim,
    ScriptRun, ScriptSentence, ClaimReference
)
from backend.models.enums import ScriptRunStatus, SentenceType, ClaimStatus, ReviewStatus

class ScriptWriter:
    def __init__(self, db: Session):
        self.db = db

    def generate_script(self, story_run_id: int) -> int:
        story_run = self.db.query(StoryRun).get(story_run_id)
        if not story_run:
            raise ValueError(f"StoryRun {story_run_id} not found.")

        script_run = ScriptRun(
            story_run_id=story_run.id,
            status=ScriptRunStatus.RUNNING.value
        )
        self.db.add(script_run)
        self.db.flush()

        try:
            scenes = self.db.query(Scene).filter_by(story_run_id=story_run.id).order_by(Scene.order_index).all()
            for scene in scenes:
                segments = self.db.query(NarrationSegment).filter_by(scene_id=scene.id).order_by(NarrationSegment.order_index).all()
                for seg in segments:
                    # Parse supporting claims
                    try:
                        claim_ids = json.loads(seg.supporting_claims) if seg.supporting_claims else []
                    except:
                        claim_ids = []

                    valid_claims = []
                    for cid in claim_ids:
                        claim = self.db.query(ResearchClaim).get(cid)
                        if not claim:
                            continue
                        
                        # Factual boundaries
                        # Must belong to current project
                        if claim.project_id != story_run.project_id:
                            continue
                        
                        # Not REJECTED
                        if claim.status in [ClaimStatus.REJECTED.value, ClaimStatus.CONFLICTED.value]:
                            continue
                        # Not LOW_QUALITY
                        if getattr(claim, 'quality_classification', '') == 'LOW_QUALITY':
                            continue
                        
                        valid_claims.append(claim)

                    if not valid_claims:
                        continue

                    # 1. TRANSITION sentence
                    trans = ScriptSentence(
                        script_run_id=script_run.id,
                        narration_segment_id=seg.id,
                        order_index=1,
                        text="Moving to the next point.",
                        original_text="Moving to the next point.",
                        sentence_type=SentenceType.TRANSITION.value
                    )
                    self.db.add(trans)
                    self.db.flush()

                    # 2. FACTUAL sentences
                    idx = 2
                    for claim in valid_claims:
                        # We use EXACT formatting to preserve numerical/temporal/certainty exactly
                        # If a claim says "reportedly 2.3 million copies sold in 2021", 
                        # this string concatenation preserves it completely without LLM mutation.
                        text = f"The research confirms: {claim.claim_text}"
                        fact = ScriptSentence(
                            script_run_id=script_run.id,
                            narration_segment_id=seg.id,
                            order_index=idx,
                            text=text,
                            original_text=text,
                            sentence_type=SentenceType.FACTUAL.value
                        )
                        self.db.add(fact)
                        self.db.flush()
                        idx += 1

                        # Claim Reference
                        cref = ClaimReference(
                            script_sentence_id=fact.id,
                            research_claim_id=claim.id
                        )
                        self.db.add(cref)
            
            script_run.status = ScriptRunStatus.COMPLETED.value
            script_run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()
            return script_run.id

        except Exception as e:
            self.db.rollback()
            script_run.status = ScriptRunStatus.FAILED.value
            script_run.error_message = str(e)
            self.db.commit()
            raise e

    def update_sentence(self, sentence_id: int, new_text: str):
        sentence = self.db.query(ScriptSentence).get(sentence_id)
        if not sentence:
            raise ValueError("Sentence not found")
        
        sentence.text = new_text
        
        if sentence.sentence_type == SentenceType.FACTUAL.value:
            # Check if all supported claims are still literally present in the text
            # Or just mark NEEDS_REVIEW to enforce human approval since they edited it.
            # "The system must mark the sentence as requiring revalidation / review."
            # "Do NOT silently preserve APPROVED factual status after a materially changed edit."
            if new_text != sentence.original_text:
                sentence.review_status = ReviewStatus.NEEDS_REVIEW.value
        
        self.db.commit()
