import re
from typing import List, Optional

# A configurable list of protected entities (e.g., game titles) that must be exact-matched in searches.
PROTECTED_ENTITIES = [
    "No Man's Sky",
    "Cyberpunk 2077",
    "Elden Ring",
    "Red Dead Redemption 2",
    "The Witcher 3",
    "Minecraft"
]

AMBIGUOUS_KEYWORDS = {
    "dream", "fall", "war", "world", "rise", "survive", "dead", "future", "origin", "disaster", "comeback"
}

class SearchPlanGenerator:
    """
    Deterministically generates strict search queries by isolating protected entities,
    removing narrative/ambiguous noise, and applying targeted footage-type heuristics.
    """
    
    def __init__(self, protected_entities: List[str] = None):
        self.protected_entities = protected_entities or PROTECTED_ENTITIES

    def _extract_protected_entity(self, intent_desc: str) -> Optional[str]:
        # Sort by length descending to match longest first (e.g., 'The Witcher 3' before 'The Witcher')
        sorted_entities = sorted(self.protected_entities, key=len, reverse=True)
        lower_desc = intent_desc.lower()
        for entity in sorted_entities:
            if entity.lower() in lower_desc:
                return entity
        return None

    def generate_queries(self, intent_description: str) -> List[str]:
        if not intent_description or not intent_description.strip():
            return []
            
        queries = []
        lower_desc = intent_description.lower()
        
        entity = self._extract_protected_entity(intent_description)
        
        is_trailer = "trailer" in lower_desc
        is_gameplay = "gameplay" in lower_desc
        
        # If neither trailer nor gameplay is explicitly requested, default to gameplay for safety
        if not is_trailer and not is_gameplay:
            is_gameplay = True

        year_match = re.search(r'\b(20\d{2})\b', intent_description)
        year = year_match.group(1) if year_match else None

        # Build base queries around the protected entity
        if entity:
            quoted_entity = f'"{entity}"'
            
            if is_gameplay:
                queries.append(f'{quoted_entity} gameplay')
                if year:
                    queries.append(f'{quoted_entity} gameplay {year}')
                if "launch" in lower_desc or "release" in lower_desc:
                    queries.append(f'{quoted_entity} launch gameplay')
                # Source-oriented
                queries.append(f'{quoted_entity} official gameplay')
                
            if is_trailer:
                queries.append(f'{quoted_entity} official trailer')
                if year:
                    queries.append(f'{quoted_entity} {year} trailer')
                # Source-oriented (assuming PlayStation or dev channel)
                queries.append(f'{quoted_entity} PlayStation trailer')
                
        else:
            # Fallback if no protected entity is found: clean the string
            # Remove ambiguous narrative words
            words = re.findall(r"[\w']+", intent_description)
            cleaned_words = [w for w in words if w.lower() not in AMBIGUOUS_KEYWORDS]
            cleaned_query = " ".join(cleaned_words)
            queries.append(cleaned_query)
            if is_gameplay and "gameplay" not in cleaned_query.lower():
                queries.append(f"{cleaned_query} gameplay")

        # Deduplicate while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            if q.lower() not in seen:
                seen.add(q.lower())
                unique_queries.append(q)
                
        return unique_queries
