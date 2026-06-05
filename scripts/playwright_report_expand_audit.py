#!/usr/bin/env python3
"""Expand all report <details> sections and capture layout audit screenshots."""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
OUT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "ui-audit"
DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}


def expand_all_details(page) -> dict:
    return page.evaluate(
        """() => {
          const results = { opened: 0, failed: [], labels: [] };
          const details = [...document.querySelectorAll('details')];
          for (const el of details) {
            const label = (el.querySelector('summary')?.textContent || '').trim().slice(0, 80);
            try {
              el.open = true;
              results.opened += 1;
              results.labels.push(label);
            } catch (e) {
              results.failed.push(label);
            }
          }
          return results;
        }"""
    )


def layout_metrics(page) -> dict:
    return page.evaluate(
        """() => {
          const doc = document.documentElement;
          const overflowX = doc.scrollWidth > doc.clientWidth + 1;
          const offenders = [];
          for (const el of document.querySelectorAll('*')) {
            const r = el.getBoundingClientRect();
            if (r.width < 2 || r.height < 2) continue;
            if (r.right > doc.clientWidth + 2) {
              const tag = el.tagName.toLowerCase();
              const cls = (el.className || '').toString().slice(0, 60);
              offenders.push({ tag, cls, right: Math.round(r.right), vw: doc.clientWidth });
            }
          }
          const uniq = [];
          const seen = new Set();
          for (const o of offenders) {
            const k = o.tag + ':' + o.cls;
            if (seen.has(k)) continue;
            seen.add(k);
            uniq.push(o);
            if (uniq.length >= 25) break;
          }
          return {
            overflowX,
            scrollWidth: doc.scrollWidth,
            clientWidth: doc.clientWidth,
            scrollHeight: doc.scrollHeight,
            offenders: uniq,
          };
        }"""
    )


def visible_contract(page) -> dict:
    return page.evaluate(
        """() => {
          const text = document.body.textContent;
          const required = [
            "Candidate report",
            "Why blocked",
            "Fix now",
            "Evidence summary",
            "Audit archive summary",
            "Phoenix provides trace/eval evidence",
            "AgentGate gate-bound metrics decide BLOCKED/APPROVED",
          ];
          return {
            required: Object.fromEntries(required.map((label) => [label, text.includes(label)])),
            visibleDetails: [...document.querySelectorAll('details')].filter((el) => {
              const r = el.getBoundingClientRect();
              return r.top < window.innerHeight && r.bottom > 0;
            }).length,
          };
        }"""
    )


def blocker_interaction_metrics(page) -> dict:
    return page.evaluate(
        """() => {
          const pager = document.querySelector('.blocker-findings-pager');
          if (!pager) return { found: false };
          const pageTwo = pager.querySelector('.blocker-pager-btn[data-page="2"]');
          if (pageTwo) pageTwo.click();
          const pageTwoVisible = [...pager.querySelectorAll('.blocker-summary-row')]
            .some((row) => row.dataset.page === '2' && !row.hidden);
          const firstVisible = [...pager.querySelectorAll('.blocker-summary-row')].find((row) => !row.hidden);
          const expand = firstVisible?.querySelector('.blocker-expand-btn');
          if (expand) expand.click();
          const detail = firstVisible
            ? document.getElementById(`blocker-detail-${firstVisible.dataset.findingIndex}`)
            : null;
          return {
            found: true,
            pageTwoVisible,
            detailOpened: Boolean(detail && !detail.hidden),
            copyButtons: pager.querySelectorAll('[data-copy]').length,
          };
        }"""
    )


def decision_evidence_metrics(page) -> dict:
    return page.evaluate(
        """() => {
          const table = document.querySelector('.decision-evidence-table');
          if (!table) return { found: false };
          const reasonCell = table.querySelector('tbody tr td:first-child');
          const reasonWidth = reasonCell ? reasonCell.getBoundingClientRect().width : 0;
          return { found: true, reasonWidth: Math.round(reasonWidth) };
        }"""
    )


def assert_layout(page, viewport_name: str, metrics_expanded: dict, details_after_expand: int) -> list[str]:
    failures: list[str] = []
    if viewport_name == "mobile" and metrics_expanded.get("overflowX"):
        failures.append(
            f"mobile page overflow-x: scrollWidth={metrics_expanded.get('scrollWidth')} "
            f"> clientWidth={metrics_expanded.get('clientWidth')}"
        )
    evidence = decision_evidence_metrics(page)
    if evidence.get("found") and evidence.get("reasonWidth", 0) < 80:
        failures.append(
            f"decision evidence REASON column too narrow: {evidence.get('reasonWidth')}px"
        )
    if details_after_expand > 12:
        failures.append(f"too many details after redesign: {details_after_expand}")
    contract = visible_contract(page)
    missing = [label for label, present in contract.get("required", {}).items() if not present]
    if missing:
        failures.append("visible report contract missing: " + ", ".join(missing))
    interaction = blocker_interaction_metrics(page)
    if interaction.get("found"):
        if not interaction.get("pageTwoVisible"):
            failures.append("blocker pager did not show page 2")
        if not interaction.get("detailOpened"):
            failures.append("blocker detail row did not open")
        if interaction.get("copyButtons", 0) < 1:
            failures.append("blocker copy buttons missing")
    return failures


def audit_viewport(playwright, viewport_name: str, size: dict) -> dict:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport=size)
    page = context.new_page()
    page.goto(f"{BASE_URL}/reports/latest", wait_until="networkidle")

    collapsed_before = page.locator("details:not([open])").count()
    expand_info = expand_all_details(page)
    page.wait_for_timeout(400)

    collapsed_after = page.locator("details:not([open])").count()
    metrics = layout_metrics(page)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shot_collapsed = OUT_DIR / f"report-{viewport_name}-collapsed.png"
    shot_expanded = OUT_DIR / f"report-{viewport_name}-all-expanded.png"

    page.goto(f"{BASE_URL}/reports/latest", wait_until="networkidle")
    page.screenshot(path=str(shot_collapsed), full_page=True)

    expand_all_details(page)
    page.wait_for_timeout(500)
    page.screenshot(path=str(shot_expanded), full_page=True)
    metrics_expanded = layout_metrics(page)
    details_after_expand = page.locator("details").count()
    layout_failures = assert_layout(page, viewport_name, metrics_expanded, details_after_expand)

    context.close()
    browser.close()

    return {
        "viewport": viewport_name,
        "collapsed_before": collapsed_before,
        "collapsed_after": collapsed_after,
        "expand": expand_info,
        "metrics_collapsed": metrics,
        "metrics_expanded": metrics_expanded,
        "details_after_expand": details_after_expand,
        "layout_failures": layout_failures,
        "screenshots": {
            "collapsed": str(shot_collapsed),
            "expanded": str(shot_expanded),
        },
    }


def main() -> None:
    results = []
    with sync_playwright() as p:
        results.append(audit_viewport(p, "desktop", DESKTOP))
        results.append(audit_viewport(p, "mobile", MOBILE))

    out = OUT_DIR / "report-expand-audit.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nWrote {out}")

    all_failures = [
        f"{row['viewport']}: {msg}" for row in results for msg in row.get("layout_failures", [])
    ]
    if all_failures:
        raise SystemExit("Layout audit failed:\n" + "\n".join(all_failures))


if __name__ == "__main__":
    main()
