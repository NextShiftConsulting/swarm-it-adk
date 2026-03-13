"""
SwarmFactory - High-level API for creating multi-provider agent swarms.

Simplifies swarm creation to a single function call with config-driven setup.
Handles:
- Provider instantiation (auto-loads credentials)
- Agent wrapper creation
- SwarmExecutor configuration
- RSCT certification

Example:
    from swarm_it.swarm_factory import create_swarm

    swarm = create_swarm({
        "name": "research_team",
        "agents": [
            {
                "name": "Researcher",
                "provider": "openrouter",
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "role": "Research and analysis",
                "system_prompt": "You are a research analyst..."
            }
        ]
    })

    results = swarm.execute("Analyze quantum computing")
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .providers import get_provider, LLMProvider


@dataclass
class AgentConfig:
    """Configuration for a single agent."""
    name: str
    provider: str  # "openrouter", "mimo", "bedrock", etc.
    model: str
    role: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 500


@dataclass
class SwarmConfig:
    """Configuration for an agent swarm."""
    name: str
    agents: List[Dict[str, Any]]
    certifier_thresholds: Optional[Dict[str, float]] = None
    description: Optional[str] = None


class ProviderAgentWrapper:
    """
    Wraps swarm-it-adk LLMProvider for use with swarm executors.

    This adapter allows LLMProviders to be used as agents in swarm systems
    that expect a specific interface (name, role, execute method).
    """

    def __init__(
        self,
        name: str,
        role: str,
        system_prompt: str,
        provider: LLMProvider,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ):
        """
        Initialize agent wrapper.

        Args:
            name: Agent name
            role: Agent role description
            system_prompt: System prompt for agent behavior
            provider: LLMProvider instance
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        """
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.provider_impl = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = provider.model

    def execute(self, prompt: str) -> 'AgentOutput':
        """
        Execute agent with given prompt.

        Args:
            prompt: User prompt

        Returns:
            AgentOutput with response, metadata, and cost tracking
        """
        # Import here to avoid circular dependency
        from dataclasses import dataclass

        @dataclass
        class AgentOutput:
            """Agent execution output."""
            agent_name: str
            provider: str
            prompt: str
            response: str
            metadata: Dict[str, Any]

        # Call LLMProvider
        response = self.provider_impl.complete(
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        return AgentOutput(
            agent_name=self.name,
            provider=response.provider,
            prompt=prompt,
            response=response.content,
            metadata={
                "model": response.model,
                "role": self.role,
                "cost_usd": response.cost_usd,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
            }
        )


def create_swarm(config: Dict[str, Any]) -> 'SwarmExecutor':
    """
    Create a multi-provider agent swarm from configuration.

    This is the main high-level API for swarm creation. Handles:
    - Provider instantiation with auto credential loading
    - Agent wrapper creation
    - SwarmExecutor configuration
    - RSCT certifier setup

    Args:
        config: Swarm configuration dict with:
            - name: Swarm name (str)
            - agents: List of agent configs (list of dicts)
            - certifier_thresholds: Optional RSCT thresholds (dict)
            - description: Optional swarm description (str)

    Returns:
        Configured SwarmExecutor ready for task execution

    Example:
        config = {
            "name": "research_team",
            "agents": [
                {
                    "name": "Researcher",
                    "provider": "openrouter",
                    "model": "meta-llama/llama-3.1-8b-instruct:free",
                    "role": "Research",
                    "system_prompt": "You are a researcher...",
                    "temperature": 0.7,
                    "max_tokens": 500,
                },
                {
                    "name": "Critic",
                    "provider": "bedrock",
                    "model": "deepseek-v3.2",
                    "role": "Critical analysis",
                    "system_prompt": "You are a critic...",
                }
            ],
            "certifier_thresholds": {
                "kappa": 0.1,
                "R": 0.1,
                "S": 0.1,
                "N": 0.95
            }
        }

        swarm = create_swarm(config)
        results = swarm.execute("Analyze quantum computing")
    """
    # Import SwarmExecutor and RSCTCertifier
    # Note: These need to be available in the environment
    try:
        from swarm_it import RSCTCertifier
        from swarm_it.base_swarm import SwarmExecutor
    except ImportError:
        # Fallback: try importing from experiments
        import sys
        from pathlib import Path
        exp_path = Path(__file__).parent.parent.parent.parent / 'yrsn-experiments' / 'exp' / 'multi_provider_swarms'
        if exp_path.exists() and str(exp_path) not in sys.path:
            sys.path.insert(0, str(exp_path))

        try:
            from base_swarm import SwarmExecutor, RSCTCertifier
        except ImportError:
            raise ImportError(
                "SwarmExecutor and RSCTCertifier not found. "
                "Ensure swarm_it or base_swarm is available."
            )

    # Parse config
    swarm_name = config.get("name", "agent_swarm")
    agents_config = config.get("agents", [])
    certifier_thresholds = config.get("certifier_thresholds")

    if not agents_config:
        raise ValueError("No agents specified in config")

    # Initialize certifier
    certifier = RSCTCertifier()
    if certifier_thresholds:
        certifier.thresholds = certifier_thresholds

    # Create swarm executor
    swarm = SwarmExecutor(team_name=swarm_name, certifier=certifier)

    # Create and add agents
    for agent_config in agents_config:
        # Validate required fields
        required = ["name", "provider", "model", "role", "system_prompt"]
        for field in required:
            if field not in agent_config:
                raise ValueError(f"Agent config missing required field: {field}")

        # Create provider (auto-loads credentials)
        provider = get_provider(
            agent_config["provider"],
            model=agent_config["model"]
        )

        # Create agent wrapper
        agent = ProviderAgentWrapper(
            name=agent_config["name"],
            role=agent_config["role"],
            system_prompt=agent_config["system_prompt"],
            provider=provider,
            temperature=agent_config.get("temperature", 0.7),
            max_tokens=agent_config.get("max_tokens", 500),
        )

        # Add to swarm
        swarm.add_agent(agent)

    return swarm


def create_agent(
    name: str,
    provider: str,
    model: str,
    role: str,
    system_prompt: str,
    **kwargs
) -> ProviderAgentWrapper:
    """
    Create a single agent (convenience function).

    Args:
        name: Agent name
        provider: Provider name ("openrouter", "bedrock", etc.)
        model: Model ID
        role: Agent role description
        system_prompt: System prompt for agent behavior
        **kwargs: Additional arguments (temperature, max_tokens)

    Returns:
        ProviderAgentWrapper instance

    Example:
        agent = create_agent(
            name="Researcher",
            provider="openrouter",
            model="meta-llama/llama-3.1-8b-instruct:free",
            role="Research",
            system_prompt="You are a researcher..."
        )
    """
    # Create provider
    llm_provider = get_provider(provider, model=model)

    # Create wrapper
    return ProviderAgentWrapper(
        name=name,
        role=role,
        system_prompt=system_prompt,
        provider=llm_provider,
        temperature=kwargs.get("temperature", 0.7),
        max_tokens=kwargs.get("max_tokens", 500),
    )


# Preset configurations for common swarm patterns
PRESET_SWARMS = {
    "research_team": {
        "name": "research_team",
        "description": "3-agent research team (free models)",
        "agents": [
            {
                "name": "Researcher",
                "provider": "openrouter",
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "role": "Information Gathering",
                "system_prompt": """You are a research analyst. Your role is to:
