import json
from pathlib import Path
from typing import Any

from backend.agentgate.demo.trace_seed_generator import write_seed_evidence
from backend.agentgate.main import app
from backend.agentgate.release.release_check import run_release_check
from fastapi.testclient import TestClient


def _seed(version: str, tmp_path: Path) -> Path:
    output = tmp_path / f"seed_{version.replace('.', '')}_evidence.jsonl"
    write_seed_evidence(version, output)
    return output


def test_release_check_writes_standalone_html_report(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    run_release_check(evidence, output_dir)

    html_path = output_dir / "release_report.html"
    assert html_path.exists()
    assert html_path.stat().st_size > 0


def test_standalone_html_is_offline_capable(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    run_release_check(evidence, output_dir)

    html = (output_dir / "release_report.html").read_text(encoding="utf-8")

    assert "<style>" in html
    assert "--paper:" in html
    assert "Inter" in html
    assert "/static/dashboard.css" not in html
    assert 'href="/"' not in html
    assert "Candidate report" in html
    assert "Release controls" in html
    assert "reference_ops_p0_release_suite" in html
    assert "controlled" in html
    assert "Ratio " in html
    assert "Audit scope and sample notes" in html
    assert "Gate-binding decision contract" in html
    assert "Release controls generated" in html
    assert "Fix now" not in html
    assert "Hard block deep_investigate_alert unless user_role is developer or sre." in html
    assert "Technical backing: regression_gates.json" in html
    assert "Why blocked" in html
    assert "Audit status" in html
    assert "Demo evidence: controlled sample data, not production traffic." in html
    assert "<script>" in html
    assert "blocker-findings-preview" in html
    assert "BLOCKED" in html


def test_artifact_route_serves_html_report(tmp_path: Path, monkeypatch: Any) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "latest"
    run_release_check(evidence, output_dir)
    monkeypatch.setenv("AGENTGATE_LATEST_ARTIFACT_DIR", str(output_dir))
    client = TestClient(app)

    response = client.get("/artifacts/release_report.html")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Candidate report" in response.text
    assert "Release controls" in response.text
    assert "Audit scope and sample notes" in response.text
    assert "Why blocked" in response.text
    assert response.headers.get("content-disposition", "").endswith('release_report.html"')


def test_report_page_shows_download_bundle_button(tmp_path: Path, monkeypatch: Any) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "latest"
    run_release_check(evidence, output_dir)
    monkeypatch.setenv("AGENTGATE_LATEST_ARTIFACT_DIR", str(output_dir))
    client = TestClient(app)

    response = client.get("/reports/latest")

    assert response.status_code == 200
    assert "Download full report bundle" in response.text
    assert 'href="/artifacts/release_audit_bundle.zip"' in response.text
    assert 'class="button primary"' in response.text
    assert "audit-artifact-dock" in response.text


def test_artifact_route_serves_zip_bundle(tmp_path: Path, monkeypatch: Any) -> None:
    import io
    import zipfile

    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "latest"
    run_release_check(evidence, output_dir)
    monkeypatch.setenv("AGENTGATE_LATEST_ARTIFACT_DIR", str(output_dir))
    client = TestClient(app)

    response = client.get("/artifacts/release_audit_bundle.zip")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
    assert "release_report.html" in names
    assert "release_decision.json" in names
    assert "metrics_summary.json" in names


def test_release_decision_includes_html_in_artifact_paths(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    run_release_check(evidence, output_dir)

    decision = json.loads((output_dir / "release_decision.json").read_text(encoding="utf-8"))
    artifact_paths = decision["artifact_paths"]

    assert "release_report" in artifact_paths
    assert artifact_paths["release_report"].endswith("release_report.html")
    assert Path(artifact_paths["release_report"]).exists()
