#!/usr/bin/env python3
"""
Example: Kappa Viability Check with ADK

Demonstrates how to check if embedding models have sufficient
over-parameterization ratio (κ) for geometric operations.

Key Concepts:
- κ (kappa) = dim / stable_rank
- κ >= 50 required for rotors to work well
- When κ < 50, use expansion factor k = min(ceil(65/κ), 5)

Usage:
    python examples/kappa_viability_check.py
"""

import sys
sys.path.insert(0, "adk")

from swarm_it import (
    SentenceTransformerProvider,
    KappaViabilityChecker,
    check_kappa,
)

# Sample texts for testing
SAMPLE_TEXTS = [
    "The stock market closed higher today.",
    "Scientists discover new species in the ocean.",
    "Quantum computers use qubits for computation.",
    "The weather has been warm this week.",
    "Machine learning finds patterns in data.",
    "Electric vehicles are gaining popularity.",
    "The human genome has billions of base pairs.",
    "Climate change affects global sea levels.",
    "Neural networks use gradient descent.",
    "The Eiffel Tower is in Paris, France.",
] * 30  # 300 samples for stable statistics


def main():
    print("=" * 60)
    print("ADK Kappa Viability Check Example")
    print("=" * 60)

    # Create checker with threshold
    checker = KappaViabilityChecker(threshold=50.0)

    # Models to test
    models = [
        "all-MiniLM-L6-v2",      # 384-dim
        "all-mpnet-base-v2",     # 768-dim
    ]

    print(f"\nTesting {len(models)} models with {len(SAMPLE_TEXTS)} samples...")

    for model_name in models:
        print(f"\n{'='*50}")
        print(f"Model: {model_name}")
        print(f"{'='*50}")

        # Create provider
        provider = SentenceTransformerProvider(model_name)
        print(f"  Dimension: {provider.dim}")

        # Check kappa viability
        result = checker.check_provider(provider, SAMPLE_TEXTS)

        # Display results
        status = "VIABLE" if result.is_viable else "CHOKED"
        print(f"\n  Stable Rank:  {result.stable_rank:.2f}")
        print(f"  κ (kappa):    {result.kappa:.2f} [{status}]")

        if not result.is_viable:
            print(f"\n  [!] EXPANSION NEEDED")
            print(f"      Recommended k: {result.recommended_k}")
            print(f"      κ after expansion: {result.kappa_after_expansion:.2f}")
        else:
            print(f"\n  [✓] Ready for geometric operations")

    # Quick check example
    print(f"\n{'='*60}")
    print("Quick Check API")
    print(f"{'='*60}")

    provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
    embeddings = provider.embed(SAMPLE_TEXTS[:100])

    # One-liner check
    result = check_kappa(embeddings)
    print(f"\n  check_kappa() result:")
    print(f"  {result}")

    # Decision logic
    print(f"\n  Decision logic:")
    if result.is_viable:
        print(f"    → Proceed with rotor operations (k=1)")
    else:
        print(f"    → Expand MLP capacity by k={result.recommended_k}")
        print(f"    → Reference: Adila et al. 'Grow, Don't Overwrite'")


if __name__ == "__main__":
    main()
