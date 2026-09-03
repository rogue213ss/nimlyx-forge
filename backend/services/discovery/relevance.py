import re
from typing import Tuple, Optional
from .models import NormalizedCandidate
from .search_plan import SearchPlanGenerator

# Simple heuristic lists for source categorization
PLATFORMS = {"playstation", "xbox", "nintendo", "steam"}
MEDIA = {"ign", "gamespot", "polygon", "kotaku", "eurogamer", "gameinformer"}
DEVELOPERS = {"hello games", "cd projekt red", "fromsoftware", "rockstar games"}

def detect_source_type(channel: str) -> str:
    if not channel:
        return "UNKNOWN"
    chan_lower = channel.lower()
    if chan_lower in PLATFORMS:
        return "OFFICIAL_PLATFORM"
    if chan_lower in DEVELOPERS:
        return "OFFICIAL_DEVELOPER"
    if chan_lower in MEDIA:
        return "KNOWN_MEDIA"
    return "UNKNOWN"

class RelevanceScorer:
    def __init__(self, plan_generator: SearchPlanGenerator = None):
        self.plan_generator = plan_generator or SearchPlanGenerator()

    def score_candidate(self, intent_description: str, candidate: NormalizedCandidate) -> Tuple[float, Optional[str], str, bool]:
        """
        Returns: (score, rejection_reason, source_type, is_short)
        rejection_reason is None if accepted.
        """
        title = (candidate.title or "").lower()
        desc = (candidate.description or "").lower()
        channel = (candidate.source_channel or "").lower()
        
        is_short = False
        if candidate.duration and candidate.duration <= 61:
            is_short = True
        if "#shorts" in title or "shorts" in title:
            is_short = True

        source_type = detect_source_type(channel)
        
        score = 0.0
        rejection_reason = None
        
        intent_lower = intent_description.lower()
        entity = self.plan_generator._extract_protected_entity(intent_description)
        
        if entity:
            entity_lower = entity.lower()
            if entity_lower in title:
                score += 50
            elif entity_lower in desc:
                score += 30
            else:
                rejection_reason = f"Protected entity '{entity}' completely absent from title and description."
                return (0.0, rejection_reason, source_type, is_short)
        
        # Source bonuses
        if source_type == "OFFICIAL_DEVELOPER":
            score += 25
        elif source_type == "OFFICIAL_PLATFORM":
            score += 20
        elif source_type == "KNOWN_MEDIA":
            score += 10
            
        # Intent-specific keywords
        if "gameplay" in intent_lower and "gameplay" in title:
            score += 15
        if "trailer" in intent_lower and "trailer" in title:
            score += 15
            
        year_match = re.search(r'\b(20\d{2})\b', intent_lower)
        if year_match:
            year = year_match.group(1)
            if year in title or year in desc:
                score += 10
                
        # Negative signals
        if is_short and "short" not in intent_lower:
            score -= 30
            
        if "minecraft" in title and entity and entity.lower() != "minecraft":
            rejection_reason = "Unrelated franchise (Minecraft) detected."
            return (0.0, rejection_reason, source_type, is_short)
            
        # Dangerous keyword pollution
        dangerous = {"dream", "fall", "movie"}
        for word in dangerous:
            if word in title and word not in intent_lower:
                score -= 20
        # Exception: if "movie" is in title but we wanted a game trailer, reject it if it's clearly a movie trailer
        if "movie" in title and "trailer" in intent_lower:
            # Let's say we assume it's a movie trailer
            score -= 50
            
        return (score, rejection_reason, source_type, is_short)
