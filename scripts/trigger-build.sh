#!/bin/bash
# Package source and trigger CodeBuild
#
# Usage: ./scripts/trigger-build.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
YRSN_DIR="${YRSN_SRC:-/Users/rudy/GitHub/yrsn/src}"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT="${AWS_ACCOUNT:-188494237500}"
S3_BUCKET="swarmit-codebuild-$AWS_ACCOUNT"
PROJECT_NAME="swarmit-api-build"

echo "=== Packaging source for CodeBuild ==="

# Create temp dir
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

# Copy sidecar
echo "Copying sidecar..."
mkdir -p "$BUILD_DIR/sidecar"
cp -r "$ROOT_DIR/sidecar/"* "$BUILD_DIR/sidecar/"
rm -rf "$BUILD_DIR/sidecar/__pycache__" "$BUILD_DIR/sidecar/tests"

# Copy yrsn
echo "Copying yrsn..."
if [ -d "$YRSN_DIR/yrsn" ]; then
    cp -r "$YRSN_DIR/yrsn" "$BUILD_DIR/sidecar/"
else
    echo "Error: yrsn not found at $YRSN_DIR"
    exit 1
fi

# Remove pycache
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Create zip
echo "Creating zip..."
cd "$BUILD_DIR"
zip -q -r source.zip .

# Upload to S3
echo "Uploading to S3..."
aws s3 cp source.zip "s3://$S3_BUCKET/swarmit-api-source.zip" --region "$AWS_REGION"

# Trigger build
echo "Triggering CodeBuild..."
BUILD_ID=$(aws codebuild start-build \
    --project-name "$PROJECT_NAME" \
    --region "$AWS_REGION" \
    --query 'build.id' \
    --output text)

echo ""
echo "=== Build started ==="
echo "Build ID: $BUILD_ID"
echo ""
echo "Monitor with:"
echo "  aws codebuild batch-get-builds --ids $BUILD_ID --query 'builds[0].buildStatus'"
echo ""
echo "Or watch logs:"
echo "  aws logs tail /codebuild/swarmit-api --follow"
