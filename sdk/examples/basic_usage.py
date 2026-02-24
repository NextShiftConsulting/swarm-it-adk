"""
Basic Swarm It Usage Examples

Shows the simplest ways to integrate RSCT certification.
"""

from swarm_it import SwarmIt, GateBlockedError


def example_simple_check():
    """
    Example 1: Simple certification check

    The most basic pattern - check before you call.
    """
    print("=" * 60)
    print("Example 1: Simple Certification Check")
    print("=" * 60)

    # Initialize client (uses SWARM_IT_API_KEY env var if no key provided)
    swarm = SwarmIt()

    prompt = "What is the capital of France?"

    # Certify the prompt
    cert = swarm.certify(prompt)

    print(f"Prompt: {prompt}")
    print(f"Certificate ID: {cert.id}")
    print(f"RSN: R={cert.R:.3f}, S={cert.S:.3f}, N={cert.N:.3f}")
    print(f"Decision: {cert.decision.value}")
    print(f"Allowed: {cert.allowed}")
    print(f"Margin: {cert.margin:.3f}")

    if cert.allowed:
        print("\n✓ Safe to execute LLM call")
        # response = openai.chat.completions.create(...)
    else:
        print(f"\n✗ Blocked: {cert.reason}")


def example_decorator():
    """
    Example 2: Using the @gate decorator

    Automatically certify any function that takes a prompt.
    """
    print("\n" + "=" * 60)
    print("Example 2: Gate Decorator")
    print("=" * 60)

    swarm = SwarmIt()

    @swarm.gate
    def ask_llm(prompt: str) -> str:
        """This function is automatically gated."""
        # In real code: return openai.chat.completions.create(...)
        return f"[Mock response to: {prompt}]"

    # Safe prompt - will execute
    try:
        result = ask_llm("What is 2 + 2?")
        print(f"Result: {result}")
    except GateBlockedError as e:
        print(f"Blocked: {e.certificate.reason}")


def example_custom_block_handler():
    """
    Example 3: Custom handler for blocked requests

    Instead of raising an exception, return a fallback.
    """
    print("\n" + "=" * 60)
    print("Example 3: Custom Block Handler")
    print("=" * 60)

    swarm = SwarmIt()

    def on_blocked(cert):
        """Return a safe fallback when blocked."""
        return f"I can't help with that. (Reason: {cert.reason})"

    @swarm.gate(on_block=on_blocked)
    def ask_llm(prompt: str) -> str:
        return f"[Response to: {prompt}]"

    # This will either execute or return the fallback
    result = ask_llm("Tell me something interesting")
    print(f"Result: {result}")


def example_with_metadata():
    """
    Example 4: Including metadata for audit

    Track user/session info with certificates.
    """
    print("\n" + "=" * 60)
    print("Example 4: Certification with Metadata")
    print("=" * 60)

    swarm = SwarmIt()

    cert = swarm.certify(
        context="Explain quantum computing",
        policy="standard",
        metadata={
            "user_id": "user-123",
            "session_id": "sess-456",
            "request_id": "req-789",
            "source": "web-app",
        },
    )

    print(f"Certificate: {cert.id}")
    print(f"Policy: {cert.policy}")
    print(f"Full certificate data: {cert.raw}")


def example_batch_certification():
    """
    Example 5: Certifying multiple prompts

    Check a batch of prompts and filter blocked ones.
    """
    print("\n" + "=" * 60)
    print("Example 5: Batch Certification")
    print("=" * 60)

    swarm = SwarmIt()

    prompts = [
        "What is the weather today?",
        "Explain machine learning",
        "Write a poem about nature",
        "How do I make coffee?",
    ]

    allowed = []
    blocked = []

    for prompt in prompts:
        cert = swarm.certify(prompt)
        if cert.allowed:
            allowed.append((prompt, cert))
        else:
            blocked.append((prompt, cert))

    print(f"Allowed: {len(allowed)}")
    for prompt, cert in allowed:
        print(f"  ✓ {prompt[:40]}... (R={cert.R:.2f})")

    print(f"\nBlocked: {len(blocked)}")
    for prompt, cert in blocked:
        print(f"  ✗ {prompt[:40]}... ({cert.reason})")


def example_context_manager():
    """
    Example 6: Using context manager for cleanup

    Properly manage client resources.
    """
    print("\n" + "=" * 60)
    print("Example 6: Context Manager")
    print("=" * 60)

    with SwarmIt() as swarm:
        cert = swarm.certify("What is AI?")
        print(f"Decision: {cert.decision.value}")

    print("Client closed automatically")


if __name__ == "__main__":
    example_simple_check()
    example_decorator()
    example_custom_block_handler()
    example_with_metadata()
    example_batch_certification()
    example_context_manager()

    print("\n" + "=" * 60)
    print("All examples complete!")
    print("=" * 60)
