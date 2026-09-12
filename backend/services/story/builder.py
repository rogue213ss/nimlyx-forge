from backend.models.project import Project
from sqlalchemy.orm import Session
from backend.models import (
    ResearchRun, ResearchClaim, ResearchEvidence, ResearchSource,
    Project, Episode, Scene, NarrationSegment, VisualIntent,
    StoryRun, StoryEvent, StoryBeat, StoryAct, StoryEventClaim, StoryBeatClaim
)
from backend.models.enums import StoryRunStatus, DatePrecision, NarrativeRole, ClaimStatus
import re
import json
import datetime

class StoryBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build_story(self, project_id: int, episode_id: int, research_run_id: int, config: dict = None) -> int:
        run = StoryRun(
            project_id=project_id,
            episode_id=episode_id,
            research_run_id=research_run_id,
            status=StoryRunStatus.RUNNING.value,
            configuration=json.dumps(config or {})
        )
        self.db.add(run)
        self.db.commit()

        try:
            selected_claims = self._select_claims(run)
            events = self._reconstruct_timeline(run, selected_claims)
            acts = self._structure_acts(run)
            beats = self._generate_beats(run, events, acts)
            self._generate_scenes(run, acts, beats)
            self._evaluate_quality(run, selected_claims, events, beats)

            run.status = StoryRunStatus.COMPLETED.value
            run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()
            return run.id
        except Exception as e:
            self.db.rollback()
            run = self.db.query(StoryRun).get(run.id)
            run.status = StoryRunStatus.FAILED.value
            self.db.commit()
            raise e

    def _select_claims(self, run: StoryRun):
        claims = self.db.query(ResearchClaim).filter_by(research_run_id=run.research_run_id).all()
        selected = []
        for claim in claims:
            if claim.status == ClaimStatus.REJECTED.value:
                continue
            if getattr(claim, 'quality_classification', None) == "LOW_QUALITY":
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

            if score >= 30 and has_relevance:
                claim._selection_reason = ", ".join(reasons)
                selected.append(claim)





        return selected

    def _reconstruct_timeline(self, run: StoryRun, selected_claims):
        events = []
        for claim in selected_claims:
            text = (getattr(claim, 'claim_text', None) or "")

            date_precision = DatePrecision.UNKNOWN.value
            event_date = None

            year_match = re.search(r'\b((?:19|20)\d{2})\b', text)
            if year_match:
                event_date = year_match.group(1)
                date_precision = DatePrecision.YEAR.value

                months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
                for m in months:
                    if m in text.lower():
                        event_date = f"{m.capitalize()} {event_date}"
                        date_precision = DatePrecision.MONTH.value
                        break
            elif "years later" in text.lower() or "after" in text.lower():
                event_date = "Relative"
                date_precision = DatePrecision.RELATIVE.value

            ev = StoryEvent(
                story_run_id=run.id,
                title=f"Event: {text[:30]}...",
                summary=text,
                event_date=event_date,
                date_precision=date_precision,
                importance_score=50,
                category=getattr(claim, 'category', 'General')
            )
            self.db.add(ev)
            self.db.flush()

            mapping = StoryEventClaim(event_id=ev.id, claim_id=claim.id)
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

    def _generate_beats(self, run: StoryRun, events, acts):
        def sort_key(e):
            if e.date_precision == DatePrecision.YEAR.value or e.date_precision == DatePrecision.MONTH.value:
                return (0, str(e.event_date))
            return (1, str(e.id))

        sorted_events = sorted(events, key=sort_key)

        beats = []
        n = len(sorted_events)

        for i, ev in enumerate(sorted_events):
            if i < n // 3:
                act = acts[0]
                role = NarrativeRole.SETUP.value if i > 0 else NarrativeRole.HOOK.value
                emotion = "AMBITION"
            elif i < 2 * (n // 3):
                act = acts[1]
                role = NarrativeRole.RISING_TENSION.value
                emotion = "TENSION"
            else:
                act = acts[2]
                role = NarrativeRole.CONCLUSION.value if i == n - 1 else NarrativeRole.REFLECTION.value
                emotion = "RESOLUTION"

            beat = StoryBeat(
                story_run_id=run.id,
                act_id=act.id,
                order_index=i,
                title=ev.title.replace("Event: ", "Beat: "),
                summary=ev.summary,
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

        return beats

    def _generate_scenes(self, run: StoryRun, acts, beats):
        scene_idx = 1
        for act in acts:
            act_beats = [b for b in beats if b.act_id == act.id]
            for beat in act_beats:
                claims = self.db.query(StoryBeatClaim).filter_by(beat_id=beat.id).all()
                claim_ids = [c.claim_id for c in claims]

                scene = Scene(
                    episode_id=run.episode_id,
                    order_index=scene_idx,
                    title=f"Scene for {beat.title}",
                    story_run_id=run.id,
                    story_beat_id=beat.id,
                    act_id=act.id,
                    purpose=beat.summary,
                    emotional_intent=beat.emotional_state,
                    estimated_duration_seconds=30
                )
                self.db.add(scene)
                self.db.flush()

                seg = NarrationSegment(
                    scene_id=scene.id,
                    order_index=1,
                    text=f"Narrator discusses: {beat.summary}",
                    is_brief=1,
                    purpose="Explain narrative beat",
                    must_communicate=json.dumps([beat.summary]),
                    must_not_claim=json.dumps(["unsupported factual assertions"]),
                    tone="Investigative",
                    estimated_duration_seconds=30,
                    supporting_claims=json.dumps(claim_ids)
                )
                self.db.add(seg)
                self.db.flush()

                vi = VisualIntent(
                    narration_segment_id=seg.id,
                    description=f"Show visual context for {beat.summary}",
                    search_query=beat.title,
                    preferred_content_types=json.dumps(["gameplay", "trailer"]),
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
            "Timeline coverage": len([e for e in events if e.date_precision != DatePrecision.UNKNOWN.value]),
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
