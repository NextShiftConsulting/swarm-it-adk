"""
Provider Factory - Create providers with credentials.

Integrates with swarm-it-auth for credential management.
"""

from typing import Optional, Dict, Any, List
from .base import LLMProvider, ProviderType
from .openrouter import OpenRouterProvider
from .mimo import MIMOProvider
from .bedrock import BedrockProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider


def get_provider(
    provider: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> LLMProvider:
    """
    Factory function to create LLM provider.

    Integrates with swarm-it-auth for credential management.

    Args:
        provider: Provider name ("openrouter", "mimo", "bedrock", etc.)
        api_key: API key (if None, tries to load from swarm-it-auth)
        model: Model ID (uses provider default if None)
        **kwargs: Additional provider-specific parameters

    Returns:
        LLMProvider instance

    Example:
        # With explicit API key
        provider = get_provider("openrouter", api_key="sk-...")

        # Auto-load from swarm-it-auth
        provider = get_provider("openrouter")  # Uses swarm-it-auth

        # Specify model
        provider = get_provider("bedrock", model="deepseek-v3.2")
    """
    provider_lower = provider.lower()

    # Load API key from swarm-it-auth if not provided
    if api_key is None and provider_lower != "bedrock":
        api_key = _load_api_key_from_auth(provider_lower)

    # Create provider
    if provider_lower == "openrouter":
        return OpenRouterProvider(
            api_key=api_key,
            model=model or "meta-llama/llama-3.1-8b-instruct:free",
            **kwargs
        )

    elif provider_lower == "mimo":
        return MIMOProvider(
            api_key=api_key,
            model=model or "mimo-v2-flash",
            **kwargs
        )

    elif provider_lower == "bedrock":
        # Bedrock uses AWS credentials (boto3), not API key
        return BedrockProvider(
            model=model or "deepseek-v3.2",
            **kwargs
        )

    elif provider_lower == "openai":
        return OpenAIProvider(
            api_key=api_key,
            model=model or "gpt-4o",
            **kwargs
        )

    elif provider_lower == "anthropic":
        return AnthropicProvider(
            api_key=api_key,
            model=model or "claude-3-5-sonnet-20241022",
            **kwargs
        )

    else:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Available: openrouter, mimo, bedrock, openai, anthropic"
        )


def _load_api_key_from_auth(provider: str) -> Optional[str]:
    """
    Load API key from swarm-it-auth.

    Args:
        provider: Provider name

    Returns:
        API key or None
    """
    try:
        # Try to import swarm-it-auth
        import sys
        from pathlib import Path

        # Add swarm-it-auth to path
        auth_path = Path(__file__).parent.parent.parent.parent.parent / 'swarm-it-auth'
        if auth_path.exists() and str(auth_path) not in sys.path:
            sys.path.insert(0, str(auth_path))

        from swarm_auth.adapters import EnvCredentialAdapter

        creds = EnvCredentialAdapter(prefix="")
        api_key = creds.retrieve(f"{provider.upper()}_API_KEY")

        return api_key

    except ImportError:
        # swarm-it-auth not available, return None
        return None


def list_providers() -> List[Dict[str, Any]]:
    """
    List all available providers.

    Returns:
        List of provider info dicts
    """
    return [
        {
            "name": "openrouter",
            "description": "OpenRouter - 25+ free models",
            "free_models": True,
            "requires_api_key": True,
        },
        {
            "name": "mimo",
            "description": "MIMO (Xiaomi) - Cost-effective Chinese LLM",
            "free_models": False,
            "requires_api_key": True,
        },
        {
            "name": "bedrock",
            "description": "AWS Bedrock - DeepSeek, Qwen, GLM, Claude",
            "free_models": False,
            "requires_api_key": False,  # Uses AWS credentials
        },
        {
            "name": "openai",
            "description": "OpenAI - GPT-4, GPT-3.5",
            "free_models": False,
            "requires_api_key": True,
        },
        {
            "name": "anthropic",
            "description": "Anthropic - Claude (direct API)",
            "free_models": False,
            "requires_api_key": True,
        },
    ]
