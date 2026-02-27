"""
FastAPI Integration Example

Shows how to add RSCT certification to a FastAPI application.
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from swarm_it import SwarmIt
from swarm_it.integrations import SwarmItMiddleware, require_certificate

# Initialize
app = FastAPI(title="Swarm It Demo API")
swarm = SwarmIt()


# Request/Response models
class ChatRequest(BaseModel):
    prompt: str
    model: str = "gpt-4"
    max_tokens: int = 1000


class ChatResponse(BaseModel):
    response: str
    certificate_id: str
    allowed: bool


class CompletionRequest(BaseModel):
    messages: list
    model: str = "gpt-4"


# Option 1: Middleware (certifies all matching routes)
# Uncomment to enable:
# app.add_middleware(
#     SwarmItMiddleware,
#     client=swarm,
#     paths=["/api/"],  # Only certify /api/* routes
#     exclude_paths=["/api/health"],
# )


# Option 2: Per-route decorator
@app.post("/api/chat", response_model=ChatResponse)
@require_certificate(swarm, context_param="prompt")
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint with automatic certification.

    The @require_certificate decorator:
    1. Extracts 'prompt' from the request
    2. Certifies it
    3. Blocks with 403 if rejected
    4. Proceeds if allowed
    """
    # If we get here, certification passed
    # In real code: call your LLM here

    # Mock response
    return ChatResponse(
        response=f"[Response to: {request.prompt[:50]}...]",
        certificate_id="cert-xxx",  # Would come from actual cert
        allowed=True,
    )


# Option 3: Manual certification in handler
@app.post("/api/complete")
async def complete_endpoint(request: CompletionRequest):
    """
    Completion endpoint with manual certification.

    More control over the certification flow.
    """
    # Extract last user message
    user_messages = [m for m in request.messages if m.get("role") == "user"]
    if not user_messages:
        raise HTTPException(400, "No user message found")

    last_message = user_messages[-1]["content"]

    # Certify manually
    cert = swarm.certify(
        context=last_message,
        metadata={
            "model": request.model,
            "message_count": len(request.messages),
        },
    )

    if not cert.allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Request blocked by RSCT gate",
                "reason": cert.reason,
                "certificate": {
                    "id": cert.id,
                    "R": cert.R,
                    "S": cert.S,
                    "N": cert.N,
                    "decision": cert.decision.value,
                },
            },
        )

    # Proceed with LLM call
    return {
        "response": f"[Response to: {last_message[:50]}...]",
        "certificate": cert.to_dict(),
    }


# Option 4: Dependency injection
async def get_certificate(prompt: str) -> dict:
    """
    FastAPI dependency for certification.

    Use in routes that need certificate data.
    """
    cert = swarm.certify(prompt)
    if not cert.allowed:
        raise HTTPException(403, f"Blocked: {cert.reason}")
    return cert


@app.post("/api/ask")
async def ask_endpoint(
    prompt: str,
    cert=Depends(lambda: None),  # Would use get_certificate in real app
):
    """Endpoint using dependency injection for certification."""
    return {"response": f"[Response to: {prompt}]"}


# Health check (excluded from certification)
@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Certificate inspection endpoint
@app.post("/api/certify-only")
async def certify_only(request: ChatRequest):
    """
    Certification-only endpoint.

    Returns certificate without executing LLM.
    Useful for pre-flight checks.
    """
    cert = swarm.certify(request.prompt)

    return {
        "certificate_id": cert.id,
        "timestamp": cert.timestamp,
        "rsn": {
            "R": cert.R,
            "S": cert.S,
            "N": cert.N,
        },
        "metrics": {
            "alpha": cert.alpha,
            "kappa": cert.kappa,
            "sigma": cert.sigma,
            "margin": cert.margin,
        },
        "gate": {
            "decision": cert.decision.value,
            "allowed": cert.allowed,
            "reason": cert.reason,
        },
    }


if __name__ == "__main__":
    import uvicorn

    print("Starting Swarm It Demo API...")
    print("Docs at: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
