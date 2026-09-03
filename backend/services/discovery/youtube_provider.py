import os
import re
from typing import List
from datetime import datetime, timezone
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

from .provider import ProviderInterface
from .models import NormalizedCandidate

load_dotenv()
logger = logging.getLogger(__name__)

class YouTubeProvider(ProviderInterface):
    def __init__(self, api_key: str = None, max_results: int = None):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        if not self.api_key or self.api_key == "your_api_key_here":
            raise ValueError("YOUTUBE_API_KEY is not set or is invalid.")
        
        try:
            max_results_env = int(os.environ.get("YOUTUBE_MAX_RESULTS", 10))
        except ValueError:
            max_results_env = 10
            
        self.max_results = max_results or max_results_env
        self.youtube = build('youtube', 'v3', developerKey=self.api_key, cache_discovery=False)

    @property
    def platform_name(self) -> str:
        return "youtube"

    def canonicalize_url(self, video_id: str) -> str:
        return f"https://www.youtube.com/watch?v={video_id}"

    def parse_duration(self, duration_str: str) -> float:
        """Parses ISO 8601 duration (PT#M#S) into seconds."""
        if not duration_str:
            return None
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            return None
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return float(hours * 3600 + minutes * 60 + seconds)

    def parse_published_date(self, date_str: str) -> datetime:
        if not date_str:
            return None
        # Format: 2016-08-09T14:00:00Z
        try:
            # Python 3.11+ supports fromisoformat with Z
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    def search(self, query: str, max_results: int = None) -> List[NormalizedCandidate]:
        limit = max_results or self.max_results
        try:
            # 1. Search for video IDs
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=limit,
                type='video'
            ).execute()

            video_ids = []
            for item in search_response.get('items', []):
                if item['id']['kind'] == 'youtube#video':
                    video_ids.append(item['id']['videoId'])

            if not video_ids:
                return []

            # 2. Get video details (for duration and accurate metadata)
            video_response = self.youtube.videos().list(
                id=','.join(video_ids),
                part='snippet,contentDetails'
            ).execute()

            candidates = []
            for item in video_response.get('items', []):
                vid = item['id']
                snippet = item.get('snippet', {})
                contentDetails = item.get('contentDetails', {})
                
                thumbnails = snippet.get('thumbnails', {})
                thumbnail_url = None
                if 'high' in thumbnails:
                    thumbnail_url = thumbnails['high']['url']
                elif 'default' in thumbnails:
                    thumbnail_url = thumbnails['default']['url']

                candidates.append(NormalizedCandidate(
                    source_url=self.canonicalize_url(vid),
                    source_platform=self.platform_name,
                    source_id=vid,
                    title=snippet.get('title'),
                    source_channel=snippet.get('channelTitle'),
                    description=snippet.get('description'),
                    duration=self.parse_duration(contentDetails.get('duration')),
                    thumbnail_url=thumbnail_url,
                    published_date=self.parse_published_date(snippet.get('publishedAt'))
                ))
            return candidates

        except HttpError as e:
            logger.error(f"YouTube API HttpError: {e}")
            raise Exception(f"YouTube API Error: {e.resp.status}") from e
        except Exception as e:
            logger.error(f"Unexpected error in YouTubeProvider: {e}")
            raise
