"""
Swarm-It Sidecar - RSCT Certification Service

Run as standalone service alongside your AI application.
Inspired by Tendermint's ABCI model.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8080

    # Or with Docker:
    docker run -p 8080:8080 swarmit/sidecar
"""

import os
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from api.rest import router as api_router
from api.metrics import init_metrics, get_metrics, get_metrics_content_type

app = FastAPI(
    title="Swarm-It Sidecar",
    description="RSCT Certification Service for AI/LLM Governance",
    version="0.1.0",
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "swarm-it-sidecar"}


@app.get("/ready")
async def ready():
    """Readiness check endpoint."""
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type(),
    )


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    init_metrics(version="0.1.0")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
