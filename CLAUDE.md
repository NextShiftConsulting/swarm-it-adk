# Swarm It Project Instructions

## Git Commits

**NEVER add Claude attribution of any kind.** This includes:
- No "Generated with Claude Code" messages
- No "Co-Authored-By: Claude" lines
- No references to Claude, Anthropic, or AI assistance in commit messages
- No AI attribution in code comments or documentation

## Patent Notice

This project includes patented technology. See [PATENT_NOTICE.md](PATENT_NOTICE.md).

All production code must properly attribute the patent-pending status in user-facing documentation.

## SDK Development

### Certificate Architecture

The SDK's `RSCTCertificate` must maintain round-trip compatibility with yrsn's `YRSNCertificate`:

```python
# SDK certificate preserves full hierarchy block
@dataclass
class RSCTCertificate:
    # Core simplex
    R: float
    S: float
    N: float
    kappa_gate: float  # Enforced: min(kappa_H, kappa_L, ...)

    # Hierarchy block (from yrsn)
    kappa_H: Optional[float] = None
    kappa_L: Optional[float] = None
    kappa_interface: Optional[float] = None
```

### Bridge Functions

Always use `to_yrsn_dict()` and `from_yrsn_dict()` when serializing certificates for yrsn interoperability.

## Quality Gates

All significant work should pass quality gates:

1. **Stage 1 (Relevance)**: R >= 0.3
2. **Stage 2 (Stability)**: S >= 0.4
3. **Stage 3 (Novelty)**: N <= 0.5
4. **Stage 4 (kappa-gate)**: kappa >= 0.7
