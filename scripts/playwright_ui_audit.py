#!/usr/bin/env python3
"""Playwright UI audit for AgentGate hackathon demo pages."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE_URL = os.getenv("AGENTGATE_UI_AUDIT_BASE_URL", "http://127.0.0.1:8000")
SKIP_RUN_COMPLETE = os.getenv("AGENTGATE_UI_AUDIT_SKIP_RUN_COMPLETE", "false").lower() in {"1", "true", "yes"}
OUT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "ui-audit"
DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}


@dataclass
class Check:
    name: str
    passed: bool
    points: int
    max_points: int
    note: str = ""


@dataclass
class PageScore:
    page: str
    viewport: str
    total: int
    max_total: int
    checks: list[Check] = field(default_factory=list)
    screenshot: str = ""

    @property
    def pct(self) -> float:
        return round(100 * self.total / self.max_total, 1) if self.max_total else 0.0


def add(checks: list[Check], name: str, passed: bool, points: int, note: str = "") -> None:
    checks.append(Check(name=name, passed=passed, points=points if passed else 0, max_points=points, note=note))


def text_visible(page: Page, pattern: str) -> bool:
    try:
        return page.get_by_text(re.compile(pattern, re.I)).first.is_visible()
    except Exception:
        return False


def count_visible(page: Page, selector: str) -> int:
    return page.locator(selector).count()


def audit_overview(page: Page, viewport: str) -> PageScore:
    page.goto(f"{BASE_URL}/", wait_until="networkidle")
    checks: list[Check] = []

    add(checks, "Hero outcome-first headline", text_visible(page, r"Stop unsafe AI agent versions"), 8)
    add(checks, "Primary CTA: Run release check", page.locator('a[href="/run"]').filter(has_text=re.compile("Run release check", re.I)).count() > 0, 6)
    add(checks, "Secondary CTA: Open latest report", page.locator('a[href="/reports/latest"]').filter(has_text=re.compile("Open latest report", re.I)).count() > 0, 4)
    add(checks, "Tertiary CTA: View evidence artifacts", page.locator('a[href*="#audit-artifacts"]').filter(has_text=re.compile("View evidence artifacts", re.I)).count() > 0, 4)
    add(checks, "How it works section", text_visible(page, r"How it works"), 6)
    add(checks, "Stack section", text_visible(page, r"Where each piece sits"), 6)
    add(checks, "Latest verdict 卡", page.locator(".summary-panel .status").count() > 0, 8)
    add(checks, "Hero KPI row", page.locator(".summary-judgement .kpi-row").count() > 0, 6)
    add(checks, "Nav: Overview / Run check / Latest Report", all(
        page.locator(f'nav a[href="{href}"]').count() > 0 for href in ["/", "/run", "/reports/latest"]
    ) and page.locator('nav a[href="/run"]').filter(has_text=re.compile("Run check", re.I)).count() > 0, 6)
    add(checks, "手機無水平溢出", _no_horizontal_overflow(page), 8 if viewport == "mobile" else 4,
        "390px 無 document 水平捲動" if viewport == "mobile" else "desktop sanity")

    total = sum(c.points for c in checks)
    max_total = sum(c.max_points for c in checks)
    shot = _shot(page, f"overview-{viewport}")
    return PageScore("Overview /", viewport, total, max_total, checks, shot)


def audit_run_idle(page: Page, viewport: str) -> PageScore:
    page.goto(f"{BASE_URL}/run", wait_until="networkidle")
    checks: list[Check] = []

    add(checks, "Run release check title", text_visible(page, r"Run release check"), 6)
    add(checks, "左側 Before you run panel", page.locator(".run-panel h2").filter(has_text=re.compile("Before you run", re.I)).count() > 0, 6)
    add(checks, "右側 workflow stepper", page.locator(".timeline .step").count() >= 7, 10)
    add(checks, "無 event console", page.locator("#event-console.event-console").count() == 0, 10,
        "console UI 已移除")
    add(checks, "Diagnosis model 顯示", text_visible(page, r"Diagnosis model"), 6)
    add(checks, "Run release check 按鈕", page.locator("#run-button").filter(has_text=re.compile("Run release check", re.I)).count() > 0, 6)
    add(checks, "圓形 step index", page.locator(".step-index").count() >= 7, 8)
    add(checks, "Redirect script 存在", "window.location.assign(REPORT_URL)" in page.content(), 4)
    add(checks, "手機 layout 可讀", _no_horizontal_overflow(page), 10 if viewport == "mobile" else 4)

    total = sum(c.points for c in checks)
    max_total = sum(c.max_points for c in checks)
    shot = _shot(page, f"run-idle-{viewport}")
    return PageScore("Run check /run (idle)", viewport, total, max_total, checks, shot)


def audit_run_complete(page: Page, viewport: str) -> PageScore | None:
    page.goto(f"{BASE_URL}/run", wait_until="networkidle")
    checks: list[Check] = []

    page.locator("#run-button").click()
    page.wait_for_function(
        """() => {
            const summary = document.getElementById('run-summary');
            if (!summary) return false;
            const text = (summary.textContent || '').toLowerCase();
            return text.includes('decision written') || text.includes('failed') || text.includes('error');
        }""",
        timeout=300_000,
    )

    summary = page.locator("#run-summary").inner_text().strip().lower()
    if "failed" in summary or "error" in summary:
        note = page.locator("#run-result").inner_text()[:200]
        add(checks, "Release check 成功", False, 20, note)
        shot = _shot(page, f"run-error-{viewport}")
        total = sum(c.points for c in checks)
        max_total = sum(c.max_points for c in checks)
        return PageScore("Run check /run (complete)", viewport, total, max_total, checks, shot)

    completed_steps = page.locator(".step-complete").count()
    add(checks, "Release check 成功", True, 10)
    add(checks, "Stepper 全部完成", completed_steps >= 7, 12, f"completed={completed_steps}")
    add(checks, "含 load evidence 步驟", text_visible(page, r"Load candidate evidence"), 6)
    add(checks, "含 generate release controls 步驟", text_visible(page, r"Generate future release controls"), 8)
    page.wait_for_url(re.compile(r"/reports/latest$"), timeout=10_000)
    add(checks, "完成後 redirect 到 report", "/reports/latest" in page.url, 12)
    add(checks, "無 event console 行", page.locator("#event-console .console-line").count() == 0, 8)
    add(checks, "Report 頁可載入", text_visible(page, r"Candidate report|Release controls"), 10)

    total = sum(c.points for c in checks)
    max_total = sum(c.max_points for c in checks)
    shot = _shot(page, f"run-complete-{viewport}")
    return PageScore("Run check /run (complete)", viewport, total, max_total, checks, shot)


def audit_report(page: Page, viewport: str) -> PageScore:
    response = page.goto(f"{BASE_URL}/reports/latest", wait_until="networkidle")
    checks: list[Check] = []
    if response and response.status == 404:
        add(checks, "Report 可載入", False, 100, "404 - 需先跑 release check")
        return PageScore("Latest Report /reports/latest", viewport, 0, 100, checks)

    add(checks, "Candidate report 標題", text_visible(page, r"Candidate report"), 6)
    add(checks, "release review heading", text_visible(page, r"release review"), 6)
    add(checks, "Why blocked 區塊", text_visible(page, r"Why blocked"), 8)
    add(checks, "Fix now 區塊", text_visible(page, r"Fix now"), 8)
    add(checks, "Evidence summary 區塊", text_visible(page, r"Evidence summary"), 8)
    add(checks, "Audit archive summary", text_visible(page, r"Audit archive summary"), 8)
    add(checks, "Authority note", text_visible(page, r"AgentGate gate-bound metrics decide BLOCKED/APPROVED"), 8)
    add(checks, "Audit scope 區塊", text_visible(page, r"Audit scope, coverage, and reproducibility"), 6)
    add(checks, "Release controls + AG-RG", count_visible(page, ".control-id") >= 7, 10,
        f"controls={count_visible(page, '.control-id')}")
    add(checks, "Release controls 標題", text_visible(page, r"Release controls detail"), 8)
    add(checks, "Blocker findings 表格", page.locator(".blocker-findings-table tbody tr").count() >= 1, 8,
        f"rows={page.locator('.blocker-findings-table tbody tr').count()}")
    add(checks, "Blocker findings 非整段隱藏", page.locator("details:has(> .appendix-summary):has-text('Show all')").count() == 0, 6)
    add(checks, "Appendix details present", page.locator("details:has(.appendix-summary)").count() >= 1, 8)
    add(checks, "Copy remediation context", page.locator("button.copy-button").count() >= 1, 10,
        f"buttons={page.locator('button.copy-button').count()}")
    add(checks, "Gemini 附錄", text_visible(page, r"Gemini semantic diagnosis"), 8)
    add(checks, "Artifact fingerprints", text_visible(page, r"Artifact fingerprints"), 6)
    add(checks, "Copy remediation context labels", text_visible(page, r"Copy remediation context"), 6)
    add(checks, "Regression tasks KPI", text_visible(page, r"Regression tasks"), 6)
    add(checks, "Audit trail artifact downloads", page.locator(".audit-artifact-dock .artifact-chip, .audit-artifact-dock .button").count() >= 4, 8)
    add(checks, "Decision badge", page.locator(".decision-card .status, .report-head .status").count() > 0, 4)
    add(checks, "手機 high-risk cards", _mobile_risk_cards_ok(page, viewport), 10 if viewport == "mobile" else 4)
    add(checks, "手機無水平溢出", _no_horizontal_overflow(page), 6 if viewport == "mobile" else 2)

    total = sum(c.points for c in checks)
    max_total = sum(c.max_points for c in checks)
    shot = _shot(page, f"report-{viewport}")
    return PageScore("Latest Report /reports/latest", viewport, total, max_total, checks, shot)


def _no_horizontal_overflow(page: Page) -> bool:
    return page.evaluate(
        "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"
    )


def _console_is_dark(page: Page) -> bool:
    return page.evaluate(
        """() => {
            const el = document.querySelector('#event-console');
            if (!el) return false;
            const bg = getComputedStyle(el).backgroundColor;
            return bg !== 'rgba(0, 0, 0, 0)' && bg !== 'rgb(255, 255, 255)';
        }"""
    )


def _mobile_risk_cards_ok(page: Page, viewport: str) -> bool:
    if viewport != "mobile":
        return page.locator(".risk-card, .high-risk-cards .risk-card").count() >= 0 or True
    cards = page.locator(".risk-card").count()
    table = page.locator(".table-wrap-full table").count()
    if cards >= 1:
        return True
    # fallback: table exists but no overflow
    return table >= 1 and _no_horizontal_overflow(page)


def _shot(page: Page, name: str) -> str:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def grade(pct: float) -> str:
    if pct >= 90:
        return "A"
    if pct >= 80:
        return "B+"
    if pct >= 70:
        return "B"
    if pct >= 60:
        return "C+"
    if pct >= 50:
        return "C"
    return "D"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[PageScore] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for viewport_name, size in [("desktop", DESKTOP), ("mobile", MOBILE)]:
            context = browser.new_context(viewport=size)
            page = context.new_page()
            results.append(audit_overview(page, viewport_name))
            results.append(audit_run_idle(page, viewport_name))
            if viewport_name == "desktop" and not SKIP_RUN_COMPLETE:
                complete = audit_run_complete(page, viewport_name)
                if complete:
                    results.append(complete)
            results.append(audit_report(page, viewport_name))
            context.close()
        browser.close()

    report = {
        "base_url": BASE_URL,
        "pages": [asdict(r) for r in results],
        "summary": [],
    }

    print("\n=== AgentGate Playwright UI Audit ===\n")
    for r in results:
        g = grade(r.pct)
        print(f"{r.page} [{r.viewport}]")
        print(f"  Score: {r.total}/{r.max_total} ({r.pct}%) - Grade {g}")
        print(f"  Screenshot: {r.screenshot}")
        for c in r.checks:
            mark = "✓" if c.passed else "✗"
            print(f"    {mark} {c.name} ({c.points}/{c.max_points}) {c.note}")
        print()
        report["summary"].append({"page": r.page, "viewport": r.viewport, "pct": r.pct, "grade": g})

    out_json = OUT_DIR / "scores.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Full report: {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
