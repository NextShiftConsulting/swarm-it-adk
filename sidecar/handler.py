"""
AWS Lambda handler for Swarm-It API.

Wraps the FastAPI application using Mangum for Lambda compatibility.
Deployed to api.swarms.network via API Gateway.
"""

from mangum import Mangum
from main import app

# Lambda entry point - called by AWS Lambda runtime
main = Mangum(app, lifespan="off")
