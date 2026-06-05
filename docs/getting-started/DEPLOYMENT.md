# Deployment

Run the AgentGate release dashboard locally or on Cloud Run.

## Local dashboard

```bash
uv run uvicorn backend.agentgate.main:app --reload
open http://127.0.0.1:8000/
```

Environment (see `.env.example`):

```bash
export AGENTGATE_LATEST_ARTIFACT_DIR="artifacts/release/latest"
export AGENTGATE_CANDIDATE_VERSION="v2"
export AGENTGATE_CANDIDATE_VERSIONS="v2,v2.1"
export AGENTGATE_DIAGNOSIS_MODE="gemini"
export AGENTGATE_GEMINI_MODEL="gemini-flash-latest"
```

Phoenix and Vertex credentials are required for default Phoenix MCP + Gemini runs.

## Docker (local)

```bash
docker build -t agentgate .
docker run --rm -p 8080:8080 \
  -e PHOENIX_COLLECTOR_ENDPOINT="$PHOENIX_COLLECTOR_ENDPOINT" \
  -e PHOENIX_API_KEY="$PHOENIX_API_KEY" \
  -e PHOENIX_PROJECT_NAME="$PHOENIX_PROJECT_NAME" \
  -e GOOGLE_CLOUD_PROJECT="$GOOGLE_CLOUD_PROJECT" \
  -e GOOGLE_CLOUD_LOCATION="global" \
  -e GOOGLE_GENAI_USE_VERTEXAI="True" \
  -e AGENTGATE_GEMINI_MODEL="gemini-flash-latest" \
  agentgate
```

## Cloud Run

Use a **dedicated GCP project** for AgentGate Gemini/Vertex — not the target production agent's runtime project unless policy explicitly allows it.

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  aiplatform.googleapis.com secretmanager.googleapis.com \
  --project "$GOOGLE_CLOUD_PROJECT"

gcloud run deploy agentgate \
  --source . \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=True,AGENTGATE_GEMINI_MODEL=gemini-flash-latest,PHOENIX_COLLECTOR_ENDPOINT=${PHOENIX_COLLECTOR_ENDPOINT},PHOENIX_PROJECT_NAME=${PHOENIX_PROJECT_NAME}" \
  --set-secrets "PHOENIX_API_KEY=phoenix-api-key:latest"
```

Notes:

- Cloud Run **region** (`us-central1`) and Vertex **location** (`global` for `gemini-flash-latest`) are separate settings.
- Store `PHOENIX_API_KEY` in Secret Manager for production deploys.

## Gemini / Vertex setup

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT="<dedicated-project>"
export GOOGLE_CLOUD_LOCATION="global"
```

Gemini diagnosis boundaries: [`../integration/RELEASE_OUTPUT.md`](../integration/RELEASE_OUTPUT.md).
