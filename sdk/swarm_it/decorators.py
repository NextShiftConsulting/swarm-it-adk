"""
Swarm It Decorators

Simple decorators for gating LLM calls with RSCT certification.
"""

import functools
import inspect
from typing import Callable, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import SwarmIt, Certificate


class GateBlockedError(Exception):
    """Raised when execution is blocked by gate."""

    def __init__(self, certificate: "Certificate"):
        self.certificate = certificate
        super().__init__(
            f"Execution blocked: {certificate.reason} "
            f"(decision={certificate.decision.value})"
        )


def _create_gate_decorator(
    client: "SwarmIt",
    policy: Optional[str] = None,
    on_block: Optional[Callable[["Certificate"], Any]] = None,
):
    """
    Create a gate decorator bound to a client.

    Args:
        client: SwarmIt client instance
        policy: Certification policy
        on_block: Handler for blocked executions (returns value or raises)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract context from first string argument
            context = _extract_context(func, args, kwargs)

            if context is None:
                # No context found, execute without gating
                return func(*args, **kwargs)

            # Certify
            cert = client.certify(context, policy=policy)

            if not cert.allowed:
                if on_block is not None:
                    return on_block(cert)
                raise GateBlockedError(cert)

            # Execute
            return func(*args, **kwargs)

        # Attach certificate getter for inspection
        wrapper._swarm_it_client = client
        return wrapper

    return decorator


def _extract_context(func: Callable, args: tuple, kwargs: dict) -> Optional[str]:
    """
    Extract the context string from function arguments.

    Looks for:
    1. Argument named 'prompt', 'context', 'query', or 'message'
    2. First string argument
    3. 'content' field in first dict argument
    """
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    # Check kwargs for known names
    for name in ("prompt", "context", "query", "message", "input"):
        if name in kwargs and isinstance(kwargs[name], str):
            return kwargs[name]

    # Check positional args by parameter name
    for i, (param_name, arg) in enumerate(zip(params, args)):
        if param_name in ("prompt", "context", "query", "message", "input"):
            if isinstance(arg, str):
                return arg

    # Fallback: first string argument
    for arg in args:
        if isinstance(arg, str):
            return arg

    # Fallback: first dict with 'content' key
    for arg in args:
        if isinstance(arg, dict) and "content" in arg:
            return str(arg["content"])

    # Check kwargs values
    for value in kwargs.values():
        if isinstance(value, str):
            return value

    return None


def gate(
    func: Optional[Callable] = None,
    *,
    client: Optional["SwarmIt"] = None,
    policy: Optional[str] = None,
    on_block: Optional[Callable[["Certificate"], Any]] = None,
):
    """
    Standalone gate decorator (requires client or SWARM_IT_API_KEY env var).

    Usage:
        from swarm_it import gate

        @gate
        def ask_llm(prompt):
            return openai.chat.completions.create(...)

        # With explicit client
        @gate(client=my_swarm_client)
        def ask_llm(prompt):
            ...
    """
    from .client import SwarmIt

    def decorator(f: Callable) -> Callable:
        # Use provided client or create one from env
        c = client or SwarmIt()
        return _create_gate_decorator(c, policy=policy, on_block=on_block)(f)

    if func is not None:
        return decorator(func)
    return decorator


def certified(
    func: Optional[Callable] = None,
    *,
    client: Optional["SwarmIt"] = None,
    policy: Optional[str] = None,
    inject_cert: bool = False,
):
    """
    Gate decorator that optionally injects the certificate.

    Usage:
        @certified(inject_cert=True)
        def ask_llm(prompt, cert=None):
            print(f"Executing with margin: {cert.margin}")
            return openai.chat.completions.create(...)
    """
    from .client import SwarmIt

    def decorator(f: Callable) -> Callable:
        c = client or SwarmIt()

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            context = _extract_context(f, args, kwargs)

            if context is None:
                return f(*args, **kwargs)

            cert = c.certify(context, policy=policy)

            if not cert.allowed:
                raise GateBlockedError(cert)

            if inject_cert:
                kwargs["cert"] = cert

            return f(*args, **kwargs)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
