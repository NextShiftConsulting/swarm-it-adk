#!/bin/bash
# Build container image for Swarm-It API
#
# Creates a Docker image with yrsn + PyTorch for full RSCT support.
# Pushes to ECR for deployment on ECS/Fargate.
#
# Usage: ./scripts/build-container.sh [--push]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
YRSN_DIR="${YRSN_SRC:-/Users/rudy/GitHub/yrsn/src}"

IMAGE_NAME="swarmit-api"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT="${AWS_ACCOUNT:-188494237500}"
ECR_REPO="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/$IMAGE_NAME"

echo "=== Building Swarm-It Container ==="
echo "Root: $ROOT_DIR"
echo "YRSN: $YRSN_DIR"

# Create build context
BUILD_DIR="$ROOT_DIR/build/container"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Copy sidecar code
echo "Copying sidecar..."
cp -r "$ROOT_DIR/sidecar/"* "$BUILD_DIR/"
rm -rf "$BUILD_DIR/__pycache__" "$BUILD_DIR/tests"

# Copy yrsn
echo "Copying yrsn..."
if [ -d "$YRSN_DIR/yrsn" ]; then
    cp -r "$YRSN_DIR/yrsn" "$BUILD_DIR/"
else
    echo "Error: yrsn not found at $YRSN_DIR"
    exit 1
fi

# Remove pycache
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

# Build image
echo "Building Docker image..."
cd "$BUILD_DIR"
docker build -t "$IMAGE_NAME:latest" .

echo ""
echo "=== Build complete ==="
echo "Image: $IMAGE_NAME:latest"
echo ""

# Push if requested
if [ "$1" = "--push" ]; then
    echo "Logging into ECR..."
    aws ecr get-login-password --region "$AWS_REGION" | \
        docker login --username AWS --password-stdin "$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com"

    echo "Tagging and pushing..."
    docker tag "$IMAGE_NAME:latest" "$ECR_REPO:latest"
    docker push "$ECR_REPO:latest"

    echo ""
    echo "=== Push complete ==="
    echo "Image: $ECR_REPO:latest"
fi
