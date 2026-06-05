from typing import Any

from backend.agentgate.core.agent_pack import LoadedAgentPack


def build_landing_story(
    latest_context: dict[str, Any] | None,
    blocked_context: dict[str, Any] | None,
    approved_context: dict[str, Any] | None,
    demo_story: dict[str, Any],
    pack: LoadedAgentPack,
) -> dict[str, Any]:
    story_context = blocked_context or latest_context
    if not story_context and not latest_context:
        return {
            "primary_blocker": "No release candidate evaluated yet",
            "live_timeline": _default_landing_timeline(),
            "blocked_cards": [],
            "improvement_loop": None,
            "featured_intervention": None,
            "secondary_proof": None,
            "operational_status": None,
            "regression_gate_count": 0,
            "policy_highlights": _policy_highlights(None, pack),
            "agent_display_name": pack.display_name,
            "verdict_note": None,
            "card_dangerous_trace_count": 0,
            "reference_demo_section_title": demo_story.get("section_title", "Demo workflow"),
            "reference_demo_section_note": demo_story.get("section_note"),
            "reference_demo_nav_label": demo_story.get("nav_label"),
            "deployment_stack_title": _deployment_stack_title(pack),
            "deployment_stack_note": _deployment_stack_note(pack),
            "live_demo_label": _live_demo_label(pack),
        }

    card_context = latest_context or story_context
    findings = story_context.get("critical_findings", []) if story_context else []
    card_regression_gates = (card_context or {}).get("regression_gates", [])
    timeline_context = latest_context or story_context
    card_findings = (card_context or {}).get("critical_findings", [])
    card_dangerous_trace_count = len(
        {finding.get("trace_id") for finding in card_findings if finding.get("trace_id")}
    )
    blocked_cards = blocked_cards_from_findings(findings, demo_story, story_context)
    dangerous_trace_count = len(
        {finding.get("trace_id") for finding in findings if finding.get("trace_id")}
    )

    live_timeline = _live_timeline(
        timeline_context,
        card_dangerous_trace_count if latest_context else dangerous_trace_count,
        len(card_regression_gates),
    )

    return {
        "primary_blocker": primary_blocker_label(latest_context, blocked_cards),
        "live_timeline": live_timeline,
        "blocked_cards": blocked_cards,
        "improvement_loop": _improvement_loop(
            blocked_context or latest_context,
            approved_context,
            demo_story,
        ),
        "featured_intervention": _featured_intervention(blocked_context or story_context),
        "secondary_proof": _secondary_proof(approved_context),
        "operational_status": _operational_status(latest_context),
        "regression_gate_count": len(card_regression_gates),
        "policy_highlights": _policy_highlights(story_context, pack),
        "agent_display_name": _agent_display_name(latest_context or story_context),
        "verdict_note": _verdict_note(latest_context),
        "card_dangerous_trace_count": card_dangerous_trace_count,
        "reference_demo_section_title": demo_story.get("section_title", "Demo workflow"),
        "reference_demo_section_note": demo_story.get("section_note"),
        "reference_demo_nav_label": demo_story.get("nav_label"),
        "deployment_stack_title": _deployment_stack_title(pack),
        "deployment_stack_note": _deployment_stack_note(pack),
        "live_demo_label": _live_demo_label(pack),
    }


