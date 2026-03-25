"""
RSCT Vision Tools for Swarm-It ADK.

Provides Python wrappers for rsct-vision MCP server tools:
- Research: Knowledge graph + vector search
- Spec: Generate hardware assertion DSL
- Implement: Generate BARR-C compliant code
- Test: Flash + observe + evaluate assertions
- Pipeline: Full R→S→I→T workflow

Usage:
    from swarm_it.rsct_tools import RSCTClient

    client = RSCTClient()

    # Full pipeline
    result = await client.run_pipeline(
        board_id="stm32f4",
        task_summary="Verify boot LED sequence"
    )

    # Individual phases
    research = await client.research(task_summary="LED boot sequence")
    spec = await client.spec(task_summary="...", research_input=research)
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .mcp_tools import Tool, ToolMetadata, ToolCategory, ToolRegistry


# =============================================================================
# PYDANTIC MODELS (JSON-safe request/response)
# =============================================================================

class ResearchPattern(BaseModel):
    """Pattern from knowledge graph."""
    pattern_id: str
    title: str
    description: str
    board_ids: List[str] = []
    tags: List[str] = []
    confidence: float


class ResearchResult(BaseModel):
    """Result of Research phase."""
    status: str
    patterns: List[ResearchPattern] = []
    notes: str = ""


class Assertion(BaseModel):
    """Hardware behavior assertion."""
    name: str
    dsl: str
    description: str = ""
    tags: List[str] = []


class SpecResult(BaseModel):
    """Result of Specification phase."""
    status: str
    assertions: List[Assertion] = []
    notes: str = ""


class GeneratedFile(BaseModel):
    """Generated code file."""
    path: str
    language: str
    style_clean: bool


class ImplementResult(BaseModel):
    """Result of Implementation phase."""
    status: str
    files: List[GeneratedFile] = []
    iterations_used: int = 0
    notes: str = ""


class AssertionResult(BaseModel):
    """Result of evaluating one assertion."""
    name: str
    dsl: str
    outcome: str  # pass, fail, error
    message: str = ""
    diff_summary: str = ""


class TestResult(BaseModel):
    """Result of Testing phase."""
    status: str
    assertions: List[AssertionResult] = []
    notes: str = ""


class PipelineResult(BaseModel):
    """Result of full RSCT pipeline."""
    research: ResearchResult
    spec: SpecResult
    implement: ImplementResult
    test: TestResult


# =============================================================================
# MCP CLIENT
# =============================================================================

@dataclass
class RSCTClientConfig:
    """Configuration for RSCT MCP client."""
    server_command: str = "./rsct-mcp-server"
    server_args: List[str] = field(default_factory=list)
    anthropic_api_key: Optional[str] = None

    def __post_init__(self):
        if self.anthropic_api_key is None:
            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")


class RSCTClient:
    """
    Client for rsct-vision MCP server.

    Wraps the Go MCP server that implements RSCT workflow phases.
    """

    def __init__(self, config: Optional[RSCTClientConfig] = None):
        self.config = config or RSCTClientConfig()
        self._server_params = StdioServerParameters(
            command=self.config.server_command,
            args=self.config.server_args,
            env={"ANTHROPIC_API_KEY": self.config.anthropic_api_key or ""}
        )

    async def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool and return the result."""
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name=name, arguments=arguments)

                # Parse JSON from text content block
                if result.content and len(result.content) > 0:
                    return json.loads(result.content[0].text)
                return {}

    async def research(
        self,
        task_summary: str,
        board_id: str = "",
        max_patterns: int = 5,
    ) -> ResearchResult:
        """
        Run Research phase: search knowledge graph for relevant patterns.

        Args:
            task_summary: Description of the task
            board_id: Target board ID (optional)
            max_patterns: Maximum patterns to return

        Returns:
            ResearchResult with found patterns
        """
        result = await self._call_tool("rsct_research", {
            "task_summary": task_summary,
            "board_id": board_id,
            "max_patterns": max_patterns,
        })
        return ResearchResult(**result)

    async def spec(
        self,
        task_summary: str,
        board_id: str = "",
        research_input: Optional[ResearchResult] = None,
    ) -> SpecResult:
        """
        Run Specification phase: generate hardware assertion DSL.

        Args:
            task_summary: Description of the task
            board_id: Target board ID
            research_input: Output from Research phase

        Returns:
            SpecResult with generated assertions
        """
        args = {
            "task_summary": task_summary,
            "board_id": board_id,
        }
        if research_input:
            args["research_input"] = research_input.model_dump()

        result = await self._call_tool("rsct_spec", args)
        return SpecResult(**result)

    async def implement(
        self,
        task_summary: str,
        spec_input: SpecResult,
        board_id: str = "",
        output_dir: str = "./output",
    ) -> ImplementResult:
        """
        Run Implementation phase: generate BARR-C compliant code.

        Args:
            task_summary: Description of the task
            spec_input: Output from Spec phase
            board_id: Target board ID
            output_dir: Directory for generated code

        Returns:
            ImplementResult with generated files
        """
        result = await self._call_tool("rsct_implement", {
            "task_summary": task_summary,
            "board_id": board_id,
            "spec_input": spec_input.model_dump(),
            "output_dir": output_dir,
        })
        return ImplementResult(**result)

    async def test(
        self,
        spec_input: SpecResult,
        impl_input: ImplementResult,
        board_id: str = "",
        flash_command: Optional[List[str]] = None,
        camera_device: str = "",
        mock_video: str = "",
    ) -> TestResult:
        """
        Run Testing phase: flash, observe, evaluate assertions.

        Args:
            spec_input: Assertions to evaluate
            impl_input: Code to flash
            board_id: Target board ID
            flash_command: Command to flash firmware
            camera_device: Camera device path
            mock_video: Mock video for CI testing

        Returns:
            TestResult with assertion outcomes
        """
        result = await self._call_tool("rsct_test", {
            "board_id": board_id,
            "spec_input": spec_input.model_dump(),
            "impl_input": impl_input.model_dump(),
            "flash_command": flash_command or [],
            "camera_device": camera_device,
            "mock_video": mock_video,
        })
        return TestResult(**result)

    async def run_pipeline(
        self,
        board_id: str,
        task_summary: str,
        output_dir: str = "./output",
        flash_command: Optional[List[str]] = None,
        camera_device: str = "",
    ) -> PipelineResult:
        """
        Run full RSCT pipeline: Research → Spec → Implement → Test.

        Args:
            board_id: Target board ID
            task_summary: Description of the task
            output_dir: Directory for generated code
            flash_command: Command to flash firmware
            camera_device: Camera device path

        Returns:
            PipelineResult with all phase outputs
        """
        result = await self._call_tool("rsct_pipeline", {
            "board_id": board_id,
            "task_summary": task_summary,
            "output_dir": output_dir,
            "flash_command": flash_command or [],
            "camera_device": camera_device,
        })
        return PipelineResult(**result)

    async def validate_hardware(
        self,
        board_id: str,
        code: str,
    ) -> TestResult:
        """
        Legacy hardware validation (alias for rsct_test with inline code).

        Args:
            board_id: Target board ID
            code: Firmware code to validate

        Returns:
            TestResult with assertion outcomes
        """
        result = await self._call_tool("validate_physical_hardware", {
            "board_id": board_id,
            "code": code,
        })
        return TestResult(**result)


