"""
SWARM-06: Jailbreak Detector Adapter

Follows the hex arch pattern from yrsn/core/routing/defenses/sybil.py.

This adapter implements jailbreak detection using:
1. Existing SentenceTransformerExtractor (from YRSN)
2. Trained classifier checkpoint
3. Composition with DefenseStack

Usage:
    from adapters.jailbreak_detector import JailbreakDetector, JailbreakCheckResult

    detector = JailbreakDetector.from_checkpoint("checkpoints/jailbreak_detector.pt")
    result = detector.check("Ignore previous instructions...")

    if result.is_jailbreak:
        # Block or flag
        pass

Integration with DefenseStack:
    # Add as additional defense layer
    defense_result = defense_stack.check_all(...)
    jailbreak_result = jailbreak_detector.check(prompt)

    if jailbreak_result.is_jailbreak:
        defense_result.allowed = False
        defense_result.details["jailbreak"] = jailbreak_result.to_dict()

Reference: DOE_SWARM-06_Jailbreak_Detection_Benchmark.md
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import logging

import torch
import torch.nn as nn

# YRSN paths for adapter imports
YRSN_SRC = Path("/Users/rudy/GitHub/yrsn/src")
YRSN_CHECKPOINTS = Path("/Users/rudy/GitHub/yrsn/checkpoints")
sys.path.insert(0, str(YRSN_SRC / "yrsn/adapters/models"))
sys.path.insert(0, str(YRSN_SRC / "yrsn/core/decomposition"))

logger = logging.getLogger(__name__)

# Import centralized rotor config (direct path to avoid import chain issues)
try:
    import sys as _sys
    _config_path = str(YRSN_SRC / "yrsn/config")
    if _config_path not in _sys.path:
        _sys.path.insert(0, _config_path)
    from rotor_config import ROTOR_DIMENSION, get_rotor_dimension
except ImportError:
    import os
    ROTOR_DIMENSION = int(os.getenv("ROTOR_DIMENSION", "128"))
    def get_rotor_dimension(): return ROTOR_DIMENSION


# =============================================================================
# LOCAL MODEL DEFINITIONS (avoid triggering full yrsn import)
# =============================================================================

class TextMLP384to64(nn.Module):
    """Text projection 384d → 64d (for memristor systems)."""
    def __init__(self):
        super().__init__()
        self.alpha = nn.Parameter(torch.tensor(0.5))
        self.fc1 = nn.Linear(384, 192)
        self.ln1 = nn.LayerNorm(192)
        self.fc2 = nn.Linear(192, 128)
        self.ln2 = nn.LayerNorm(128)
        self.fc3 = nn.Linear(128, 64)
        self.skip = nn.Linear(384, 64)

    def forward(self, x):
        h = torch.relu(self.ln1(self.fc1(x)))
        h = torch.relu(self.ln2(self.fc2(h)))
        h = self.fc3(h)
        s = self.skip(x)
        return self.alpha * h + (1 - self.alpha) * s


class TextMLP384to128(nn.Module):
    """Text projection 384d → 128d (default, better semantic preservation)."""
    def __init__(self):
        super().__init__()
        self.alpha = nn.Parameter(torch.tensor(0.5))
        self.fc1 = nn.Linear(384, 256)
        self.ln1 = nn.LayerNorm(256)
        self.fc2 = nn.Linear(256, 192)
        self.ln2 = nn.LayerNorm(192)
        self.fc3 = nn.Linear(192, 128)
        self.skip = nn.Linear(384, 128)

    def forward(self, x):
        h = torch.relu(self.ln1(self.fc1(x)))
        h = torch.relu(self.ln2(self.fc2(h)))
        h = self.fc3(h)
        s = self.skip(x)
        return self.alpha * h + (1 - self.alpha) * s


def get_projection_model(target_dim: int = None) -> nn.Module:
    """Get projection model for target dimension."""
    dim = target_dim or get_rotor_dimension()
    if dim == 128:
        return TextMLP384to128()
    else:
        return TextMLP384to64()


# =============================================================================
# DATA CLASSES (Following yrsn pattern)
# =============================================================================

@dataclass(frozen=True)
class JailbreakCheckResult:
    """
    Result of jailbreak detection check.

    Follows pattern from yrsn/core/routing/defenses/sybil.py:SybilCheckResult

    Attributes:
        is_jailbreak: Whether prompt is detected as jailbreak
        confidence: Classifier confidence [0, 1]
        state: Classification state (BENIGN, JAILBREAK, UNCERTAIN, UNSAFE)
        gate_passed: Whether RSCT quality gates passed
        rsn: RSN values if computed
        rationale: Human-readable explanation
    """
    is_jailbreak: bool
    confidence: float
    state: str  # BENIGN, JAILBREAK, UNCERTAIN, UNSAFE
    gate_passed: bool
    rsn: Optional[Tuple[float, float, float]] = None  # (R, S, N)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Export for logging/serialization."""
        return {
            "is_jailbreak": self.is_jailbreak,
            "confidence": self.confidence,
            "state": self.state,
            "gate_passed": self.gate_passed,
            "rsn": list(self.rsn) if self.rsn else None,
            "rationale": self.rationale,
        }


