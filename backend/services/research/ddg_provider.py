import requests
import re
import urllib.parse
from typing import List, Dict, Any
from backend.services.research.providers import SourceDiscoveryProvider, SourceRetrievalProvider

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

class DuckDuckGoDiscoveryProvider(SourceDiscoveryProvider):
    def discover(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        url = "https://lite.duckduckgo.com/lite/"
        data = {"q": query}
        headers = {
            'User-Agent': USER_AGENT,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        
        results = []
        links = re.findall(r'<a.*?href="([^"]+)".*?class=["\']result-link["\'].*?>(.*?)</a>', response.text)
        
        for href, title in links[:5]:
            title_clean = re.sub(r'<[^>]+>', '', title).strip()
            
            # Determine reliability tier explicitly
            netloc = urllib.parse.urlparse(href).netloc.lower()
            tier = "TIER_4"
            if "wikipedia.org" in netloc:
                continue # Let wikipedia provider handle wikipedia
            elif any(x in netloc for x in ["bandainamcoent", "fromsoftware", "nintendo", "playstation", "xbox", "steampowered", "cdprojekt", "supergiant"]):
                tier = "TIER_1"
            elif any(x in netloc for x in ["ign.com", "polygon.com", "pcgamer.com", "kotaku.com", "eurogamer.net", "gamespot.com", "destructoid.com"]):
                tier = "TIER_2"
            elif any(x in netloc for x in ["fandom.com", "reddit.com", "wiki"]):
                tier = "TIER_4"
                
            results.append({
                "url": href,
                "title": title_clean,
                "publisher": netloc,
                "source_type": "WEB_ARTICLE",
                "reliability_tier": tier
            })
            
        return results

class WebScraperRetrievalProvider(SourceRetrievalProvider):
    def retrieve(self, url: str) -> Dict[str, Any]:
        headers = {'User-Agent': USER_AGENT}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        
        # Extremely crude HTML to Text extraction
        text = re.sub(r'<script.*?</script>', ' ', res.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        if not text:
            return {"status": "MALFORMED", "error": "No text content extracted"}
            
        return {
            "status": "SUCCESS",
            "content_text": text,
            "content_hash": str(hash(text))
        }
