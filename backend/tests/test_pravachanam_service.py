import pytest
import os
from unittest.mock import patch, MagicMock

os.environ.setdefault("DB_PATH", ":memory:")

from services.pravachanam_service import PravachanamService, TOPIC_MAP


SPEAKER_LIST_HTML = """
<html><body>
<table>
  <tr>
    <td class="views-field views-field-nothing">
      <a href="/pravachanambrowselist2/16/89/20?field_pm_language_target_id=20">Sri Chaganti Koteshwara Rao</a><br>Adi Shankaracharya
    </td>
    <td class="views-field views-field-field-pm-album">6</td>
  </tr>
  <tr>
    <td class="views-field views-field-nothing">
      <a href="/pravachanambrowselist2/49/89/20?field_pm_language_target_id=20">Sri Samavedam Shanmukha Sharma</a><br>Adi Shankaracharya
    </td>
    <td class="views-field views-field-field-pm-album">1</td>
  </tr>
</table>
</body></html>
"""

PRAVACHANA_LIST_HTML = """
<html><body>
<table>
  <tr>
    <td class="views-field views-field-views-conditional-field-1"><b>Prasnottara Ratna Malika </b><br><br>
<b>Artist: </b>Chaganti Koteshwara Rao<br><br>
<b>Category:</b> [Adi Shankaracharya ] <br><br>
<b>Duration:</b> 7 Hours 40 Minutes <br><br>
<b>No.of Files:</b> 5</td>
    <td class="views-field views-field-views-conditional-field"></td>
  </tr>
</table>
</body></html>
"""


@pytest.fixture
def svc():
    return PravachanamService()


def _mock_response(html: str):
    r = MagicMock()
    r.status_code = 200
    r.text = html
    r.raise_for_status = lambda: None
    return r


def test_topic_map_has_key_topics():
    assert "bhagavad gita" in TOPIC_MAP
    assert "ramayanam" in TOPIC_MAP
    assert "shankaracharya" in TOPIC_MAP
    assert "shiva" in TOPIC_MAP
    assert "upanishad" in TOPIC_MAP


def test_search_returns_pravachana_results(svc):
    with patch("services.pravachanam_service.requests.get") as mock_get, \
         patch("services.pravachanam_service.time.sleep"):
        mock_get.side_effect = [
            _mock_response(SPEAKER_LIST_HTML),   # speaker list fetch
            _mock_response(PRAVACHANA_LIST_HTML), # Chaganti pravachana list
            _mock_response(PRAVACHANA_LIST_HTML), # Samavedam pravachana list
        ]
        results = svc.search("Adi Shankaracharya")
    assert len(results) >= 1
    r = results[0]
    assert r["scholar"] == "Chaganti Koteshwara Rao"
    assert r["title"] == "Prasnottara Ratna Malika"
    assert r["duration"] == "7 Hours 40 Minutes"
    assert r["files_count"] == 5
    assert "pravachanam.com" in r["url"]
    assert r["lang"] == "Telugu"


def test_search_returns_empty_for_unknown_topic(svc):
    results = svc.search("Quantum Physics")
    assert results == []


def test_search_uses_best_topic_match(svc):
    with patch("services.pravachanam_service.requests.get") as mock_get, \
         patch("services.pravachanam_service.time.sleep"):
        mock_get.return_value = _mock_response("<html><body><table></table></body></html>")
        results = svc.search("gita")
    # gita should map to topic 12 (Bhagavadgita)
    called_url = mock_get.call_args[0][0]
    assert "/speakerbrowselist/12/20" in called_url