# =============================================================================
# CLASSIFIER ARCHITECTURE (Must match training)
# =============================================================================

class JailbreakClassifierModel(nn.Module):
    """
    MLP classifier on embeddings.

    Must match architecture from train_hybrid_rsct_classifier.py
    """
    def __init__(self, input_dim: int = 384, hidden_dims: List[int] = [128, 64, 32]):
        super().__init__()

        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.3),
            ])
            prev_dim = hidden_dim

        layers.append(nn.Linear(prev_dim, 1))
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x).squeeze(-1)


# =============================================================================
# JAILBREAK DETECTOR (Following hex arch pattern)
# =============================================================================

class JailbreakDetector:
    """
    Detects jailbreak attempts via embedding classification.

    Uses:
    - SentenceTransformerExtractor from YRSN (IFeatureExtractor port)
    - Trained classifier checkpoint
    - Optional RSCT gate pre-filtering

    Follows hex arch pattern from yrsn/core/routing/defenses/sybil.py
    """

    def __init__(
        self,
        classifier: nn.Module,
        extractor,  # IFeatureExtractor from YRSN
        threshold: float = 0.5,
        enable_rsct_gates: bool = True,
        n_threshold: float = 0.6,
        coherence_threshold: float = 0.3,
        projection: Optional[nn.Module] = None,
        rotor: Optional[nn.Module] = None,
    ):
        """
        Initialize jailbreak detector.

        Args:
            classifier: Trained JailbreakClassifierModel
            extractor: Text embedding extractor (SentenceTransformerExtractor)
            threshold: Classification threshold
            enable_rsct_gates: Whether to use RSCT quality gates
            n_threshold: N-gate threshold
            coherence_threshold: Coherence gate threshold
            projection: TextMLP for RSN computation
            rotor: HybridSimplexRotor for RSN computation
        """
        self.classifier = classifier
        self.extractor = extractor
        self.threshold = threshold
        self.enable_rsct_gates = enable_rsct_gates
        self.n_threshold = n_threshold
        self.coherence_threshold = coherence_threshold
        self.projection = projection
        self.rotor = rotor

        # Set to eval mode
        self.classifier.eval()
        if self.projection:
            self.projection.eval()
        if self.rotor:
            self.rotor.eval()

        logger.debug("JailbreakDetector initialized")

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: Path,
        extractor_name: str = "all-MiniLM-L6-v2",
        yrsn_checkpoints: Path = Path("/Users/rudy/GitHub/yrsn/checkpoints"),
    ) -> 'JailbreakDetector':
        """
        Load detector from checkpoint.

        Args:
            checkpoint_path: Path to classifier checkpoint
            extractor_name: SentenceTransformer model name
            yrsn_checkpoints: Path to YRSN checkpoints for projection/rotor
        """
        # Load text extractor using YRSN adapter
        from text_adapter import SentenceTransformerExtractor
        extractor = SentenceTransformerExtractor(model_name=extractor_name)

        # Load checkpoint
        ckpt = torch.load(checkpoint_path, map_location='cpu', weights_only=False)

        # Get config
        config = ckpt.get("config", {})
        embed_dim = config.get("embed_dim", 384)

        # Create and load classifier
        classifier = JailbreakClassifierModel(input_dim=embed_dim)
        classifier.load_state_dict(ckpt["model_state_dict"])

        # Load RSCT components if needed (dimension-aware via rotor_config)
        projection = None
        rotor = None

        # Get configured dimension
        rotor_dim = get_rotor_dimension()

        # Dimension-aware checkpoint paths
        proj_path = yrsn_checkpoints / f"text_mlp_384to{rotor_dim}_trained.pt"
        rotor_path = yrsn_checkpoints / f"trained_rotor_universal{rotor_dim}.pt"

        # Fallback to old naming convention if new doesn't exist
        # Both projection and rotor must match dimensions
        if not proj_path.exists() or not rotor_path.exists():
            # Fall back to 64d for both (guaranteed to exist from original training)
            proj_path = yrsn_checkpoints / "text_mlp_384to64_trained.pt"
            rotor_path = yrsn_checkpoints / "trained_rotor_text64.pt"
            rotor_dim = 64
            logger.info("128d checkpoints not found, falling back to 64d")

        if proj_path.exists() and rotor_path.exists():
            # Load projection (dimension-aware)
            projection = get_projection_model(rotor_dim)
            proj_ckpt = torch.load(proj_path, map_location='cpu', weights_only=False)
            projection.load_state_dict(proj_ckpt.get('model_state_dict', proj_ckpt))
            logger.info(f"Loaded {rotor_dim}d projection from {proj_path}")

            # Load rotor (direct import from decomposition path)
            from hybrid_rotor import HybridSimplexRotor
            rotor = HybridSimplexRotor(embed_dim=rotor_dim, subspace_dim=rotor_dim, hidden_dim=256)
            rotor_ckpt = torch.load(rotor_path, map_location='cpu', weights_only=False)
            rotor.load_state_dict(rotor_ckpt.get('model_state_dict', rotor_ckpt))
            logger.info(f"Loaded {rotor_dim}d rotor from {rotor_path}")

        return cls(
            classifier=classifier,
            extractor=extractor,
            threshold=config.get("threshold", 0.5),
            enable_rsct_gates=True,
            n_threshold=config.get("n_threshold", 0.6),
            coherence_threshold=config.get("coherence_threshold", 0.3),
            projection=projection,
            rotor=rotor,
        )

    def _compute_rsn(self, embedding: np.ndarray) -> Tuple[float, float, float]:
        """Compute RSN using YRSN rotor."""
        if self.projection is None or self.rotor is None:
            return (0.33, 0.33, 0.34)  # Default uniform

        with torch.no_grad():
            emb = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0)
            emb_64 = self.projection(emb)
            rsn = self.rotor(emb_64)

            return (
                float(rsn['R'].item()),
                float(rsn['S'].item()),
                float(rsn['N'].item()),
            )

    def _compute_coherence(self, R: float, S: float, N: float) -> float:
        """Compute coherence from RSN."""
        probs = np.array([R, S, N])
        probs = np.clip(probs, 1e-10, 1.0)
        entropy = -np.sum(probs * np.log(probs))
        max_entropy = np.log(3)
        return 1 - entropy / max_entropy

    def _apply_gates(self, R: float, S: float, N: float) -> Tuple[bool, str]:
        """Apply RSCT quality gates."""
        coherence = self._compute_coherence(R, S, N)

        # N-gate: high noise = UNSAFE
        if N >= self.n_threshold:
            return False, f"N-gate failed (N={N:.2f} >= {self.n_threshold})"

        # Coherence gate
        if coherence < self.coherence_threshold:
            return False, f"Coherence gate failed ({coherence:.2f} < {self.coherence_threshold})"

        return True, "All gates passed"

    def check(self, text: str) -> JailbreakCheckResult:
        """
        Check if text is a jailbreak attempt.

        Args:
            text: Input text to check

        Returns:
            JailbreakCheckResult with detection result
        """
        # Extract embedding using YRSN adapter
        embedding = self.extractor.extract([text])[0]  # [384]

        # Compute RSN if RSCT gates enabled
        rsn = None
        gate_passed = True
        gate_rationale = ""

        if self.enable_rsct_gates:
            rsn = self._compute_rsn(embedding)
            gate_passed, gate_rationale = self._apply_gates(*rsn)

        # Run classifier
        with torch.no_grad():
            emb_tensor = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0)
            logit = self.classifier(emb_tensor)
            prob = torch.sigmoid(logit).item()

        # Determine state - classifier-first approach
        # N-gate failure (high noise) → always suspicious
        # Coherence gate failure → use classifier (gate is too conservative)
        # Gates pass → use classifier

        n_gate_failed = rsn and rsn[2] >= self.n_threshold

        if n_gate_failed:
            # N-gate failure = high noise = UNSAFE (conservative)
            state = "UNSAFE"
            is_jailbreak = True
            rationale = f"N-gate failed (N={rsn[2]:.2f} >= {self.n_threshold})"
        elif prob > self.threshold:
            # Classifier says jailbreak
            state = "JAILBREAK"
            is_jailbreak = True
            rationale = f"Classifier confidence {prob:.2f} > threshold {self.threshold}"
        elif not gate_passed:
            # Coherence gate failed but classifier says benign
            state = "UNCERTAIN"
            is_jailbreak = False  # Trust classifier over coherence gate
            rationale = f"{gate_rationale}; classifier={prob:.2f}"
        else:
            # All gates passed, classifier says benign
            state = "BENIGN"
            is_jailbreak = False
            rationale = f"Classifier confidence {prob:.2f} <= threshold {self.threshold}"

        return JailbreakCheckResult(
            is_jailbreak=is_jailbreak,
            confidence=prob,
            state=state,
            gate_passed=gate_passed,
            rsn=rsn,
            rationale=rationale,
        )

    def check_batch(self, texts: List[str]) -> List[JailbreakCheckResult]:
        """Check multiple texts."""
        return [self.check(text) for text in texts]

    def reset(self) -> None:
        """Reset detector state (for stateful detectors)."""
        pass  # Currently stateless


