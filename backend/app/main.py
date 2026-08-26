"""Human-AI Co-Creative Storytelling - MVP backend.

ET617 Group 15. Implements HLD sections 6-8 at prototype fidelity:
split-screen workspace API, Helsinki guardrail graph, swappable model gateway,
and a telemetry store with anonymised export.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .routers import chat, experiments, research, session, workspaces

app = FastAPI(
    title="Human-AI Co-Creative Storytelling",
    description="ET617 Group 15 - educational storytelling MVP",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(session.router)
app.include_router(workspaces.router)
app.include_router(chat.router)
app.include_router(research.router)
app.include_router(experiments.router)


@app.get("/api/health")
async def health():
    from .providers import get_provider
    ok, status = await get_provider(settings.effective_provider).health()
    return {
        "ok": True,
        "default_provider": settings.effective_provider,
        "configured_provider": settings.default_provider,
        "provider_healthy": ok,
        "provider_status": status,
    }
