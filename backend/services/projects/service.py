from sqlalchemy.orm import Session
from backend.models.channel import Channel
from backend.models.project import Project
from backend.models.episode import Episode
from backend.models.scene import Scene
from backend.models.narration_segment import NarrationSegment
from backend.models.visual_intent import VisualIntent

def create_channel(db: Session, name: str) -> Channel:
    channel = Channel(name=name)
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel

def create_project(db: Session, channel_id: int, name: str) -> Project:
    project = Project(channel_id=channel_id, name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

def create_episode(db: Session, project_id: int, name: str) -> Episode:
    episode = Episode(project_id=project_id, name=name)
    db.add(episode)
    db.commit()
    db.refresh(episode)
    return episode

def create_scene(db: Session, episode_id: int, title: str, order_index: int) -> Scene:
    scene = Scene(episode_id=episode_id, title=title, order_index=order_index)
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene

def create_narration_segment(db: Session, scene_id: int, text: str, order_index: int) -> NarrationSegment:
    segment = NarrationSegment(scene_id=scene_id, text=text, order_index=order_index)
    db.add(segment)
    db.commit()
    db.refresh(segment)
    return segment

def create_visual_intent(db: Session, narration_segment_id: int, description: str, search_query: str = None) -> VisualIntent:
    intent = VisualIntent(narration_segment_id=narration_segment_id, description=description, search_query=search_query)
    db.add(intent)
    db.commit()
    db.refresh(intent)
    return intent
