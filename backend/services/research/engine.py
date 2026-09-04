import datetime
import json
import urllib.parse
from sqlalchemy.orm import Session
from backend.models.project import Project
from backend.models.research_run import ResearchRun
from backend.models.research_source import ResearchSource
from backend.models.research_claim import ResearchClaim
from backend.models.research_evidence import ResearchEvidence
from backend.models.enums import ResearchRunStatus, RetrievalStatus, ClaimStatus, EvidenceType
from backend.services.research.providers import SourceDiscoveryProvider, SourceRetrievalProvider, ClaimExtractor
from backend.services.research.plan import ResearchPlanner

def normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    netloc = parsed.netloc.lower()
    path = parsed.path
    if not path:
        path = "/"
    return urllib.parse.urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))

def classify_scope(title: str, topic: str, url: str = "") -> str:
    if not title or not topic:
        return "REJECTED"
    
    title_lower = title.lower()
    topic_lower = topic.lower()
    url_lower = url.lower() if url else ""
    
    topic_words = set(topic_lower.split())
    title_words = set(title_lower.split())
    url_words = set(url_lower.replace('-', ' ').replace('_', ' ').replace('/', ' ').split())
    
    if topic_lower in title_lower or topic_lower.replace(' ', '') in url_lower:
        return "PRIMARY"
        
    game_name = topic_lower.replace(" game", "").replace(" video game", "")
    if game_name in title_lower or game_name.replace(' ', '') in url_lower:
        if game_name + " 2" in title_lower or game_name + " ii" in title_lower:
            return "RELATED"
        return "PRIMARY"
        
    stop_words = {"game", "video", "the", "a", "an", "of", "in", "and", "for", "review"}
    sig_topic_words = topic_words - stop_words
    sig_title_words = title_words - stop_words
    
    if sig_topic_words and sig_topic_words.issubset(sig_title_words):
        return "RELATED"
        
    if sig_topic_words and sig_topic_words.intersection(url_words):
        return "RELATED"
        
    return "REJECTED"

