"""
ADK test configuration.

Marks API-dependent tests as xfail when credentials are missing.
Tests still run (and show as xfail), but don't break the suite.
If a key appears and the test starts passing, pytest reports XPASS
so you notice the change.
"""

import os

import pytest


def pytest_collection_modifyitems(config, items):
    """Mark tests that need external API keys as xfail when keys are missing."""
    missing_openai = not os.environ.get("OPENAI_API_KEY")

    for item in items:
        # Auto-detect: if the test file imports OpenAI or the error is OpenAIError
        markers = {m.name for m in item.iter_markers()}

        if "requires_api_key" in markers and missing_openai:
            item.add_marker(pytest.mark.xfail(
                reason="OPENAI_API_KEY not set",
                raises=Exception,
                strict=False,
            ))
