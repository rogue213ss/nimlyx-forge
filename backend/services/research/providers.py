from abc import ABC, abstractmethod
from typing import List, Dict, Any

class SourceDiscoveryProvider(ABC):
    @abstractmethod
    def discover(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        pass

class SourceRetrievalProvider(ABC):
    @abstractmethod
    def retrieve(self, url: str) -> Dict[str, Any]:
        pass

class ClaimExtractor(ABC):
    @abstractmethod
    def extract(self, text: str, source_tier: str = "TIER_4", topic: str = "") -> List[Dict[str, Any]]:
        pass

class DummyDiscoveryProvider(SourceDiscoveryProvider):
    def discover(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        return [
            {
                "url": f"http://dummy.com/{hash(query)}",
                "title": f"Dummy title for {query}",
                "publisher": "dummy.com",
                "source_type": "WEB_ARTICLE",
                "reliability_tier": "TIER_4"
            }
        ]

class DummyRetrievalProvider(SourceRetrievalProvider):
    def retrieve(self, url: str) -> Dict[str, Any]:
        if "fail" in url:
            return {"status": "HTTP_ERROR", "error": "Injected failure"}
        return {
            "status": "SUCCESS",
            "content_text": "Dummy content that represents a factual claim about the topic.",
            "content_hash": str(hash(url))
        }

class DummyClaimExtractor(ClaimExtractor):
    def extract(self, text: str, source_tier: str = "TIER_4", topic: str = "") -> List[Dict[str, Any]]:
        if not text:
            return []
        return [
            {
                "claim_text": "Dummy claim 1 extracted.", "normalized_claim_text": "dummy claim 1 extracted.",
                "category": "development",
                "confidence": "HIGH",
                "confidence_reason": "Dummy reason",
                "raw_text": text[:50],
                "evidence_type": "SUPPORTING"
            }
        ]

