import pytest
from features import extract_features

def test_basic_url_features():
    url = "https://example.com/login"
    f = extract_features(url)
    assert "url_length" in f
    assert f["count_dots"] >= 1
    assert f["has_at_symbol"] in (0,1)
    assert isinstance(f["character_entropy"], float)

def test_ip_host_detection():
    url = "http://192.168.0.1/login"
    f = extract_features(url)
    assert f["has_ip_in_host"] == 1

def test_suspicious_token_count():
    url = "http://secure-login.example/verify"
    f = extract_features(url)
    assert f["suspicious_token_count"] >= 1
