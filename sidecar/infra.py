"""
Infrastructure - Loads yrsn resources.

Simple. Works. Don't overthink it.

In Lambda: yrsn is bundled in the package root.
Locally: loads from YRSN_SRC environment variable.
"""

import os
import sys

# Lambda: yrsn is bundled at package root (same dir as this file)
# Local: use YRSN_SRC env var
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
YRSN_SRC = os.environ.get("YRSN_SRC", _THIS_DIR)
YRSN_KEYS = os.environ.get("YRSN_KEYS", os.path.join(_THIS_DIR, "keys"))

if YRSN_SRC not in sys.path:
    sys.path.insert(0, YRSN_SRC)
if os.path.exists(YRSN_KEYS) and YRSN_KEYS not in sys.path:
    sys.path.insert(0, YRSN_KEYS)


def _load_key(name: str) -> str | None:
    """Load API key from env or yrsn/keys.

    In Lambda: keys come from environment variables (set via Lambda config).
    Locally: can also read from YRSN_KEYS directory.
    """
    if os.environ.get(name):
        return os.environ[name]
    # Try loading from keys directory (local dev only)
    key_file = os.path.join(YRSN_KEYS, f"{name}.txt")
    if os.path.exists(key_file):
        try:
            with open(key_file) as f:
                content = f.read().strip()
                if "=" in content:
                    content = content.split("=", 1)[1].strip('"')
                os.environ[name] = content
                return content
        except Exception:
            pass
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
    """Get HybridSimplexRotor from yrsn (returns None if unavailable)."""
    try:
        from yrsn.core.decomposition import HybridSimplexRotor
        rotor = HybridSimplexRotor(
            embed_dim=embed_dim,
            hidden_dim=512,
            subspace_dim=64,
        )
        rotor.eval()
        return rotor
    except ImportError as e:
        import logging
        logging.warning(f"yrsn import failed: {e}")
        return None
    except Exception as e:
        import logging
        logging.warning(f"yrsn rotor creation failed: {e}")
        return None
