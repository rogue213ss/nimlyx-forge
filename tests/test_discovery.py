import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.db import Base
from backend.services.projects.service import create_channel, create_project, create_episode, create_scene, create_narration_segment, create_visual_intent
from backend.services.discovery.query_generator import QueryGenerator
from backend.services.discovery.provider import ProviderInterface
from backend.services.discovery.models import NormalizedCandidate
from backend.services.discovery.service import DiscoveryService
from backend.models.enums import AssetState
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

# 1 & 2: VisualIntent -> search query generation & multiple queries
def test_query_generator():
    generator = QueryGenerator()
    queries = generator.generate_queries("No Man's Sky 2016 launch day footage")
    assert "No Man's Sky 2016 launch day footage" in queries
    assert len(queries) > 1
    assert any("2016" in q for q in queries)

class MockProvider(ProviderInterface):
    def __init__(self, platform_name="mock_platform"):
        self._platform_name = platform_name
        self.mock_results = []
        self.called_queries = []

    @property
    def platform_name(self) -> str:
        return self._platform_name

    def search(self, query: str, max_results: int = 5):
        self.called_queries.append(query)
        if query == "FAIL":
            raise Exception("Provider failed")
        return self.mock_results

# 3, 4, 6: normalized provider result -> SourceAsset, duplicate source URL reuse, newly discovered always CANDIDATE
def test_discovery_orchestration(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "NMS 2016 launch")

    provider = MockProvider()
    provider.mock_results = [
        NormalizedCandidate(source_url="url1", source_platform="yt", title="Vid1"),
        NormalizedCandidate(source_url="url2", source_platform="yt", title="Vid2")
    ]
    
    service = DiscoveryService(providers=[provider])
    mappings = service.discover_candidates_for_intent(db_session, intent1.id)
    
    assert len(mappings) == 2
    for m in mappings:
        assert m.state == AssetState.CANDIDATE # 6: always creates AssetMappings in CANDIDATE
    
    db_session.commit()
    assets = db_session.query(SourceAsset).all()
    assert len(assets) == 2 # 3: normalized provider result -> SourceAsset

    # Re-run discovery with the same provider results.
    mappings_again = service.discover_candidates_for_intent(db_session, intent1.id)
    assert len(mappings_again) == 0 # existing mappings are not duplicated
    
    # Check that we haven't duplicated the source assets
    assets_again = db_session.query(SourceAsset).all()
    assert len(assets_again) == 2 # 4: duplicate source URL reuse
    
# 5: same SourceAsset mapped to multiple VisualIntents
def test_same_source_multiple_intents(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "NMS intent 1")
    intent2 = create_visual_intent(db_session, seg1.id, "NMS intent 2")

    provider = MockProvider()
    provider.mock_results = [
        NormalizedCandidate(source_url="url_shared", source_platform="yt", title="VidShared")
    ]
    service = DiscoveryService(providers=[provider])
    
    service.discover_candidates_for_intent(db_session, intent1.id)
    service.discover_candidates_for_intent(db_session, intent2.id)
    
    # There should only be 1 SourceAsset, but 2 AssetMappings
    assets = db_session.query(SourceAsset).all()
    assert len(assets) == 1
    
    mappings = db_session.query(AssetMapping).all()
    assert len(mappings) == 2
    assert mappings[0].visual_intent_id != mappings[1].visual_intent_id

# 7 & 8: discovery cannot bypass state machine, provider failures do not corrupt database
def test_discovery_provider_failures(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    # The intent is "FAIL" to trigger the mock provider exception
    intent1 = create_visual_intent(db_session, seg1.id, "FAIL")

    provider = MockProvider()
    service = DiscoveryService(providers=[provider])
    
    # Should not raise exception to the caller, just logs and continues
    mappings = service.discover_candidates_for_intent(db_session, intent1.id)
    assert len(mappings) == 0

# 9: malformed provider metadata is rejected cleanly
def test_malformed_metadata_rejected(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "intent")

    provider = MockProvider()
    # Malformed because source_url is missing
    class MalformedCandidate:
        source_platform = "yt"
        title = "Missing URL"
    
    provider.mock_results = [
        NormalizedCandidate(source_url="valid_url", source_platform="yt"),
        MalformedCandidate()
    ]
    service = DiscoveryService(providers=[provider])
    
    mappings = service.discover_candidates_for_intent(db_session, intent1.id)
    assert len(mappings) == 1
    assert mappings[0].source_asset.source_url == "valid_url"

# 10: discovery is provider-agnostic
def test_multiple_providers(db_session):
    channel = create_channel(db_session, "C")
    project = create_project(db_session, channel.id, "P")
    ep = create_episode(db_session, project.id, "E")
    scene = create_scene(db_session, ep.id, "S", 1)
    seg1 = create_narration_segment(db_session, scene.id, "T1", 1)
    intent1 = create_visual_intent(db_session, seg1.id, "intent")

    provider1 = MockProvider("yt")
    provider1.mock_results = [NormalizedCandidate(source_url="p1_url", source_platform="yt")]
    
    provider2 = MockProvider("igdb")
    provider2.mock_results = [NormalizedCandidate(source_url="p2_url", source_platform="igdb")]
    
    service = DiscoveryService(providers=[provider1, provider2])
    service.discover_candidates_for_intent(db_session, intent1.id)
    
    assets = db_session.query(SourceAsset).all()
    assert len(assets) == 2
    platforms = set([a.source_platform for a in assets])
    assert "yt" in platforms
    assert "igdb" in platforms
