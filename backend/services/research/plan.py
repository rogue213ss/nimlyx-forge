from typing import List, Dict

class ResearchPlanner:
    def generate_plan(self, topic: str) -> List[Dict[str, str]]:
        if not topic:
            return []
            
        categories = [
            "development",
            "developers studio",
            "origins",
            "funding Kickstarter",
            "technology design engine",
            "announcement",
            "marketing",
            "release",
            "launch",
            "reception",
            "sales commercial performance",
            "post launch updates",
            "community",
            "awards",
            "legacy"
        ]
        
        queries = []
        for cat in categories:
            queries.append({
                "category": cat.split()[0], # use first word as internal category name
                "query": f"{topic} {cat}"
            })
            
        return queries
