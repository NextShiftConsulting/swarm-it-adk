"""
MIMO Provider - Xiaomi's LLM API.

Cost-effective Chinese LLM provider (~$1/M tokens).
OpenAI-compatible API.
"""

from typing import List, Dict, Any, Optional
from .base import LLMProvider, LLMResponse, ProviderType, LLMProviderConfig


class MIMOProvider(LLMProvider):
    """
    MIMO (Xiaomi) LLM provider.

    Cost-effective API (~$1/M input tokens, $3/M output tokens).
    OpenAI-compatible interface.

    Example:
        provider = MIMOProvider(
            api_key="your-mimo-key",
            model="mimo-v2-flash"
        )

        response = provider.complete([
            {"role": "user", "content": "Hello!"}
        ])
    """

    MODELS = [
        "mimo-v2-flash",  # Fast, cheap
        "mimo-v2",        # Balanced
    ]

    # Pricing (per 1M tokens)
    PRICING = {
        "mimo-v2-flash": {"input": 1.0, "output": 3.0},
        "mimo-v2": {"input": 2.0, "output": 6.0},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "mimo-v2-flash",
        config: Optional[LLMProviderConfig] = None,
    ):
        """
        Initialize MIMO provider.

        Args:
            api_key: MIMO API key
            model: Model ID (default: mimo-v2-flash)
            config: Provider configuration
        """
        self._model = model
        self._config = config or LLMProviderConfig(model=model)

        # Initialize OpenAI-compatible client
        from openai import OpenAI
        self._client = OpenAI(
            base_url="https://api.mimo.ai/v1",
            api_key=api_key,
        )

    @property
    def provider_type(self) -> ProviderType:
        """Get provider type."""
        return ProviderType.MIMO

    @property
    def model(self) -> str:
        """Get current model."""
        return self._model

    def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Complete chat conversation via MIMO."""
        params = {
            "model": self._model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self._config.temperature),
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
        }

        response = self._client.chat.completions.create(**params)

        choice = response.choices[0]
        content = choice.message.content

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        # Calculate cost
        cost_usd = self.estimate_cost(input_tokens, output_tokens)

        return LLMResponse(
            content=content,
            model=self._model,
            provider="mimo",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            raw=response.model_dump() if hasattr(response, 'model_dump') else {},
        )

    def list_models(self) -> List[str]:
        """List available models."""
        return self.MODELS

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> Optional[float]:
        """Estimate cost for token usage."""
        if self._model not in self.PRICING:
            return None

        pricing = self.PRICING[self._model]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost
