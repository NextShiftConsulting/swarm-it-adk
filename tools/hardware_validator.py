# swarm_it/tools/hardware_validator.py
import asyncio
import json
from pydantic import BaseModel, Field
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Define the connection parameters to our compiled Go binary
server_params = StdioServerParameters(
    command="./rsct-mcp-server", 
    args=[],
    env={"ANTHROPIC_API_KEY": "your-api-key-here"} # Pass necessary env vars
)

class HardwareValidationRequest(BaseModel):
    board_id: str = Field(..., description="The target board, e.g., 'esp32' or 'stm32'")
    code: str = Field(..., description="The BARR-C compliant C firmware code")

class HardwareValidationResponse(BaseModel):
    status: str
    assertions_passed: int
    assertions_failed: int
    diff_summary: list[str]
    raw_logs: dict

async def run_hardware_validation(request: HardwareValidationRequest) -> HardwareValidationResponse:
    """
    Connects to the RSCT Go MCP Server over stdio, triggering the physical 
    camera observation and hardware assertion diffing.
    """
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. Handshake with the Go Server
            await session.initialize()
            
            # 2. Execute the tool
            result = await session.call_tool(
                name="validate_physical_hardware", 
                arguments={
                    "board_id": request.board_id,
                    "code": request.code
                }
            )
            
            # 3. Parse the JSON response from Go back into our Pydantic model
            # The Go server returns the data wrapped in a text content block
            raw_data = json.loads(result.content[0].text)
            
            failed_assertions = [a for a in raw_data.get("assertions", []) if a.get("outcome") != "pass"]
            
            return HardwareValidationResponse(
                status=raw_data.get("status", "error"),
                assertions_passed=len(raw_data.get("assertions", [])) - len(failed_assertions),
                assertions_failed=len(failed_assertions),
                diff_summary=[a.get("diff_summary", "") for a in failed_assertions],
                raw_logs=raw_data
            )

# Example usage within a Swarm-It agent node:
if __name__ == "__main__":
    test_req = HardwareValidationRequest(
        board_id="esp32",
        code="void LED_Init(void) { /* ... */ }"
    )
    
    response = asyncio.run(run_hardware_validation(test_req))
    print(f"Hardware Test Status: {response.status}")