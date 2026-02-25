#!/bin/bash
# Build Lambda deployment package for api.swarms.network
#
# Creates lambda_api.zip containing:
#   - sidecar code (FastAPI app)
#   - yrsn core library
#   - Python dependencies
#
# Usage: ./scripts/build-lambda.sh
# Output: dist/lambda_api.zip

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build/lambda"
YRSN_DIR="${YRSN_SRC:-/Users/rudy/GitHub/yrsn/src}"

echo "=== Building Lambda package ==="
echo "Root: $ROOT_DIR"
echo "YRSN: $YRSN_DIR"

# Clean
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Install dependencies for Lambda (Linux x86_64)
echo "Installing dependencies for Lambda..."
pip install -q -t "$BUILD_DIR" \
    fastapi \
    pydantic \
    mangum \
    httpx \
    openai \
    prometheus-client \
    --platform manylinux2014_x86_64 \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all:

# Copy sidecar code
echo "Copying sidecar code..."
cp "$ROOT_DIR/sidecar/handler.py" "$BUILD_DIR/"
cp "$ROOT_DIR/sidecar/main.py" "$BUILD_DIR/"
cp "$ROOT_DIR/sidecar/infra.py" "$BUILD_DIR/"
cp "$ROOT_DIR/sidecar/ports.py" "$BUILD_DIR/"
cp "$ROOT_DIR/sidecar/adapters.py" "$BUILD_DIR/"
cp "$ROOT_DIR/sidecar/bootstrap.py" "$BUILD_DIR/"

# Copy subdirectories
cp -r "$ROOT_DIR/sidecar/api" "$BUILD_DIR/"
cp -r "$ROOT_DIR/sidecar/engine" "$BUILD_DIR/"
cp -r "$ROOT_DIR/sidecar/store" "$BUILD_DIR/"
cp -r "$ROOT_DIR/sidecar/a2a" "$BUILD_DIR/"
cp -r "$ROOT_DIR/sidecar/config" "$BUILD_DIR/"

# Copy yrsn
echo "Copying yrsn library..."
if [ -d "$YRSN_DIR/yrsn" ]; then
    cp -r "$YRSN_DIR/yrsn" "$BUILD_DIR/"
else
    echo "Warning: yrsn not found at $YRSN_DIR"
    echo "Set YRSN_SRC environment variable to yrsn/src path"
fi

# Remove pycache and tests
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true

# Create zip
echo "Creating zip..."
cd "$BUILD_DIR"
zip -q -r "$DIST_DIR/lambda_api.zip" .

SIZE=$(du -h "$DIST_DIR/lambda_api.zip" | cut -f1)
echo ""
echo "=== Build complete ==="
echo "Output: $DIST_DIR/lambda_api.zip ($SIZE)"
echo ""
echo "Deploy with:"
echo "  aws lambda update-function-code \\"
echo "    --function-name swarmit-api \\"
echo "    --zip-file fileb://$DIST_DIR/lambda_api.zip"
