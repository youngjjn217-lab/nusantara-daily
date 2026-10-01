# -*- coding: utf-8 -*-
"""Fetches USD/IDR, 1,000 IDR->KRW, IHSG, and KOSPI via Yahoo Finance.

Part of Nusantara Daily. Author: Kim Young Jin.
Copyright (c) 2026 Kim Young Jin. All rights reserved.

No API key is required - yfinance reads Yahoo Finance's public quote data.
IDR/KRW is derived from USD/IDR and USD/KRW (Yahoo doesn't publish that pair
directly): 1,000 IDR = 1,000 * (USD/KRW rate) / (USD/IDR rate) KRW.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import yfinance as yf

CACHE_DIR = Path.home() / ".nusantara_daily"
CACHE_PATH = CACHE_DIR / "market_cache.json"
REFRESH_INTERVAL_SECONDS = 15 * 60

_lock = threading.Lock()
_state: dict[str, Any] = {"markets": [], "last_updated": None, "error": None}


def _last_two_closes(history) -> tuple[float, float] | None:
    closes = history["Close"].dropna()
    if len(closes) < 2:
        return None
    return float(closes.iloc[-2]), float(closes.iloc[-1])


def fetch_markets() -> dict[str, Any]:
    try:
        tickers = yf.Tickers("IDR=X KRW=X ^JKSE ^KS11")
        usdidr_hist = tickers.tickers["IDR=X"].history(period="5d")
        usdkrw_hist = tickers.tickers["KRW=X"].history(period="5d")
        jkse_hist = tickers.tickers["^JKSE"].history(period="5d")
        ks11_hist = tickers.tickers["^KS11"].history(period="5d")

        usdidr = _last_two_closes(usdidr_hist)
        usdkrw = _last_two_closes(usdkrw_hist)
        jkse = _last_two_closes(jkse_hist)
        ks11 = _last_two_closes(ks11_hist)
        if not all([usdidr, usdkrw, jkse, ks11]):
            return {"markets": [], "last_updated": None, "error": "시세 데이터가 충분하지 않습니다"}

        idrkrw_prev = 1000 * usdkrw[0] / usdidr[0]
        idrkrw_now = 1000 * usdkrw[1] / usdidr[1]

        def pct(prev: float, now: float) -> float:
            return (now - prev) / prev * 100 if prev else 0.0

        markets = [
            {"id": "usdidr", "label": "USD/IDR", "value": usdidr[1], "change": pct(usdidr[0], usdidr[1]), "decimals": 0},
            {"id": "idrkrw", "label": "1,000 IDR→KRW", "value": idrkrw_now, "change": pct(idrkrw_prev, idrkrw_now), "decimals": 2},
            {"id": "ihsg", "label": "IHSG", "value": jkse[1], "change": pct(jkse[0], jkse[1]), "decimals": 2},
            {"id": "kospi", "label": "KOSPI", "value": ks11[1], "change": pct(ks11[0], ks11[1]), "decimals": 2},
        ]
        return {"markets": markets, "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"), "error": None}
    except Exception as exc:
        return {"markets": [], "last_updated": None, "error": str(exc)}


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
    result = fetch_markets()
    with _lock:
        if result["markets"]:
            _state["markets"] = result["markets"]
            _state["last_updated"] = result["last_updated"]
        _state["error"] = result["error"]
    if persist and result["markets"]:
        save_cache(result)
    return result


def init_from_cache_or_fetch() -> None:
    cached = load_cache()
    if cached and cached.get("markets"):
        with _lock:
            _state["markets"] = cached["markets"]
            _state["last_updated"] = cached.get("last_updated")
            _state["error"] = None
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
