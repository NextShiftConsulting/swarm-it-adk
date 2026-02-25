"""
Bootstrap - Composition root.

This is the ONLY place that knows about concrete adapters.
Wires everything together at startup.
"""

import sys
import os

# Configure yrsn path (deployment config, not hardcoded in core)
YRSN_SRC = os.environ.get("YRSN_SRC", "/Users/rudy/GitHub/yrsn/src")
YRSN_KEYS = os.environ.get("YRSN_KEYS", "/Users/rudy/GitHub/yrsn/keys")

if YRSN_SRC not in sys.path:
    sys.path.insert(0, YRSN_SRC)
if YRSN_KEYS not in sys.path:
    sys.path.insert(0, YRSN_KEYS)


def _load_api_key(name: str) -> str | None:
    """Load API key from yrsn/keys if not in env."""
    if os.environ.get(name):
        return os.environ[name]
    key_file = os.path.join(YRSN_KEYS, f"{name}.txt")
    if os.path.exists(key_file):
        with open(key_file) as f:
            content = f.read().strip()
            # Handle KEY="value" or KEY=value format
            if "=" in content:
                content = content.split("=", 1)[1].strip('"')
            os.environ[name] = content
            return content
    return None


def create_engine():
    """Create engine with trained yrsn adapters."""
    from .adapters import OpenAIEmbeddingAdapter, YRSNRotorAdapter
    from .engine.core import RSCTEngine

    # Load OpenAI key from yrsn/keys
    _load_api_key("OPENAI_API_KEY")

    # Pipeline: OpenAI (768-dim) → projection (768→64) → rotor (64→RSN)
    return RSCTEngine(
        embedding_adapter=OpenAIEmbeddingAdapter(),
        rsn_adapter=YRSNRotorAdapter(),
    )


def create_mock_engine():
    """Create engine with mock adapters (for testing)."""
    from .ports import EmbeddingPort, RSNPort
    from .engine.core import RSCTEngine

    class MockEmbedding(EmbeddingPort):
        def embed(self, text):
            return [0.0] * 1536

    class MockRSN(RSNPort):
        def compute(self, embeddings):
            return {"R": 0.4, "S": 0.3, "N": 0.3}

    return RSCTEngine(
        embedding_adapter=MockEmbedding(),
        rsn_adapter=MockRSN(),
    )
