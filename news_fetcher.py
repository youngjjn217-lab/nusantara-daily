# -*- coding: utf-8 -*-
"""Fetches, classifies, clusters, and translates Indonesian news.

Part of Nusantara Daily. Author: Kim Young Jin.
Copyright (c) 2026 Kim Young Jin. All rights reserved.

Pipeline per category:
  1. Fetch via GNews.io search (real summaries, English) when a free API key
     is configured; fall back to Google News RSS (no key, headline only)
     otherwise or on any GNews failure.
  2. Keep only items with a clear Indonesia signal in the title AND a
     category keyword in the title - both sources occasionally let an
     off-topic or wrong-country story through.
  3. Tag each item "news" or "opinion" from title/URL cues (column, editorial,
     analysis, opinion section paths). This is a heuristic, not a legal
     fact-check - the UI always links to the original so a reader can judge.
  4. Cluster near-duplicate headlines (different outlets covering the same
     event) into one story with a combined source list, so the UI can show
     "N개 매체 교차 확인" instead of listing the same event N times.
  5. Translate title + summary to Korean lazily, only for whatever the
     frontend actually requests (see translate_items_to_korean), using
     MyMemory's free public API (no key, no signup).
"""

from __future__ import annotations

import html
import json
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests


def _app_dir() -> Path:
    """Directory to look for config.json in. A PyInstaller --onefile build
    extracts to a fresh temp folder every run, so a config.json placed there
    would be invisible next time; read it from beside the actual .exe
    instead. Running from source, this is just the project folder."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CACHE_DIR = Path.home() / ".nusantara_daily"
CACHE_PATH = CACHE_DIR / "news_cache.json"
CONFIG_PATH = _app_dir() / "config.json"

REQUEST_TIMEOUT = 12
GNEWS_MAX_ITEMS_PER_CATEGORY = 6
GOOGLE_NEWS_MAX_ITEMS_PER_CATEGORY = 20
DEFAULT_VIEW_LIMIT = 15

REFRESH_INTERVAL_SECONDS_NO_KEY = 20 * 60
REFRESH_INTERVAL_SECONDS_WITH_KEY = 3 * 60 * 60

CATEGORIES: list[dict[str, Any]] = [
    {"id": "eco", "label": "경제·증시",
     "query": "Indonesia (economy OR business OR market OR rupiah OR IDX OR stocks)",
     "gnews_query": 'Indonesia AND (economy OR rupiah OR "central bank" OR stocks OR market OR inflation)',
     "keywords": ["econom", "rupiah", "market", "stock", "central bank", "bank indonesia", "inflation", "idx", "trade", "invest", "ekonomi", "saham"]},
    {"id": "pol", "label": "정치·사회",
     "query": "Indonesia (politics OR government OR president OR election OR parliament)",
     "gnews_query": "Indonesia AND (politics OR government OR president OR election OR parliament)",
     "keywords": ["politic", "president", "government", "election", "parliament", "minister", "prabowo", "policy", "politik", "presiden", "pemerintah"]},
    {"id": "tek", "label": "테크·산업",
     "query": "Indonesia (technology OR startup OR fintech OR e-commerce OR manufacturing)",
     "gnews_query": 'Indonesia AND (startup OR fintech OR "e-commerce" OR "digital economy" OR tech)',
     "keywords": ["tech", "startup", "fintech", "e-commerce", "digital", "software", "app", "manufactur", "teknologi"]},
    {"id": "car", "label": "자동차",
     "query": 'Indonesia (automotive OR "electric vehicle" OR carmaker OR motorcycle OR "car sales")',
     "gnews_query": 'Indonesia AND (automotive OR "electric vehicle" OR carmaker OR motorcycle OR "car sales")',
     "keywords": ["car", "automotive", "vehicle", "motorcycle", "carmaker", "motogp", " ev ", "electric vehicle", "otomotif", "mobil", "motor"]},
    {"id": "int", "label": "국제",
     "query": "Indonesia (ASEAN OR diplomatic OR foreign policy OR bilateral OR trade deal)",
     "gnews_query": 'Indonesia AND (ASEAN OR diplomatic OR "foreign policy" OR bilateral OR "trade deal")',
     "keywords": ["asean", "diplomat", "foreign", "bilateral", "trade deal", "embassy", "summit", "china", "malaysia", "singapore", "regional"]},
    {"id": "liv", "label": "생활·환경",
     "query": "Indonesia (environment OR climate OR infrastructure OR health OR disaster)",
     "gnews_query": "Indonesia AND (environment OR climate OR infrastructure OR health OR disaster)",
     "keywords": ["environ", "climate", "disaster", "health", "infrastructure", "volcan", "flood", "earthquake", "wildfire", "haze", "eruption", "lingkungan", "bencana", "kesehatan"]},
]
CATEGORY_BY_ID = {c["id"]: c for c in CATEGORIES}

_INDONESIA_SIGNAL_TERMS = [
    "indonesia", "jakarta", "prabowo", "pertamina", "mandalika", "rupiah",
    "jokowi", "bandung", "surabaya", "bali", "kalimantan", "sumatra",
    "sulawesi", "papua", "jawa", "java",
]

_OPINION_SIGNALS = [
    "opinion", "editorial", "column", "commentary", "analysis:", "viewpoint",
    "perspective", "op-ed",
]
_OPINION_URL_SIGNALS = ["/opinion/", "/column/", "/editorial/", "/analysis/", "/viewpoint/"]

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_TITLE_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "is",
    "are", "was", "were", "with", "by", "from", "as", "after", "amid",
    "amidst", "over", "up", "its", "this", "that", "than", "into", "but",
    "more", "says", "say", "said", "could", "would", "will", "may", "sets",
    "set", "eyes", "hope", "hopes", "aim", "aims", "despite", "ready",
    "new", "first",
}
NEAR_DUPLICATE_OVERLAP = 0.48  # fraction of the shorter title's (stemmed) words shared
MIN_SHARED_TOKENS = 3  # absolute floor so two short titles don't match on noise

_lock = threading.Lock()
_state: dict[str, Any] = {"items": [], "errors": {}, "last_updated": None}


def _load_gnews_api_key() -> str | None:
    import os

    env_key = os.environ.get("NUSANTARA_GNEWS_API_KEY")
    if env_key:
        return env_key.strip()
    if CONFIG_PATH.is_file():
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            key = config.get("gnews_api_key")
            if key:
                return str(key).strip()
        except (json.JSONDecodeError, OSError):
            pass
    return None


GNEWS_API_KEY = _load_gnews_api_key()
REFRESH_INTERVAL_SECONDS = REFRESH_INTERVAL_SECONDS_WITH_KEY if GNEWS_API_KEY else REFRESH_INTERVAL_SECONDS_NO_KEY


def _classify_type(title: str, url: str) -> str:
    title_lower = title.lower()
    url_lower = (url or "").lower()
    if any(sig in title_lower for sig in _OPINION_SIGNALS):
        return "opinion"
    if any(sig in url_lower for sig in _OPINION_URL_SIGNALS):
        return "opinion"
    return "news"


def _stem(word: str) -> str:
    """Light, rule-based stemming so "loan"/"loans" or "target"/"targets" count
    as the same word for duplicate detection. Not linguistically rigorous,
    just enough to stop simple plural/tense mismatches from hiding an obvious
    duplicate headline."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("es"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    return word


