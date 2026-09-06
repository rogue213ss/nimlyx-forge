from dotenv import load_dotenv
load_dotenv()
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
@cli.command()
@click.option('--project-id', required=True, type=int)
@click.option('--topic', required=False, type=str, help="Sets the project topic for the research plan.")
def research_plan(project_id, topic):
    from backend.services.research.plan import ResearchPlanner
    from backend.models.project import Project
    with SessionLocal() as db:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            click.echo("Project not found.")
            return
            
        if topic:
            project.topic = topic
            db.commit()
            
        use_topic = project.topic or project.name
        
        planner = ResearchPlanner()
        plan = planner.generate_plan(use_topic)
        click.echo(f"Research Plan for '{use_topic}':")
        for p in plan:
            click.echo(f"  - [{p['category']}] {p['query']}")

@cli.command()
@click.option('--project-id', required=True, type=int)
def research(project_id):
    from backend.services.research.engine import ResearchEngine
    from backend.services.research.wikipedia_provider import WikipediaDiscoveryProvider, WikipediaRetrievalProvider
    from backend.services.research.ddg_provider import DuckDuckGoDiscoveryProvider, WebScraperRetrievalProvider
    from backend.services.research.composite_provider import CompositeRetrievalProvider
    from backend.services.research.extractor import AdvancedHeuristicExtractor
    from backend.models.project import Project
    
    with SessionLocal() as db:
        project = db.query(Project).filter_by(id=project_id).first()
        if not project:
            click.echo("Project not found.")
            return
            
        wiki_disc = WikipediaDiscoveryProvider()
        ddg_disc = DuckDuckGoDiscoveryProvider()
        
        retrieval = CompositeRetrievalProvider(WikipediaRetrievalProvider(), WebScraperRetrievalProvider())
        extractor = AdvancedHeuristicExtractor()
        
        engine = ResearchEngine(db, [wiki_disc, ddg_disc], retrieval, extractor)
        run = engine.create_run(project_id, {"query": project.topic or project.name})
        click.echo(f"Created Research Run {run.id}")
        
        click.echo("Executing research plan...")
        engine.execute_plan(run.id)
        
        from backend.models.research_source import ResearchSource
        sources = db.query(ResearchSource).filter_by(discovered_in_run_id=run.id).all()
        click.echo(f"Discovered {len(sources)} sources. Retrieving...")
        
        for src in sources:
            engine.retrieve_source(src.id)
            engine.process_source_claims(run.id, src.id)
            
        engine.complete_run(run.id)
        click.echo(f"Completed Research Run {run.id}")

@cli.command()
@click.option('--run-id', required=True, type=int)
def research_status(run_id):
    from backend.models.research_run import ResearchRun
    with SessionLocal() as db:
        run = db.query(ResearchRun).filter_by(id=run_id).first()
        if not run:
            click.echo("Run not found.")
            return
        click.echo(f"Run {run.id} Status: {run.status.name}")
        click.echo(f"Stats: {run.stats}")

@cli.command()
@click.option('--run-id', required=True, type=int)
def research_sources(run_id):
    from backend.models.research_source import ResearchSource
    with SessionLocal() as db:
        sources = db.query(ResearchSource).filter_by(discovered_in_run_id=run_id).all()
        for src in sources:
            click.echo(f"Source {src.id}: {src.title} ({src.url}) - [{src.scope}] Tier {src.reliability_tier} - {src.retrieval_status.name}")

@cli.command()
@click.option('--run-id', required=True, type=int)
def research_claims(run_id):
    from backend.models.research_claim import ResearchClaim
    with SessionLocal() as db:
        claims = db.query(ResearchClaim).filter_by(research_run_id=run_id).all()
        for claim in claims:
            click.echo(f"Claim {claim.id} [{claim.status.name} | Conf: {claim.confidence}]: {claim.claim_text}")

@cli.command()
@click.option('--claim-id', required=True, type=int)
def research_evidence(claim_id):
    from backend.models.research_claim import ResearchClaim
    with SessionLocal() as db:
        claim = db.query(ResearchClaim).filter_by(id=claim_id).first()
        if not claim:
            click.echo("Claim not found.")
            return
        click.echo(f"Evidence for Claim {claim.id} (Confidence: {claim.confidence} - {claim.confidence_reason}):")
        for ev in claim.evidence:
            src = ev.source
            click.echo(f"  -> Source {ev.source_id} [{src.scope} | {src.reliability_tier}] [{ev.evidence_type.name}]: {ev.raw_text}")





