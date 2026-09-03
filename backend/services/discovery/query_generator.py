from typing import List
import re

class QueryGenerator:
    """
    Generates multiple search queries from a VisualIntent.
    For V2, this is deterministic based on the intent description.
    """
    def generate_queries(self, intent_description: str) -> List[str]:
        queries = []
        
        # 1. The literal intent description
        queries.append(intent_description)
        
        # 2. Remove common "noise" words
        stopwords = {"footage", "of", "the", "a", "an", "showing", "video"}
        # preserve apostrophes
        words = re.findall(r"[\w']+", intent_description)
        cleaned_words = [w for w in words if w.lower() not in stopwords]
        cleaned_query = " ".join(cleaned_words)
        if cleaned_words and cleaned_query != intent_description:
            queries.append(cleaned_query)
            
        # 3. Add trailer year if applicable
        years = [w for w in cleaned_words if w.isdigit() and len(w) == 4]
        if years and "trailer" not in cleaned_query.lower():
            year = years[0]
            base = [w for w in cleaned_words if w != year]
            queries.append(" ".join(base) + f" trailer {year}")
            
        # 4. Add gameplay if applicable
        if "gameplay" not in intent_description.lower():
            queries.append(intent_description + " gameplay")
        
        # Deduplicate while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            if q.lower() not in seen:
                seen.add(q.lower())
                unique_queries.append(q)
                
        return unique_queries