# =============================================================================
# DEFENSE STACK INTEGRATION HELPER
# =============================================================================

def integrate_with_defense_stack(
    defense_result,  # DefenseCheckResult from YRSN
    jailbreak_result: JailbreakCheckResult,
) -> None:
    """
    Integrate jailbreak detection with DefenseStack result.

    Modifies defense_result in place to include jailbreak signals.

    Usage:
        defense_result = defense_stack.check_all(...)
        jailbreak_result = jailbreak_detector.check(prompt)
        integrate_with_defense_stack(defense_result, jailbreak_result)
    """
    if jailbreak_result.is_jailbreak:
        defense_result.allowed = False

    # Add to details
    if not hasattr(defense_result, 'details'):
        defense_result.details = {}

    defense_result.details["jailbreak"] = jailbreak_result.to_dict()


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_jailbreak_detector(
    checkpoint_name: str = "hybrid_classifier_384d.pt",
    experiment_dir: Path = Path(__file__).parent.parent,
) -> JailbreakDetector:
    """
    Factory function to create JailbreakDetector.

    Args:
        checkpoint_name: Name of checkpoint file in experiment checkpoints/
        experiment_dir: Path to SWARM-06 experiment directory

    Returns:
        Configured JailbreakDetector
    """
    checkpoint_path = experiment_dir / "checkpoints" / checkpoint_name
    return JailbreakDetector.from_checkpoint(checkpoint_path)