1. Identify key concepts and research questions
2. Survey relevant literature and evidence
3. Extract factual claims
4. Provide comprehensive background

Output: Structured research summary with key points."""
            },
            {
                "name": "Synthesizer",
                "provider": "openrouter",
                "model": "mistralai/mistral-7b-instruct:free",
                "role": "Synthesis & Integration",
                "system_prompt": """You are a synthesis specialist. Your role is to:
1. Integrate findings from multiple sources
2. Identify patterns and connections
3. Build coherent narratives
4. Resolve contradictions

Output: Integrated synthesis with insights."""
            },
            {
                "name": "Critic",
                "provider": "openrouter",
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "role": "Critical Analysis",
                "system_prompt": """You are a critical evaluator. Your role is to:
1. Assess validity of claims and evidence
2. Identify limitations and gaps
3. Evaluate methodological rigor
4. Provide constructive critique

Output: Critical evaluation with specific concerns."""
            }
        ]
    },
    "cost_optimized": {
        "name": "cost_optimized_team",
        "description": "Mixed provider team for cost optimization",
        "agents": [
            {
                "name": "Researcher",
                "provider": "openrouter",
                "model": "meta-llama/llama-3.1-8b-instruct:free",
                "role": "Research",
                "system_prompt": "You are a research analyst. Gather and analyze information."
            },
            {
                "name": "Synthesizer",
                "provider": "bedrock",
                "model": "deepseek-v3.2",
                "role": "Synthesis",
                "system_prompt": "You are a synthesis specialist. Integrate findings."
            },
            {
                "name": "Technical Reviewer",
                "provider": "bedrock",
                "model": "qwen3-coder",
                "role": "Technical Review",
                "system_prompt": "You are a technical reviewer. Evaluate technical accuracy."
            }
        ]
    }
}


def create_preset_swarm(preset: str) -> 'SwarmExecutor':
    """
    Create a swarm from a preset configuration.

    Args:
        preset: Preset name ("research_team", "cost_optimized")

    Returns:
        Configured SwarmExecutor

    Example:
        swarm = create_preset_swarm("research_team")
        results = swarm.execute("Analyze AI safety")
    """
    if preset not in PRESET_SWARMS:
        available = ", ".join(PRESET_SWARMS.keys())
        raise ValueError(f"Unknown preset: {preset}. Available: {available}")

    return create_swarm(PRESET_SWARMS[preset])
