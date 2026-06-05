from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.agentgate.api.routes_health import router as health_router
from backend.agentgate.settings import configure_vertex_environment
from backend.agentgate.web.routes_dashboard import router as dashboard_router

configure_vertex_environment()


app = FastAPI(title="AgentGate", version="0.1.0")
app.include_router(health_router)
app.include_router(dashboard_router)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "web" / "static")),
    name="static",
)
