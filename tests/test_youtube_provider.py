import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from backend.services.discovery.youtube_provider import YouTubeProvider
from googleapiclient.errors import HttpError
import os

# 1. YouTube response -> NormalizedCandidate
# 2. Canonical URL generation
# 3. video ID extraction
# 5. missing API key
# 6. quota/API error
# 9. Configurable max results

def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="is not set or is invalid"):
        YouTubeProvider()

@patch('backend.services.discovery.youtube_provider.build')
def test_youtube_provider_success(mock_build, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test_key")
    monkeypatch.setenv("YOUTUBE_MAX_RESULTS", "2")
    
    # Mock the API responses
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    
    mock_search = MagicMock()
    mock_service.search().list = mock_search
    mock_search_request = MagicMock()
    mock_search.return_value = mock_search_request
    mock_search_request.execute.return_value = {
        'items': [
            {'id': {'kind': 'youtube#video', 'videoId': 'vid1'}},
            {'id': {'kind': 'youtube#channel', 'channelId': 'ignore_me'}}
        ]
    }
    
    mock_videos = MagicMock()
    mock_service.videos().list = mock_videos
    mock_videos_request = MagicMock()
    mock_videos.return_value = mock_videos_request
    mock_videos_request.execute.return_value = {
        'items': [
            {
                'id': 'vid1',
                'snippet': {
                    'title': 'Test Video',
                    'channelTitle': 'Test Channel',
                    'publishedAt': '2016-08-09T14:00:00Z',
                    'description': 'A test video',
                    'thumbnails': {'high': {'url': 'http://thumb'}}
                },
                'contentDetails': {
                    'duration': 'PT1H2M3S'
                }
            }
        ]
    }
    
    provider = YouTubeProvider()
    assert provider.max_results == 2
    
    candidates = provider.search("test query")
    
    # Assert API was called correctly
    mock_search.assert_called_with(q="test query", part="id,snippet", maxResults=2, type="video")
    mock_videos.assert_called_with(id="vid1", part="snippet,contentDetails")
    
    # Assert Candidate Normalization
    assert len(candidates) == 1
    c = candidates[0]
    assert c.source_url == "https://www.youtube.com/watch?v=vid1"
    assert c.source_platform == "youtube"
    assert c.source_id == "vid1"
    assert c.title == "Test Video"
    assert c.source_channel == "Test Channel"
    assert c.description == "A test video"
    assert c.duration == 3723.0  # 1 hour, 2 min, 3 sec
    assert c.thumbnail_url == "http://thumb"
    assert c.published_date.year == 2016

@patch('backend.services.discovery.youtube_provider.build')
def test_youtube_provider_http_error(mock_build, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test_key")
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    
    # Simulate HttpError
    mock_search = MagicMock()
    mock_service.search().list = mock_search
    mock_search_request = MagicMock()
    mock_search.return_value = mock_search_request
    
    resp = MagicMock()
    resp.status = 403
    mock_search_request.execute.side_effect = HttpError(resp, b"Quota Exceeded")
    
    provider = YouTubeProvider()
    with pytest.raises(Exception, match="YouTube API Error: 403"):
        provider.search("test")

def test_parse_duration():
    # We can test this without mocking since it's a pure function
    provider = YouTubeProvider(api_key="fake")
    assert provider.parse_duration("PT1M") == 60.0
    assert provider.parse_duration("PT1H") == 3600.0
    assert provider.parse_duration("PT1H1M1S") == 3661.0
    assert provider.parse_duration(None) is None
    assert provider.parse_duration("invalid") is None
