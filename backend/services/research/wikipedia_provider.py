import requests
import urllib.parse
from typing import List, Dict, Any
from backend.services.research.providers import SourceDiscoveryProvider, SourceRetrievalProvider, ClaimExtractor

USER_AGENT = 'NimlyxForgeBot/1.0 (ResearchEngine; backend)'

class WikipediaDiscoveryProvider(SourceDiscoveryProvider):
    def discover(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": "1"
        }
        headers = {'User-Agent': USER_AGENT}
        
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        if "query" in data and "search" in data["query"]:
            for item in data["query"]["search"][:5]:  # Take top 5 search results
                title = item["title"]
                results.append({
                    "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
                    "title": title,
                    "publisher": "Wikipedia",
                    "source_type": "WIKI_ARTICLE",
                    "reliability_tier": "TIER_3"
                })
                
        return results

class WikipediaRetrievalProvider(SourceRetrievalProvider):
    def retrieve(self, url: str) -> Dict[str, Any]:
        headers = {'User-Agent': USER_AGENT}
        
        # Extract title from URL (e.g., https://en.wikipedia.org/wiki/Cyberpunk_2077)
        parsed = urllib.parse.urlparse(url)
        title = urllib.parse.unquote(parsed.path.split('/')[-1])
        
        api_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={urllib.parse.quote(title)}&format=json"
        res = requests.get(api_url, headers=headers)
        res.raise_for_status()
        data = res.json()
        
        pages = data.get('query', {}).get('pages', {})
        if not pages or "-1" in pages:
            return {"status": "NOT_FOUND", "error": "Wikipedia page not found."}
            
        page = list(pages.values())[0]
        extract = page.get('extract', '')
        
        if not extract:
            return {"status": "MALFORMED", "error": "No text extract found."}
            
        return {
            "status": "SUCCESS",
            "content_text": extract,
            "content_hash": str(hash(extract))
        }

class HeuristicClaimExtractor(ClaimExtractor):
    def extract(self, text: str) -> List[Dict[str, Any]]:
        claims = []
        paragraphs = text.split('\n')
        
        keywords = {
            "development": ["develop", "engine", "studio", "director", "programmer", "budget"],
            "release": ["released", "launch", "delayed", "announced", "trailer"],
            "sales": ["sold", "million", "copies", "revenue", "grossed"],
            "reception": ["received", "reviews", "critic", "score", "metacritic", "award"]
        }
        
        for p in paragraphs:
            p = p.strip()
            if len(p) < 50:
                continue
                
            p_lower = p.lower()
            found_category = None
            
            for cat, words in keywords.items():
                if any(w in p_lower for w in words):
                    found_category = cat
                    break
                    
            if found_category:
                # Take first sentence roughly
                first_sentence = p.split('. ')[0] + '.'
                if len(first_sentence) > 200:
                    first_sentence = first_sentence[:197] + '...'
                    
                claims.append({
                    "claim_text": first_sentence,
                    "category": found_category,
                    "confidence": "MEDIUM",
                    "raw_text": p,
                    "evidence_type": "SUPPORTING"
                })
                
        return claims
