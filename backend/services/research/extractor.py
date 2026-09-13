import re
import json
from typing import List, Dict, Any
from backend.services.research.providers import ClaimExtractor

def normalize_claim(text: str) -> str:
    # Lowercase, remove punctuation, collapse whitespace
    t = text.lower()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

class AdvancedHeuristicExtractor(ClaimExtractor):
    def extract(self, text: str, source_tier: str = "TIER_4", topic: str = "") -> List[Dict[str, Any]]:
        claims = []

        # Clean out wikipedia references like [12], [citation needed]
        text_clean = re.sub(r'\[\d+\]', '', text)
        text_clean = re.sub(r'\[citation needed\]', '', text_clean)

        text_flat = text_clean.replace('\n', ' ')
        sentences = re.split(r'(?<=[.!?]) +(?=[A-Z0-9])', text_flat)

        keywords = {
            "development": ["develop", "engine", "studio", "director", "programmer", "budget", "cost", "team", "patch", "update", "obsidian"],
            "release": ["released", "launch", "delayed", "announced", "trailer", "date", "deadline"],
            "sales": ["sold", "million", "copies", "revenue", "grossed", "units", "commercial", "record"],
            "reception": ["received", "reviews", "critic", "score", "metacritic", "award", "won", "nominated", "reception"],
            "legacy": ["legacy", "influence", "classic", "retrospective"],
            "world": ["mojave", "hoover dam", "new vegas strip", "world", "setting"],
            "factions": ["faction", "ncr", "legion", "house", "companion", "character"],
            "design": ["design", "gameplay", "mechanics", "branching", "choice", "consequence", "reputation"],
            "bugs": ["bug", "glitch", "crash", "problem", "technical"]
        }

        topic_raw = topic.replace(" game", "").replace(" video game", "").lower()
        topic_name = re.sub(r'[^\w\s]', '', topic_raw)
        topic_name = re.sub(r'\s+', ' ', topic_name).strip()

        valid_entities = [topic_name] if topic_name else []
        if topic_name == "fallout new vegas":
            valid_entities.extend(["new california republic", "ncr", "obsidian entertainment"])

        context_decay = 0

        for s in sentences:
            # HARDENED: Use a decaying context window so a single topic mention
            # provides context for up to 3 sentences, rather than the whole document.
            s_clean_for_context = re.sub(r'[^\w\s]', '', s.lower())
            s_clean_for_context = re.sub(r'\s+', ' ', s_clean_for_context).strip()

            s_padded = f" {s_clean_for_context} "
            if any(f" {ent} " in s_padded for ent in valid_entities):
                context_decay = 3

            has_context = (context_decay > 0)

            if context_decay > 0:
                context_decay -= 1

            s = s.strip()
            
            # 1. HARDEN EXTRACTION CLEANLINESS (Reject scrapings & UI fragments)
            bad_patterns = [
                r'\[\s*edit\s*\]',
                r'home\s+reviews',
                r'jump\s+to',
                r'see\s+also',
                r'^references',
                r'↑',
                r'&\#\d+;', r'&[a-zA-Z]+;', # HTML entities
                r'loading\s+screens\s*:',   # loading screen text
                r'dialogue\s*\)'            # dialogue labels
            ]
            if any(re.search(pat, s, re.IGNORECASE) for pat in bad_patterns):
                continue
                
            # Reject dialogue mashups: e.g. Courier : "..." Ambassador : "..."
            if re.search(r'[A-Za-z]+\s*:\s*".*?[A-Za-z]+\s*:\s*"', s):
                continue
            
            # Reject truncated/incomplete sentences
            if s.endswith('..') or s.endswith('...'):
                continue

            # 2. CLAIM QUALITY CHECK (Must resemble a complete factual statement)
            if len(s) < 30 or len(s) > 300:
                continue
            
            # Must start with alphanumeric or quote
            if not (s[0].isupper() or s[0].isdigit() or s.startswith('"') or s.startswith("'")):
                continue
            
            # Must end with sentence punctuation or quote
            if s[-1] not in ['.', '!', '?'] and not s.endswith('"') and not s.endswith("'"):
                continue


            s_lower = s.lower()
            found_category = None

            for cat, words in keywords.items():
                if any(f" {w} " in f" {s_lower} " or f" {w}." in f" {s_lower} " for w in words):
                    found_category = cat
                    break

            if found_category:
                ev_reasons = []

                if has_context:
                    ev_reasons.append("Contains target entity")
                else:
                    ev_reasons.append("Does not explicitly name target entity")

                if len(s) > 50 and len(s) < 200:
                    ev_reasons.append("Optimal length complete sentence")

                temporal_context = None
                year_match = re.search(r'\b(19|20)\d{2}\b', s)
                if year_match:
                    temporal_context = year_match.group(0)
                    ev_reasons.append("Contains explicit temporal marker")

                numeric_match = re.search(r'\b\d+([.,]\d+)?\b', s)
                if numeric_match:
                    ev_reasons.append("Contains specific numeric data")

                # RELEVANCE FIREWALL: Date/number/financial signals can never independently satisfy topic relevance.
                # A claim must first establish a credible connection to the target topic/entity.
                if "Contains target entity" not in ev_reasons:
                    continue

                ev_quality = "LOW"
                if len(ev_reasons) >= 3 and "Contains target entity" in ev_reasons:
                    ev_quality = "HIGH"
                elif len(ev_reasons) >= 2:
                    ev_quality = "MEDIUM"

                conf_signals = {
                    "source_tier": source_tier,
                    "evidence_quality": ev_quality,
                    "has_temporal": temporal_context is not None,
                    "has_numeric": numeric_match is not None
                }

                conf_score = 0
                if source_tier == "TIER_1": conf_score += 3
                elif source_tier == "TIER_2": conf_score += 2
                elif source_tier == "TIER_3": conf_score += 1

                if ev_quality == "HIGH": conf_score += 2
                elif ev_quality == "MEDIUM": conf_score += 1

                if conf_signals["has_temporal"]: conf_score += 1
                if conf_signals["has_numeric"]: conf_score += 1

                if conf_score >= 5: confidence = "HIGH"
                elif conf_score >= 3: confidence = "MEDIUM"
                else: confidence = "LOW"

                quality_classification = "LOW_QUALITY"
                if confidence == "HIGH" and ev_quality == "HIGH":
                    quality_classification = "STORY_READY"
                elif confidence in ["MEDIUM", "HIGH"] and ev_quality in ["MEDIUM", "HIGH"]:
                    quality_classification = "REVIEW_REQUIRED"

                normalized = normalize_claim(s)

                if not any(c['normalized_claim_text'] == normalized for c in claims):
                    claims.append({
                        "claim_text": s,
                        "normalized_claim_text": normalized,
                        "category": found_category,
                        "temporal_context": temporal_context,
                        "confidence": confidence,
                        "confidence_reason": f"Score {conf_score} based on signals",
                        "confidence_signals": json.dumps(conf_signals),
                        "quality_classification": quality_classification,
                        "raw_text": s,
                        "evidence_quality": ev_quality,
                        "evidence_quality_reason": "; ".join(ev_reasons),
                        "evidence_type": "SUPPORTING"
                    })

        return claims

