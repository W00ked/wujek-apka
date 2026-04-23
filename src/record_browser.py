from __future__ import annotations

import contextlib
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import Error, TimeoutError, sync_playwright

from .config import Settings
from .errors import PipelineError
from .logging_utils import get_logger


class _StaticServer:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port: int | None = None

    def __enter__(self) -> "_StaticServer":
        handler = partial(SimpleHTTPRequestHandler, directory=str(self.directory))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=2)

    @property
    def url(self) -> str:
        if self.port is None:
            raise RuntimeError("server not started")
        return f"http://127.0.0.1:{self.port}/page.html"


def record_page(
    page_dir: Path,
    output_dir: Path,
    settings: Settings,
    *,
    expected_ui_duration_sec: float,
) -> Path:
    logger = get_logger(__name__, step="playwright")
    output_dir.mkdir(parents=True, exist_ok=True)
    timeout_ms = int(
        (
            max(0.0, expected_ui_duration_sec)
            + max(0.0, float(settings.render.ui_warmup_sec))
            + max(0.0, float(settings.render.record_timeout_buffer_sec))
        )
        * 1000
    )

    with _StaticServer(page_dir) as server:
        for attempt in range(2):
            try:
                with sync_playwright() as playwright:
                    browser_launcher = getattr(playwright, settings.playwright.browser)
                    browser = browser_launcher.launch()
                    context = browser.new_context(
                        viewport={"width": settings.render.width, "height": settings.render.height},
                        record_video_dir=str(output_dir),
                        record_video_size={
                            "width": settings.render.width,
                            "height": settings.render.height,
                        },
                    )
                    page = context.new_page()
                    page.goto(server.url, wait_until="load")
                    page.wait_for_function("() => window.__VIDEO_READY__ === true")
                    page.evaluate(
                        "() => document.fonts.ready",
                    )
                    page.evaluate("() => window.scrollTo(0, 0)")
                    warmup_ms = max(0, int(float(settings.render.ui_warmup_sec) * 1000))
                    if warmup_ms > 0:
                        page.wait_for_timeout(warmup_ms)
                    page.evaluate("async () => { await window.startVideoScroll(); }")
                    page.wait_for_function(
                        "() => window.__VIDEO_DONE__ === true",
                        timeout=timeout_ms,
                    )
                    page.wait_for_timeout(300)
                    video = page.video
                    if video is None:
                        raise PipelineError("Playwright did not expose recorded video", code=50, step="playwright")
                    page.close()
                    context.close()
                    browser.close()
                    return Path(video.path())
            except (TimeoutError, Error, PipelineError) as exc:
                logger.warning("browser recording attempt %s failed: %s", attempt + 1, exc)
                if attempt == 1:
                    if isinstance(exc, PipelineError):
                        raise exc
                    raise PipelineError(f"browser recording failed: {exc}", code=50, step="playwright") from exc
    raise PipelineError("browser recording failed unexpectedly", code=50, step="playwright")