class ResearchEngine:
    def __init__(self, db: Session, discovery_providers: list, retrieval_provider: SourceRetrievalProvider, extractor: ClaimExtractor):
        self.db = db
        self.discovery_providers = discovery_providers if isinstance(discovery_providers, list) else [discovery_providers]
        self.retrieval = retrieval_provider
        self.extractor = extractor
        self.planner = ResearchPlanner()

    def create_run(self, project_id: int, config: dict) -> ResearchRun:
        run = ResearchRun(
            project_id=project_id,
            status=ResearchRunStatus.RUNNING,
            configuration=json.dumps(config, sort_keys=True, separators=(',', ':'))
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def execute_plan(self, run_id: int):
        run = self.db.query(ResearchRun).filter_by(id=run_id).one()
        project = self.db.query(Project).filter_by(id=run.project_id).one()
        topic = project.topic or json.loads(run.configuration or '{}').get("query", "Unknown")
            
        plan_queries = self.planner.generate_plan(topic)
        
        for plan in plan_queries:
            query = plan["query"]
            for provider in self.discovery_providers:
                try:
                    results = provider.discover(query)
                    for res in results:
                        raw_url = res.get("url")
                        if not raw_url:
                            continue
                        canonical = normalize_url(raw_url)
                        
                        existing = self.db.query(ResearchSource).filter_by(
                            project_id=run.project_id, 
                            canonical_url=canonical
                        ).first()
                        
                        if not existing:
                            title = res.get("title", "")
                            scope = classify_scope(title, topic, raw_url)
                            
                            src = ResearchSource(
                                project_id=run.project_id,
                                discovered_in_run_id=run.id,
                                url=raw_url,
                                canonical_url=canonical,
                                title=title,
                                publisher=res.get("publisher"),
                                source_type=res.get("source_type"),
                                reliability_tier=res.get("reliability_tier"),
                                scope=scope,
                                is_syndicated=False
                            )
                            self.db.add(src)
                    self.db.commit()
                except Exception as e:
                    self.db.rollback()
                    continue

    def discover_and_add_sources(self, run_id: int, query: str):
        # Legacy
        run = self.db.query(ResearchRun).filter_by(id=run_id).one()
        project = self.db.query(Project).filter_by(id=run.project_id).one()
        topic = project.topic or query
        
        try:
            results = self.discovery_providers[0].discover(query)
            for res in results:
                raw_url = res.get("url")
                if not raw_url:
                    continue
                canonical = normalize_url(raw_url)
                
                existing = self.db.query(ResearchSource).filter_by(
                    project_id=run.project_id, 
                    canonical_url=canonical
                ).first()
                
                if not existing:
                    title = res.get("title", "")
                    src = ResearchSource(
                        project_id=run.project_id,
                        discovered_in_run_id=run.id,
                        url=raw_url,
                        canonical_url=canonical,
                        title=title,
                        publisher=res.get("publisher"),
                        source_type=res.get("source_type"),
                        reliability_tier=res.get("reliability_tier"),
                        scope=classify_scope(title, topic, raw_url),
                        is_syndicated=False
                    )
                    self.db.add(src)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e

    def retrieve_source(self, source_id: int):
        src = self.db.query(ResearchSource).filter_by(id=source_id).one()
        try:
            if src.scope == 'REJECTED':
                return
            res = self.retrieval.retrieve(src.url)
            status = res.get("status", "SUCCESS")
            
            if status == "SUCCESS":
                src.retrieval_status = RetrievalStatus.SUCCESS
                src.content_text = res.get("content_text")
                c_hash = res.get("content_hash")
                src.content_hash = c_hash
                src.retrieved_at = datetime.datetime.now(datetime.timezone.utc)
                
                # Check for syndication
                if c_hash:
                    existing_hash = self.db.query(ResearchSource).filter(
                        ResearchSource.id != src.id,
                        ResearchSource.content_hash == c_hash,
                        ResearchSource.project_id == src.project_id
                    ).first()
                    if existing_hash:
                        src.is_syndicated = True
            else:
                src.retrieval_status = getattr(RetrievalStatus, status, RetrievalStatus.HTTP_ERROR)
                src.error_info = res.get("error")
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            src.retrieval_status = RetrievalStatus.HTTP_ERROR
            src.error_info = str(e)
            self.db.commit()

    def process_source_claims(self, run_id: int, source_id: int):
        run = self.db.query(ResearchRun).filter_by(id=run_id).one()
        src = self.db.query(ResearchSource).filter_by(id=source_id).one()
        project = self.db.query(Project).filter_by(id=run.project_id).one()
        topic = project.topic or ""
        
        if src.scope == 'REJECTED' or src.retrieval_status != RetrievalStatus.SUCCESS or not src.content_text:
            return
            
        extracted_data = self.extractor.extract(src.content_text, source_tier=src.reliability_tier, topic=topic)
        
        for data in extracted_data:
            normalized_text = data.get("normalized_claim_text")
            temporal_context = data.get("temporal_context")
            if not normalized_text:
                continue
                
            # Deterministic normalisation check
            existing_claim = self.db.query(ResearchClaim).filter_by(
                project_id=run.project_id,
                normalized_claim_text=normalized_text,
                temporal_context=temporal_context
            ).first()
            
            if not existing_claim:
                existing_claim = ResearchClaim(
                    project_id=run.project_id,
                    research_run_id=run.id,
                    claim_text=data.get("claim_text"),
                    normalized_claim_text=normalized_text,
                    temporal_context=temporal_context,
                    category=data.get("category"),
                    confidence=data.get("confidence"),
                    confidence_reason=data.get("confidence_reason"),
                    confidence_signals=data.get("confidence_signals"),
                    quality_classification=data.get("quality_classification"),
                    status=ClaimStatus.UNVERIFIED
                )
                self.db.add(existing_claim)
                self.db.commit()
                self.db.refresh(existing_claim)
                
            existing_ev = self.db.query(ResearchEvidence).filter_by(
                claim_id=existing_claim.id,
                source_id=src.id,
                raw_text=data.get("raw_text")
            ).first()
            
            if not existing_ev:
                ev_type = getattr(EvidenceType, data.get("evidence_type", "SUPPORTING"))
                ev = ResearchEvidence(
                    claim_id=existing_claim.id,
                    source_id=src.id,
                    raw_text=data.get("raw_text"),
                    evidence_type=ev_type,
                    evidence_quality=data.get("evidence_quality"),
                    evidence_quality_reason=data.get("evidence_quality_reason")
                )
                self.db.add(ev)
                self.db.commit()
                
            # Update verification status
            # Count independent sources (not syndicated)
            independent_sources = self.db.query(ResearchEvidence).join(ResearchSource).filter(
                ResearchEvidence.claim_id == existing_claim.id,
                ResearchSource.is_syndicated == False
            ).group_by(ResearchSource.id).count()
            
            # Check for conflicting evidence
            conflicts = self.db.query(ResearchEvidence).filter(
                ResearchEvidence.claim_id == existing_claim.id,
                ResearchEvidence.evidence_type == EvidenceType.CONTRADICTING
            ).count()
            
            if conflicts > 0:
                existing_claim.status = ClaimStatus.CONFLICTED
            elif independent_sources > 1:
                existing_claim.status = ClaimStatus.CORROBORATED
            elif independent_sources == 1:
                existing_claim.status = ClaimStatus.SINGLE_SOURCE
            
            self.db.commit()

    def complete_run(self, run_id: int):
        run = self.db.query(ResearchRun).filter_by(id=run_id).one()
        run.status = ResearchRunStatus.COMPLETED
        run.completed_at = datetime.datetime.now(datetime.timezone.utc)
        
        sources_count = self.db.query(ResearchSource).filter_by(discovered_in_run_id=run.id).count()
        claims_count = self.db.query(ResearchClaim).filter_by(research_run_id=run.id).count()
        
        stats = {
            "sources_discovered": sources_count,
            "claims_extracted": claims_count
        }
        run.stats = json.dumps(stats, sort_keys=True, separators=(',', ':'))
        self.db.commit()

