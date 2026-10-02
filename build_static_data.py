# -*- coding: utf-8 -*-
"""Builds the static data/*.json files that power the GitHub Pages version
of Nusantara Daily (docs/). Run on a schedule by
.github/workflows/update-news.yml and update-markets.yml - see README.md.

Part of Nusantara Daily. Author: Kim Young Jin.
Copyright (c) 2026 Kim Young Jin. All rights reserved.

Unlike the live server (server.py), there is no request to lazily translate
on - this script eagerly translates every fetched item, since whatever it
writes is the entire dataset every visitor will see until the next run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import market_fetcher
import news_fetcher

DOCS_DATA_DIR = Path(__file__).resolve().parent / "docs" / "data"


def build_news() -> None:
    result = news_fetcher.fetch_all()
    items = news_fetcher.translate_items_to_korean(result["items"])

    category_counts = {c["id"]: 0 for c in news_fetcher.CATEGORIES}
    source_counts: dict[str, int] = {}
    for item in items:
        category_counts[item["category"]] = category_counts.get(item["category"], 0) + 1
        for s in item["sources"]:
            source_counts[s["name"]] = source_counts.get(s["name"], 0) + 1

    payload = {
        "items": items,
        "categories": [
            {"id": c["id"], "label": c["label"], "count": category_counts.get(c["id"], 0)}
            for c in news_fetcher.CATEGORIES
        ],
        "sources": sorted(
            [{"name": name, "count": count} for name, count in source_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        ),
        "last_updated": result["last_updated"],
        "errors": result["errors"],
    }

    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DATA_DIR / "news.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"news.json: {len(items)} items, errors={result['errors']}")


def build_markets() -> None:
    result = market_fetcher.fetch_markets()
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DATA_DIR / "markets.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"markets.json: {len(result['markets'])} tickers, error={result['error']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=["news", "markets", "all"], nargs="?", default="all")
    args = parser.parse_args()

    if args.target in ("news", "all"):
        build_news()
    if args.target in ("markets", "all"):
        build_markets()

    sys.exit(0)
