import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from backend.database.db import SessionLocal
from backend.models.scene import Scene
from backend.services.projects.service import create_narration_segment, create_visual_intent

def seed_v2():
    with SessionLocal() as db:
        scenes = db.query(Scene).all()
        for scene in scenes:
            if not scene.narration_segments:
                seg = create_narration_segment(db, scene.id, f"Narration for {scene.title}", 1)
                create_visual_intent(db, seg.id, f"No Man's Sky {scene.title.lower()} gameplay")
                create_visual_intent(db, seg.id, f"No Man's Sky {scene.title.lower()} trailer")
        print("Seeded NarrationSegments and VisualIntents")

if __name__ == '__main__':
    seed_v2()