# =============================================================================
# MCP TOOL WRAPPERS (for ToolRegistry)
# =============================================================================

class RSCTResearchTool(Tool):
    """RSCT Research phase tool."""

    def __init__(self, client: RSCTClient):
        self.client = client

    def execute(self, task_summary: str, board_id: str = "", max_patterns: int = 5) -> Dict[str, Any]:
        return asyncio.run(self.client.research(task_summary, board_id, max_patterns)).model_dump()

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="rsct-research",
            category=ToolCategory.UTILITY,
            version="0.1.0",
            description="RSCT Research: search knowledge graph for hardware patterns",
            tags=["rsct", "research", "hardware", "patterns"],
        )


class RSCTSpecTool(Tool):
    """RSCT Specification phase tool."""

    def __init__(self, client: RSCTClient):
        self.client = client

    def execute(self, task_summary: str, board_id: str = "", research_input: Optional[Dict] = None) -> Dict[str, Any]:
        ri = ResearchResult(**research_input) if research_input else None
        return asyncio.run(self.client.spec(task_summary, board_id, ri)).model_dump()

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="rsct-spec",
            category=ToolCategory.UTILITY,
            version="0.1.0",
            description="RSCT Spec: generate hardware assertion DSL",
            tags=["rsct", "spec", "assertions", "dsl"],
        )


class RSCTTestTool(Tool):
    """RSCT Testing phase tool."""

    def __init__(self, client: RSCTClient):
        self.client = client

    def execute(self, board_id: str, code: str) -> Dict[str, Any]:
        return asyncio.run(self.client.validate_hardware(board_id, code)).model_dump()

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="rsct-test",
            category=ToolCategory.VALIDATOR,
            version="0.1.0",
            description="RSCT Test: flash, observe, and validate hardware behavior",
            tags=["rsct", "test", "hardware", "validation", "vision"],
        )


class RSCTPipelineTool(Tool):
    """RSCT full pipeline tool."""

    def __init__(self, client: RSCTClient):
        self.client = client

    def execute(self, board_id: str, task_summary: str, output_dir: str = "./output") -> Dict[str, Any]:
        return asyncio.run(self.client.run_pipeline(board_id, task_summary, output_dir)).model_dump()

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="rsct-pipeline",
            category=ToolCategory.UTILITY,
            version="0.1.0",
            description="RSCT Pipeline: full Research → Spec → Implement → Test workflow",
            tags=["rsct", "pipeline", "hardware", "e2e"],
        )


def register_rsct_tools(registry: ToolRegistry, config: Optional[RSCTClientConfig] = None) -> None:
    """
    Register RSCT tools in the global registry.

    Args:
        registry: Tool registry to register in
        config: RSCT client configuration
    """
    client = RSCTClient(config)

    registry.register("rsct-research", RSCTResearchTool(client))
    registry.register("rsct-spec", RSCTSpecTool(client))
    registry.register("rsct-test", RSCTTestTool(client), aliases=["hardware-validator"])
    registry.register("rsct-pipeline", RSCTPipelineTool(client))
