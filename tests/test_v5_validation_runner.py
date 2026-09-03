import pytest
import os
from v5_8_real_world import is_valid_youtube_url, get_urls

def test_is_valid_youtube_url():
    assert is_valid_youtube_url("https://www.youtube.com/watch?v=12345") is True
    assert is_valid_youtube_url("https://youtu.be/12345") is True
    
    assert is_valid_youtube_url("http://www.youtube.com/watch?v=12345") is False
    assert is_valid_youtube_url("https://www.youtube.com/watch") is False
    assert is_valid_youtube_url("https://google.com") is False
    assert is_valid_youtube_url("") is False
    assert is_valid_youtube_url("file:///etc/passwd") is False
    assert is_valid_youtube_url("../../../evil.sh") is False

def test_get_urls_cli_override():
    # CLI takes precedence
    args = ["--source-a-url", "https://www.youtube.com/watch?v=CLI_A",
            "--source-b-url", "https://www.youtube.com/watch?v=CLI_B"]
    url_a, url_b = get_urls(args)
    assert url_a == "https://www.youtube.com/watch?v=CLI_A"
    assert url_b == "https://www.youtube.com/watch?v=CLI_B"

def test_get_urls_env_fallback(monkeypatch):
    monkeypatch.setenv("V5_SOURCE_A_URL", "https://www.youtube.com/watch?v=ENV_A")
    monkeypatch.setenv("V5_SOURCE_B_URL", "https://www.youtube.com/watch?v=ENV_B")
    
    url_a, url_b = get_urls([])
    assert url_a == "https://www.youtube.com/watch?v=ENV_A"
    assert url_b == "https://www.youtube.com/watch?v=ENV_B"
    
    # CLI still overrides ENV
    args = ["--source-a-url", "https://www.youtube.com/watch?v=CLI_A"]
    url_a, url_b = get_urls(args)
    assert url_a == "https://www.youtube.com/watch?v=CLI_A"
    assert url_b == "https://www.youtube.com/watch?v=ENV_B"

def test_get_urls_defaults(monkeypatch):
    monkeypatch.delenv("V5_SOURCE_A_URL", raising=False)
    monkeypatch.delenv("V5_SOURCE_B_URL", raising=False)
    
    url_a, url_b = get_urls([])
    assert url_a == "https://www.youtube.com/watch?v=n0E96p_MFRA"
    assert url_b == "https://www.youtube.com/watch?v=0hWbkz3661U"

def test_get_urls_malformed():
    args = ["--source-a-url", "http://evil.com/evil.sh"]
    with pytest.raises(ValueError, match="Invalid YouTube URL for Source A"):
        get_urls(args)