def _title_tokens(title_lower: str) -> set[str]:
    return {
        _stem(w) for w in _TOKEN_RE.findall(title_lower)
        if w not in _TITLE_STOPWORDS and len(w) > 2
    }


def _filter_relevant(items: list[dict[str, Any]], category: dict[str, Any]) -> list[dict[str, Any]]:
    keywords = category.get("keywords") or []
    filtered = []
    for item in items:
        title_lower = item["title"].lower()
        if not any(term in title_lower for term in _INDONESIA_SIGNAL_TERMS):
            continue
        if keywords and not any(kw in title_lower for kw in keywords):
            continue
        filtered.append(item)
    return filtered


def _parse_pub_date(raw: str) -> tuple[str, float]:
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M"), dt.timestamp()
    except (TypeError, ValueError):
        return raw[:16] if raw else "-", 0.0


def _parse_iso_date(raw: str) -> tuple[str, float]:
    try:
        dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M"), dt.timestamp()
    except (TypeError, ValueError):
        return raw[:16] if raw else "-", 0.0


def _clean_summary(raw_description: str, title: str) -> str:
    text = _HTML_TAG_RE.sub(" ", raw_description or "")
    text = html.unescape(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if text.lower().startswith(title.lower()):
        remainder = text[len(title):].strip(" -–—|·")
        if len(remainder) < 60:
            return ""
        text = remainder
    if len(text) > 240:
        text = text[:240].rsplit(" ", 1)[0] + "…"
    return text


def _split_title_source(raw_title: str) -> tuple[str, str]:
    if " - " in raw_title:
        title, _, publisher = raw_title.rpartition(" - ")
        if title and publisher:
            return title, publisher
    return raw_title, "Google News"


def _make_item(category: dict[str, Any], title: str, summary: str, source: str, url: str,
                date_str: str, sort_key: float) -> dict[str, Any]:
    return {
        "category": category["id"],
        "category_label": category["label"],
        "title": title,
        "summary": summary,
        "type": _classify_type(title, url),
        "sources": [{"name": source, "url": url}],
        "published_at": date_str,
        "sort_key": sort_key,
    }


def _fetch_category_gnews(category: dict[str, Any], max_items: int) -> tuple[list[dict[str, Any]], str | None]:
    # GNews's top-headlines "country" filter only reflects where a source is
    # registered, not what the article is about, and its English-language
    # Indonesia-registered source pool is too thin to rely on. The search
    # endpoint with `in=title` is more reliable: every result must have the
    # query terms in the headline itself.
    try:
        response = requests.get(
            "https://gnews.io/api/v4/search",
            params={
                "q": category["gnews_query"],
                "lang": "en",
                "in": "title",
                "max": max_items,
                "sortby": "publishedAt",
                "apikey": GNEWS_API_KEY,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return [], str(exc)

    items: list[dict[str, Any]] = []
    for article in payload.get("articles", [])[:max_items]:
        title = (article.get("title") or "").strip()
        if not title:
            continue
        summary = (article.get("description") or "").strip()
        if summary.lower() == title.lower():
            summary = ""
        source_name = ((article.get("source") or {}).get("name")) or "GNews"
        url = article.get("url") or ""
        date_str, sort_key = _parse_iso_date(article.get("publishedAt") or "")
        items.append(_make_item(category, title, summary, source_name, url, date_str, sort_key))
    return items, None


def _fetch_category_google_news(category: dict[str, Any], max_items: int) -> tuple[list[dict[str, Any]], str | None]:
    url = "https://news.google.com/rss/search"
    params = {"q": f"{category['query']} when:2d", "hl": "en-ID", "gl": "ID", "ceid": "ID:en"}
    try:
        response = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as exc:
        return [], str(exc)

    items: list[dict[str, Any]] = []
    for item in root.findall(".//item")[:max_items]:
        raw_title = item.findtext("title") or ""
        if not raw_title:
            continue
        title, source = _split_title_source(raw_title)
        summary = _clean_summary(item.findtext("description") or "", title)
        date_str, sort_key = _parse_pub_date(item.findtext("pubDate") or "")
        link = item.findtext("link") or ""
        items.append(_make_item(category, title, summary, source, link, date_str, sort_key))
    return items, None


def fetch_category(category_id: str) -> tuple[list[dict[str, Any]], str | None]:
    category = CATEGORY_BY_ID.get(category_id)
    if category is None:
        return [], f"알 수 없는 카테고리: {category_id}"

    if GNEWS_API_KEY:
        items, _ = _fetch_category_gnews(category, GNEWS_MAX_ITEMS_PER_CATEGORY)
        items = _filter_relevant(items, category)
        if items:
            return items, None

    items, error = _fetch_category_google_news(category, GOOGLE_NEWS_MAX_ITEMS_PER_CATEGORY)
    return _filter_relevant(items, category), error


def _cluster_by_similarity(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge near-duplicate headlines into one story with a combined source
    list, so the same event reported by several outlets becomes one card
    with a cross-source "corroborated" count instead of several copies."""
    clusters: list[dict[str, Any]] = []
    cluster_tokens: list[set[str]] = []

    for item in items:
        title_lower = item["title"].strip().lower()
        tokens = _title_tokens(title_lower)
        matched_idx = None
        if len(tokens) >= 3:
            for idx, c_tokens in enumerate(cluster_tokens):
                if not c_tokens:
                    continue
                shared = tokens & c_tokens
                if len(shared) < MIN_SHARED_TOKENS:
                    continue
                overlap = len(shared) / min(len(tokens), len(c_tokens))
                if overlap >= NEAR_DUPLICATE_OVERLAP:
                    matched_idx = idx
                    break
        if matched_idx is None:
            new_cluster = dict(item)
            new_cluster["sources"] = list(item["sources"])
            clusters.append(new_cluster)
            cluster_tokens.append(tokens)
        else:
            matched = clusters[matched_idx]
            existing_names = {s["name"] for s in matched["sources"]}
            for s in item["sources"]:
                if s["name"] not in existing_names:
                    matched["sources"].append(s)
                    existing_names.add(s["name"])
            if item["sort_key"] > matched["sort_key"]:
                matched["sort_key"] = item["sort_key"]
                matched["published_at"] = item["published_at"]
            if not matched["summary"] and item["summary"]:
                matched["summary"] = item["summary"]
            # Widen the cluster's token set so a third, differently-worded
            # paraphrase of the same story can still match against it.
            cluster_tokens[matched_idx] = cluster_tokens[matched_idx] | tokens

    return clusters


def _assign_ids(items: list[dict[str, Any]]) -> None:
    for item in items:
        key = item["title"].strip().lower()
        item["id"] = str(abs(hash(key)))


def fetch_all() -> dict[str, Any]:
    raw_items: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for i, category in enumerate(CATEGORIES):
        if GNEWS_API_KEY and i > 0:
            time.sleep(2)  # avoid GNews's short-window burst rate limit
        cat_items, error = fetch_category(category["id"])
        if error:
            errors[category["id"]] = error
        raw_items.extend(cat_items)

    items = _cluster_by_similarity(raw_items)
    _assign_ids(items)
    items.sort(key=lambda x: x["sort_key"], reverse=True)

    return {
        "items": items,
        "errors": errors,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---- translation (lazy, cached, best-effort) ----

TRANSLATION_CACHE_PATH = CACHE_DIR / "translation_cache.json"
_translation_cache: dict[str, str] | None = None
_translation_disabled_until = 0.0


def _load_translation_cache() -> dict[str, str]:
    global _translation_cache
    if _translation_cache is not None:
        return _translation_cache
    if TRANSLATION_CACHE_PATH.is_file():
        try:
            _translation_cache = json.loads(TRANSLATION_CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            _translation_cache = {}
    else:
        _translation_cache = {}
    return _translation_cache


def _save_translation_cache() -> None:
    if _translation_cache is None:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSLATION_CACHE_PATH.write_text(json.dumps(_translation_cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _translate_title_summary(title: str, summary: str) -> tuple[str, str]:
    global _translation_disabled_until

    combined = f"{title}\n---\n{summary}" if summary else title
    cache = _load_translation_cache()
    cache_key = str(abs(hash(combined)))
    cached = cache.get(cache_key)
    if cached is not None:
        if "\n---\n" in cached:
            t, s = cached.split("\n---\n", 1)
            return t, s
        return cached, ""

    if time.time() < _translation_disabled_until:
        return title, summary

    try:
        response = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": combined, "langpair": "en|ko"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("quotaFinished"):
            _translation_disabled_until = time.time() + 3600
            return title, summary
        translated = ((data.get("responseData") or {}).get("translatedText") or "").strip()
        if not translated:
            return title, summary
    except Exception:
        return title, summary

    cache[cache_key] = translated
    if "\n---\n" in translated:
        t, s = translated.split("\n---\n", 1)
        return t.strip(), s.strip()
    return translated, ""


def translate_items_to_korean(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    translated: list[dict[str, Any]] = []
    for item in items:
        title_ko, summary_ko = _translate_title_summary(item["title"], item["summary"])
        new_item = dict(item)
        new_item["title"] = title_ko
        new_item["summary"] = summary_ko
        translated.append(new_item)
        time.sleep(0.15)
    _save_translation_cache()
    return translated


# ---- cache + state ----

def save_cache(state: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cache() -> dict[str, Any] | None:
    if not CACHE_PATH.is_file():
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def get_state() -> dict[str, Any]:
    with _lock:
        return dict(_state)


def refresh(persist: bool = True) -> dict[str, Any]:
    result = fetch_all()
    with _lock:
        _state["items"] = result["items"]
        _state["errors"] = result["errors"]
        _state["last_updated"] = result["last_updated"]
    if persist:
        save_cache(result)
    return result


def _cache_is_stale(last_updated: str | None) -> bool:
    if not last_updated:
        return True
    try:
        age = (datetime.now() - datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")).total_seconds()
    except ValueError:
        return True
    return age > REFRESH_INTERVAL_SECONDS


def init_from_cache_or_fetch() -> None:
    cached = load_cache()
    if cached and cached.get("items") and not _cache_is_stale(cached.get("last_updated")):
        with _lock:
            _state["items"] = cached["items"]
            _state["errors"] = cached.get("errors", {})
            _state["last_updated"] = cached.get("last_updated")
    else:
        refresh()


def start_background_refresh() -> None:
    def _loop() -> None:
        while True:
            time.sleep(REFRESH_INTERVAL_SECONDS)
            try:
                refresh()
            except Exception:
                pass

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
