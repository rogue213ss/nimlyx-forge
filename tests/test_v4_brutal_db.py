import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.services.projects.service import create_channel, create_project, create_episode, create_scene, create_narration_segment, create_visual_intent
from backend.services.discovery.service import DiscoveryService
from backend.services.discovery.provider import ProviderInterface
from backend.services.discovery.models import NormalizedCandidate
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

class BrutalProvider(ProviderInterface):
    @property
    def platform_name(self) -> str: return "brutal"
    def search(self, query: str, max_results: int = 5):
        if "CRASH" in query:
            raise Exception("Brutal Crash")
        return [
            NormalizedCandidate(source_url="http://good", source_platform="yt", title="No Man's Sky good"),
            NormalizedCandidate(source_url=None, source_platform="yt", title="No Man's Sky missing url"),
        ]

def test_brutal_db_integrity(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent_good = create_visual_intent(db_session, seg1.id, "No Man's Sky good")
    intent_crash = create_visual_intent(db_session, seg1.id, "CRASH test intent")

    service = DiscoveryService(providers=[BrutalProvider()])
    
    # 1. Partial success: 1 good, 1 missing url -> only 1 asset saved
    mappings = service.discover_candidates_for_intent(db_session, intent_good.id)
    assert len(mappings) == 1
    assert mappings[0].state == AssetState.CANDIDATE
    assert mappings[0].source_asset.source_url == "http://good"
    
    # 2. Complete crash during discovery loop
    # Service intercepts the error and logs it, then continues.
    # So it should return 0 mappings and not crash the whole app.
    mappings_crash = service.discover_candidates_for_intent(db_session, intent_crash.id)
    assert len(mappings_crash) == 0
    
    # DB should still be clean (1 asset, 1 mapping)
    assert db_session.query(SourceAsset).count() == 1
    assert db_session.query(AssetMapping).count() == 1

def test_state_machine_invalid_transitions(db_session):
    from backend.services.assets.service import update_mapping_state
    
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent = create_visual_intent(db_session, seg1.id, "No Man's Sky")
    
    asset = SourceAsset(source_url="url", source_platform="yt")
    db_session.add(asset)
    db_session.commit()
    
    mapping = AssetMapping(visual_intent_id=intent.id, source_asset_id=asset.id, state=AssetState.CANDIDATE)
    db_session.add(mapping)
    db_session.commit()
    
    # Valid transition CANDIDATE -> SELECTED
    mapping = update_mapping_state(db_session, mapping.id, AssetState.SELECTED)
    assert mapping.state == AssetState.SELECTED
    
    # Invalid transition SELECTED -> DOWNLOADED (must be VERIFIED/APPROVED first)
    with pytest.raises(ValueError, match="Invalid state transition"):
        update_mapping_state(db_session, mapping.id, AssetState.DOWNLOADED)

