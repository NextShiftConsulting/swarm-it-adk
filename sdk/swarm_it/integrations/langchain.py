"""
LangChain Integration for Swarm It

Provides RSCT certification gating for LangChain chains and agents.

Usage:
    from swarm_it import SwarmIt
    from swarm_it.integrations import SwarmItRunnable

    swarm = SwarmIt(api_key="...")

    # Wrap any runnable with certification
    gated_chain = SwarmItRunnable(swarm) | my_chain

    # Or use as a callback
    from swarm_it.integrations import SwarmItCallbackHandler
    result = chain.invoke(input, callbacks=[SwarmItCallbackHandler(swarm)])
"""

from typing import Any, Dict, List, Optional, Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import SwarmIt, Certificate


class SwarmItRunnable:
    """
    LangChain Runnable that gates execution with RSCT certification.

    This acts as a "gate" in your chain - it checks the input,
    certifies it, and only passes through if allowed.

    Usage:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate

        swarm = SwarmIt(api_key="...")

        # Create gated chain
        prompt = ChatPromptTemplate.from_messages([...])
        llm = ChatOpenAI()

        chain = SwarmItRunnable(swarm) | prompt | llm

        # This will certify before executing
        result = chain.invoke({"question": "What is AI?"})
    """

    def __init__(
        self,
        client: "SwarmIt",
        policy: Optional[str] = None,
        input_key: str = "input",
        pass_certificate: bool = False,
    ):
        """
        Args:
            client: SwarmIt client
            policy: Certification policy
            input_key: Key to extract context from input dict
            pass_certificate: If True, adds 'certificate' to output
        """
        self.client = client
        self.policy = policy
        self.input_key = input_key
        self.pass_certificate = pass_certificate

    def invoke(
        self,
        input: Any,
        config: Optional[Dict] = None,
    ) -> Any:
        """Invoke with certification gate."""
        from ..exceptions import GateBlockedError

        # Extract context
        context = self._extract_context(input)

        # Certify
        cert = self.client.certify(context, policy=self.policy)

        if not cert.allowed:
            raise GateBlockedError(cert)

        # Pass through (optionally with certificate)
        if self.pass_certificate:
            if isinstance(input, dict):
                return {**input, "certificate": cert}
            return {"input": input, "certificate": cert}

        return input

    def stream(
        self,
        input: Any,
        config: Optional[Dict] = None,
    ) -> Iterator[Any]:
        """Stream with certification gate."""
        result = self.invoke(input, config)
        yield result

    def _extract_context(self, input: Any) -> str:
        """Extract context string from input."""
        if isinstance(input, str):
            return input

        if isinstance(input, dict):
            # Try common keys
            for key in (self.input_key, "question", "query", "prompt", "message"):
                if key in input:
                    value = input[key]
                    if isinstance(value, str):
                        return value

            # Try first string value
            for value in input.values():
                if isinstance(value, str):
                    return value

        # Fallback to string representation
        return str(input)

    # LangChain Runnable protocol
    def __or__(self, other):
        """Support chain composition with |"""
        try:
            from langchain_core.runnables import RunnableSequence

            return RunnableSequence(first=self, last=other)
        except ImportError:
            raise ImportError(
                "LangChain not installed. Install with: pip install langchain-core"
            )

    def __ror__(self, other):
        """Support reverse chain composition with |"""
        try:
            from langchain_core.runnables import RunnableSequence

            return RunnableSequence(first=other, last=self)
        except ImportError:
            raise ImportError(
                "LangChain not installed. Install with: pip install langchain-core"
            )


class SwarmItCallbackHandler:
    """
    LangChain callback handler for certification logging.

    This doesn't gate execution - it logs certificate information
    for observability. Use SwarmItRunnable for actual gating.

    Usage:
        from langchain_openai import ChatOpenAI

        swarm = SwarmIt(api_key="...")
        handler = SwarmItCallbackHandler(swarm)

        llm = ChatOpenAI()
        result = llm.invoke("Hello", callbacks=[handler])

        # Check logged certificates
        for cert in handler.certificates:
            print(f"R={cert.R}, allowed={cert.allowed}")
    """

    def __init__(
        self,
        client: "SwarmIt",
        policy: Optional[str] = None,
        block_on_reject: bool = False,
    ):
        self.client = client
        self.policy = policy
        self.block_on_reject = block_on_reject
        self.certificates: List["Certificate"] = []

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs,
    ) -> None:
        """Called when LLM starts - certify the prompts."""
        from ..exceptions import GateBlockedError

        for prompt in prompts:
            cert = self.client.certify(prompt, policy=self.policy)
            self.certificates.append(cert)

            if self.block_on_reject and not cert.allowed:
                raise GateBlockedError(cert)

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs,
    ) -> None:
        """Called when chain starts."""
        pass  # Could certify chain inputs here

    def on_llm_end(self, response, **kwargs) -> None:
        """Called when LLM ends."""
        pass

    def on_llm_error(self, error, **kwargs) -> None:
        """Called on LLM error."""
        pass


def create_gated_chain(
    client: "SwarmIt",
    chain,
    policy: Optional[str] = None,
):
    """
    Convenience function to wrap a chain with certification.

    Usage:
        gated = create_gated_chain(swarm, my_chain)
        result = gated.invoke({"question": "What is AI?"})
    """
    return SwarmItRunnable(client, policy=policy) | chain
