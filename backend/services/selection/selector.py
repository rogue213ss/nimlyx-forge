from backend.services.selection.scorer import SelectionScorer
from backend.services.selection.planner import ClipPlanner
from backend.models.enums import SelectionStatus
import sqlalchemy as sa
from sqlalchemy.orm import Session
from backend.models.asset_mapping import AssetMapping

class FootageSelector:
    """
    V6 corrective patch (see docs/phase-reports/v6.md):

    Automated selection may never overwrite a mapping whose selection_status
    is APPROVED. APPROVED represents an explicit human editorial decision,
    and is the only SelectionStatus value currently protected this way.
    A mapping in this state is left completely untouched by rank_intent()
    and select_best_for_intent() -- its selection_score, selection_reason,
    confidence_level, selection_status, and clip-plan timestamp fields are
    all skipped. This holds across repeated calls, rescoring, new candidates
    being introduced for the same intent, and re-ordering caused by any of
    the above -- there is no code path in this class that can touch an
    APPROVED mapping's stored fields.

    REJECTED is NOT treated as protected. As of this patch, nothing in the
    codebase distinguishes a system-generated REJECTED from a human-issued
    one (there is no separate "editorial rejection" flag or status), and
    every current writer of REJECTED is this selector acting on a
    confidence score. Making REJECTED sticky here would therefore be
    guessing at an editorial-intent model that does not exist yet. This is
    tracked as technical debt -- see docs/phase-reports/v6.md.
    """

    def __init__(self, db: Session):
        self.db = db
        self.scorer = SelectionScorer()
        self.planner = ClipPlanner()

    def rank_intent(self, intent_id: int):
        mappings = self.db.query(AssetMapping).filter(AssetMapping.visual_intent_id == intent_id).all()
        if not mappings:
            return []

        scored_mappings = []
        for m in mappings:
            if m.selection_status == SelectionStatus.APPROVED:
                # Protected editorial decision: never rescore, never touch.
                scored_mappings.append(m)
                continue

            source = m.source_asset
            intent = m.visual_intent
            
            score, reason, is_hard_rejection = self.scorer.score_candidate(m, intent, source)
            conf = self.scorer.determine_confidence(score, is_hard_rejection)
            
            m.selection_score = score
            m.selection_reason = reason
            m.confidence_level = conf
            
            scored_mappings.append(m)
            
        # Tie-breaker deterministic sorting:
        # 1. selection_score DESC
        # 2. relevance_score DESC
        # 3. official-source priority DESC (approximated by channel list)
        # 4. published_date DESC
        # 5. source_asset.id ASC
        # 6. asset_mapping.id ASC
        
        def sort_key(m):
            score = m.selection_score or 0.0
            relevance = m.relevance_score or 0.0
            chan = (m.source_asset.source_channel or "").lower()
            is_official = 1 if chan in ['hellogamestube', 'playstation', 'xbox'] else 0
            pub_date = m.source_asset.published_date.timestamp() if m.source_asset.published_date else 0.0
            return (
                -score,
                -relevance,
                -is_official,
                -pub_date,
                m.source_asset_id,
                m.id
            )
            
        scored_mappings.sort(key=sort_key)
        self.db.commit()
        return scored_mappings

    def select_best_for_intent(self, intent_id: int):
        # 1. Rank all candidates
        ranked = self.rank_intent(intent_id)
        if not ranked:
            return None
            
        # 2. Reset existing selection statuses for this intent to ensure idempotency
        # Only modify if they aren't already what they should be, or just reset them?
        # Actually, if we just set the top one and reject/unscore the rest, that's idempotent.
        
        best = ranked[0]
        
        for m in ranked:
            if m.selection_status == SelectionStatus.APPROVED:
                # Protected editorial decision: skip status change and clip
                # (re-)planning entirely. Do not touch this mapping.
                continue

            # We don't change AssetState. Only SelectionStatus.
            if m.confidence_level == "REJECTED":
                m.selection_status = SelectionStatus.REJECTED
            elif m == best:
                if m.confidence_level == "HIGH":
                    m.selection_status = SelectionStatus.AUTO_SELECTED
                elif m.confidence_level == "MEDIUM":
                    m.selection_status = SelectionStatus.NEEDS_REVIEW
                else:
                    m.selection_status = SelectionStatus.REJECTED # LOW gets rejected for auto-selection
            else:
                # Other non-best candidates
                if m.confidence_level in ["HIGH", "MEDIUM"]:
                    m.selection_status = SelectionStatus.NEEDS_REVIEW # Runner ups
                else:
                    m.selection_status = SelectionStatus.REJECTED

            # Plan the clip
            start, end, t_conf, t_reason = self.planner.plan_clip(m, m.source_asset)
            m.start_timestamp = start
            m.end_timestamp = end
            m.timestamp_confidence = t_conf
            m.timestamp_reason = t_reason

        self.db.commit()
        return best
