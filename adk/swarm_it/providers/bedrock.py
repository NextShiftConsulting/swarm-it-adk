"""
AWS Bedrock Provider - Chinese and US models.

Supports:
- DeepSeek (Chinese) - 95% cheaper than Claude
- Qwen (Alibaba) - 97% cheaper
- GLM (Zhipu AI) - 98% cheaper
- Claude (Anthropic)
- And more...
"""

import json
from typing import List, Dict, Any, Optional
from .base import LLMProvider, LLMResponse, ProviderType, LLMProviderConfig


class BedrockProvider(LLMProvider):
    """
    AWS Bedrock LLM provider.

    Supports multiple model families:
    - DeepSeek (Chinese): deepseek-v3-2, deepseek-r1
    - Qwen (Alibaba): qwen3-coder-next
    - GLM (Zhipu): glm-4-7-flash
    - Claude (Anthropic): claude-3-haiku, claude-3-5-sonnet

    Example:
        provider = BedrockProvider(
            model="deepseek-v3.2",
            region="us-east-1"
        )

        response = provider.complete([
            {"role": "user", "content": "Hello!"}
        ])
    """

    # Model ID mapping (short name -> full Bedrock ID)
    MODELS = {
        # DeepSeek (Chinese)
        "deepseek-v3.2": "deepseek.deepseek-v3-2",
        "deepseek-v3.1": "deepseek.deepseek-v3-1",
        "deepseek-r1": "deepseek.deepseek-r1",

        # Qwen (Alibaba)
        "qwen3-coder": "qwen.qwen3-coder-next",

        # GLM (Zhipu AI)
        "glm-flash": "glm.glm-4-7-flash",

        # Claude (Anthropic)
        "claude-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
        "claude-sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    }

    # Pricing (per 1M tokens) - input/output
    PRICING = {
        "deepseek-v3.2": {"input": 0.14, "output": 0.28},
        "deepseek-v3.1": {"input": 0.14, "output": 0.28},
        "deepseek-r1": {"input": 0.16, "output": 0.64},
        "qwen3-coder": {"input": 0.10, "output": 0.30},
        "glm-flash": {"input": 0.08, "output": 0.24},
        "claude-haiku": {"input": 0.25, "output": 1.25},
        "claude-sonnet": {"input": 3.00, "output": 15.00},
    }

    def __init__(
        self,
        model: str = "deepseek-v3.2",
        region: str = "us-east-1",
        config: Optional[LLMProviderConfig] = None,
    ):
        """
        Initialize Bedrock provider.

        Args:
            model: Model short name (e.g., "deepseek-v3.2")
            region: AWS region
            config: Provider configuration
        """
        if model not in self.MODELS:
            raise ValueError(
                f"Unknown model: {model}. "
                f"Available: {list(self.MODELS.keys())}"
            )

        self._model = model
        self._model_id = self.MODELS[model]
        self._config = config or LLMProviderConfig(model=model)

        # Initialize Bedrock client
        import boto3
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=region
        )

    @property
    def provider_type(self) -> ProviderType:
        """Get provider type."""
        return ProviderType.BEDROCK

    @property
    def model(self) -> str:
        """Get current model."""
        return self._model

    def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Complete chat conversation via Bedrock."""
        # Extract system message if present
        system_message = None
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                user_messages.append(msg)

        # Build request body (Claude format)
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
            "temperature": kwargs.get("temperature", self._config.temperature),
            "messages": user_messages,
        }

        if system_message:
            request_body["system"] = system_message

        # Invoke model
        response = self._client.invoke_model(
            modelId=self._model_id,
            body=json.dumps(request_body)
        )

        # Parse response
        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        # Parse usage
        usage = result.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens

        # Calculate cost
        cost_usd = self.estimate_cost(input_tokens, output_tokens)

        return LLMResponse(
            content=content,
            model=self._model,
            provider="bedrock",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            raw=result,
        )

    def list_models(self) -> List[str]:
        """List available models."""
        return list(self.MODELS.keys())

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