@cli.command()
@click.option('--run-id', required=True, type=int)
def research_quality(run_id):
    from backend.models.research_source import ResearchSource
    from backend.models.research_claim import ResearchClaim
    from backend.models.enums import ClaimStatus
    with SessionLocal() as db:
        # Sources
        sources = db.query(ResearchSource).filter_by(discovered_in_run_id=run_id).all()
        tiers = {}
        scopes = {}
        syndicated = 0
        for s in sources:
            tiers[s.reliability_tier] = tiers.get(s.reliability_tier, 0) + 1
            scopes[s.scope] = scopes.get(s.scope, 0) + 1
            if s.is_syndicated:
                syndicated += 1
                
        # Claims
        claims = db.query(ResearchClaim).filter_by(research_run_id=run_id).all()
        confidences = {}
        categories = {}
        statuses = {}
        qualities = {}
        for c in claims:
            confidences[c.confidence] = confidences.get(c.confidence, 0) + 1
            categories[c.category] = categories.get(c.category, 0) + 1
            statuses[c.status.name] = statuses.get(c.status.name, 0) + 1
            qualities[c.quality_classification] = qualities.get(c.quality_classification, 0) + 1
            
        click.echo(f"--- RESEARCH QUALITY REPORT [RUN {run_id}] ---")
        click.echo(f"\nSOURCES: {len(sources)} total ({syndicated} syndicated)")
        click.echo("Tiers:")
        for k, v in tiers.items(): click.echo(f"  {k}: {v}")
        click.echo("Scopes:")
        for k, v in scopes.items(): click.echo(f"  {k}: {v}")
        
        click.echo(f"\nCLAIMS: {len(claims)} total")
        click.echo("Confidences:")
        for k, v in confidences.items(): click.echo(f"  {k}: {v}")
        click.echo("Statuses:")
        for k, v in statuses.items(): click.echo(f"  {k}: {v}")
        click.echo("Quality Classifications:")
        for k, v in qualities.items(): click.echo(f"  {k}: {v}")
        
        click.echo("\nCOVERAGE BY CATEGORY:")
        for k, v in categories.items(): click.echo(f"  {k}: {v} claims")


@cli.command()
@click.option("--project-id", type=int, required=True)
@click.option("--research-run-id", type=int, required=True)
def story_build(project_id, research_run_id):
    from backend.services.story.builder import StoryBuilder
    from backend.models import Episode, Project, ResearchRun
    
    from backend.database.db import get_db
    db = SessionLocal()
    
    project = db.query(Project).get(project_id)
    r_run = db.query(ResearchRun).get(research_run_id)
    
    episode = db.query(Episode).filter_by(project_id=project_id).first()
    if not episode:
        episode = Episode(project_id=project_id, name="Auto-generated Episode")
        db.add(episode)
        db.commit()
        
    builder = StoryBuilder(db)
    story_run_id = builder.build_story(project_id, episode.id, research_run_id)
    click.echo(f"StoryRun {story_run_id} built successfully.")

@cli.command()
@click.option("--story-run-id", type=int, required=True)
def story_quality(story_run_id):
    from backend.models import StoryRun
    from backend.database.db import get_db
    db = SessionLocal()
    run = db.query(StoryRun).get(story_run_id)
    click.echo(f"Quality: {run.quality_score}")
    click.echo(f"Stats: {run.stats}")

@cli.command()
@click.option("--story-run-id", type=int, required=True)
def story_scenes(story_run_id):
    from backend.models import Scene, NarrationSegment, VisualIntent
    from backend.database.db import get_db
    db = SessionLocal()
    scenes = db.query(Scene).filter_by(story_run_id=story_run_id).order_by(Scene.order_index).all()
    for s in scenes:
        click.echo(f"Scene {s.order_index}: {s.title} [Purpose: {s.purpose}]")
        for n in s.narration_segments:
            click.echo(f"  Narration: {n.text} (Duration: {n.estimated_duration_seconds}s)")
            for vi in n.visual_intents:
                click.echo(f"    Visual: {vi.description}")




@cli.command()
@click.option('--story-run-id', type=int, required=True)
def script_build(story_run_id):
    from backend.database.db import get_db
    db = SessionLocal()
    from backend.services.script.writer import ScriptWriter
    writer = ScriptWriter(db)
    script_id = writer.generate_script(story_run_id)
    click.echo(f"ScriptRun {script_id} generated successfully.")

@cli.command()
@click.option('--script-run-id', type=int, required=True)
def script_status(script_run_id):
    from backend.database.db import get_db
    db = SessionLocal()
    from backend.models.script import ScriptRun
    run = db.query(ScriptRun).get(script_run_id)
    if not run:
        click.echo("Not found")
        return
    click.echo(f"ScriptRun {run.id} Status: {run.status}")

