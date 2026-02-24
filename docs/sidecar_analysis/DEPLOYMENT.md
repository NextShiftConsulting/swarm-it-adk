# Sidecar Deployment Guide

## Deployment Options

| Mode | Best For | Complexity |
|------|----------|------------|
| [Docker Compose](#docker-compose) | Local dev, single-node | Low |
| [Kubernetes](#kubernetes) | Production, multi-node | Medium |
| [MCP Server](#mcp-server) | Claude Desktop, IDE integration | Low |
| [Standalone](#standalone) | Testing, development | Lowest |

---

## Docker Compose

### Quick Start

```bash
cd sidecar
docker-compose up -d
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  swarm-it:
    build: .
    ports:
      - "8080:8080"
    environment:
      - SWARM_IT_DB_PATH=/data/certificates.db
      - KAPPA_THRESHOLD=0.7
    volumes:
      - swarm-data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 3s
      retries: 3

volumes:
  swarm-data:
```

### With Your AI App

```yaml
version: '3.8'

services:
  my-ai-app:
    image: my-ai-app:latest
    environment:
      SWARM_IT_URL: http://swarm-it:8080
    depends_on:
      swarm-it:
        condition: service_healthy

  swarm-it:
    image: swarmit/sidecar:latest
    ports:
      - "8080:8080"
    volumes:
      - swarm-data:/data

volumes:
  swarm-data:
```

---

## Kubernetes

### Pod Sidecar Pattern

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ai-workload
  labels:
    app: ai-workload
spec:
  containers:
  # Your AI application
  - name: ai-app
    image: my-ai-app:latest
    env:
    - name: SWARM_IT_URL
      value: "http://localhost:8080"
    ports:
    - containerPort: 3000

  # Swarm-It sidecar
  - name: swarm-it
    image: swarmit/sidecar:latest
    ports:
    - containerPort: 8080
    env:
    - name: SWARM_IT_DB_PATH
      value: "/data/certificates.db"
    volumeMounts:
    - name: cert-storage
      mountPath: /data
    livenessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 10
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      initialDelaySeconds: 3
      periodSeconds: 5

  volumes:
  - name: cert-storage
    emptyDir: {}
```

### Deployment + Service

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: swarm-it
spec:
  replicas: 3
  selector:
    matchLabels:
      app: swarm-it
  template:
    metadata:
      labels:
        app: swarm-it
    spec:
      containers:
      - name: swarm-it
        image: swarmit/sidecar:latest
        ports:
        - containerPort: 8080
        env:
        - name: SWARM_IT_DB_PATH
          value: "/data/certificates.db"
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: swarm-it
spec:
  selector:
    app: swarm-it
  ports:
  - port: 8080
    targetPort: 8080
  type: ClusterIP
```

### Helm Chart (coming soon)

```bash
helm repo add swarmit https://charts.swarm-it.dev
helm install swarm-it swarmit/sidecar
```

---

## MCP Server

Deploy as a Model Context Protocol server for Claude Desktop or IDE integration.

### Installation

```bash
# Clone and setup
git clone https://github.com/NextShiftConsulting/swarm-it.git
cd swarm-it/sidecar

# Install dependencies
pip install -e .
```

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "swarm-it": {
      "command": "python",
      "args": ["-m", "swarm_it.mcp_server"],
      "cwd": "/path/to/swarm-it/sidecar"
    }
  }
}
```

### MCP Server Implementation

Create `sidecar/mcp_server.py`:

```python
#!/usr/bin/env python3
"""
Swarm-It MCP Server

Exposes RSCT certification as MCP tools for Claude Desktop.
"""

import json
import sys
from typing import Any

from engine.rsct import RSCTEngine
from store.certificates import CertificateStore

engine = RSCTEngine()
store = CertificateStore()


def handle_request(request: dict) -> dict:
    """Handle MCP request."""
    method = request.get("method")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "certify",
                    "description": "Certify a prompt for RSCT compliance",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string", "description": "Prompt to certify"},
                            "context": {"type": "string", "description": "Optional context"},
                        },
                        "required": ["prompt"],
                    },
                },
                {
                    "name": "validate",
                    "description": "Submit post-execution validation feedback",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "certificate_id": {"type": "string"},
                            "validation_type": {"type": "string", "enum": ["TYPE_I", "TYPE_II", "TYPE_III", "TYPE_IV", "TYPE_V", "TYPE_VI"]},
                            "score": {"type": "number"},
                            "failed": {"type": "boolean"},
                        },
                        "required": ["certificate_id", "validation_type", "score", "failed"],
                    },
                },
                {
                    "name": "get_certificate",
                    "description": "Get a certificate by ID",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "certificate_id": {"type": "string"},
                        },
                        "required": ["certificate_id"],
                    },
                },
            ]
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "certify":
            cert = engine.certify(
                prompt=args["prompt"],
                context=args.get("context"),
            )
            store.store(cert)
            return {"content": [{"type": "text", "text": json.dumps(cert, indent=2)}]}

        elif tool_name == "validate":
            result = engine.record_validation(
                certificate_id=args["certificate_id"],
                validation_type=args["validation_type"],
                score=args["score"],
                failed=args["failed"],
            )
            return {"content": [{"type": "text", "text": json.dumps({"recorded": True, "adjustment": result})}]}

        elif tool_name == "get_certificate":
            cert = store.get(args["certificate_id"])
            if cert:
                return {"content": [{"type": "text", "text": json.dumps(cert, indent=2)}]}
            return {"content": [{"type": "text", "text": "Certificate not found"}], "isError": True}

    return {"error": {"code": -32601, "message": "Method not found"}}


def main():
    """MCP server main loop."""
    # Send server info
    print(json.dumps({
        "jsonrpc": "2.0",
        "id": 0,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "swarm-it", "version": "0.1.0"},
        }
    }), flush=True)

    # Handle requests
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_request(request)
            response["jsonrpc"] = "2.0"
            response["id"] = request.get("id")
            print(json.dumps(response), flush=True)
        except Exception as e:
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": request.get("id") if "request" in dir() else None,
                "error": {"code": -32603, "message": str(e)},
            }), flush=True)


if __name__ == "__main__":
    main()
```

### Testing MCP Server

```bash
# Test locally
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m mcp_server

# Expected output:
# {"tools": [{"name": "certify", ...}, {"name": "validate", ...}]}
```

---

## Standalone

### Direct Python

```bash
cd sidecar
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

### With Hot Reload (Development)

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

### Environment Setup

```bash
export SWARM_IT_DB_PATH=./certificates.db
export KAPPA_THRESHOLD=0.7
export PORT=8080

python main.py
```

---

## Verification

After deployment, verify with:

```bash
# Health check
curl http://localhost:8080/health
# {"status": "healthy", "service": "swarm-it-sidecar"}

# Test certification
curl -X POST http://localhost:8080/api/v1/certify \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2+2?"}'

# Expected: certificate with decision: "EXECUTE"
```

---

## Production Checklist

- [ ] Set `SWARM_IT_DB_PATH` for persistence
- [ ] Configure health checks
- [ ] Set up log aggregation
- [ ] Add Prometheus metrics endpoint
- [ ] Configure rate limiting (nginx/envoy)
- [ ] Enable TLS termination
- [ ] Set resource limits (K8s)
- [ ] Configure backup for certificate DB
