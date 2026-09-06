import pytest
import os
import time
from unittest.mock import patch, MagicMock
from backend.services.llm.gemini_provider import GeminiProvider
from backend.services.llm.rate_limiter import GeminiRateLimiter

@pytest.fixture(autouse=True)
def clean_env():
    GeminiRateLimiter.reset()
    keys = ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_4", "GEMINI_API_KEY2", "GEMINI_API_KEY3", "GEMINI_API_KEY4", "LLM_FALLBACK_MODELS"]
    for k in keys:
        if k in os.environ:
            del os.environ[k]
    yield
    for k in keys:
        if k in os.environ:
            del os.environ[k]
            
def set_keys():
    os.environ["GEMINI_API_KEY"] = "key1"
    os.environ["GEMINI_API_KEY_2"] = "key2"
    os.environ["GEMINI_API_KEY_3"] = "key3"
    os.environ["GEMINI_API_KEY_4"] = "key4"

@patch("backend.services.llm.gemini_provider.genai.Client")
def test_key_1_excluded_when_multiple_keys_discovered(mock_client_cls):
    set_keys()
    
    used_keys = []
    
    def side_effect(api_key=None):
        used_keys.append(api_key)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"sentences": []}'
        mock_client.models.generate_content.return_value = mock_response
        return mock_client
        
    mock_client_cls.side_effect = side_effect
    
    provider = GeminiProvider()
    provider.generate_script({}, {"model": "model-a"})
    
    assert "key2" in used_keys
    assert "key1" not in used_keys

@patch("backend.services.llm.gemini_provider.genai.Client")
@patch("backend.services.llm.gemini_provider.time.sleep")
def test_key2_fails_key3_succeeds(mock_sleep, mock_client_cls):
    set_keys()
    
    mock_client_2 = MagicMock()
    mock_client_3 = MagicMock()
    
    def side_effect(api_key=None):
        if api_key == "key2": return mock_client_2
        if api_key == "key3": return mock_client_3
        return MagicMock()
        
    mock_client_cls.side_effect = side_effect
    
    mock_response = MagicMock()
    mock_response.text = '{"sentences": []}'
    
    mock_client_2.models.generate_content.side_effect = Exception("503 UNAVAILABLE")
    mock_client_3.models.generate_content.return_value = mock_response
    
    provider = GeminiProvider()
    provider.generate_script({}, {"model": "model-a"})
    
    assert mock_client_2.models.generate_content.called
    assert mock_client_3.models.generate_content.called
    
@patch("backend.services.llm.gemini_provider.genai.Client")
@patch("backend.services.llm.gemini_provider.time.sleep")
def test_hard_per_key_rpm_limit(mock_sleep, mock_client_cls):
    # This explicitly tests that a 6th request within 60 seconds on the SAME key will trigger a sleep
    os.environ["GEMINI_API_KEY_2"] = "key2"
    # No other keys available
    
    # We directly inject 5 requests into the recent history of key slot 2
    now = time.time()
    for _ in range(5):
        GeminiRateLimiter._history.setdefault(2, __import__("collections").deque()).append(now)
        
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_response = MagicMock()
    mock_response.text = '{"sentences": []}'
    mock_client.models.generate_content.return_value = mock_response
    
    provider = GeminiProvider()
    provider.generate_script({}, {"model": "model-a"})
    
    # Provider must have slept! (wait time should have been approx 60 seconds)
    assert mock_sleep.called
    # First sleep argument is the wait time, should be > 59 seconds
    assert mock_sleep.call_args[0][0] > 59
    assert mock_client.models.generate_content.called

def test_daily_limit_exclusion():
    set_keys()
    GeminiRateLimiter._daily_counts[2] = {"date": time.strftime("%Y-%m-%d", time.gmtime(time.time())), "count": 20_000_000}
    
    # Should get_wait_time == -1
    assert GeminiRateLimiter.get_wait_time(2) == -1
    
@patch("backend.services.llm.gemini_provider.genai.Client")
@patch("backend.services.llm.gemini_provider.time.sleep")
def test_429_rotation(mock_sleep, mock_client_cls):
    set_keys()
    mock_client_2 = MagicMock()
    mock_client_3 = MagicMock()
    
    def side_effect(api_key=None):
        if api_key == "key2": return mock_client_2
        if api_key == "key3": return mock_client_3
        return MagicMock()
        
    mock_client_cls.side_effect = side_effect
    
    mock_response = MagicMock()
    mock_response.text = '{"sentences": []}'
    
    mock_client_2.models.generate_content.side_effect = Exception("429 Quota Exceeded")
    mock_client_3.models.generate_content.return_value = mock_response
    
    provider = GeminiProvider()
    provider.generate_script({}, {"model": "model-a"})
    
    assert mock_client_2.models.generate_content.called
    assert mock_client_3.models.generate_content.called
    
    # Key 2 should be temporarily unavailable
    assert 2 in GeminiRateLimiter._unavailable_until

@patch("backend.services.llm.gemini_provider.genai.Client")
def test_400_fails_cleanly(mock_client_cls):
    set_keys()
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.side_effect = Exception("400 Bad Request")
    
    provider = GeminiProvider()
    with pytest.raises(Exception, match="400"):
        provider.generate_script({}, {"model": "model-a"})

@patch("backend.services.llm.gemini_provider.genai.Client")
def test_backward_compatibility_single_key(mock_client_cls):
    # If only key 1 is present, it should use it instead of raising error
    os.environ["GEMINI_API_KEY"] = "key1"
    
    used_keys = []
    
    def side_effect(api_key=None):
        used_keys.append(api_key)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"sentences": []}'
        mock_client.models.generate_content.return_value = mock_response
        return mock_client
        
    mock_client_cls.side_effect = side_effect
    
    provider = GeminiProvider()
    provider.generate_script({}, {"model": "model-a"})
    
    assert "key1" in used_keys
