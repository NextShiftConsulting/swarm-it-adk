#!/usr/bin/env python3
"""
Swarm-It Quickstart - Minimal Working Example

No dependencies required beyond standard library + sidecar.

Usage:
    cd swarm-it
    python examples/quickstart.py
"""

import sys
import os

# Add sidecar to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sidecar'))

from engine.rsct import RSCTEngine
from store.certificates import CertificateStore


def main():
    print("=" * 50)
    print("Swarm-It Quickstart")
    print("=" * 50)
    print()

    # Initialize
    engine = RSCTEngine()
    store = CertificateStore()

    # Test prompts
    prompts = [
        "What is 2+2?",
        "Explain quantum physics",
        "Describe this image of a sunset",  # Multimodal
    ]

    for prompt in prompts:
        print(f"Prompt: {prompt[:40]}...")

        # Certify
        cert = engine.certify(prompt)
        store.store(cert)

        # Show result
        print(f"  R={cert['R']:.2f} S={cert['S']:.2f} N={cert['N']:.2f}")
        print(f"  kappa_gate={cert['kappa_gate']:.2f}")
        print(f"  decision={cert['decision']} (gate {cert['gate_reached']})")
        print(f"  allowed={cert['allowed']}")

        if cert['is_multimodal']:
            print(f"  multimodal: weak_modality={cert['weak_modality']}")

        print()

    # Stats
    print("-" * 50)
    print(f"Total certificates: {store.count()}")
    print(f"Thresholds: {engine.get_thresholds()}")


if __name__ == "__main__":
    main()
