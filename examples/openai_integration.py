#!/usr/bin/env python3
"""
OpenAI Integration with Swarm-It Certification

This example shows how to wrap OpenAI calls with RSCT certification.

Prerequisites:
    pip install openai httpx

    # Start sidecar
    cd sidecar && docker-compose up -d

    # Set API key
    export OPENAI_API_KEY=sk-...

Usage:
    python examples/openai_integration.py
"""

import os
import sys

# Add clients/python to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'clients', 'python'))

from swarm_it import SwarmIt, ValidationType

# Check for OpenAI
try:
    from openai import OpenAI
except ImportError:
    print("Please install openai: pip install openai")
    sys.exit(1)


def certified_chat(
    prompt: str,
    swarm: SwarmIt,
    client: OpenAI,
    model: str = "gpt-4o-mini",
) -> dict:
    """
    OpenAI chat completion with RSCT certification.

    Args:
        prompt: User prompt
        swarm: Swarm-It client
        client: OpenAI client
        model: Model to use

    Returns:
        Dict with response and certificate
    """
    # Step 1: Pre-execution certification
    print(f"[Certifying] {prompt[:50]}...")
    cert = swarm.certify(prompt)

    print(f"[Certificate] decision={cert.decision.value} kappa={cert.kappa_gate:.2f}")

    if not cert.allowed:
        return {
            "error": f"Blocked: {cert.reason}",
            "certificate": cert,
            "response": None,
        }

    # Step 2: Execute LLM call
    print(f"[Executing] Calling {model}...")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        content = response.choices[0].message.content
        failed = False
    except Exception as e:
        content = None
        failed = True
        print(f"[Error] {e}")

    # Step 3: Post-execution validation
    print(f"[Validating] Recording feedback...")
    swarm.validate(
        cert.id,
        ValidationType.TYPE_I,  # Groundedness
        score=0.9 if not failed else 0.0,
        failed=failed,
    )

    return {
        "response": content,
        "certificate": cert,
        "error": None if not failed else "LLM call failed",
    }


def main():
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY environment variable")
        sys.exit(1)

    # Initialize clients
    swarm = SwarmIt(url="http://localhost:8080")
    openai_client = OpenAI()

    # Check sidecar health
    if not swarm.health():
        print("Sidecar not running. Start with: cd sidecar && docker-compose up -d")
        sys.exit(1)

    print("=" * 60)
    print("Swarm-It + OpenAI Integration Demo")
    print("=" * 60)

    # Test cases
    prompts = [
        "What is the capital of France?",
        "Explain quantum entanglement in simple terms.",
        "Write a haiku about programming.",
    ]

    for prompt in prompts:
        print(f"\n{'='*60}")
        result = certified_chat(prompt, swarm, openai_client)

        if result["error"]:
            print(f"[Result] Error: {result['error']}")
        else:
            print(f"[Result] {result['response'][:200]}...")

    # Show statistics
    print(f"\n{'='*60}")
    print("Sidecar Statistics:")
    stats = swarm.statistics()
    print(f"  Total certificates: {stats.get('total_certificates', 0)}")
    print(f"  Thresholds: {stats.get('thresholds', {})}")


if __name__ == "__main__":
    main()
