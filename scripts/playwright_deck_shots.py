#!/usr/bin/env python3
"""Capture open-slide deck pages and verify route / page-count health."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "artifacts" / "deck-audit"


@dataclass
class DeckAudit:
    slide_id: str
    base_url: str
    route_template: str
    expected_pages: int
    notes_count: int | None
    pages_ok: int
    screenshots: list[str]
    errors: list[str]

    @property
    def passed(self) -> bool:
        if self.pages_ok != self.expected_pages:
            return False
        if self.notes_count is not None and self.notes_count != self.expected_pages:
            return False
        return not self.errors


def count_exported_pages(slide_tsx: Path) -> int:
    text = slide_tsx.read_text(encoding="utf-8")
    match = re.search(r"export default\s*\[(.*?)\]\s*satisfies\s*Page\[\]", text, re.S)
    if not match:
        raise ValueError(f"Could not parse exported pages from {slide_tsx}")
    body = match.group(1)
    return len(re.findall(r"^\s*[A-Za-z_]\w*\s*,?\s*$", body, re.M))


def count_notes(slide_tsx: Path) -> int:
    text = slide_tsx.read_text(encoding="utf-8")
    match = re.search(r"export const notes\s*=\s*\[(.*?)\]\s*;", text, re.S)
    if not match:
        return 0
    return len(re.findall(r"`", match.group(1))) // 2


def audit_deck(
    *,
    slide_id: str,
    base_url: str,
    route_template: str,
    expected_pages: int | None,
    out_dir: Path,
    slide_tsx: Path | None,
) -> DeckAudit:
    notes_count: int | None = None
    if slide_tsx and slide_tsx.is_file():
        if expected_pages is None:
            expected_pages = count_exported_pages(slide_tsx)
        notes_count = count_notes(slide_tsx)
    if expected_pages is None:
        raise ValueError("expected_pages is required when slide_tsx is missing")

    out_dir.mkdir(parents=True, exist_ok=True)
    screenshots: list[str] = []
    errors: list[str] = []
    pages_ok = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        for page_num in range(1, expected_pages + 1):
            url = route_template.format(
                base_url=base_url.rstrip("/"),
                slide_id=slide_id,
                page=page_num,
            )
            try:
                response = page.goto(url, wait_until="networkidle", timeout=30_000)
                if response is None or response.status >= 400:
                    status = response.status if response else "no response"
                    errors.append(f"p={page_num}: HTTP {status}")
                    continue
                page.wait_for_timeout(900)
                not_found = page.locator("text=Page not found").count() > 0
                if not_found:
                    errors.append(f"p={page_num}: open-slide route rendered Page not found")
                    continue
                shot = out_dir / f"{slide_id}-p{page_num:02d}.png"
                page.screenshot(path=str(shot), full_page=False)
                screenshots.append(str(shot.relative_to(REPO_ROOT)))
                pages_ok += 1
            except Exception as exc:  # noqa: BLE001 - collect all page failures
                errors.append(f"p={page_num}: {exc}")

        browser.close()

    return DeckAudit(
        slide_id=slide_id,
        base_url=base_url,
        route_template=route_template,
        expected_pages=expected_pages,
        notes_count=notes_count,
        pages_ok=pages_ok,
        screenshots=screenshots,
        errors=errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slide-id", default="agentgate-launch")
    parser.add_argument("--base-url", default="http://127.0.0.1:4173")
    parser.add_argument(
        "--route-template",
        default="{base_url}/s/{slide_id}?p={page}",
        help="Format string with {base_url}, {slide_id}, and {page}",
    )
    parser.add_argument("--pages", type=int, default=None, help="Expected page count")
    parser.add_argument(
        "--slide-tsx",
        type=Path,
        default=REPO_ROOT / "my-deck" / "slides" / "agentgate-launch" / "index.tsx",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT / "agentgate-launch")
    args = parser.parse_args()

    slide_tsx = args.slide_tsx if args.slide_tsx.exists() else None
    result = audit_deck(
        slide_id=args.slide_id,
        base_url=args.base_url,
        route_template=args.route_template,
        expected_pages=args.pages,
        out_dir=args.out_dir,
        slide_tsx=slide_tsx,
    )

    report_path = args.out_dir / "audit.json"
    report_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

    print(json.dumps(asdict(result), indent=2))
    print(f"\nReport -> {report_path}")
    print(f"Screenshots -> {args.out_dir}")

    if result.notes_count is not None:
        print(f"Pages: {result.expected_pages}, notes: {result.notes_count}, captured: {result.pages_ok}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
