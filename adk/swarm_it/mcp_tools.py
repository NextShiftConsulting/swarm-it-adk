"""
MCP-Style Tool Integration - Stripe Minions Pattern

Inspired by Stripe's "Toolshed" (400+ MCP tools):
- Standardized tool interface (Model Context Protocol)
- Plugin discovery and registration
- Version management
- Tool categories (embeddings, rotors, validators, etc.)

Pattern: Pluggable tool ecosystem with standard interface
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import inspect


class ToolCategory(Enum):
    """Tool categories for organization."""
    EMBEDDING = "embedding"        # Text embedding providers
    ROTOR = "rotor"               # RSN decomposition rotors
    VALIDATOR = "validator"        # Quality validators
    PREPROCESSOR = "preprocessor"  # Text preprocessing
    POSTPROCESSOR = "postprocessor" # Certificate post-processing
    INTEGRATION = "integration"    # External integrations
    UTILITY = "utility"           # Helper utilities


@dataclass
class ToolMetadata:
    """Metadata for registered tool."""
    name: str
    category: ToolCategory
    version: str
    description: str
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)  # Dependencies
    cost_per_call: Optional[float] = None  # If external API


class Tool(ABC):
    """
    Base class for MCP-compatible tools.

    All tools must implement:
    - execute(): Main tool logic
    - metadata: Tool metadata property
    """

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Execute tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Tool output
        """
        pass

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Return tool metadata."""
        pass

    def validate_params(self, **kwargs) -> bool:
        """
        Validate input parameters (optional override).

        Returns:
            True if valid, False otherwise
        """
        return True


class ToolRegistry:
    """
    MCP-style tool registry (Stripe's "Toolshed" pattern).

    Manages tool registration, discovery, and execution.

    Usage:
        registry = ToolRegistry()

        # Register tool
        registry.register("openai-embeddings", OpenAIEmbeddingTool())

        # Discover tools
        tools = registry.list_by_category(ToolCategory.EMBEDDING)

        # Execute tool
        result = registry.execute("openai-embeddings", text="Hello world")
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._aliases: Dict[str, str] = {}

    def register(
        self,
        name: str,
        tool: Tool,
        aliases: Optional[List[str]] = None,
    ) -> None:
        """
        Register a tool in the registry.

        Args:
            name: Unique tool identifier
            tool: Tool instance
            aliases: Alternative names for tool

        Raises:
            ValueError: If tool name already registered
        """
        if name in self._tools:
            raise ValueError(f"Tool '{name}' already registered")

        self._tools[name] = tool

        # Register aliases
        if aliases:
            for alias in aliases:
                if alias in self._aliases:
                    raise ValueError(f"Alias '{alias}' already registered")
                self._aliases[alias] = name

    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]

        # Remove aliases
        self._aliases = {k: v for k, v in self._aliases.items() if v != name}

    def get(self, name: str) -> Optional[Tool]:
        """
        Get tool by name or alias.

        Args:
            name: Tool name or alias

        Returns:
            Tool instance or None if not found
        """
        # Check aliases first
        actual_name = self._aliases.get(name, name)
        return self._tools.get(actual_name)

    def execute(self, name: str, **kwargs) -> Any:
        """
        Execute tool by name.

        Args:
            name: Tool name or alias
            **kwargs: Tool parameters

        Returns:
            Tool output

        Raises:
            ValueError: If tool not found or params invalid
        """
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")

        if not tool.validate_params(**kwargs):
            raise ValueError(f"Invalid parameters for tool '{name}'")

        return tool.execute(**kwargs)

    def list_all(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def list_by_category(self, category: ToolCategory) -> List[str]:
        """List tools by category."""
        return [
            name for name, tool in self._tools.items()
            if tool.metadata.category == category
        ]

    def list_by_tag(self, tag: str) -> List[str]:
        """List tools by tag."""
        return [
            name for name, tool in self._tools.items()
            if tag in tool.metadata.tags
        ]

    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """Get tool metadata."""
        tool = self.get(name)
        return tool.metadata if tool else None

    def search(self, query: str) -> List[str]:
        """
        Search tools by name or description.

        Args:
            query: Search query

        Returns:
            List of matching tool names
        """
        query_lower = query.lower()
        matches = []

        for name, tool in self._tools.items():
            if query_lower in name.lower():
                matches.append(name)
            elif query_lower in tool.metadata.description.lower():
                matches.append(name)

        return matches


# Example tool implementations

class OpenAIEmbeddingTool(Tool):
    """OpenAI text embedding tool."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model

    def execute(self, text: str) -> List[float]:
        """Generate embedding for text."""
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)

        response = client.embeddings.create(
            model=self.model,
            input=text
        )

        return response.data[0].embedding

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="openai-embeddings",
            category=ToolCategory.EMBEDDING,
            version="1.0.0",
            description="OpenAI text embeddings (text-embedding-3-small)",
            author="OpenAI",
            tags=["embeddings", "openai", "text"],
            cost_per_call=0.00002,  # $0.02 per 1M tokens
        )


class YRSNRotorTool(Tool):
    """YRSN HybridSimplexRotor tool."""

    def __init__(self, embed_dim: int = 64):
        from yrsn.core.decomposition import HybridSimplexRotor
        self.rotor = HybridSimplexRotor(embed_dim=embed_dim)

    def execute(self, embedding: List[float]) -> Dict[str, float]:
        """Decompose embedding into R, S, N."""
        import torch

        # Convert to tensor
        if not isinstance(embedding, torch.Tensor):
            embedding = torch.tensor(embedding, dtype=torch.float32)

        # Ensure batch dimension
        if embedding.dim() == 1:
            embedding = embedding.unsqueeze(0)

        # Decompose
        rsn_dict = self.rotor(embedding)

        return {
            "R": float(rsn_dict['R'][0].detach()),
            "S": float(rsn_dict['S'][0].detach()),
            "N": float(rsn_dict['N'][0].detach()),
        }

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="yrsn-rotor",
            category=ToolCategory.ROTOR,
            version="1.0.0",
            description="YRSN HybridSimplexRotor for RSN decomposition",
            author="YRSN",
            tags=["rotor", "rsn", "decomposition"],
            requires=["yrsn>=0.1.0"],
        )


class QualityGateTool(Tool):
    """Quality gate validator tool."""

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = thresholds or {
            "kappa": 0.7,
            "R": 0.3,
            "S": 0.4,
            "N": 0.5,
        }

    def execute(self, R: float, S: float, N: float) -> Dict[str, Any]:
        """Apply quality gates."""
        kappa = min(R, S)

        # Gate 1: Integrity
        if N > 0.7:
            return {
                "decision": "REJECT",
                "gate_reached": 1,
                "reason": f"High noise: N={N:.3f} (integrity gate)",
            }

        # Gate 2: Noise
        if N > self.thresholds["N"]:
            return {
                "decision": "BLOCK",
                "gate_reached": 2,
                "reason": f"Noise threshold: N={N:.3f} > {self.thresholds['N']}",
            }

        # Gate 3: Relevance
        if R < self.thresholds["R"]:
            return {
                "decision": "BLOCK",
                "gate_reached": 3,
                "reason": f"Low relevance: R={R:.3f} < {self.thresholds['R']}",
            }

        # Gate 4: Stability
        if S < self.thresholds["S"]:
            return {
                "decision": "REPAIR",
                "gate_reached": 4,
                "reason": f"Low stability: S={S:.3f} < {self.thresholds['S']}",
            }

        # Gate 5: Compatibility
        if kappa < self.thresholds["kappa"]:
            return {
                "decision": "BLOCK",
                "gate_reached": 5,
                "reason": f"Low compatibility: kappa={kappa:.3f} < {self.thresholds['kappa']}",
            }

        # All gates passed
        return {
            "decision": "EXECUTE",
            "gate_reached": 5,
            "reason": f"All gates passed (kappa={kappa:.3f}, R={R:.3f}, S={S:.3f})",
        }

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="quality-gates",
            category=ToolCategory.VALIDATOR,
            version="1.0.0",
            description="5-gate RSCT quality validator",
            author="YRSN",
            tags=["validation", "quality", "gates"],
        )


# Global registry instance
_global_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get global tool registry."""
    return _global_registry


def register_default_tools(
    openai_api_key: Optional[str] = None,
    thresholds: Optional[Dict[str, float]] = None,
) -> None:
    """
    Register default tools in global registry.

    Args:
        openai_api_key: OpenAI API key (if available)
        thresholds: Quality gate thresholds
    """
    registry = get_registry()

    # Register YRSN rotor
    try:
        registry.register("yrsn-rotor", YRSNRotorTool(), aliases=["rotor"])
    except Exception:
        pass  # YRSN may not be installed

    # Register quality gates
    registry.register("quality-gates", QualityGateTool(thresholds), aliases=["gates"])

    # Register OpenAI embeddings (if key provided)
    if openai_api_key:
        registry.register(
            "openai-embeddings",
            OpenAIEmbeddingTool(openai_api_key),
            aliases=["embeddings", "openai"]
        )
