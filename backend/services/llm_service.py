import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import boto3
import requests

from services.cost_tracking_service import CostTrackingService

logger = logging.getLogger(__name__)

LLAMA_MODEL = "us.meta.llama3-1-8b-instruct-v1:0"
HAIKU_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

_WIKI_HEADERS = {"User-Agent": "SanatanaDharmaSpeeches/1.0 (educational research)"}
_WIKI_API = "https://te.wikipedia.org/w/api.php"


def _wiki_get(params: dict) -> dict:
    """GET from Telugu Wikipedia, always decoding response as UTF-8."""
    resp = requests.get(_WIKI_API, params=params, headers=_WIKI_HEADERS, timeout=8)
    return json.loads(resp.content.decode("utf-8"))


def _fetch_wikipedia_telugu(query: str, telugu_query: str) -> list[dict]:
    """Search Telugu Wikipedia and return top result as a vyakhanam entry."""
    try:
        # Search Telugu Wikipedia
        search = _wiki_get({
            "action": "query", "list": "search",
            "srsearch": telugu_query or query,
            "srnamespace": "0", "srlimit": "1", "format": "json",
        })
        results = search.get("query", {}).get("search", [])
        if not results:
            # Fallback: search in English
            search = _wiki_get({
                "action": "query", "list": "search",
                "srsearch": query, "srnamespace": "0",
                "srlimit": "1", "format": "json",
            })
            results = search.get("query", {}).get("search", [])
        if not results:
            return []

        title = results[0]["title"]
        # Fetch intro extract
        extract_resp = _wiki_get({
            "action": "query", "titles": title,
            "prop": "extracts", "exintro": "true",
            "exsentences": "5", "format": "json",
        })
        pages = extract_resp.get("query", {}).get("pages", {})
        page = next(iter(pages.values()))
        raw_html = page.get("extract", "")
        # Strip HTML tags
        text = re.sub(r"<[^>]+>", "", raw_html).strip()
        if not text:
            return []

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        body = " ".join(sentences[:4])
        highlight = sentences[0] if sentences else body[:150]
        page_url = f"https://te.wikipedia.org/wiki/{title.replace(' ', '_')}"
        return [{
            "scholar": "తెలుగు వికీపీడియా",
            "affiliation": "Wikipedia Telugu",
            "source_url": page_url,
            "text": body,
            "highlight": highlight,
            "lang": "Telugu",
        }]
    except Exception as e:
        logger.error("Wikipedia Telugu fetch failed: %s", e)
        return []

# Approximate cost per 1k tokens (USD)
LLAMA_COST_PER_1K_IN = 0.0003
LLAMA_COST_PER_1K_OUT = 0.0006
HAIKU_COST_PER_1K_IN = 0.00025
HAIKU_COST_PER_1K_OUT = 0.00125


@dataclass
class ParsedQuery:
    topic: str
    scripture: str | None
    chapter: int | None
    sloka: int | None
    keywords: list[str] = field(default_factory=list)
    language: str = "Telugu"
    search_intent: str = "general"


