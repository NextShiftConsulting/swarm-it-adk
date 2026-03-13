"""
OpenRouter Provider - Access to 25+ free models.

Supports: Qwen, LLaMA, Mistral, Gemma, and many more.
Free tier available with no credit card.
"""

from typing import List, Dict, Any, Optional
from .base import LLMProvider, LLMResponse, ProviderType, LLMProviderConfig


class OpenRouterProvider(LLMProvider):
    """
    OpenRouter LLM provider.

    OpenRouter provides access to multiple models through one API:
    - 25+ free models (no credit card required)
    - Unified OpenAI-compatible interface
    - One API key for all models

    Free Models (Feb 2026):
    - meta-llama/llama-3.1-8b-instruct:free
    - mistralai/mistral-7b-instruct:free
    - google/gemma-2-9b-it:free
    - Check https://openrouter.ai/models?q=free for current list

    Example:
        provider = OpenRouterProvider(
            api_key="sk-or-v1-...",
            model="meta-llama/llama-3.1-8b-instruct:free"
        )

        response = provider.complete([
            {"role": "user", "content": "Hello!"}
        ])
    """

    # Common free models (check OpenRouter for current availability)
    FREE_MODELS = [
        "meta-llama/llama-3.1-8b-instruct:free",
        "meta-llama/llama-3.1-70b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "google/gemma-2-9b-it:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
    ]

    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/llama-3.1-8b-instruct:free",
        config: Optional[LLMProviderConfig] = None,
    ):
        """
        Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            model: Model ID (default: free LLaMA 3.1)
            config: Provider configuration
        """
        self._model = model
        self._config = config or LLMProviderConfig(model=model)

        # Initialize OpenAI-compatible client
        from openai import OpenAI
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

    @property
    def provider_type(self) -> ProviderType:
        """Get provider type."""
        return ProviderType.OPENROUTER

    @property
    def model(self) -> str:
        """Get current model."""
        return self._model

    def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        Complete chat conversation via OpenRouter.

        Args:
            messages: Chat messages
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse with standardized response
        """
        # Merge config with kwargs
        params = {
            "model": self._model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self._config.temperature),
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
        }

        # Make API call
        response = self._client.chat.completions.create(**params)

        # Extract response
        choice = response.choices[0]
        content = choice.message.content

        # Parse usage
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        # Calculate cost (free models = $0)
        cost_usd = 0.0 if ":free" in self._model else None

        return LLMResponse(
            content=content,
            model=self._model,
            provider="openrouter",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            raw=response.model_dump() if hasattr(response, 'model_dump') else {},
        )

    def list_models(self) -> List[str]:
        """
        List available models.

        Returns:
            List of free models (check OpenRouter for full list)
        """
        return self.FREE_MODELS

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> Optional[float]:
        """
        Estimate cost for token usage.

        Free models return $0, paid models return None (unknown).
        """
        if ":free" in self._model:
            return 0.0
        return None  # Paid models - pricing varies

    @property
    def supports_function_calling(self) -> bool:
        """Some OpenRouter models support function calling."""
        return True  # Check specific model capabilities
