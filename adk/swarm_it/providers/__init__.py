"""
LLM Provider Adapters for swarm-it-adk

Provides standardized interface for multiple LLM providers.
Follows hexagonal architecture (ports & adapters).

Usage:
    from swarm_it.providers import OpenRouterProvider, get_provider

    # Get provider with credentials
    provider = get_provider("openrouter", api_key="...")

    # Make LLM call
    response = provider.complete([
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello!"}
    ])

    # Certify response
    from swarm_it import certify
    cert = certify(response)

Supported Providers:
- OpenRouter (25+ free models)
- MIMO (Xiaomi)
- Bedrock (AWS - DeepSeek, Qwen, GLM, Claude)
- OpenAI
- Anthropic
"""

from .base import LLMProvider, LLMProviderConfig, LLMResponse
from .openrouter import OpenRouterProvider
from .mimo import MIMOProvider
from .bedrock import BedrockProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .factory import get_provider, list_providers

__all__ = [
    # Base
    "LLMProvider",
    "LLMProviderConfig",
    "LLMResponse",

    # Providers
    "OpenRouterProvider",
    "MIMOProvider",
    "BedrockProvider",
    "OpenAIProvider",
    "AnthropicProvider",

    # Factory
    "get_provider",
    "list_providers",
]
