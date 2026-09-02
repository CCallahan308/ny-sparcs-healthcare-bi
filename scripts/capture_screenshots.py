"""Capture full-page app screenshots for the README.

Development-only tool; not part of the pipeline or deployment. Requires:

    pip install playwright

and uses the locally installed Chrome browser (channel="chrome"), so no
Playwright browser download is needed. Marts must already be built.

    python scripts/capture_screenshots.py
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

OUT_DIR = ROOT / "docs" / "screenshots"
PORT = 8502
BASE_URL = f"http://localhost:{PORT}"

PAGE_LABELS = [
    ("home", "Home"),
    ("executive_summary", "Executive Summary"),
    ("service_lines", "Service Lines"),
    ("payer_exposure", "Payer Exposure"),
    ("facility_benchmarks", "Facility Benchmarks"),
    ("process_control", "Process Control"),
    ("data_quality", "Data Quality"),
]


def wait_for_server(timeout_seconds: float = 60.0) -> None:
    import urllib.request

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/_stcore/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(1.0)
    raise RuntimeError("Streamlit did not become healthy in time")


CONTENT_SELECTOR = (
    ".js-plotly-plot, [data-testid='stMetricValue'], "
    "[data-testid='stDataFrame'], [data-testid='stJson'], "
    "[data-testid='stAlert']"
)


def settle(page) -> None:
    """Wait until the page has fully streamed in and charts have painted.

    Streamlit delivers elements progressively; leaving early captures blank
    charts and missing tables. We poll a content selector count until it
    stops changing, with a hard cap so text-only pages cannot hang.
    """
    page.wait_for_load_state("networkidle")
    # Some text-only pages carry no element matching CONTENT_SELECTOR.
    with contextlib.suppress(Exception):
        page.wait_for_selector(CONTENT_SELECTOR, timeout=15_000)
    page.wait_for_function(
        """() => new Promise(resolve => {
            const selector = ".js-plotly-plot svg .scatter, "
                + "[data-testid='stDataFrame'], [data-testid='stMetric'], "
                + "[data-testid='stAlert'], h4, h5, [data-testid='stExpander'], "
                + "[data-testid='stJson']";
            let last = -1, stable = 0;
            const timer = setInterval(() => {
                const count = document.querySelectorAll(selector).length;
                if (count === last) {
                    stable += 1;
                    if (stable >= 3) { clearInterval(timer); resolve(true); }
                } else { stable = 0; last = count; }
            }, 500);
            setTimeout(() => { clearInterval(timer); resolve(true); }, 20000);
        })""",
        timeout=30_000,
    )
    page.wait_for_timeout(1500)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app/Home.py",
            f"--server.port={PORT}",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
        ],
        cwd=ROOT,
    )
    try:
        wait_for_server()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.goto(BASE_URL, wait_until="networkidle")
            # Streamlit lays out its scroll container to the viewport; a tall
            # viewport puts every section in view so nothing is cut off.
            page.set_viewport_size({"width": 1400, "height": 3800})
            settle(page)
            for file_stem, label in PAGE_LABELS:
                # Direct URL loads give every page a fresh render; client-side
                # sidebar navigation left below-fold charts unpainted.
                page.goto(f"{BASE_URL}/{label.replace(' ', '_')}", wait_until="networkidle")
                page.set_viewport_size({"width": 1400, "height": 3800})
                # Hide deploy/menu chrome so captures show only app content.
                page.add_style_tag(
                    content="[data-testid='stToolbar'], "
                    "[data-testid='stStatusWidget'] {display: none;}"
                )
                settle(page)
                destination = OUT_DIR / f"{file_stem}.png"
                # Streamlit reports body scrollHeight 0 (the app scrolls in
                # an inner container), which blanks full_page captures.
                # Screenshot the main container element instead.
                page.locator('[data-testid="stMainBlockContainer"]').screenshot(
                    path=str(destination)
                )
                print(f"captured {destination.name}")
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=15)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
