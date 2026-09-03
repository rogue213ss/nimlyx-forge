import click
from backend.database.db import SessionLocal
from backend.database.init_db import init_db
from backend.services.projects.service import (
    create_channel, create_project, create_episode, 
    create_scene, create_narration_segment, create_visual_intent
)
from backend.services.assets.service import (
    create_source_asset, create_asset_mapping, 
    set_mapping_timestamps, update_mapping_state, approve_asset_acquisition
)
from backend.models.enums import AssetState, CopyrightStatus
from backend.models.episode import Episode
from backend.models.scene import Scene
from backend.models.narration_segment import NarrationSegment
from backend.models.asset_mapping import AssetMapping

@click.group()
def cli():
    """Footage Database CLI"""
    pass

@cli.command()
def init():
    """Initialize the database"""
    init_db()
    click.echo("Database initialized.")

@cli.command()
@click.option('--name', required=True, help="Channel name")
def add_channel(name):
    with SessionLocal() as db:
        channel = create_channel(db, name)
        click.echo(f"Created Channel: {channel.id} - {channel.name}")

@cli.command()
@click.option('--channel-id', required=True, type=int)
@click.option('--name', required=True)
def add_project(channel_id, name):
    with SessionLocal() as db:
        project = create_project(db, channel_id, name)
        click.echo(f"Created Project: {project.id} - {project.name}")

@cli.command()
@click.option('--project-id', required=True, type=int)
@click.option('--name', required=True)
def add_episode(project_id, name):
    with SessionLocal() as db:
        episode = create_episode(db, project_id, name)
        click.echo(f"Created Episode: {episode.id} - {episode.name}")

@cli.command()
@click.option('--episode-id', required=True, type=int)
def list_scenes(episode_id):
    with SessionLocal() as db:
        scenes = db.query(Scene).filter(Scene.episode_id == episode_id).order_by(Scene.order_index).all()
        for s in scenes:
            click.echo(f"Scene {s.id}: [{s.order_index}] {s.title}")

@cli.command()
@click.option('--scene-id', required=True, type=int)
def list_segments(scene_id):
    with SessionLocal() as db:
        segments = db.query(NarrationSegment).filter(NarrationSegment.scene_id == scene_id).order_by(NarrationSegment.order_index).all()
        for s in segments:
            click.echo(f"Segment {s.id}: [{s.order_index}] {s.text[:50]}...")

@cli.command()
@click.option('--url', required=True)
@click.option('--platform', default="youtube")
@click.option('--title', default=None)
@click.option('--copyright', type=click.Choice([e.name for e in CopyrightStatus]), default=CopyrightStatus.UNKNOWN.name)
def add_source(url, platform, title, copyright):
    with SessionLocal() as db:
        asset = create_source_asset(db, url, platform, title=title, copyright_status=CopyrightStatus[copyright])
        click.echo(f"Source Asset {asset.id}: {asset.source_url} ({asset.copyright_status.name})")

@cli.command()
@click.option('--intent-id', required=True, type=int)
@click.option('--asset-id', required=True, type=int)
def map_source(intent_id, asset_id):
    with SessionLocal() as db:
        mapping = create_asset_mapping(db, intent_id, asset_id)
        click.echo(f"Asset Mapping {mapping.id}: Intent {intent_id} -> Asset {asset_id} (State: {mapping.state.name})")

@cli.command()
@click.option('--mapping-id', required=True, type=int)
@click.option('--start', required=True, type=float)
@click.option('--end', required=True, type=float)
def set_timestamps(mapping_id, start, end):
    with SessionLocal() as db:
        try:
            mapping = set_mapping_timestamps(db, mapping_id, start, end)
            click.echo(f"Mapping {mapping.id} timestamps set: {mapping.start_timestamp} - {mapping.end_timestamp}")
        except ValueError as e:
            raise click.ClickException(str(e))

@cli.command()
@click.option('--mapping-id', required=True, type=int)
@click.option('--state', type=click.Choice([e.name for e in AssetState]), required=True)
def update_mapping(mapping_id, state):
    with SessionLocal() as db:
        try:
            mapping = update_mapping_state(db, mapping_id, AssetState[state])
            click.echo(f"Mapping {mapping.id} state updated to: {mapping.state.name}")
        except ValueError as e:
            raise click.ClickException(str(e))

@cli.command()
@click.option('--episode-id', required=True, type=int)
def list_footage_status(episode_id):
    with SessionLocal() as db:
        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        if not episode:
            click.echo("Episode not found.")
            return
            
        click.echo(f"Footage status for Episode: {episode.name}")
        for scene in episode.scenes:
            click.echo(f"\nScene: {scene.title}")
            for seg in scene.narration_segments:
                click.echo(f"  Segment: {seg.text[:30]}...")
                for intent in seg.visual_intents:
                    click.echo(f"    Intent: {intent.description}")
                    for mapping in intent.asset_mappings:
                        asset = mapping.source_asset
                        click.echo(f"      -> Asset {asset.id} [{mapping.state.name}]: {asset.source_url}")
                        if mapping.start_timestamp is not None:
                            click.echo(f"         Timestamps: {mapping.start_timestamp} - {mapping.end_timestamp}")

