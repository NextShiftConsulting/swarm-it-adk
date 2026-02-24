"""
Example AI App with Swarm-It Integration

A simple FastAPI app that demonstrates:
1. Pre-execution certification
2. LLM call
3. Post-execution validation
"""

import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="AI App with Swarm-It")

SWARM_IT_URL = os.getenv("SWARM_IT_URL", "http://localhost:8080")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    response: str
    certificate_id: str
    decision: str
    kappa_gate: float


@app.get("/")
async def root():
    return {"service": "ai-app", "swarm_it_url": SWARM_IT_URL}


@app.get("/health")
async def health():
    # Check swarm-it health
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{SWARM_IT_URL}/health")
            swarm_healthy = r.status_code == 200
        except Exception:
            swarm_healthy = False

    return {
        "status": "healthy" if swarm_healthy else "degraded",
        "swarm_it": "connected" if swarm_healthy else "disconnected",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint with RSCT certification.
    """
    async with httpx.AsyncClient() as client:
        # Step 1: Certify
        cert_response = await client.post(
            f"{SWARM_IT_URL}/api/v1/certify",
            json={"prompt": request.prompt},
        )

        if cert_response.status_code != 200:
            raise HTTPException(500, "Certification failed")

        cert = cert_response.json()

        if not cert["allowed"]:
            raise HTTPException(403, f"Blocked: {cert['reason']}")

        # Step 2: Call LLM (mock for demo, replace with real OpenAI call)
        if OPENAI_API_KEY:
            # Real OpenAI call
            llm_response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": request.prompt}],
                    "max_tokens": 200,
                },
            )
            if llm_response.status_code == 200:
                content = llm_response.json()["choices"][0]["message"]["content"]
            else:
                content = f"LLM error: {llm_response.status_code}"
        else:
            # Mock response
            content = f"[Mock response to: {request.prompt[:50]}...]"

        # Step 3: Validate
        await client.post(
            f"{SWARM_IT_URL}/api/v1/validate",
            json={
                "certificate_id": cert["id"],
                "validation_type": "TYPE_I",
                "score": 0.9,
                "failed": False,
            },
        )

        return ChatResponse(
            response=content,
            certificate_id=cert["id"],
            decision=cert["decision"],
            kappa_gate=cert["kappa_gate"],
        )
