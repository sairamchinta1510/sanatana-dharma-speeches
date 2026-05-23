import json
import os
import time
import pytest

os.environ["DB_PATH"] = ":memory:"

from services.cache_service import CacheService


@pytest.fixture
def cache():
    import database; database.init_db()
    return CacheService(ttl_seconds=2)


def test_miss_on_empty(cache):
    assert cache.get("video", "siva tatvam", "Telugu") is None


def test_set_and_get(cache):
    data = [{"title": "Test Video", "speaker": "Scholar"}]
    cache.set("video", "siva tatvam", "Telugu", data)
    result = cache.get("video", "siva tatvam", "Telugu")
    assert result == data


def test_expired_returns_none(cache):
    data = [{"title": "Test"}]
    cache.set("audio", "gita", "Telugu", data)
    time.sleep(3)  # TTL is 2s in fixture
    assert cache.get("audio", "gita", "Telugu") is None


def test_different_lang_different_entry(cache):
    cache.set("video", "karma yoga", "Telugu", [{"title": "Telugu"}])
    cache.set("video", "karma yoga", "English", [{"title": "English"}])
    assert cache.get("video", "karma yoga", "Telugu")[0]["title"] == "Telugu"
    assert cache.get("video", "karma yoga", "English")[0]["title"] == "English"


def test_normalized_key(cache):
    cache.set("video", "  Siva Tatvam  ", "Telugu", [{"title": "x"}])
    assert cache.get("video", "siva tatvam", "Telugu") is not None