@cli.command()
@click.option('--script-run-id', type=int, required=True)
def script_show(script_run_id):
    from backend.database.db import get_db
    db = SessionLocal()
    from backend.models.script import ScriptSentence
    sentences = db.query(ScriptSentence).filter_by(script_run_id=script_run_id).order_by(ScriptSentence.id).all()
    for s in sentences:
        click.echo(f"[{s.sentence_type}] {s.text}")

@cli.command()
@click.option('--script-run-id', type=int, required=True)
def script_provenance(script_run_id):
    from backend.database.db import get_db
    db = SessionLocal()
    from backend.models.script import ScriptSentence, ClaimReference
    from backend.models import ResearchClaim, ResearchEvidence
    sentences = db.query(ScriptSentence).filter_by(script_run_id=script_run_id).order_by(ScriptSentence.id).all()
    for s in sentences:
        click.echo(f"\nSentence #{s.id}: {s.text}")
        refs = db.query(ClaimReference).filter_by(script_sentence_id=s.id).all()
        for r in refs:
            c = db.query(ResearchClaim).get(r.research_claim_id)
            evs = db.query(ResearchEvidence).filter_by(claim_id=c.id).all()
            for ev in evs:
                click.echo(f" -> Claim #{c.id}: {c.claim_text}")
                click.echo(f"    Evidence #{ev.id} (Source #{ev.source_id})")

@cli.command()
@click.option('--script-run-id', type=int, required=True)
def script_review(script_run_id):
    from backend.database.db import get_db
    db = SessionLocal()
    from backend.models.script import ScriptSentence
    from backend.models.enums import ReviewStatus
    sentences = db.query(ScriptSentence).filter_by(script_run_id=script_run_id).all()
    for s in sentences:
        s.review_status = ReviewStatus.APPROVED.value
    db.commit()
    click.echo(f"ScriptRun {script_run_id} approved explicitly.")


@cli.command()
@click.option('--story-run-id', type=int, required=True)
def llm_script_build(story_run_id):
    db = SessionLocal()
    from backend.services.script.llm_writer import LLMScriptWriter
    writer = LLMScriptWriter(db)
    try:
        s_id = writer.generate_script(story_run_id)
        click.echo(f"LLM ScriptRun {s_id} generated successfully.")
    except Exception as e:
        click.echo(f"Failed to generate LLM script: {e}", err=True)

@cli.command()
@click.option('--script-run-id', type=int, required=True)
def llm_script_show(script_run_id):
    db = SessionLocal()
    from backend.models.script import ScriptSentence
    sents = db.query(ScriptSentence).filter_by(script_run_id=script_run_id).order_by(ScriptSentence.id).all()
    for s in sents:
        click.echo(f"[{s.sentence_type}] ({s.review_status}) {s.text}")

@cli.command()
@click.option('--script-run-id', type=int, required=True)
def llm_script_status(script_run_id):
    db = SessionLocal()
    from backend.models.script import ScriptRun, ScriptSentence
    sr = db.query(ScriptRun).get(script_run_id)
    sents = db.query(ScriptSentence).filter_by(script_run_id=script_run_id).count()
    click.echo(f"LLM ScriptRun: {sr.id} | Status: {sr.status} | Sentences: {sents} | Provider: {sr.provider_name} | Tokens: {sr.token_usage}")

@cli.command()
@click.option('--script-run-id', type=int, required=True)
def llm_script_provenance(script_run_id):
    db = SessionLocal()
    from backend.models.script import ScriptSentence, ClaimReference
    sents = db.query(ScriptSentence).filter_by(script_run_id=script_run_id).order_by(ScriptSentence.id).all()
    for s in sents:
        click.echo(f"\nSentence: {s.text}")
        refs = db.query(ClaimReference).filter_by(script_sentence_id=s.id).all()
        if not refs:
            click.echo("  [NO REFERENCES]")
        for r in refs:
            click.echo(f"  -> Claim #{r.research_claim_id}")

@cli.command()
@click.option('--script-run-id', type=int, required=True)
def llm_script_review(script_run_id):
    db = SessionLocal()
    from backend.models.script import ScriptSentence
    from backend.models.enums import ReviewStatus
    sents = db.query(ScriptSentence).filter_by(script_run_id=script_run_id, review_status=ReviewStatus.NEEDS_REVIEW.value).all()
    click.echo(f"Found {len(sents)} sentences needing review.")


if __name__ == '__main__':
    cli()
