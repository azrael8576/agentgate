"""Optional HTML report export after release artifact write.

Keeps the release pipeline from importing web modules at load time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def export_release_report_html(output_dir: Path) -> Path:
    from backend.agentgate.web.report_renderer import render_standalone_release_report_html

    return render_standalone_release_report_html(output_dir)


def sync_decision_artifact_paths(output_dir: Path, artifact_paths: dict[str, str]) -> None:
    from backend.agentgate.web.report_renderer import update_release_decision_artifact_paths

    update_release_decision_artifact_paths(output_dir, artifact_paths)
