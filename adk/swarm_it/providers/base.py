"""
Base LLM Provider Port - Abstraction for LLM API calls.

Hexagonal Architecture:
- LLMProvider is the PORT (interface)
- Concrete providers are ADAPTERS (implementations)
- Applications depend on PORT, not concrete adapters
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ProviderType(Enum):
    """LLM provider types."""
    OPENROUTER = "openrouter"
    MIMO = "mimo"
    BEDROCK = "bedrock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class LLMResponse:
    """
    Standardized LLM response.

    Unified response format across all providers.
    """
    content: str
    model: str
    provider: str

    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Cost (if available)
    cost_usd: Optional[float] = None

    # Raw response for debugging
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def cost_per_1k_tokens(self) -> Optional[float]:
        """Calculate cost per 1K tokens."""
        if self.cost_usd and self.total_tokens > 0:
            return (self.cost_usd / self.total_tokens) * 1000
        return None


@dataclass
class LLMProviderConfig:
    """
    Provider configuration.

    Common configuration across all providers.
    """
    model: str
    temperature: float = 0.7
    max_tokens: int = 500
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0

    # Provider-specific settings
    extra: Dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """
    PORT: LLM Provider abstraction.

    This is the interface that applications depend on.
    Concrete providers implement this interface.

    Hexagonal Architecture:
        Application → LLMProvider (PORT) ← Adapter (OpenRouter, MIMO, etc.)

    Example:
        provider = get_provider("openrouter", api_key="...")
        response = provider.complete([
            {"role": "user", "content": "Hello"}
        ])
    """

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Get provider type."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Get current model."""
        pass

    @abstractmethod
    def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        Complete a chat conversation.

        Args:
            messages: List of message dicts with 'role' and 'content'
                     e.g., [{"role": "user", "content": "Hello"}]
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse with standardized response

        Example:
            response = provider.complete([
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "What is 2+2?"}
            ], temperature=0.5)
        """
        pass

    @abstractmethod
    def list_models(self) -> List[str]:
        """
        List available models for this provider.

        Returns:
            List of model IDs
        """
        pass

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> Optional[float]:
        """
        Estimate cost for token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD, or None if pricing unknown
        """
        # Override in subclasses with actual pricing
        return None

    @property
    def supports_streaming(self) -> bool:
        """Check if provider supports streaming."""
        return False

    @property
    def supports_function_calling(self) -> bool:
        """Check if provider supports function calling."""
        return False

    def validate_config(self, config: LLMProviderConfig) -> bool:
        """
        Validate provider configuration.

        Args:
            config: Provider configuration

        Returns:
            True if valid

        Raises:
            ValueError: If configuration invalid
        """
        if config.temperature < 0 or config.temperature > 2:
            raise ValueError("Temperature must be between 0 and 2")

        if config.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        return True
