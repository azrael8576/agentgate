#!/usr/bin/env bash
# Fail if agent-specific strings appear outside allowlisted paths.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PATTERN='GamaPlay|6180|gamania|deep_investigate_issue|summarize_h5_incidents|analyze_gamania_stock|stability-ops-automation'

ALLOW_GLOBS=(
  '!configs/agents/stability_ops/**'
  '!backend/agentgate/demo/**'
  '!docs/integrations/stability_ops/**'
  '!docs/REFERENCE_WORKFLOW.md'
  '!docs/internal/**'
  '!examples/artifacts/**'
  '!artifacts/**'
  '!tests/**'
)

SCAN_PATHS=(
  README.md
  AGENTS.md
  CONTEXT.md
  docs
  backend/agentgate/core
  backend/agentgate/release
  backend/agentgate/web
  configs/phoenix
)

if rg -n "$PATTERN" "${ALLOW_GLOBS[@]}" "${SCAN_PATHS[@]}" 2>/dev/null; then
  echo "audit_agent_coupling: forbidden agent-specific strings found in product layer (see above)." >&2
  exit 1
fi

if rg -n 'GamaPlay|6180|gamania' backend/agentgate/demo/ 2>/dev/null; then
  echo "audit_agent_coupling: PII markers found under backend/agentgate/demo/." >&2
  exit 1
fi

echo "audit_agent_coupling: OK"
