from typing import List, Dict
from sqlalchemy.orm import Session
from .provider import ProviderInterface
from .search_plan import SearchPlanGenerator
from .relevance import RelevanceScorer
from .models import NormalizedCandidate
from backend.models.visual_intent import VisualIntent
from backend.models.source_asset import SourceAsset
from backend.models.asset_mapping import AssetMapping
from backend.models.enums import AssetState, CopyrightStatus
from backend.services.assets.service import create_asset_mapping
import logging

logger = logging.getLogger(__name__)

class DiscoveryService:
    def __init__(self, providers: List[ProviderInterface], plan_generator: SearchPlanGenerator = None, scorer: RelevanceScorer = None):
        self.providers = providers
        self.plan_generator = plan_generator or SearchPlanGenerator()
        self.scorer = scorer or RelevanceScorer(plan_generator=self.plan_generator)

    def discover_candidates_for_intent(self, db: Session, intent_id: int) -> List[AssetMapping]:
        """
        Orchestrates V4 discovery for a specific visual intent.
        Returns the new AssetMappings created in CANDIDATE state, ordered by relevance.
        """
        intent = db.query(VisualIntent).filter(VisualIntent.id == intent_id).first()
        if not intent:
            raise ValueError(f"VisualIntent {intent_id} not found")

        # 1. Generate queries (Search Plan)
        queries = self.plan_generator.generate_queries(intent.description)
        
        if intent.search_query and intent.search_query not in queries:
            queries.insert(0, intent.search_query)

        all_candidates: List[NormalizedCandidate] = []
        
        # 2. Run queries across providers
        for provider in self.providers:
            for query in queries:
                try:
                    candidates = provider.search(query)
                    all_candidates.extend(candidates)
                except Exception as e:
                    logger.error(f"Provider {provider.platform_name} failed for query '{query}': {e}")
                    # Continue gracefully if a provider fails

        # 3. Apply Relevance Scoring & Deduplicate
        unique_scored_candidates = {}
        for c in all_candidates:
            if not getattr(c, "source_url", None):
                continue
                
            score, rejection_reason, source_type, is_short = self.scorer.score_candidate(intent.description, c)
            c.relevance_score = score
            c.rejection_reason = rejection_reason
            c.source_type = source_type
            c.is_short = is_short
            
            # Keep highest score if duplicate URL found
            if c.source_url not in unique_scored_candidates:
                unique_scored_candidates[c.source_url] = c
            else:
                if score > unique_scored_candidates[c.source_url].relevance_score:
                    unique_scored_candidates[c.source_url] = c

        new_mappings = []
        
        # Sort candidates by relevance score descending
        sorted_candidates = sorted(unique_scored_candidates.values(), key=lambda x: x.relevance_score, reverse=True)

        # 4. Persist to Database
        for candidate in sorted_candidates:
            if candidate.rejection_reason:
                # Skip rejected candidates completely
                logger.info(f"Rejected candidate {candidate.source_url}: {candidate.rejection_reason}")
                continue
                
            asset = db.query(SourceAsset).filter(SourceAsset.source_url == candidate.source_url).first()
            if not asset:
                asset = SourceAsset(
                    source_url=candidate.source_url,
                    source_platform=candidate.source_platform,
                    source_id=candidate.source_id,
                    title=candidate.title,
                    source_channel=candidate.source_channel,
                    description=candidate.description,
                    source_duration=candidate.duration,
                    thumbnail_url=candidate.thumbnail_url,
                    published_date=candidate.published_date,
                    is_short=candidate.is_short,
                    copyright_status=CopyrightStatus.UNKNOWN
                )
                db.add(asset)
                db.commit()
                db.refresh(asset)
            
            existing_mapping = db.query(AssetMapping).filter(
                AssetMapping.visual_intent_id == intent.id,
                AssetMapping.source_asset_id == asset.id
            ).first()
            
            if not existing_mapping:
                mapping = create_asset_mapping(db, intent.id, asset.id, state=AssetState.CANDIDATE)
                mapping.relevance_score = candidate.relevance_score
                db.commit()
                db.refresh(mapping)
                new_mappings.append(mapping)

        return new_mappings
