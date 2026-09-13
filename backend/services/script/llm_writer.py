import json
import os
from sqlalchemy.orm import Session
from backend.models import (
    StoryRun, Scene, NarrationSegment, ScriptRun, ScriptSentence, 
    ClaimReference, ResearchClaim, ResearchEvidence
)
from backend.models.enums import ClaimStatus, SentenceType, ReviewStatus, ScriptRunStatus
from backend.services.script.validator import FactualValidator
from backend.services.llm.provider import LLMProvider, MockProvider, OpenAIProvider
from backend.services.llm.gemini_provider import GeminiProvider

class LLMScriptWriter:
    def __init__(self, db: Session, provider: LLMProvider = None):
        self.db = db
        self.provider = provider or self._get_default_provider()
        
    def _get_default_provider(self):
        provider_name = os.environ.get("LLM_PROVIDER", "").lower()
        if provider_name == "gemini":
            return GeminiProvider()
        elif provider_name == "openai" or os.environ.get("OPENAI_API_KEY"):
            return OpenAIProvider()
        return MockProvider()

    def generate_script(self, story_run_id: int) -> int:
        story_run = self.db.query(StoryRun).get(story_run_id)
        if not story_run:
            raise ValueError(f"StoryRun {story_run_id} not found")

        # Create a new ScriptRun
        script_run = ScriptRun(
            story_run_id=story_run_id,
            status=ScriptRunStatus.RUNNING.value,
            provider_name=self.provider.__class__.__name__,
            model_name=os.environ.get("LLM_MODEL", "gemini-2.5-flash"),
            prompt_version="v1.0"
        )
        self.db.add(script_run)
        self.db.commit()

        try:
            previous_script = []
            scenes = self.db.query(Scene).filter_by(story_run_id=story_run_id).order_by(Scene.order_index).all()
            for scene in scenes:
                segments = self.db.query(NarrationSegment).filter_by(scene_id=scene.id).order_by(NarrationSegment.order_index).all()
                for seg in segments:
                    claim_ids = json.loads(seg.supporting_claims) if seg.supporting_claims else []
                    must_not_claim = json.loads(seg.must_not_claim) if seg.must_not_claim else []
                    
                    verified_claims = []
                    valid_claim_ids = set()
                    for cid in claim_ids:
                        c = self.db.query(ResearchClaim).get(cid)
                        if c and c.status not in [ClaimStatus.REJECTED.value, ClaimStatus.CONFLICTED.value]:
                            if c.project_id != story_run.project_id:
                                continue

                            valid_claim_ids.add(c.id)
                            verified_claims.append({
                                "id": c.id,
                                "claim_text": c.claim_text,
                                "status": c.status
                            })

                    if not verified_claims:
                        continue

                    prompt_package = {
                        "story_context": f"Episode {story_run.episode_id}, Scene {scene.title}",
                        "narration_purpose": seg.purpose,
                        "must_not_claim": must_not_claim,
                        "verified_claims": verified_claims,
                        "previously_generated_text": " ".join(previous_script[-10:])
                    }

                    config = {
                        "model": os.environ.get("LLM_MODEL", "gemini-2.5-flash"),
                        "max_tokens": 1000,
                        "timeout": 30
                    }

                    response = self.provider.generate_script(prompt_package, config)
                    
                    usage = response.get("usage", {})
                    if usage:
                        curr_usage = json.loads(script_run.token_usage) if script_run.token_usage else {"total_tokens": 0}
                        curr_usage["total_tokens"] = curr_usage.get("total_tokens", 0) + usage.get("total_tokens", 0)
                        script_run.token_usage = json.dumps(curr_usage)
                    
                    for idx, sent_data in enumerate(response.get("sentences", [])):
                        text = sent_data.get("text", "")
                        stype = sent_data.get("type", SentenceType.FACTUAL.value)
                        c_ids = sent_data.get("claim_ids", [])
                        
                        previous_script.append(text)
                        
                        review_status = ReviewStatus.DRAFT.value
                        
                        matched_claims = []
                        for cid in c_ids:
                            if cid in valid_claim_ids:
                                matched_claims.append(self.db.query(ResearchClaim).get(cid))
                            else:
                                review_status = ReviewStatus.NEEDS_REVIEW.value
                        
                        if stype == SentenceType.FACTUAL.value and not matched_claims:
                            review_status = ReviewStatus.REJECTED.value

                        if stype == SentenceType.FACTUAL.value and matched_claims:
                            if not FactualValidator.validate_sentence(text, matched_claims, must_not_claim):
                                review_status = ReviewStatus.NEEDS_REVIEW.value

                        s = ScriptSentence(
                            script_run_id=script_run.id,
                            narration_segment_id=seg.id,
                            order_index=idx,
                            text=text,
                            original_text=text,
                            sentence_type=stype,
                            review_status=review_status
                        )
                        self.db.add(s)
                        self.db.flush()
                        
                        for mc in matched_claims:
                            ref = ClaimReference(
                                script_sentence_id=s.id,
                                research_claim_id=mc.id
                            )
                            self.db.add(ref)

            script_run.status = ScriptRunStatus.COMPLETED.value
            self.db.commit()
            return script_run.id
            
        except Exception as e:
            self.db.rollback()
            script_run.status = ScriptRunStatus.FAILED.value
            script_run.error_message = str(e)
            self.db.commit()
            raise e