class LLMService:
    def __init__(self, tracker: CostTrackingService):
        self.tracker = tracker
        region = os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("bedrock-runtime", region_name=region)

    def _call_llama(self, prompt: str) -> str:
        body = json.dumps({
            "prompt": (
                "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n"
                f"{prompt}"
                "<|eot_id|><|start_header_id|>assistant<|end_header_id|>"
            ),
            "max_gen_len": 512,
            "temperature": 0.1,
        })
        resp = self._client.invoke_model(modelId=LLAMA_MODEL, body=body)
        raw = json.loads(resp["body"].read())
        text = raw.get("generation", "")
        tokens_in = len(prompt) // 4
        tokens_out = len(text) // 4
        cost = (tokens_in / 1000 * LLAMA_COST_PER_1K_IN +
                tokens_out / 1000 * LLAMA_COST_PER_1K_OUT)
        self.tracker.record(model=LLAMA_MODEL, tokens_in=tokens_in,
                            tokens_out=tokens_out, cost_usd=cost)
        return text

    def _call_haiku(self, prompt: str) -> str:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = self._client.invoke_model(modelId=HAIKU_MODEL, body=body)
        raw = json.loads(resp["body"].read())
        text = raw["content"][0]["text"]
        tokens_in = len(prompt) // 4
        tokens_out = len(text) // 4
        cost = (tokens_in / 1000 * HAIKU_COST_PER_1K_IN +
                tokens_out / 1000 * HAIKU_COST_PER_1K_OUT)
        self.tracker.record(model=HAIKU_MODEL, tokens_in=tokens_in,
                            tokens_out=tokens_out, cost_usd=cost)
        return text

    def _parse_json(self, text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{") if "{" in text else text.find("[")
            end = text.rfind("}") if "{" in text else text.rfind("]")
            return json.loads(text[start:end + 1])

    def parse_query(self, query: str, lang: str) -> "ParsedQuery | None":
        if self.tracker.is_budget_exceeded():
            logger.warning("LLM budget exceeded — skipping parse_query")
            return None
        prompt = (
            f"Parse this Sanatan Dharma search query into JSON.\n"
            f"Query: \"{query}\"\nLanguage preference: {lang}\n\n"
            "Return ONLY valid JSON with keys: topic, scripture (null if none), "
            "chapter (int or null), sloka (int or null), "
            "keywords (list of 3-5 strings including Telugu transliterations), "
            "language, search_intent.\n"
            "Example for 'Bhagavad Gita Chapter 2 Sloka 5':\n"
            '{"topic":"Bhagavad Gita","scripture":"Bhagavad Gita","chapter":2,"sloka":5,'
            '"keywords":["BG 2.5","భగవద్గీత అధ్యాయం 2 శ్లోకం 5"],'
            '"language":"Telugu","search_intent":"specific sloka"}'
        )
        try:
            text = self._call_llama(prompt)
            data = self._parse_json(text)
            return ParsedQuery(**data)
        except Exception as e:
            logger.error(f"parse_query failed: {e}")
            return None

    def generate_search_terms(self, parsed: "ParsedQuery") -> list[str]:
        if self.tracker.is_budget_exceeded():
            return [parsed.topic]
        prompt = (
            f"Generate 4 YouTube/archive.org search queries for this Dharma topic.\n"
            f"Topic: {parsed.topic}, Scripture: {parsed.scripture}, "
            f"Chapter: {parsed.chapter}, Sloka: {parsed.sloka}, "
            f"Keywords: {parsed.keywords}, Language: {parsed.language}\n\n"
            "Return ONLY a JSON array of strings (search queries). "
            "Include Telugu script and English transliterations.\n"
            'Example: ["Siva Tatvam Telugu discourse","శివ తత్వం ప్రవచనం"]'
        )
        try:
            text = self._call_llama(prompt)
            raw = self._parse_json(text)
            # Flatten any nested lists and keep only strings
            if isinstance(raw, list):
                flat = []
                for item in raw:
                    if isinstance(item, str):
                        flat.append(item)
                    elif isinstance(item, list):
                        flat.extend(s for s in item if isinstance(s, str))
                if flat:
                    return flat
            return [parsed.topic]
        except Exception as e:
            logger.error(f"generate_search_terms failed: {e}")
            return parsed.keywords[:3]

    def rank_results(self, results: list[dict], parsed: "ParsedQuery") -> list[dict]:
        if self.tracker.is_budget_exceeded() or not results:
            return results
        items = [{"index": i, "title": r.get("title", ""), "speaker": r.get("speaker", "")}
                 for i, r in enumerate(results)]
        prompt = (
            f"Score these search results for relevance to: \"{parsed.topic}\" "
            f"(scripture={parsed.scripture}, chapter={parsed.chapter}, sloka={parsed.sloka}).\n"
            f"Results: {json.dumps(items)}\n\n"
            "Return ONLY a JSON array with objects {index, score} where score is 0.0-1.0.\n"
            'Example: [{"index":0,"score":0.9},{"index":1,"score":0.3}]'
        )
        try:
            text = self._call_llama(prompt)
            scores = {s["index"]: s["score"] for s in self._parse_json(text)}
            return sorted(results, key=lambda r: scores.get(results.index(r), 0), reverse=True)
        except Exception as e:
            logger.error(f"rank_results failed: {e}")
            return results

    def highlight_vyakhanams(self, texts: list[dict], parsed: "ParsedQuery") -> list[dict]:
        if self.tracker.is_budget_exceeded() or not texts:
            return texts
        prompt = (
            f"For the topic \"{parsed.topic}\" "
            f"(scripture={parsed.scripture}, chapter={parsed.chapter}, sloka={parsed.sloka}), "
            f"identify the most relevant excerpt from each scholar's text below.\n"
            f"Scholars: {json.dumps([{'scholar': t['scholar'], 'text': t['text'][:500]} for t in texts])}\n\n"
            "Return ONLY a JSON array with objects {scholar, excerpt} — "
            "the excerpt should be the single most relevant sentence or passage (max 200 chars)."
        )
        try:
            text = self._call_llama(prompt)
            highlights = {h["scholar"]: h["excerpt"] for h in self._parse_json(text)}
            for t in texts:
                t["highlight"] = highlights.get(t["scholar"], t["text"][:200])
            return texts
        except Exception as e:
            logger.error(f"highlight_vyakhanams failed: {e}")
            return texts

    def generate_telugu_vyakhanams(self, query: str) -> list[dict]:
        """Fetch authentic Telugu text from Telugu Wikipedia as vyakhanam fallback."""
        if self.tracker.is_budget_exceeded():
            logger.warning("LLM budget exceeded — skipping generate_telugu_vyakhanams")
            return []
        # Use Llama to translate the query into Telugu for better Wikipedia search
        try:
            prompt = (
                f"Translate this to Telugu script only, no other text: \"{query}\""
            )
            telugu_query = self._call_llama(prompt).strip().split("\n")[0].strip()
        except Exception:
            telugu_query = query

        return _fetch_wikipedia_telugu(query, telugu_query)

    def explain_topic(self, parsed: "ParsedQuery") -> "dict | None":
        if self.tracker.is_budget_exceeded():
            logger.warning("LLM budget exceeded — skipping explain_topic")
            return None
        prompt = (
            f"You are a Sanatan Dharma scholar. "
            f"Explain the topic \"{parsed.topic}\" in 2-3 clear sentences suitable for a devotee. "
            f"Then suggest exactly 3 related topics they might want to explore next.\n\n"
            f"Return ONLY valid JSON with keys: explanation (string), related_topics (array of 3 strings).\n"
            f'Example: {{"explanation": "Siva Tatvam refers to...", "related_topics": ["Panchakshara", "Rudram", "Shiva Purana"]}}'
        )
        try:
            text = self._call_llama(prompt)
            data = self._parse_json(text)
            return {
                "explanation": data.get("explanation", ""),
                "related_topics": data.get("related_topics", []),
            }
        except Exception as e:
            logger.error(f"explain_topic failed: {e}")
            return None
