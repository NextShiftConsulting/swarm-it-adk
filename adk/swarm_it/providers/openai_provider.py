"""
OpenAI Provider - GPT models.

Standard OpenAI API (GPT-4, GPT-3.5, etc.).
"""

from typing import List, Dict, Any, Optional
from .base import LLMProvider, LLMResponse, ProviderType, LLMProviderConfig


class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM provider.

    Supports: GPT-4, GPT-3.5-turbo, and other OpenAI models.

    Example:
        provider = OpenAIProvider(
            api_key="sk-...",
            model="gpt-4o"
        )

        response = provider.complete([
            {"role": "user", "content": "Hello!"}
        ])
    """

    MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ]

    # Pricing (per 1M tokens)
    PRICING = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        config: Optional[LLMProviderConfig] = None,
    ):
        """Initialize OpenAI provider."""
        self._model = model
        self._config = config or LLMProviderConfig(model=model)

        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENAI

    @property
    def model(self) -> str:
        return self._model

    def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Complete chat conversation via OpenAI."""
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

        cost_usd = self.estimate_cost(input_tokens, output_tokens)

        return LLMResponse(
            content=content,
            model=self._model,
            provider="openai",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            raw=response.model_dump() if hasattr(response, 'model_dump') else {},
        )

    def list_models(self) -> List[str]:
        return self.MODELS

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> Optional[float]:
        if self._model not in self.PRICING:
            return None

        pricing = self.PRICING[self._model]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    @property
    def supports_function_calling(self) -> bool:
        return True
