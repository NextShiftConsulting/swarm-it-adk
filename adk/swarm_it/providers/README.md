# LLM Providers Module

**Hexagonal Architecture - Standardized LLM API Abstraction**

## Overview

This module provides a standardized interface for multiple LLM providers:
- **OpenRouter** - 25+ free models (Qwen, LLaMA, Mistral, Gemma)
- **MIMO** - Xiaomi's cost-effective API (~$1/M tokens)
- **Bedrock** - AWS (DeepSeek 95% cheaper, Qwen, GLM, Claude)
- **OpenAI** - GPT-4, GPT-3.5
- **Anthropic** - Claude (direct API)

## Architecture

```
Application Code
      ↓ depends on
  LLMProvider (PORT) ← abstraction
      ↑ implemented by
  OpenRouterProvider, MIMOProvider, etc. (ADAPTERS)
```

**Benefits:**
- ✅ Swap providers without changing code
- ✅ Easy testing with mock providers
- ✅ Standardized response format
- ✅ Cost tracking across providers
- ✅ Integrates with swarm-it-auth for credentials

## Quick Start

### 1. Install Dependencies

```bash
pip install openai anthropic boto3
```

### 2. Basic Usage

```python
from swarm_it.providers import get_provider

# Create provider (auto-loads credentials from swarm-it-auth)
provider = get_provider("openrouter")

# Make LLM call
response = provider.complete([
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "What is 2+2?"}
])

print(response.content)
print(f"Cost: ${response.cost_usd:.4f}")
print(f"Tokens: {response.total_tokens}")
```

### 3. With Certification

```python
from swarm_it.providers import get_provider
from swarm_it import certify

# Make LLM call
provider = get_provider("openrouter", model="meta-llama/llama-3.1-8b-instruct:free")
response = provider.complete([
    {"role": "user", "content": "Explain quantum computing"}
])

# Certify response
cert = certify(response.content)

if cert.decision.allowed:
    print(f"✓ Quality: R={cert.R:.3f}, S={cert.S:.3f}, N={cert.N:.3f}")
    print(response.content)
else:
    print(f"✗ Blocked: {cert.reason}")
```

## Providers

### OpenRouter (FREE!)

```python
provider = get_provider(
    "openrouter",
    api_key="sk-or-v1-...",  # Or load from swarm-it-auth
    model="meta-llama/llama-3.1-8b-instruct:free"
)

response = provider.complete([{"role": "user", "content": "Hello!"}])
```

**Free Models:**
- `meta-llama/llama-3.1-8b-instruct:free`
- `mistralai/mistral-7b-instruct:free`
- `google/gemma-2-9b-it:free`
- Check https://openrouter.ai/models?q=free

### MIMO (Xiaomi)

```python
provider = get_provider(
    "mimo",
    api_key="your-mimo-key",
    model="mimo-v2-flash"
)

response = provider.complete([{"role": "user", "content": "Hello!"}])
print(f"Cost: ${response.cost_usd:.4f}")  # ~$0.001
```

### Bedrock (AWS - Chinese Models)

```python
# DeepSeek - 95% cheaper than Claude!
provider = get_provider(
    "bedrock",
    model="deepseek-v3.2",  # No API key needed (uses AWS credentials)
    region="us-east-1"
)

response = provider.complete([{"role": "user", "content": "Hello!"}])
print(f"Cost: ${response.cost_usd:.4f}")  # ~$0.0002 for 1K tokens
```

**Available Models:**
- `deepseek-v3.2`, `deepseek-r1` (Chinese, very cheap)
- `qwen3-coder` (Alibaba, coding specialist)
- `glm-flash` (Zhipu AI, fastest & cheapest)
- `claude-haiku`, `claude-sonnet` (Anthropic)

### OpenAI

```python
provider = get_provider(
    "openai",
    api_key="sk-...",
    model="gpt-4o"
)

response = provider.complete([{"role": "user", "content": "Hello!"}])
```

### Anthropic (Direct)

```python
provider = get_provider(
    "anthropic",
    api_key="sk-ant-...",
    model="claude-3-5-sonnet-20241022"
)

response = provider.complete([{"role": "user", "content": "Hello!"}])
```

## Advanced Usage

### Cost Comparison

```python
from swarm_it.providers import get_provider

providers = {
    "OpenRouter (Free)": get_provider("openrouter"),
    "MIMO": get_provider("mimo"),
    "Bedrock DeepSeek": get_provider("bedrock", model="deepseek-v3.2"),
    "OpenAI": get_provider("openai", model="gpt-4o"),
}

prompt = [{"role": "user", "content": "Explain quantum entanglement"}]

for name, provider in providers.items():
    response = provider.complete(prompt)
    cost = response.cost_usd or 0.0
    print(f"{name:20s}: ${cost:.6f} ({response.total_tokens} tokens)")
```

### Testing with Mock Provider

```python
from swarm_it.providers.base import LLMProvider, LLMResponse

class MockProvider(LLMProvider):
    def complete(self, messages, **kwargs):
        return LLMResponse(
            content="Mock response",
            model="mock",
            provider="mock",
            total_tokens=10,
            cost_usd=0.0
        )

# Use in tests
provider = MockProvider()
response = provider.complete([{"role": "user", "content": "test"}])
```

### Custom Configuration

```python
from swarm_it.providers import get_provider, LLMProviderConfig

config = LLMProviderConfig(
    model="meta-llama/llama-3.1-8b-instruct:free",
    temperature=0.5,
    max_tokens=1000,
)

provider = get_provider("openrouter", config=config)
```

## Integration with swarm-it-auth

Credentials are automatically loaded from swarm-it-auth:

```python
# No API key needed - auto-loads from swarm-it-auth
provider = get_provider("openrouter")

# swarm-it-auth checks:
# 1. OPENROUTER_API_KEY env var
# 2. ../yrsn/keys/4-openrouter.md file
# 3. swarm-it-auth credential store
```

## Cost Savings

| Provider | Model | Cost/1M tokens | vs GPT-4o |
|----------|-------|----------------|-----------|
| OpenRouter | LLaMA 3.1 (free) | **$0** | **100% savings** |
| Bedrock | DeepSeek-V3.2 | $0.14/$0.28 | **95% savings** |
| Bedrock | Qwen3 Coder | $0.10/$0.30 | **97% savings** |
| Bedrock | GLM Flash | $0.08/$0.24 | **98% savings** |
| MIMO | mimo-v2-flash | $1.00/$3.00 | **60% savings** |
| OpenAI | GPT-4o | $2.50/$10.00 | Baseline |

## Examples

See `examples/` directory:
- `examples/providers/basic_usage.py`
- `examples/providers/cost_comparison.py`
- `examples/providers/with_certification.py`

## API Reference

### LLMProvider (PORT)

```python
class LLMProvider(ABC):
    def complete(messages: List[Dict], **kwargs) -> LLMResponse
    def list_models() -> List[str]
    def estimate_cost(input_tokens, output_tokens) -> Optional[float]
```

### LLMResponse

```python
@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Optional[float]
    raw: Dict[str, Any]
```

## Contributing

To add a new provider:

1. Create `swarm_it/providers/your_provider.py`
2. Implement `LLMProvider` interface
3. Add to `factory.py` and `__init__.py`
4. Add tests in `tests/providers/`

## License

Apache 2.0 (see main swarm-it-adk LICENSE)
