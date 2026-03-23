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
import logging
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from api.rest import router as api_router
from api.metrics import init_metrics, get_metrics, get_metrics_content_type

logger = logging.getLogger(__name__)

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

    # P18: Validate projection layer if Profile B (hardware compression) selected
    profile = os.environ.get("SWARM_PROFILE", "TRACK2_NATIVE_1024")

    if profile == "COMPACT_64_MULTIMODAL":
        logger.info("Profile B (hardware compression) selected - validating projection layer...")
        try:
            # Import here to avoid dependency if not using Profile B
            import sys
            from pathlib import Path

            # Add adk/swarm_it to path
            sys.path.insert(0, str(Path(__file__).parent.parent / "adk"))

            from swarm_it.projection import validate_projection_at_startup

            validation_result = validate_projection_at_startup()
            logger.info(f"P18 validation passed: {validation_result}")

        except Exception as e:
            logger.error(f"P18 VIOLATION: Projection validation failed at startup: {e}")
            raise RuntimeError(
                f"Cannot start server with Profile B without valid projection layer. "
                f"Error: {e}. "
                f"Either fix projection checkpoint or switch to Profile A (TRACK2_NATIVE_1024)."
            )
    else:
        logger.info(f"Profile A (native 1024-dim) selected - no projection layer needed")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