@cli.command()
@click.option('--intent-id', required=True, type=int)
@click.option('--provider', type=click.Choice(['youtube', 'mock']), default='youtube')
def discover_intent(intent_id, provider):
    """Run V2 Source Discovery for a specific VisualIntent."""
    from backend.services.discovery.service import DiscoveryService
    from backend.services.discovery.provider import ProviderInterface
    from backend.services.discovery.models import NormalizedCandidate
    from backend.services.discovery.youtube_provider import YouTubeProvider
    import os
    
    providers = []
    if provider == 'youtube':
        try:
            providers.append(YouTubeProvider())
            click.echo("Using YouTube Provider.")
        except ValueError as e:
            click.echo(f"Warning: {e}")
            click.echo("Falling back to Mock Provider.")
            provider = 'mock'

    if provider == 'mock':
        class CliMockProvider(ProviderInterface):
            @property
            def platform_name(self) -> str:
                return "mock"
            def search(self, query: str, max_results: int = 5):
                click.echo(f"  [MockProvider] Searching for: '{query}'")
                if "FAIL" in query:
                    raise Exception("Simulated provider failure")
                return [
                    NormalizedCandidate(
                        source_url=f"mock://url/{hash(query) % 1000}", 
                        source_platform="mock", 
                        title=f"Mock Result for {query}"
                    )
                ]
        providers.append(CliMockProvider())
            
    def safe_echo(text: str):
        import sys
        encoding = sys.stdout.encoding or 'utf-8'
        click.echo(text.encode(encoding, errors='replace').decode(encoding))

    with SessionLocal() as db:
        service = DiscoveryService(providers=providers)
        try:
            mappings = service.discover_candidates_for_intent(db, intent_id)
            safe_echo(f"Discovery complete. Found {len(mappings)} new candidates.")
            for m in mappings:
                asset = m.source_asset
                safe_echo(f"  -> Asset {asset.id}: {asset.title} ({asset.source_url})")
        except ValueError as e:
            raise click.ClickException(str(e))


@cli.command()
@click.option('--intent-id', required=True, type=int)
def rank_footage(intent_id):
    """Rank footage candidates for a specific VisualIntent."""
    from backend.services.selection.selector import FootageSelector
    with SessionLocal() as db:
        selector = FootageSelector(db)
        candidates = selector.rank_intent(intent_id)
        if not candidates:
            click.echo(f"No candidates found for Intent {intent_id}.")
            return
        
        click.echo(f"Ranked {len(candidates)} candidates for Intent {intent_id}:")
        for m in candidates:
            click.echo(f"  -> Asset {m.source_asset_id}: Score {m.selection_score} ({m.confidence_level})")

@cli.command()
@click.option('--intent-id', required=True, type=int)
def select_footage(intent_id):
    """Automatically select the best candidate and assign selection status for an intent."""
    from backend.services.selection.selector import FootageSelector
    with SessionLocal() as db:
        selector = FootageSelector(db)
        best = selector.select_best_for_intent(intent_id)
        if not best:
            click.echo(f"No candidates found for Intent {intent_id}.")
            return
        
        click.echo(f"Best Candidate: Mapping {best.id} (Asset {best.source_asset_id})")
        click.echo(f"Selection Status: {best.selection_status.name}")

@cli.command()
@click.option('--intent-id', required=True, type=int)
def show_footage_candidates(intent_id):
    """Show detailed explainable JSON output for intent candidates."""
    from backend.models.asset_mapping import AssetMapping
    import json
    with SessionLocal() as db:
        mappings = db.query(AssetMapping).filter(AssetMapping.visual_intent_id == intent_id).all()
        if not mappings:
            click.echo(f"No candidates found for Intent {intent_id}.")
            return
            
        for m in mappings:
            click.echo(f"\n--- Mapping {m.id} (Asset {m.source_asset_id}) ---")
            click.echo(f"Score: {m.selection_score} ({m.confidence_level})")
            click.echo(f"Status: {m.selection_status.name if hasattr(m, 'selection_status') else 'UNSCORED'}")
            if m.selection_reason:
                try:
                    reason_dict = json.loads(m.selection_reason)
                    click.echo(json.dumps(reason_dict, indent=2))
                except:
                    click.echo(m.selection_reason)
            else:
                click.echo("No selection reason available.")

@cli.command()
@click.option('--mapping-id', required=True, type=int)
def create_clip_plan(mapping_id):
    """Creates a clip plan for a mapping if valid timestamps are available."""
    from backend.services.selection.planner import ClipPlanner
    from backend.models.asset_mapping import AssetMapping
    with SessionLocal() as db:
        mapping = db.query(AssetMapping).filter(AssetMapping.id == mapping_id).first()
        if not mapping:
            click.echo("Mapping not found.")
            return
            
        planner = ClipPlanner()
        start, end, t_conf, t_reason = planner.plan_clip(mapping, mapping.source_asset)
        
        mapping.start_timestamp = start
        mapping.end_timestamp = end
        mapping.timestamp_confidence = t_conf
        mapping.timestamp_reason = t_reason
        db.commit()
        
        click.echo(f"Clip plan created for Mapping {mapping.id}:")
        click.echo(f"  Start: {start}")
        click.echo(f"  End: {end}")
        click.echo(f"  Confidence: {t_conf}")
        click.echo(f"  Reason: {t_reason}")

@cli.command()
@click.option('--mapping-id', required=True, type=int)
def show_clip_plan(mapping_id):
    """Shows the clip plan for a mapping."""
    from backend.models.asset_mapping import AssetMapping
    with SessionLocal() as db:
        mapping = db.query(AssetMapping).filter(AssetMapping.id == mapping_id).first()
        if not mapping:
            click.echo("Mapping not found.")
            return
            
        click.echo(f"Clip Plan for Mapping {mapping.id}:")
        click.echo(f"  Start: {mapping.start_timestamp}")
        click.echo(f"  End: {mapping.end_timestamp}")
        click.echo(f"  Confidence: {mapping.timestamp_confidence}")
        click.echo(f"  Reason: {mapping.timestamp_reason}")
if __name__ == "__main__":
    cli()

