#!/usr/bin/env python3
"""
Swarm-It MCP Server

Exposes RSCT certification as MCP tools for Claude Desktop / Claude Code.

Usage:
    python mcp_server.py

Claude Desktop config (~/.config/claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "swarm-it": {
          "command": "python",
          "args": ["mcp_server.py"],
          "cwd": "/path/to/swarm-it/sidecar",
          "env": {
            "PYTHONPATH": "/path/to/yrsn/src"
          }
        }
      }
    }
"""

import json
import sys
import os

# Ensure yrsn is available
YRSN_SRC = os.environ.get("YRSN_SRC", "/Users/rudy/GitHub/yrsn/src")
if YRSN_SRC not in sys.path:
    sys.path.insert(0, YRSN_SRC)

# Add sidecar to path
SIDECAR_DIR = os.path.dirname(os.path.abspath(__file__))
if SIDECAR_DIR not in sys.path:
    sys.path.insert(0, SIDECAR_DIR)

from engine.rsct import RSCTEngine
from store.certificates import CertificateStore

# Initialize engine and store
engine = RSCTEngine()
store = CertificateStore()


# =============================================================================
# MCP Tool Definitions
# =============================================================================

TOOLS = [
    {
        "name": "rsct_certify",
        "description": "Certify a prompt for RSCT compliance before LLM execution. Returns R/S/N scores and gate decision.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt to certify"
                },
                "context": {
                    "type": "string",
                    "description": "Optional context for the prompt"
                },
                "policy": {
                    "type": "string",
                    "description": "Policy name (default, strict, permissive)",
                    "default": "default"
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "rsct_validate",
        "description": "Submit post-execution validation feedback for a certificate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "certificate_id": {
                    "type": "string",
                    "description": "The certificate ID to validate"
                },
                "validation_type": {
                    "type": "string",
                    "enum": ["TYPE_I", "TYPE_II", "TYPE_III", "TYPE_IV", "TYPE_V", "TYPE_VI"],
                    "description": "Validation type (I=Groundedness, II=Contradiction, III=Inversion, IV=Drift, V=Reasoning, VI=Domain)"
                },
                "score": {
                    "type": "number",
                    "description": "Validation score (0-1)"
                },
                "failed": {
                    "type": "boolean",
                    "description": "Whether validation failed",
                    "default": False
                }
            },
            "required": ["certificate_id", "validation_type", "score"]
        }
    },
    {
        "name": "rsct_audit",
        "description": "Export certificates for compliance audit.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum certificates to return",
                    "default": 10
                },
                "format": {
                    "type": "string",
                    "enum": ["JSON", "SR11-7"],
                    "description": "Export format",
                    "default": "JSON"
                }
            }
        }
    },
    {
        "name": "rsct_health",
        "description": "Check RSCT engine health status.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


# =============================================================================
# Tool Handlers
# =============================================================================

def handle_certify(params: dict) -> dict:
    """Handle rsct_certify tool call."""
    prompt = params.get("prompt", "")
    context = params.get("context")
    policy = params.get("policy", "default")

    cert = engine.certify(
        prompt=prompt,
        context=context,
        policy=policy,
    )

    # Store certificate
    store.store(cert)

    # Format response
    return {
        "certificate_id": cert["id"],
        "R": cert["R"],
        "S": cert["S"],
        "N": cert["N"],
        "kappa": cert["kappa_gate"],
        "decision": cert["decision"],
        "allowed": cert["allowed"],
        "reason": cert["reason"],
        "gate_reached": cert["gate_reached"],
    }


def handle_validate(params: dict) -> dict:
    """Handle rsct_validate tool call."""
    cert_id = params.get("certificate_id")
    validation_type = params.get("validation_type")
    score = params.get("score")
    failed = params.get("failed", False)

    # Check certificate exists
    cert = store.get(cert_id)
    if cert is None:
        return {"error": f"Certificate not found: {cert_id}"}

    # Record validation (engine handles threshold adjustments)
    engine.record_validation(
        certificate_id=cert_id,
        validation_type=validation_type,
        score=score,
        failed=failed,
    )

    return {
        "recorded": True,
        "certificate_id": cert_id,
        "validation_type": validation_type,
        "score": score,
    }


def handle_audit(params: dict) -> dict:
    """Handle rsct_audit tool call."""
    limit = params.get("limit", 10)
    fmt = params.get("format", "JSON")

    certs = store.list(limit=limit)

    if fmt == "SR11-7":
        records = [engine.format_sr117(c) for c in certs]
    else:
        records = certs

    return {
        "certificate_count": len(records),
        "format": fmt,
        "records": records,
    }


def handle_health(params: dict) -> dict:
    """Handle rsct_health tool call."""
    return engine.health()


TOOL_HANDLERS = {
    "rsct_certify": handle_certify,
    "rsct_validate": handle_validate,
    "rsct_audit": handle_audit,
    "rsct_health": handle_health,
}


# =============================================================================
# MCP Protocol Implementation
# =============================================================================

def handle_request(request: dict) -> dict:
    """Handle MCP JSON-RPC request."""
    method = request.get("method")
    params = request.get("params", {})
    req_id = request.get("id")

    # Initialize
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "swarm-it",
                    "version": "0.1.0"
                }
            }
        }

    # List tools
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS
            }
        }

    # Call tool
    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            }

        try:
            result = handler(tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32000,
                    "message": str(e)
                }
            }

    # Notifications (no response needed)
    if method == "notifications/initialized":
        return None

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}"
        }
    }


def main():
    """MCP server main loop - reads JSON-RPC from stdin, writes to stdout."""
    # Log to stderr so it doesn't interfere with protocol
    sys.stderr.write("Swarm-It MCP Server starting...\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = handle_request(request)

            if response is not None:
                print(json.dumps(response), flush=True)

        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {e}"
                }
            }
            print(json.dumps(error_response), flush=True)
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
