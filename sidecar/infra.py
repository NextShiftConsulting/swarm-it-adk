"""
Infrastructure - Loads yrsn resources.

Simple. Works. Don't overthink it.
"""

import os
import sys

# Paths
YRSN_SRC = os.environ.get("YRSN_SRC", "/Users/rudy/GitHub/yrsn/src")
YRSN_KEYS = os.environ.get("YRSN_KEYS", "/Users/rudy/GitHub/yrsn/keys")

if YRSN_SRC not in sys.path:
    sys.path.insert(0, YRSN_SRC)
if YRSN_KEYS not in sys.path:
    sys.path.insert(0, YRSN_KEYS)


def _load_key(name: str) -> str | None:
    """Load API key from env or yrsn/keys."""
    if os.environ.get(name):
        return os.environ[name]
    key_file = os.path.join(YRSN_KEYS, f"{name}.txt")
    if os.path.exists(key_file):
        with open(key_file) as f:
            content = f.read().strip()
            if "=" in content:
                content = content.split("=", 1)[1].strip('"')
            os.environ[name] = content
            return content
    return None


class config:
    """Simple config."""
    EMBED_MODEL = "text-embedding-3-small"
    EMBED_DIM = 1536
    has_openai = bool(_load_key("OPENAI_API_KEY"))


def get_embeddings(text: str) -> list[float]:
    """Get embeddings via OpenAI."""
    _load_key("OPENAI_API_KEY")
    from openai import OpenAI
    client = OpenAI()
    resp = client.embeddings.create(input=text, model=config.EMBED_MODEL)
    return resp.data[0].embedding


def get_rotor(embed_dim: int = 1536):
    """Get HybridSimplexRotor from yrsn."""
    from yrsn.core.decomposition import HybridSimplexRotor
    rotor = HybridSimplexRotor(
        embed_dim=embed_dim,
        hidden_dim=512,
        subspace_dim=64,
    )
    rotor.eval()
    return rotor