def blocked_cards_from_findings(
    findings: list[dict[str, Any]],
    demo_story: dict[str, Any],
    story_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not findings:
        return []

    titles = demo_story.get("blocked_card_titles", {})
    max_cards = int(demo_story.get("max_blocked_cards", 3))
    gate_ids_by_metric = {
        driver.get("metric_name"): driver.get("control_id")
        for driver in (story_context or {}).get("why_blocked", {}).get("blocking_drivers", [])
        if driver.get("metric_name")
    }
    finding_type_to_metric = {
        "unauthorized_dangerous_tool_execution": "unauthorized_dangerous_tool_attempt_rate",
        "unauthorized_dangerous_tool_attempt": "unauthorized_dangerous_tool_attempt_rate",
        "dangerous_tool_policy_violation": "dangerous_tool_policy_violation_rate",
        "dangerous_intent_misroute": "intent_routing_accuracy",
        "sensitive_output_violation": "sensitive_output_violation_rate",
    }
    cards: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for finding in findings:
        finding_type = str(finding.get("finding_type") or "default")
        dedupe_key = f"{finding_type}:{finding.get('trace_id') or finding.get('case_id')}"
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        title = (
            titles.get(finding_type)
            or titles.get("default")
            or finding_type.replace("_", " ").title()
        )
        metric_name = finding_type_to_metric.get(finding_type)
        gate_id = gate_ids_by_metric.get(metric_name, "—") if metric_name else "—"
        cards.append(
            _blocked_card(
                title=title,
                summary=_finding_summary(finding),
                gate_id=gate_id,
                finding=finding,
            )
        )
        if len(cards) >= max_cards:
            break
    return cards


def primary_blocker_label(
    latest_context: dict[str, Any] | None,
    blocked_cards: list[dict[str, Any]],
) -> str:
    if latest_context:
        decision = latest_context.get("release_decision", {}).get("decision")
        drivers = latest_context.get("why_blocked", {}).get("blocking_drivers", [])
        if decision == "BLOCKED" and drivers:
            first = drivers[0]
            control_id = first.get("control_id")
            display_name = first.get("display_name")
            if control_id and display_name:
                return f"{control_id} · {display_name}"
            if display_name:
                return str(display_name)
    if blocked_cards:
        return blocked_cards[0]["title"]
    return "No blocker evidence loaded"


def _branding(pack: LoadedAgentPack) -> dict[str, Any]:
    branding = pack.report_config.get("branding")
    return branding if isinstance(branding, dict) else {}


def _deployment_stack_title(pack: LoadedAgentPack) -> str:
    return str(_branding(pack).get("deployment_stack_title", "Deployment"))


def _deployment_stack_note(pack: LoadedAgentPack) -> str:
    return str(
        _branding(pack).get(
            "deployment_stack_note",
            "Hosts this dashboard and release workflow.",
        )
    )


def _live_demo_label(pack: LoadedAgentPack) -> str:
    return str(_branding(pack).get("live_demo_label", "Live demo →"))


def _live_timeline(
    context: dict[str, Any] | None,
    dangerous_trace_count: int,
    regression_gate_count: int,
) -> list[dict[str, Any]]:
    if not context:
        return _default_landing_timeline()
    return [
        {
            "label": "Collect evidence",
            "detail": "Phoenix MCP reads traces, spans, eval labels, policy preflights, and tool activity.",
        },
        {
            "label": "Run release controls",
            "detail": (
                f"{len(context.get('failing_metrics', []))} controls failed across "
                f"{len(context.get('metrics', []))} gate-bound release metrics."
            ),
        },
        {
            "label": "Select risky sessions",
            "detail": f"{dangerous_trace_count} trace-backed sessions promoted for focused review.",
        },
        {
            "label": "Explain selected sessions",
            "detail": (
                f"{len(context.get('dangerous_session_diagnoses', []))} optional Gemini explanations "
                "for reviewer context — does not decide release."
            ),
            "optional": True,
        },
        {
            "label": "Write audit bundle",
            "detail": f"{regression_gate_count} regression gates and exportable Certificate + Dossier artifacts.",
        },
    ]


def _policy_highlights(
    context: dict[str, Any] | None, pack: LoadedAgentPack
) -> list[dict[str, str]]:
    highlight_config = pack.landing_policy_highlights()
    controls = pack.control_definitions()
    metrics_by_name = (
        {metric.get("name"): metric for metric in context.get("metrics", []) if metric.get("name")}
        if context
        else {}
    )
    highlights: list[dict[str, str]] = []
    for item in highlight_config:
        metric_id = item["metric_id"]
        control = controls.get(metric_id, {})
        metric = metrics_by_name.get(metric_id, {})
        highlights.append(
            {
                "metric": metric_id,
                "label": control.get("name", metric_id.replace("_", " ").title()),
                "threshold": metric.get("threshold_display")
                or item.get("threshold_label", "Gate threshold"),
                "value": metric.get("display_value", "—") if context else "—",
            }
        )
    return highlights


def _finding_summary(finding: dict[str, Any]) -> str:
    role = finding.get("user_role")
    tool_name = finding.get("tool_name")
    routing = finding.get("routing_summary")
    finding_type = finding.get("finding_type")
    parts: list[str] = []
    if role and role != "unknown":
        parts.append(f"Role `{role}`")
    if tool_name and tool_name not in {"unknown", "n/a"}:
        parts.append(f"tool `{tool_name}`")
    if routing and routing not in {"unknown", "n/a"}:
        parts.append(f"routing {routing}")
    if parts:
        return " · ".join(parts) + "."
    if finding_type:
        return f"Material violation: {str(finding_type).replace('_', ' ')}."
    return "Material violation in controlled release evidence."


def _blocked_card(
    *,
    title: str,
    summary: str,
    gate_id: str,
    finding: dict[str, Any] | None,
) -> dict[str, Any]:
    if not finding:
        return {
            "title": title,
            "summary": summary,
            "role": "unknown",
            "intent": "unknown",
            "tool": "unknown",
            "evidence_id": "unknown",
            "gate_id": gate_id,
            "decision": "BLOCKED",
        }
    return {
        "title": title,
        "summary": summary,
        "role": finding.get("user_role", "unknown"),
        "intent": finding.get("intent_id", "unknown"),
        "tool": finding.get("tool_name", "unknown"),
        "evidence_id": finding.get("trace_short") or finding.get("trace_id") or "unknown",
        "gate_id": gate_id,
        "decision": "BLOCKED",
    }


def _agent_display_name(context: dict[str, Any] | None) -> str | None:
    if not context:
        return None
    profile = context.get("agent_profile", {})
    return (
        profile.get("display_name")
        or profile.get("agent_name")
        or context.get("release_decision", {}).get("agent_id")
    )


def _verdict_note(latest_context: dict[str, Any] | None) -> str | None:
    if not latest_context:
        return None
    decision = latest_context.get("release_decision", {})
    verdict = decision.get("decision")
    if verdict == "APPROVED":
        failing_count = len(latest_context.get("failing_metrics", []))
        if failing_count == 0:
            return "All gate-bound required metrics passed for this candidate."
        return f"APPROVED with {failing_count} non-blocking control(s) still under review."
    if verdict == "BLOCKED":
        reason_count = len(decision.get("decision_reasons", []))
        return f"{reason_count} gate-bound control(s) failed release thresholds."
    return None


def _featured_intervention(context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not context:
        return None
    finding = _select_featured_finding(context.get("critical_findings", []))
    dangerous_trace_count = len(
        {
            item.get("trace_id")
            for item in context.get("critical_findings", [])
            if item.get("trace_id")
        }
    )
    decision = context.get("release_decision", {})
    agent_version = decision.get("agent_version", "blocked")
    future_note = _future_verification_homepage_note(context)
    return {
        "version": agent_version,
        "decision": decision.get("decision", "BLOCKED"),
        "path_summary": _featured_path_summary(finding),
        "risk_summary": _featured_risk_summary(finding),
        "intervention_note": (
            f"AgentGate blocked {agent_version} before release and generated controls "
            "for the follow-up candidate."
        ),
        "dangerous_trace_count": dangerous_trace_count,
        "regression_gate_count": len(context.get("regression_gates", [])),
        "future_verification_note": future_note,
    }


def _secondary_proof(context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not context:
        return None
    decision = context.get("release_decision", {})
    agent_version = decision.get("agent_version", "v2.1")
    control_verification = context.get("control_verification") or {}
    source_version = control_verification.get("source_release", {}).get("agent_version") or "v2"
    failing_warnings = [
        metric
        for metric in context.get("failing_metrics", [])
        if metric.get("passes_threshold") is False and metric.get("decision_impact") == "warning"
    ]
    future = decision.get("future_verification") or {}
    status = future.get("status")
    failed = int(future.get("failed") or 0)
    blocking_failed = int(future.get("blocking_failed") or 0)
    has_nonblocking_warnings = bool(failing_warnings) or (blocking_failed == 0 and failed > 0)

    warning_summary = ""
    blocker_summary = ""
    if status == "verified" and blocking_failed == 0:
        verdict_note = f"{agent_version} verified the controls generated by the blocked {source_version} release."
        blocker_summary = "All inherited blocker controls passed."
        if has_nonblocking_warnings:
            warning_summary = "Approved, not perfect — non-blocking warnings remain visible."
    elif status == "not_available":
        verdict_note = f"{agent_version} is APPROVED from current gate-bound blocker metrics only."
    else:
        verdict_note = _verdict_note(context) or f"{agent_version} release review completed."

    return {
        "version": agent_version,
        "decision": decision.get("decision", "APPROVED"),
        "verdict_note": verdict_note,
        "blocker_summary": blocker_summary,
        "warning_summary": warning_summary,
        "future_verification_note": None,
    }


def _future_verification_homepage_note(context: dict[str, Any]) -> str:
    release_decision = context.get("release_decision", {})
    agent_version = release_decision.get("agent_version", "")
    future = release_decision.get("future_verification") or {}
    status = future.get("status")
    blocking_failed = int(future.get("blocking_failed") or 0)
    failed = int(future.get("failed") or 0)

    if agent_version == "v2" or status == "not_applicable":
        return "This blocked candidate generated release controls for the next candidate."
    if status == "verified":
        if blocking_failed == 0 and failed > 0:
            return (
                "Verified against inherited release controls. "
                "Approved, not perfect — non-blocking controls remain visible."
            )
        if blocking_failed == 0:
            return "Verified against inherited release controls. All inherited blocker controls passed."
        return "Inherited blocker controls did not pass."
    if status == "not_available":
        return (
            "No previous release controls were available. "
            "Decision is based on current gate-bound blocker metrics only."
        )
    if status == "failed":
        return "Inherited blocker controls did not pass."
    return ""


def _operational_status(context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not context:
        return None
    decision = context.get("release_decision", {})
    return {
        "version": decision.get("agent_version", "unknown"),
        "decision": decision.get("decision", "unknown"),
        "verdict_note": _verdict_note(context) or "Latest run saved for operator visibility.",
        "dangerous_trace_count": len(
            {
                item.get("trace_id")
                for item in context.get("critical_findings", [])
                if item.get("trace_id")
            }
        ),
    }


def _select_featured_finding(findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not findings:
        return None
    priority = {
        "unauthorized_dangerous_tool_execution": 0,
        "unauthorized_dangerous_tool_attempt": 0,
        "policy_violation_with_execution": 1,
        "dangerous_intent_misroute": 2,
        "dangerous_tool_policy_violation": 3,
        "sensitive_output_violation": 4,
    }

    def sort_key(finding: dict[str, Any]) -> tuple[int, int, int]:
        role = str(finding.get("user_role") or "")
        tool_name = str(finding.get("tool_name") or "")
        return (
            priority.get(str(finding.get("finding_type") or ""), 9),
            0 if role and role not in {"developer", "sre"} else 1,
            0 if tool_name == "deep_investigate_alert" else 1,
        )

    return min(findings, key=sort_key)


def _featured_path_summary(finding: dict[str, Any] | None) -> str:
    _ = finding
    return "A low-privilege role reached `deep_investigate_alert` in controlled release evidence."


def _featured_risk_summary(finding: dict[str, Any] | None) -> str:
    return "Policy expected DENY — but the dangerous tool was still called."


def _improvement_loop(
    blocked_context: dict[str, Any] | None,
    approved_context: dict[str, Any] | None,
    demo_story: dict[str, Any],
) -> dict[str, Any] | None:
    if not blocked_context or not approved_context:
        return None

    loop_config = demo_story.get("improvement_loop", {})
    blocked_decision = blocked_context.get("release_decision", {})
    approved_decision = approved_context.get("release_decision", {})
    approved_metrics = {
        metric.get("name"): metric
        for metric in approved_context.get("metrics", [])
        if metric.get("name")
    }
    unauthorized_attempt_rate = approved_metrics.get(
        "unauthorized_dangerous_tool_attempt_rate", {}
    ).get("display_value", "0.0%")
    policy_violation_rate = approved_metrics.get("dangerous_tool_policy_violation_rate", {}).get(
        "display_value", "0.0%"
    )
    approved_template = loop_config.get(
        "approved_summary_template",
        "Gate-bound blocker metrics improved on the approved candidate.",
    )

    return {
        "blocked_version": blocked_decision.get("agent_version", "blocked"),
        "blocked_decision": blocked_decision.get("decision", "BLOCKED"),
        "blocked_summary": loop_config.get(
            "blocked_summary",
            "Gate-bound required metrics failed on controlled evidence.",
        ),
        "regression_gate_count": len(blocked_context.get("regression_gates", [])),
        "regression_gate_scope": loop_config.get(
            "regression_gate_scope", "Emitted from blocked candidate bundle"
        ),
        "approved_version": approved_decision.get("agent_version", "approved"),
        "approved_decision": approved_decision.get("decision", "APPROVED"),
        "approved_summary": approved_template.format(
            unauthorized_attempt_rate=unauthorized_attempt_rate,
            policy_violation_rate=policy_violation_rate,
        ),
    }


def _default_landing_timeline() -> list[dict[str, str]]:
    return [
        {
            "label": "Collect evidence",
            "detail": "Read traces, spans, eval labels, policy preflights, and tool activity from Phoenix.",
        },
        {
            "label": "Run release controls",
            "detail": "Apply gate-bound metrics with deterministic thresholds and known denominators.",
        },
        {
            "label": "Select risky sessions",
            "detail": "Promote blocker evidence and indeterminate sessions for focused release review.",
        },
        {
            "label": "Explain selected sessions",
            "detail": "Gemini explains selected dangerous sessions for reviewer context. Non-authoritative.",
            "optional": True,
        },
        {
            "label": "Write audit bundle",
            "detail": "Produce a decision, metric provenance, regression gates, and an offline report.",
        },
    ]
