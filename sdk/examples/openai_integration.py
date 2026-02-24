"""
OpenAI Integration Example

Shows how to add RSCT certification to OpenAI API calls.
"""

from swarm_it import SwarmIt, GateBlockedError

# Initialize clients
swarm = SwarmIt()

# Uncomment to use real OpenAI:
# from openai import OpenAI
# openai_client = OpenAI()


def chat_with_certification(
    messages: list,
    model: str = "gpt-4",
    **kwargs,
) -> dict:
    """
    OpenAI chat completion with RSCT certification.

    Certifies the last user message before calling the API.
    """
    # Extract last user message for certification
    user_messages = [m for m in messages if m.get("role") == "user"]
    if not user_messages:
        raise ValueError("No user message to certify")

    last_user_message = user_messages[-1]["content"]

    # Certify
    cert = swarm.certify(
        context=last_user_message,
        metadata={
            "model": model,
            "message_count": len(messages),
        },
    )

    print(f"[Certification] R={cert.R:.3f}, N={cert.N:.3f}, kappa={cert.kappa:.3f}")
    print(f"[Certification] Decision: {cert.decision.value}")

    if not cert.allowed:
        raise GateBlockedError(cert)

    # Call OpenAI (mock for demo)
    # response = openai_client.chat.completions.create(
    #     model=model,
    #     messages=messages,
    #     **kwargs
    # )
    # return response

    # Mock response
    return {
        "id": "mock-response",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": f"[Mock response to: {last_user_message[:50]}...]",
                }
            }
        ],
        "_certificate": cert.to_dict(),  # Include cert in response
    }


def streaming_chat_with_certification(
    messages: list,
    model: str = "gpt-4",
    **kwargs,
):
    """
    Streaming chat with certification gate.

    Certifies before starting the stream.
    """
    user_messages = [m for m in messages if m.get("role") == "user"]
    if not user_messages:
        raise ValueError("No user message to certify")

    cert = swarm.certify(user_messages[-1]["content"])

    if not cert.allowed:
        raise GateBlockedError(cert)

    # Stream from OpenAI (mock for demo)
    # response = openai_client.chat.completions.create(
    #     model=model,
    #     messages=messages,
    #     stream=True,
    #     **kwargs
    # )
    # for chunk in response:
    #     yield chunk

    # Mock streaming
    for word in ["This", "is", "a", "mock", "streaming", "response."]:
        yield {"choices": [{"delta": {"content": word + " "}}]}


class CertifiedOpenAI:
    """
    Wrapper class for OpenAI with automatic certification.

    Usage:
        client = CertifiedOpenAI(swarm, openai_client)
        response = client.chat("What is AI?")
    """

    def __init__(self, swarm_client: SwarmIt, openai_client=None):
        self.swarm = swarm_client
        self.openai = openai_client

    def chat(
        self,
        prompt: str,
        system: str = "You are a helpful assistant.",
        model: str = "gpt-4",
        **kwargs,
    ) -> str:
        """Simple chat with certification."""
        # Certify
        cert = self.swarm.certify(prompt)

        if not cert.allowed:
            return f"[Blocked: {cert.reason}]"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        if self.openai:
            response = self.openai.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
            return response.choices[0].message.content

        # Mock
        return f"[Mock response to: {prompt}]"

    def chat_with_history(
        self,
        messages: list,
        model: str = "gpt-4",
        **kwargs,
    ) -> dict:
        """Chat with message history."""
        return chat_with_certification(messages, model, **kwargs)


# Decorator approach for existing code
@swarm.gate
def ask_openai(prompt: str, model: str = "gpt-4") -> str:
    """
    Decorated function that automatically certifies.

    Just add @swarm.gate to your existing functions.
    """
    # In real code:
    # response = openai_client.chat.completions.create(
    #     model=model,
    #     messages=[{"role": "user", "content": prompt}]
    # )
    # return response.choices[0].message.content

    return f"[Mock: {prompt}]"


if __name__ == "__main__":
    print("=" * 60)
    print("OpenAI + Swarm It Integration Demo")
    print("=" * 60)

    # Example 1: Direct function call
    print("\n1. Direct certification:")
    try:
        response = chat_with_certification(
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "What is machine learning?"},
            ]
        )
        print(f"Response: {response['choices'][0]['message']['content']}")
    except GateBlockedError as e:
        print(f"Blocked: {e.certificate.reason}")

    # Example 2: Wrapper class
    print("\n2. Wrapper class:")
    client = CertifiedOpenAI(swarm)
    response = client.chat("Explain neural networks briefly")
    print(f"Response: {response}")

    # Example 3: Decorator
    print("\n3. Decorated function:")
    try:
        response = ask_openai("What is deep learning?")
        print(f"Response: {response}")
    except GateBlockedError as e:
        print(f"Blocked: {e.certificate.reason}")

    # Example 4: Streaming
    print("\n4. Streaming with certification:")
    try:
        print("Streaming: ", end="")
        for chunk in streaming_chat_with_certification(
            messages=[{"role": "user", "content": "Tell me a short story"}]
        ):
            content = chunk["choices"][0]["delta"].get("content", "")
            print(content, end="", flush=True)
        print()
    except GateBlockedError as e:
        print(f"Blocked: {e.certificate.reason}")
