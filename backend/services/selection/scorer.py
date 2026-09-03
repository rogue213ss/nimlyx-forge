import json
import re

class SelectionScorer:
    def __init__(self):
        pass

    def _safe_json_loads(self, val):
        if not val:
            return []
        try:
            return json.loads(val)
        except:
            return []

    def score_candidate(self, mapping, intent, source):
        # We assume mapping has relevance_score from V4
        base_relevance = mapping.relevance_score if mapping.relevance_score is not None else 0.0
        
        signals = []
        penalties = []
        is_hard_rejection = False
        rejection_reasons = []

        # Parse intent constraints
        pref_types = self._safe_json_loads(intent.preferred_content_types)
        avoid_types = self._safe_json_loads(intent.avoid_content_types)
        pref_channels = self._safe_json_loads(intent.preferred_channels)
        pref_year = intent.preferred_year

        # Normalize source metadata for text matching
        s_title = (source.title or "").lower()
        s_desc = (source.description or "").lower()
        s_channel = (source.source_channel or "").lower()
        
        # 1. Base V4 relevance
        score = base_relevance
        
        # 2. Hard Rejections
        # Reject totally empty metadata
        if not source.title and not source.description:
            is_hard_rejection = True
            rejection_reasons.append("Missing both title and description")

        # 3. Signals (Bonuses)
        # Content Type (Heuristic from title/desc)
        matched_pref_type = False
        for ptype in pref_types:
            pt = ptype.lower()
            if pt in s_title or pt in s_desc:
                signals.append({"name": "preferred_content_type", "effect": 15.0, "reason": f"Matched preferred type: {ptype}"})
                score += 15.0
                matched_pref_type = True
                break
        
        # Channel matching
        if pref_channels and s_channel:
            matched_channel = False
            for pc in pref_channels:
                if pc.lower() in s_channel:
                    signals.append({"name": "preferred_channel", "effect": 20.0, "reason": f"Matched preferred channel: {pc}"})
                    score += 20.0
                    matched_channel = True
                    break
        
        # Year matching
        if pref_year and source.published_date:
            if source.published_date.year == pref_year:
                signals.append({"name": "preferred_year", "effect": 10.0, "reason": f"Matched preferred year: {pref_year}"})
                score += 10.0
            else:
                penalties.append({"name": "mismatched_year", "effect": -10.0, "reason": f"Year {source.published_date.year} does not match preferred {pref_year}"})
                score -= 10.0

        # Official Source Bonus (example: HelloGamesTube or PlayStation)
        if s_channel in ['hellogamestube', 'playstation', 'xbox']:
            signals.append({"name": "official_source", "effect": 10.0, "reason": "Recognized official gaming channel"})
            score += 10.0

        # 4. Penalties
        # Avoided content types
        for atype in avoid_types:
            at = atype.lower()
            if at in s_title or at in s_desc:
                penalties.append({"name": "avoided_content_type", "effect": -20.0, "reason": f"Contains avoided type: {atype}"})
                score -= 20.0

        # Shorts Penalty (usually want landscape for documentary)
        if source.is_short:
            penalties.append({"name": "is_short", "effect": -25.0, "reason": "Source is a Short (vertical video)"})
            score -= 25.0

        # 5. Intent Description text overlap (simple heuristic)
        if intent.description:
            intent_words = set(re.findall(r'\w+', intent.description.lower()))
            overlap = 0
            for w in intent_words:
                if len(w) > 3 and (w in s_title or w in s_desc):
                    overlap += 1
            if overlap > 0:
                bonus = min(overlap * 2.0, 10.0) # Cap at +10
                signals.append({"name": "intent_keyword_overlap", "effect": bonus, "reason": f"Matched {overlap} keywords from intent description"})
                score += bonus

        # Determine final score (clamp 0-100)
        final_score = max(0.0, min(100.0, score))
        if is_hard_rejection:
            final_score = 0.0

        # Canonical ordering for JSON
        signals = sorted(signals, key=lambda x: x["name"])
        penalties = sorted(penalties, key=lambda x: x["name"])
        rejection_reasons = sorted(rejection_reasons)

        reason_dict = {
            "base_relevance": float(base_relevance),
            "final_score": float(final_score),
            "hard_rejection": is_hard_rejection,
            "penalties": penalties,
            "rejection_reasons": rejection_reasons,
            "signals": signals
        }
        
        # Canonical JSON string: sorted keys, no spaces after separators to match standard compact JSON but deterministic
        reason_json = json.dumps(reason_dict, sort_keys=True, separators=(',', ':'))

        return final_score, reason_json, is_hard_rejection

    def determine_confidence(self, score: float, is_hard_rejection: bool) -> str:
        if is_hard_rejection:
            return "REJECTED"
        if score >= 80.0:
            return "HIGH"
        elif score >= 60.0:
            return "MEDIUM"
        elif score >= 40.0:
            return "LOW"
        else:
            return "REJECTED"
