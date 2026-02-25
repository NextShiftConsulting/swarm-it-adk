"""
Adapters - Implementations of ports via yrsn.

TRAINED RSN PIPELINE:
    OpenAI text-embedding-3-small (dimensions=384)
        ↓
    text_mlp_384to64_trained.pt (384 → 192 → 128 → 64)
        ↓
    trained_rotor_text64.pt (64 → R, S, N)

NOTE: yrsn uses "natural" dimension reduction via trained checkpoints.
      Do NOT use untrained projections - they produce random RSN!
      See /Users/rudy/GitHub/yrsn/checkpoints/README.md

IMPORTANT: OpenAI dimensions=384 to match trained projection input.
           1536 or 768 dim would require different trained checkpoints.
"""

import os
from typing import List, Dict, Any
from .ports import EmbeddingPort, RSNPort

# Checkpoints
YRSN_CHECKPOINTS = "/Users/rudy/GitHub/yrsn/checkpoints"
TEXT_PROJECTION = f"{YRSN_CHECKPOINTS}/text_mlp_384to64_trained.pt"
ROTOR_64 = f"{YRSN_CHECKPOINTS}/trained_rotor_text64.pt"


class OpenAIEmbeddingAdapter(EmbeddingPort):
    """Adapter: OpenAI embeddings at 384-dim (matches yrsn text projection)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 384,  # Match text_mlp projection input
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model
        self._dimensions = dimensions
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def embed(self, text: str) -> List[float]:
        client = self._get_client()
        response = client.embeddings.create(
            input=text,
            model=self._model,
            dimensions=self._dimensions,
        )
        return response.data[0].embedding


class TextMLPProjection:
    """Trained text projection: 384 → 192 → 128 → 64 with skip connection."""

    def __init__(self, checkpoint_path: str, device: str = 'cpu'):
        import torch
        import torch.nn as nn

        self._torch = torch
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)

        # Architecture: 384 → 192 → 128 → 64 (from checkpoint shapes)
        self.alpha = nn.Parameter(torch.tensor(ckpt['model_state_dict']['alpha']))
        self.fc1 = nn.Linear(384, 192)
        self.ln1 = nn.LayerNorm(192)
        self.fc2 = nn.Linear(192, 128)
        self.ln2 = nn.LayerNorm(128)
        self.fc3 = nn.Linear(128, 64)
        self.skip = nn.Linear(384, 64)

        # Load trained weights
        self.fc1.weight.data = ckpt['model_state_dict']['fc1.weight']
        self.fc1.bias.data = ckpt['model_state_dict']['fc1.bias']
        self.ln1.weight.data = ckpt['model_state_dict']['ln1.weight']
        self.ln1.bias.data = ckpt['model_state_dict']['ln1.bias']
        self.fc2.weight.data = ckpt['model_state_dict']['fc2.weight']
        self.fc2.bias.data = ckpt['model_state_dict']['fc2.bias']
        self.ln2.weight.data = ckpt['model_state_dict']['ln2.weight']
        self.ln2.bias.data = ckpt['model_state_dict']['ln2.bias']
        self.fc3.weight.data = ckpt['model_state_dict']['fc3.weight']
        self.fc3.bias.data = ckpt['model_state_dict']['fc3.bias']
        self.skip.weight.data = ckpt['model_state_dict']['skip.weight']
        self.skip.bias.data = ckpt['model_state_dict']['skip.bias']

    def __call__(self, x):
        import torch.nn.functional as F
        h = F.gelu(self.ln1(self.fc1(x)))
        h = F.gelu(self.ln2(self.fc2(h)))
        h = self.fc3(h)
        skip = self.skip(x)
        return self.alpha * h + (1 - self.alpha) * skip


class YRSNRotorAdapter(RSNPort):
    """
    Adapter: RSN via trained yrsn pipeline.

    Pipeline: 384-dim → text_mlp (384→64) → rotor (64→RSN)
    Both projection and rotor are TRAINED checkpoints.
    """

    def __init__(self):
        from yrsn.core.decomposition import load_rotor_from_checkpoint
        import torch

        self._torch = torch

        # Load trained projection (384 → 64)
        self._projection = TextMLPProjection(TEXT_PROJECTION)

        # Load trained rotor (64 → RSN)
        self._rotor = load_rotor_from_checkpoint(ROTOR_64, embed_dim=64)
        self._rotor.eval()

    def compute(self, embeddings: List[float]) -> Dict[str, float]:
        with self._torch.no_grad():
            x = self._torch.tensor([embeddings], dtype=self._torch.float32)
            x_64 = self._projection(x)  # 384 → 64
            out = self._rotor(x_64)     # 64 → RSN
        return {
            "R": float(out["R"][0]),
            "S": float(out["S"][0]),
            "N": float(out["N"][0]),
        }
