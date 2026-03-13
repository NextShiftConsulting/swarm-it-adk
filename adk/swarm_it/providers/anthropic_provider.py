"""
Anthropic Provider - Claude models (direct API).

For AWS Bedrock Claude, use BedrockProvider instead.
"""

from typing import List, Dict, Any, Optional
from .base import LLMProvider, LLMResponse, ProviderType, LLMProviderConfig


class AnthropicProvider(LLMProvider):
    """
    Anthropic (Claude) LLM provider via direct API.

    For AWS Bedrock, use BedrockProvider with "claude-*" models instead.

    Example:
        provider = AnthropicProvider(
            api_key="sk-ant-...",
            model="claude-3-5-sonnet-20241022"
        )

        response = provider.complete([
            {"role": "user", "content": "Hello!"}
        ])
    """

    MODELS = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ]

    # Pricing (per 1M tokens)
    PRICING = {
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        config: Optional[LLMProviderConfig] = None,
    ):
        """Initialize Anthropic provider."""
        self._model = model
        self._config = config or LLMProviderConfig(model=model)

        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.ANTHROPIC

    @property
    def model(self) -> str:
        return self._model

    def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Complete chat conversation via Anthropic."""
        # Extract system message
        system_message = None
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                user_messages.append(msg)

        # Build params
        params = {
            "model": self._model,
            "messages": user_messages,
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
            "temperature": kwargs.get("temperature", self._config.temperature),
        }

        if system_message:
            params["system"] = system_message

        response = self._client.messages.create(**params)

        content = response.content[0].text

        usage = response.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        total_tokens = input_tokens + output_tokens

        cost_usd = self.estimate_cost(input_tokens, output_tokens)

        return LLMResponse(
            content=content,
            model=self._model,
            provider="anthropic",
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
