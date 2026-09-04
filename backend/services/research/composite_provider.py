from typing import Dict, Any
from backend.services.research.providers import SourceRetrievalProvider

class CompositeRetrievalProvider(SourceRetrievalProvider):
    def __init__(self, wiki_provider, web_provider):
        self.wiki_provider = wiki_provider
        self.web_provider = web_provider
        
    def retrieve(self, url: str) -> Dict[str, Any]:
        if "wikipedia.org" in url:
            return self.wiki_provider.retrieve(url)
        return self.web_provider.retrieve(url)
