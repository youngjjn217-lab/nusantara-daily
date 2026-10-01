# -*- coding: utf-8 -*-
"""Nusantara Daily - Korean-language daily news briefing for Koreans living
in Indonesia.

Author: Kim Young Jin
Copyright (c) 2026 Kim Young Jin. All rights reserved.

Run with `python server.py` (or run.bat). Opens http://127.0.0.1:8766 in the
default browser. No API key is required for news (Google News RSS fallback)
or markets (Yahoo Finance); a free GNews.io key upgrades news to real
summaries - see README.md.
"""

from __future__ import annotations

import os
import threading
import webbrowser
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import market_fetcher
import news_fetcher

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

IS_CLOUD = "PORT" in os.environ
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8766))
LOCAL_URL = f"http://127.0.0.1:{PORT}"

APP_VERSION = "1.0.0"
APP_AUTHOR = "Kim Young Jin"
APP_COPYRIGHT = "Copyright (c) 2026 Kim Young Jin. All rights reserved."

app = FastAPI(title="Nusantara Daily", version=APP_VERSION)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.on_event("startup")
def _startup() -> None:
    news_fetcher.init_from_cache_or_fetch()
    news_fetcher.start_background_refresh()
    market_fetcher.init_from_cache_or_fetch()
    market_fetcher.start_background_refresh()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/info")
def get_info() -> dict[str, str]:
    return {"name": "Nusantara Daily", "version": APP_VERSION, "author": APP_AUTHOR, "copyright": APP_COPYRIGHT}


@app.get("/api/news")
def get_news(category: str = "all", q: str = "") -> dict[str, Any]:
    state = news_fetcher.get_state()
    all_items = state.get("items", [])
    items = all_items

    if category != "all":
        items = [item for item in items if item["category"] == category]

    query = q.strip().lower()
    if query:
        items = [
            item for item in items
            if query in item["title"].lower()
            or query in item["summary"].lower()
            or any(query in s["name"].lower() for s in item["sources"])
        ]

    truncated = False
    match_count = len(items)
    if category == "all" and not query and match_count > news_fetcher.DEFAULT_VIEW_LIMIT:
        items = items[: news_fetcher.DEFAULT_VIEW_LIMIT]
        truncated = True

    items = news_fetcher.translate_items_to_korean(items)

    category_counts = {c["id"]: 0 for c in news_fetcher.CATEGORIES}
    source_counts: dict[str, int] = {}
    for item in all_items:
        category_counts[item["category"]] = category_counts.get(item["category"], 0) + 1
        for s in item["sources"]:
            source_counts[s["name"]] = source_counts.get(s["name"], 0) + 1

    return {
        "items": items,
        "total": len(items),
        "match_count": match_count,
        "total_all": len(all_items),
        "truncated": truncated,
        "categories": [
            {"id": c["id"], "label": c["label"], "count": category_counts.get(c["id"], 0)}
            for c in news_fetcher.CATEGORIES
        ],
        "sources": sorted(
            [{"name": name, "count": count} for name, count in source_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        ),
        "last_updated": state.get("last_updated"),
        "errors": state.get("errors", {}),
        "search_active": bool(query),
    }


@app.get("/api/markets")
def get_markets() -> dict[str, Any]:
    return market_fetcher.get_state()


@app.post("/api/refresh")
def force_refresh() -> dict[str, Any]:
    news_fetcher.refresh()
    market_fetcher.refresh()
    return get_news()


def _open_browser() -> None:
    webbrowser.open(LOCAL_URL)


if __name__ == "__main__":
    if not IS_CLOUD:
        threading.Timer(1.2, _open_browser).start()
    uvicorn.run(app, host=HOST, port=PORT)
