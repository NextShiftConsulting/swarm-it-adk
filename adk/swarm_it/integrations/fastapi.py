"""
FastAPI Integration for Swarm It

Provides middleware and decorators for API-level certification gating.

Usage:
    from fastapi import FastAPI
    from swarm_it import SwarmIt
    from swarm_it.integrations import SwarmItMiddleware

    app = FastAPI()
    swarm = SwarmIt(api_key="...")

    # Add middleware for automatic certification
    app.add_middleware(SwarmItMiddleware, client=swarm)

    # Or use decorator for specific endpoints
    from swarm_it.integrations import require_certificate

    @app.post("/chat")
    @require_certificate(swarm)
    async def chat(request: ChatRequest):
        ...
"""

import json
from typing import Callable, Optional, List, TYPE_CHECKING
from functools import wraps

if TYPE_CHECKING:
    from ..client import SwarmIt


class SwarmItMiddleware:
    """
    FastAPI/Starlette middleware for request certification.

    Certifies incoming requests and blocks those that fail gating.

    Usage:
        from fastapi import FastAPI
        from swarm_it.integrations import SwarmItMiddleware

        app = FastAPI()
        swarm = SwarmIt(api_key="...")

        app.add_middleware(
            SwarmItMiddleware,
            client=swarm,
            paths=["/api/chat", "/api/complete"],  # Only these paths
            extract_context=lambda body: body.get("prompt"),
        )
    """

    def __init__(
        self,
        app,
        client: "SwarmIt",
        paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        extract_context: Optional[Callable[[dict], str]] = None,
        policy: Optional[str] = None,
    ):
        """
        Args:
            app: ASGI app
            client: SwarmIt client
            paths: Only certify these paths (if None, certify all)
            exclude_paths: Skip these paths
            extract_context: Function to extract context from request body
            policy: Certification policy
        """
        self.app = app
        self.client = client
        self.paths = paths
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs"]
        self.extract_context = extract_context or self._default_extract
        self.policy = policy

    async def __call__(self, scope, receive, send):
        """ASGI middleware entry point."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Check if we should certify this path
        if not self._should_certify(path):
            await self.app(scope, receive, send)
            return

        # Only certify POST/PUT/PATCH with body
        method = scope.get("method", "GET")
        if method not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return

        # Read and certify body
        body_parts = []

        async def receive_wrapper():
            message = await receive()
            if message["type"] == "http.request":
                body_parts.append(message.get("body", b""))
            return message

        # Collect body
        while True:
            message = await receive_wrapper()
            if message["type"] == "http.request":
                if not message.get("more_body", False):
                    break

        body = b"".join(body_parts)

        # Try to certify
        try:
            body_json = json.loads(body) if body else {}
            context = self.extract_context(body_json)

            if context:
                cert = self.client.certify(context, policy=self.policy)

                if not cert.allowed:
                    # Return 403 with certificate info
                    await self._send_blocked_response(send, cert)
                    return

        except json.JSONDecodeError:
            pass  # Not JSON, skip certification
        except Exception:
            pass  # Certification failed, allow through (fail-open)

        # Reconstruct receive for downstream
        body_sent = False

        async def receive_reconstructed():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, receive_reconstructed, send)

    def _should_certify(self, path: str) -> bool:
        """Check if path should be certified."""
        # Check exclusions
        for exclude in self.exclude_paths:
            if path.startswith(exclude):
                return False

        # Check inclusions
        if self.paths is not None:
            for include in self.paths:
                if path.startswith(include):
                    return True
            return False

        return True

    def _default_extract(self, body: dict) -> Optional[str]:
        """Default context extraction from request body."""
        for key in ("prompt", "message", "content", "query", "input", "text"):
            if key in body and isinstance(body[key], str):
                return body[key]

        # Try nested messages (OpenAI format)
        if "messages" in body and isinstance(body["messages"], list):
            for msg in reversed(body["messages"]):
                if isinstance(msg, dict) and "content" in msg:
                    return str(msg["content"])

        return None

    async def _send_blocked_response(self, send, cert):
        """Send 403 response for blocked requests."""
        response_body = json.dumps({
            "error": "Request blocked by execution gate",
            "reason": cert.reason,
            "decision": cert.decision.value,
            "certificate": {
                "id": cert.id,
                "R": cert.R,
                "S": cert.S,
                "N": cert.N,
                "kappa": cert.kappa,
            },
        }).encode()

        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [
                [b"content-type", b"application/json"],
                [b"x-swarm-it-blocked", b"true"],
                [b"x-swarm-it-certificate", cert.id.encode()],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": response_body,
        })


def require_certificate(
    client: "SwarmIt",
    policy: Optional[str] = None,
    context_param: str = "prompt",
):
    """
    FastAPI route decorator requiring certification.

    Usage:
        @app.post("/chat")
        @require_certificate(swarm, context_param="message")
        async def chat(message: str):
            return {"response": await call_llm(message)}

    Args:
        client: SwarmIt client
        policy: Certification policy
        context_param: Name of the parameter containing the context
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from fastapi import HTTPException

            # Extract context from kwargs
            context = kwargs.get(context_param)

            if context is None:
                # Try to find it in a request body model
                for value in kwargs.values():
                    if hasattr(value, context_param):
                        context = getattr(value, context_param)
                        break
                    if hasattr(value, "dict"):
                        d = value.dict()
                        if context_param in d:
                            context = d[context_param]
                            break

            if context:
                cert = client.certify(str(context), policy=policy)

                if not cert.allowed:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "Request blocked by execution gate",
                            "reason": cert.reason,
                            "decision": cert.decision.value,
                            "certificate_id": cert.id,
                        },
                    )

                # Inject certificate if function accepts it
                import inspect
                sig = inspect.signature(func)
                if "certificate" in sig.parameters:
                    kwargs["certificate"] = cert

            return await func(*args, **kwargs)

        return wrapper

    return decorator
