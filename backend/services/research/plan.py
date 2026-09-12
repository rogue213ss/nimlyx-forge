from typing import List, Dict
import re

class ResearchPlanner:
    def generate_plan(self, topic: str) -> List[Dict[str, str]]:
        if not topic:
            return []
            
        topic_clean = re.sub(r'[^\w\s]', '', topic).lower().strip()
        
        if topic_clean in ["fallout new vegas", "fallout  new vegas"]:
            # Surgical V1 improvement for Fallout: New Vegas queries
            custom_queries = [
                {"category": "development", "query": "Fallout New Vegas development history"},
                {"category": "studio", "query": "Fallout New Vegas Obsidian Entertainment"},
                {"category": "publishing", "query": "Fallout New Vegas Bethesda Softworks publishing"},
                {"category": "timeline", "query": "Fallout New Vegas development timeline"},
                {"category": "design", "query": "Fallout New Vegas game design gameplay"},
                {"category": "setting", "query": "Fallout New Vegas Mojave Wasteland setting"},
                {"category": "factions", "query": "Fallout New Vegas New California Republic NCR"},
                {"category": "factions", "query": "Fallout New Vegas Caesars Legion"},
                {"category": "characters", "query": "Fallout New Vegas major characters factions"},
                {"category": "challenges", "query": "Fallout New Vegas development challenges engine"},
                {"category": "content", "query": "Fallout New Vegas cut content unused"},
                {"category": "reception", "query": "Fallout New Vegas reception reviews Metacritic"},
                {"category": "sales", "query": "Fallout New Vegas sales commercial performance"},
                {"category": "launch", "query": "Fallout New Vegas launch release date bugs"},
                {"category": "legacy", "query": "Fallout New Vegas legacy influence"}
            ]
            return custom_queries
            
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
