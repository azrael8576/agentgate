FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Phoenix MCP release checks spawn `npx @arizeai/phoenix-mcp` as a subprocess.
RUN apt-get update \
  && apt-get install -y --no-install-recommends nodejs npm \
  && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
COPY configs ./configs

RUN uv sync --frozen --no-dev \
  && uv run agentgate release check --source local \
    --evidence configs/agents/stability_ops/seed/v2_evidence.jsonl \
    --output-dir artifacts/release/reference-v2 \
    --diagnosis-mode deterministic \
  && uv run agentgate release check --source local \
    --evidence configs/agents/stability_ops/seed/v21_evidence.jsonl \
    --output-dir artifacts/release/reference-v21 \
    --release-controls artifacts/release/reference-v2/regression_gates.json \
    --diagnosis-mode deterministic

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "backend.agentgate.main:app", "--host", "0.0.0.0", "--port", "8080"]
