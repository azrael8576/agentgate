#!/usr/bin/env python3
"""Capture viewport screenshots of report sections (expanded) for layout review."""

from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000/reports/latest"
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "ui-audit" / "report-sections"
SECTIONS = [
    ("01-hero", ".report-head"),
    ("02-sticky", ".report-sticky-bar"),
    ("03-why-blocked", ".why-blocked-band"),
    ("04-fix-now", ".fix-now-band"),
    ("05-evidence-summary", ".blocker-findings-table"),
    ("06-audit-archive", ".audit-archive-band"),
    ("07-controls-detail", ".control-table .metric-card.fail"),
    ("08-artifacts", ".audit-artifact-dock"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        for vp, size in [("desktop", {"width": 1440, "height": 900}), ("mobile", {"width": 390, "height": 844})]:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(viewport=size).new_page()
            page.goto(BASE, wait_until="networkidle")
            for el in page.query_selector_all("details"):
                el.evaluate("e => e.open = true")
            page.wait_for_timeout(300)

            for name, selector in SECTIONS:
                loc = page.locator(selector).first
                if loc.count() == 0:
                    print(f"skip {name}-{vp}: no match")
                    continue
                box = loc.bounding_box()
                if not box:
                    print(f"skip {name}-{vp}: no box")
                    continue
                page.evaluate(
                    "(y) => window.scrollTo(0, Math.max(0, y - 80))",
                    box["y"],
                )
                page.wait_for_timeout(120)
                path = OUT / f"{name}-{vp}.png"
                page.screenshot(path=str(path), clip={
                    "x": 0,
                    "y": 0,
                    "width": size["width"],
                    "height": min(size["height"], 900),
                })
                print(f"saved {path.name}")

            browser.close()
    print(f"Done -> {OUT}")


if __name__ == "__main__":
    main()
