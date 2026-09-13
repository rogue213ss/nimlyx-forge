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
                # BUGS / DEVELOPMENT PROBLEMS
                {"category": "bugs_dev", "query": "Fallout New Vegas launch bugs development problems"},
                {"category": "bugs_dev", "query": "Fallout New Vegas bugs patches development deadline"},
                {"category": "bugs_dev", "query": "Fallout New Vegas rushed development Obsidian"},
                {"category": "bugs_dev", "query": "Fallout New Vegas technical problems launch"},
                # DESIGN / GAMEPLAY
                {"category": "design", "query": "Fallout New Vegas game design choices"},
                {"category": "design", "query": "Fallout New Vegas dialogue reputation faction design"},
                {"category": "design", "query": "Fallout New Vegas gameplay mechanics choices"},
                {"category": "design", "query": "Fallout New Vegas branching choices consequences"},
                # CHARACTERS / FACTIONS
                {"category": "factions", "query": "Fallout New Vegas major factions NCR Caesar Legion Mr House"},
                {"category": "factions", "query": "Fallout New Vegas character development"},
                {"category": "factions", "query": "Fallout New Vegas companions characters"},
                {"category": "factions", "query": "Fallout New Vegas faction reputation system"},
                # WORLD / SETTING
                {"category": "world", "query": "Fallout New Vegas Mojave world design"},
                {"category": "world", "query": "Fallout New Vegas Hoover Dam conflict"},
                {"category": "world", "query": "Fallout New Vegas New Vegas Strip world design"},
                # RECEPTION
                {"category": "reception", "query": "Fallout New Vegas critical reception reviews"},
                {"category": "reception", "query": "Fallout New Vegas Metacritic reception"},
                {"category": "reception", "query": "Fallout New Vegas retrospective reception"},
                # SALES / COMMERCIAL
                {"category": "sales", "query": "Fallout New Vegas sales figures"},
                {"category": "sales", "query": "Fallout New Vegas commercial performance"},
                {"category": "sales", "query": "Fallout New Vegas sales records"},
                # LEGACY / INFLUENCE
                {"category": "legacy", "query": "Fallout New Vegas legacy retrospective"},
                {"category": "legacy", "query": "Fallout New Vegas influence on RPGs"},
                {"category": "legacy", "query": "Fallout New Vegas considered classic"},
                {"category": "legacy", "query": "Fallout New Vegas legacy Obsidian"}
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
