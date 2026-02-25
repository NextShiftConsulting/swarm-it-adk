"""
Swarm-It RSCT Engine

Clean architecture (Tendermint-inspired):
- Sidecar: Pre-screening, API, observability (domain-agnostic)
- yrsn core: RSN computation, gate logic (domain semantics)
"""

from .rsct import RSCTEngine
from .patterns import PatternDetector, get_detector
from .semantic import SemanticAnalyzer, get_semantic_analyzer

__all__ = [
    "RSCTEngine",
    "PatternDetector",
    "get_detector",
    "SemanticAnalyzer",
    "get_semantic_analyzer",
]
