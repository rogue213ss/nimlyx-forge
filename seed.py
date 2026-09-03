import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from backend.database.db import SessionLocal
from backend.database.init_db import init_db
from backend.services.projects.service import create_channel, create_project, create_episode, create_scene

SCENES = [
    "The Impossible Dream",
    "18 Quintillion Planets",
    "The Hype",
    "The Pressure",
    "Launch Day",
    "The Reality",
    "The Multiplayer Controversy",
    "The Player Collapse",
    "The Silence",
    "Foundation",
    "Atlas Rises",
    "NEXT",
    "Beyond",
    "Origins",
    "Years of Updates",
    "The Comeback",
    "2026 / 10th Anniversary",
    "Light No Fire / Legacy",
    "Final Conclusion"
]

def seed():
    init_db()
    with SessionLocal() as db:
        # Create Channel
        channel = create_channel(db, "Gaming Documentary")
        print(f"Created Channel: {channel.name}")

        # Create Project
        project = create_project(db, channel.id, "No Man's Sky")
        print(f"Created Project: {project.name}")

        # Create Episode
        episode = create_episode(db, project.id, "How No Man's Sky Went From Gaming's Biggest Disaster to Its Greatest Comeback")
        print(f"Created Episode: {episode.name}")

        # Create Scenes
        for i, scene_title in enumerate(SCENES):
            scene = create_scene(db, episode.id, scene_title, i + 1)
            print(f"  Created Scene {scene.order_index}: {scene.title}")

if __name__ == "__main__":
    seed()
