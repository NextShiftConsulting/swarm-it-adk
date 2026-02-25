#!/bin/bash
# Deploy Swarm-It API to api.swarms.network
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Lambda function already created via Terraform
#   - OPENAI_API_KEY set (for embedding generation)
#
# Usage: ./scripts/deploy-api.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
FUNCTION_NAME="swarmit-api"
REGION="${AWS_REGION:-us-east-1}"

echo "=== Deploying Swarm-It API ==="
echo ""

# Build the package
echo "Step 1: Building Lambda package..."
"$SCRIPT_DIR/build-lambda.sh"

# Check if zip exists
ZIP_FILE="$ROOT_DIR/dist/lambda_api.zip"
if [ ! -f "$ZIP_FILE" ]; then
    echo "Error: $ZIP_FILE not found"
    exit 1
fi

# Deploy to Lambda
echo ""
echo "Step 2: Deploying to Lambda..."
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP_FILE" \
    --region "$REGION" \
    --output text \
    --query 'FunctionArn'

echo ""
echo "Step 3: Waiting for update to complete..."
aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION"

# Update environment variables (if OPENAI_API_KEY is set)
if [ -n "$OPENAI_API_KEY" ]; then
    echo ""
    echo "Step 4: Updating environment variables..."
    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --environment "Variables={OPENAI_API_KEY=$OPENAI_API_KEY,ENVIRONMENT=production,LOG_LEVEL=INFO}" \
        --region "$REGION" \
        --output text \
        --query 'FunctionArn' > /dev/null
fi

# Test the deployment
echo ""
echo "Step 5: Testing health endpoint..."
HEALTH=$(curl -s "https://api.swarms.network/health" 2>/dev/null || echo '{"error": "failed to connect"}')
echo "Response: $HEALTH"

echo ""
echo "=== Deployment complete ==="
echo ""
echo "API Endpoints:"
echo "  POST https://api.swarms.network/api/v1/certify"
echo "  POST https://api.swarms.network/api/v1/validate"
echo "  POST https://api.swarms.network/api/v1/audit"
echo "  GET  https://api.swarms.network/api/v1/statistics"
echo "  GET  https://api.swarms.network/api/v1/certificates/{id}"
echo "  GET  https://api.swarms.network/health"
echo "  GET  https://api.swarms.network/metrics"
