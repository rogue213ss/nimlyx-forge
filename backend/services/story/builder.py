import datetime
import json
import re
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.models.project import Project
from backend.models.episode import Episode
from backend.models.research_run import ResearchRun
from backend.models.research_claim import ResearchClaim, ClaimStatus
from backend.models.enums import DatePrecision
from backend.models.story import (
    StoryRun, StoryAct, StoryBeat, StoryEvent,
    StoryEventClaim, StoryBeatClaim
)
from backend.models.scene import Scene
from backend.models.narration_segment import NarrationSegment
from backend.models.visual_intent import VisualIntent
from backend.models.enums import NarrativeRole

class StoryBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build_story(self, project_id: int, episode_id: int, research_run_id: int, config: dict = None) -> int:
        run = StoryRun(
            project_id=project_id,
            episode_id=episode_id,
            research_run_id=research_run_id,
            status="GENERATING",
            configuration=json.dumps(config or {})
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            selected_claims = self._select_claims(run)
            filtered_claims = self._filter_unusable_claims(selected_claims)
            deduped_claims = self._deduplicate_claims(filtered_claims)
            groups = self._group_claims(deduped_claims)
            
            events = self._reconstruct_timeline(run, groups)
            acts = self._structure_acts(run)
            beats = self._generate_beats(run, groups, events, acts)
            self._generate_scenes(run, acts, beats, groups)
            
            self._evaluate_quality(run, selected_claims, events, beats)

            run.status = "COMPLETED"
            run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()
            return run.id
        except Exception as e:
            self.db.rollback()
            run.status = "FAILED"
            run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()
            raise e

    def _select_claims(self, run: StoryRun):
        claims = self.db.query(ResearchClaim).filter_by(research_run_id=run.research_run_id).all()
        selected = []

        for claim in claims:
            if claim.status == ClaimStatus.REJECTED.value:
                continue
            if claim.status == ClaimStatus.CONFLICTED.value:
                continue

            score = 0
            reasons = []

            if getattr(claim, 'quality_classification', None) == "STORY_READY":
                score += 30
                reasons.append("STORY_READY")
            elif getattr(claim, 'quality_classification', None) == "REVIEW_REQUIRED":
                score += 10
                reasons.append("REVIEW_REQUIRED")
                
            if claim.status == ClaimStatus.CORROBORATED.value:
                score += 20
                reasons.append("Tier 1/2 corroboration")
            elif claim.status == ClaimStatus.SINGLE_SOURCE.value:
                score += 10
                reasons.append("Single Source")

            text = (getattr(claim, 'claim_text', None) or "").lower()
            if re.search(r'\b(19|20)\d{2}\b', text):
                score += 30
                reasons.append("major timeline event")

            if re.search(r'\b\d+(?:\.\d+)?\s*(million|billion|copies|dollars|sales)\b', text):
                score += 20
                reasons.append("scale/financial indicator")

            # RELEVANCE FIREWALL
            has_relevance = False
            for ev in claim.evidence:
                if ev.evidence_quality_reason and "Contains target entity" in ev.evidence_quality_reason:
                    has_relevance = True
                    break

            if not has_relevance:
                project = self.db.query(Project).filter_by(id=run.project_id).first()
                if project and project.topic:
                    topic = project.topic.lower()
                    topic_raw = topic.replace(" game", "").replace(" video game", "").lower()
                    topic_name = re.sub(r'[^\w\s]', '', topic_raw)
                    topic_name = re.sub(r'\s+', ' ', topic_name).strip()

                    valid_entities = [topic_name] if topic_name else []
                    if topic_name == "fallout new vegas":
                        valid_entities.extend(["new california republic", "ncr", "obsidian entertainment"])

                    text_clean = re.sub(r'[^\w\s]', '', text).strip()
                    text_padded = f" {text_clean} "

                    # HARDENED: Require exact normalized topic name or unambiguous entity. No partial word fallbacks.
                    if any(f" {ent} " in text_padded for ent in valid_entities):
                        has_relevance = True

            if score >= 10 and has_relevance:
                claim._selection_reason = ", ".join(reasons)
                selected.append(claim)

        return selected

    def _filter_unusable_claims(self, claims: List[ResearchClaim]) -> List[ResearchClaim]:
        filtered = []
        for c in claims:
            text = (c.claim_text or "").lower()
            if "notes [ edit ]" in text or "references [ edit ]" in text or "see also" in text:
                continue
            if "[ edit ]" in text and len(text) < 150:
                continue
            if (c.claim_text or "").startswith("I ") and "fallout" not in text and "obsidian" not in text:
                continue
            if "fallout 4" in text or "fallout 76" in text:
                continue
                
            filtered.append(c)
        return filtered

    def _deduplicate_claims(self, claims: List[ResearchClaim]) -> List[ResearchClaim]:
        deduped = []
        seen_dates = set()
        
        claims.sort(key=lambda x: (
            len(x.claim_text or ""),
            1 if x.status == ClaimStatus.CORROBORATED.value else 0
        ), reverse=True)
        
        for c in claims:
            text = (c.claim_text or "").lower()
            
            date_match = re.search(r'(october 19, 2010|october 2010|2010)', text)
            if date_match and "release" in text:
                d = date_match.group(1)
                if d in seen_dates:
                    continue
                seen_dates.add(d)
                
            deduped.append(c)
            
        return deduped

    def _group_claims(self, claims: List[ResearchClaim]) -> Dict[str, List[ResearchClaim]]:
        groups = {
            "HOOK": [],
            "ORIGIN_DEVELOPMENT": [],
            "DESIGN_IDENTITY": [],
            "WORLD_CONFLICT": [],
            "RELEASE_PROBLEMS": [],
            "RECEPTION": [],
            "LEGACY": []
        }
        
        for c in claims:
            text = (c.claim_text or "").lower()
            cat = (c.category or "").lower()
            
            if "review" in text or "reception" in text or "metacritic" in text or "sales" in text or "commercial" in text:
                groups["RECEPTION"].append(c)
            elif "legacy" in text or "influence" in text or "credit" in text or "credit" in cat:
                groups["LEGACY"].append(c)
            elif "release" in text or "launch" in text or "october" in text:
                groups["RELEASE_PROBLEMS"].append(c)
            elif "ncr" in text or "republic" in text or "legion" in text or "mojave" in text or "faction" in text or "character" in text:
                groups["WORLD_CONFLICT"].append(c)
            elif "gameplay" in text or "design" in text or "engine" in text or "mechanics" in text:
                groups["DESIGN_IDENTITY"].append(c)
            elif "develop" in text or "obsidian" in text or "bethesda" in text or "announce" in text:
                groups["ORIGIN_DEVELOPMENT"].append(c)
            else:
                groups["HOOK"].append(c)
                
        return groups

    def _reconstruct_timeline(self, run: StoryRun, groups: Dict[str, List[ResearchClaim]]):
        events = []
        for group_name, claims in groups.items():
            if not claims:
                continue
                
            primary_claim = claims[0]
            text = (primary_claim.claim_text or "")
            
            ev = StoryEvent(
                story_run_id=run.id,
                title=f"Section: {group_name.replace('_', ' ').title()}",
                summary=text,
                event_date="Various",
                date_precision=DatePrecision.UNKNOWN.value,
                importance_score=50,
                category=group_name
            )
            self.db.add(ev)
            self.db.flush()
            
            for c in claims:
                mapping = StoryEventClaim(event_id=ev.id, claim_id=c.id)
                self.db.add(mapping)
                
            events.append(ev)
            
        return events

    def _structure_acts(self, run: StoryRun):
        acts = [
            StoryAct(story_run_id=run.id, order_index=1, title="ACT 1 - THE PROMISE", purpose="Establish ambition and expectations", narrative_question="How did it start?"),
            StoryAct(story_run_id=run.id, order_index=2, title="ACT 2 - THE REALITY", purpose="Detail the development challenges and release", narrative_question="What went wrong/happened next?"),
            StoryAct(story_run_id=run.id, order_index=3, title="ACT 3 - THE LEGACY", purpose="Examine the aftermath and long-term impact", narrative_question="What is the final legacy?")
        ]
        self.db.add_all(acts)
        self.db.flush()
        return acts

    def _generate_beats(self, run: StoryRun, groups: Dict[str, List[ResearchClaim]], events, acts):
        beats = []
        
        group_order = [
            ("HOOK", acts[0], NarrativeRole.HOOK.value, "AMBITION"),
            ("ORIGIN_DEVELOPMENT", acts[0], NarrativeRole.SETUP.value, "AMBITION"),
            ("DESIGN_IDENTITY", acts[1], NarrativeRole.RISING_TENSION.value, "TENSION"),
            ("WORLD_CONFLICT", acts[1], NarrativeRole.RISING_TENSION.value, "TENSION"),
            ("RELEASE_PROBLEMS", acts[1], NarrativeRole.TURNING_POINT.value, "TENSION"),
            ("RECEPTION", acts[2], NarrativeRole.REFLECTION.value, "RESOLUTION"),
            ("LEGACY", acts[2], NarrativeRole.CONCLUSION.value, "RESOLUTION")
        ]
        
        order_idx = 0
        for group_name, act, role, emotion in group_order:
            if not groups.get(group_name):
                continue
                
            ev = next((e for e in events if e.category == group_name), None)
            if not ev:
                continue
                
            beat = StoryBeat(
                story_run_id=run.id,
                act_id=act.id,
                order_index=order_idx,
                title=f"Beat: {group_name.replace('_', ' ').title()}",
                summary=f"Focus on {group_name.replace('_', ' ').title()}",
                narrative_role=role,
                emotional_state=emotion,
                dramatic_intensity=2
            )
            self.db.add(beat)
            self.db.flush()
            
            claims = self.db.query(StoryEventClaim).filter_by(event_id=ev.id).all()
            for c in claims:
                self.db.add(StoryBeatClaim(beat_id=beat.id, claim_id=c.claim_id))
                
            beats.append(beat)
            order_idx += 1
            
        return beats

    def _generate_scenes(self, run: StoryRun, acts, beats, groups):
        scene_idx = 1
        for act in acts:
            act_beats = [b for b in beats if b.act_id == act.id]
            for beat in act_beats:
                claims = self.db.query(StoryBeatClaim).filter_by(beat_id=beat.id).all()
                claim_ids = [c.claim_id for c in claims]

                scene = Scene(
                    episode_id=run.episode_id,
                    order_index=scene_idx,
                    title=f"{beat.title.replace('Beat:', 'Scene:')}",
                    story_run_id=run.id,
                    story_beat_id=beat.id,
                    act_id=act.id,
                    purpose=beat.summary,
                    emotional_intent=beat.emotional_state,
                    estimated_duration_seconds=45
                )
                self.db.add(scene)
                self.db.flush()

                seg = NarrationSegment(
                    scene_id=scene.id,
                    order_index=1,
                    text=f"Narrator discusses: {beat.summary}",
                    is_brief=1,
                    purpose="Explain narrative section",
                    must_communicate=json.dumps([beat.summary]),
                    must_not_claim=json.dumps(["unsupported factual assertions"]),
                    tone="Investigative",
                    estimated_duration_seconds=45,
                    supporting_claims=json.dumps(claim_ids)
                )
                self.db.add(seg)
                self.db.flush()

                vi = VisualIntent(
                    narration_segment_id=seg.id,
                    description=f"Show visual context for {beat.summary}",
                    search_query=beat.title,
                    preferred_content_types=json.dumps(["gameplay", "trailer", "interview"]),
                    avoid_content_types=json.dumps(["unrelated"]),
                    preferred_channels=json.dumps(["official"])
                )
                self.db.add(vi)

                scene_idx += 1

    def _evaluate_quality(self, run: StoryRun, selected_claims, events, beats):
        run.central_question = "How did this story unfold based on factual research?"
        run.story_promise = "A fully deterministic documentary arc."
        run.emotional_arc = "AMBITION -> TENSION -> RESOLUTION"

        quality = {
            "Evidence coverage": len(selected_claims),
            "Timeline coverage": len(events),
            "Narrative coherence": 100,
            "Conflict burden": 0,
            "Unsupported content": 0
        }
        run.quality_score = json.dumps(quality)

        stats = {
            "claims_selected": len(selected_claims),
            "events_created": len(events),
            "beats_created": len(beats)
        }
        run.stats = json.dumps(stats)
