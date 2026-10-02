# -*- coding: utf-8 -*-
"""Nusantara Daily - Windows desktop entry point (PyWebView window).

Part of Nusantara Daily. Author: Kim Young Jin.
Copyright (c) 2026 Kim Young Jin. All rights reserved.

This is the entry point PyInstaller builds into NusantaraDaily.exe. It runs
the same FastAPI app as `server.py` in a background thread and shows it in
a dedicated app window instead of the system browser - built with
build_exe.bat, the same way the sibling Nusantara Market Desk project does.
"""

from __future__ import annotations

import threading
import time

import uvicorn
import webview

from server import HOST, PORT, app


def _run_server() -> None:
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def main() -> None:
    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()
    time.sleep(1.0)  # give uvicorn a moment to bind the port before loading it

    webview.create_window(
        "Nusantara Daily",
        f"http://127.0.0.1:{PORT}",
        width=1320,
        height=880,
        min_size=(1000, 680),
        background_color="#0A1219",
    )
    webview.start()


if __name__ == "__main__":
    main()
