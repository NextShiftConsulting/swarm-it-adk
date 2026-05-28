"""
Tests for swarm_it.decorators -- fail-closed gating (R-18.2).
"""

import pytest
from unittest.mock import MagicMock
from enum import Enum

from swarm_it.decorators import (
    _extract_context,
    _create_gate_decorator,
    GateBlockedError,
)
from swarm_it.exceptions import MissingContextError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Decision(Enum):
    ALLOW = "allow"
    BLOCK = "block"


def _make_cert(allowed: bool = True, decision: str = "allow"):
    cert = MagicMock()
    cert.allowed = allowed
    cert.decision = _Decision(decision)
    cert.reason = "test"
    cert.R = 0.5
    cert.S = 0.5
    cert.N = 0.3
    cert.kappa = 0.8
    cert.id = "cert-test"
    cert.margin = 0.1
    return cert


def _make_client(allowed: bool = True):
    client = MagicMock()
    client.certify.return_value = _make_cert(allowed=allowed,
                                              decision="allow" if allowed else "block")
    return client


# ---------------------------------------------------------------------------
# _extract_context
# ---------------------------------------------------------------------------

class TestExtractContext:
    """Context extraction from function arguments."""

    def test_kwarg_prompt(self):
        def fn(prompt): ...
        assert _extract_context(fn, (), {"prompt": "hello"}) == "hello"

    def test_positional_prompt(self):
        def fn(prompt): ...
        assert _extract_context(fn, ("hello",), {}) == "hello"

    def test_first_string_fallback(self):
        def fn(x): ...
        assert _extract_context(fn, ("hello",), {}) == "hello"

    def test_dict_content_fallback(self):
        def fn(x): ...
        assert _extract_context(fn, ({"content": "hello"},), {}) == "hello"

    def test_no_context_returns_none(self):
        def fn(x): ...
        assert _extract_context(fn, (42,), {}) is None

    def test_no_args_returns_none(self):
        def fn(): ...
        assert _extract_context(fn, (), {}) is None


# ---------------------------------------------------------------------------
# Fail-closed: MissingContextError when context is None
# ---------------------------------------------------------------------------

class TestFailClosed:
    """R-18.2: decorator must raise when no context can be extracted."""

    def test_gate_decorator_raises_on_no_context(self):
        """_create_gate_decorator must not execute the function without context."""
        client = _make_client()

        decorator = _create_gate_decorator(client)

        @decorator
        def my_func(x):
            return x  # pragma: no cover -- should never run

        with pytest.raises(MissingContextError) as exc_info:
            my_func(42)

        assert "my_func" in str(exc_info.value)
        client.certify.assert_not_called()

    def test_certified_decorator_raises_on_no_context(self):
        """certified() must not execute the function without context."""
        from swarm_it.decorators import certified

        client = _make_client()

        @certified(client=client)
        def my_func(x):
            return x  # pragma: no cover

        with pytest.raises(MissingContextError) as exc_info:
            my_func(42)

        assert "my_func" in str(exc_info.value)
        client.certify.assert_not_called()

    def test_gate_decorator_raises_on_no_args(self):
        """No arguments at all must also fail closed."""
        client = _make_client()
        decorator = _create_gate_decorator(client)

        @decorator
        def my_func():
            return "should not run"  # pragma: no cover

        with pytest.raises(MissingContextError):
            my_func()


# ---------------------------------------------------------------------------
# Normal operation: context present
# ---------------------------------------------------------------------------

class TestNormalOperation:
    """When context is present, gating proceeds normally."""

    def test_allowed_execution(self):
        client = _make_client(allowed=True)
        decorator = _create_gate_decorator(client)

        @decorator
        def my_func(prompt):
            return f"result: {prompt}"

        result = my_func("test input")
        assert result == "result: test input"
        client.certify.assert_called_once_with("test input", policy=None)

    def test_blocked_execution_raises(self):
        client = _make_client(allowed=False)
        decorator = _create_gate_decorator(client)

        @decorator
        def my_func(prompt):
            return "should not run"  # pragma: no cover

        with pytest.raises(GateBlockedError):
            my_func("test input")

    def test_blocked_execution_custom_handler(self):
        client = _make_client(allowed=False)
        handler = MagicMock(return_value="blocked")
        decorator = _create_gate_decorator(client, on_block=handler)

        @decorator
        def my_func(prompt):
            return "should not run"  # pragma: no cover

        result = my_func("test input")
        assert result == "blocked"
        handler.assert_called_once()


# ---------------------------------------------------------------------------
# MissingContextError attributes
# ---------------------------------------------------------------------------

class TestMissingContextError:
    """MissingContextError carries the function name."""

    def test_func_name_attribute(self):
        err = MissingContextError("some_function")
        assert err.func_name == "some_function"
        assert "some_function" in str(err)
        assert "Certification context required" in str(err)

    def test_inherits_swarm_it_error(self):
        from swarm_it.exceptions import SwarmItError
        assert issubclass(MissingContextError, SwarmItError)
