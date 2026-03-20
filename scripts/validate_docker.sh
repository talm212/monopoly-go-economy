#!/bin/bash
# Validates Docker image builds successfully for linux/amd64.
# Run manually before deploying or in CI — NOT on every commit (too slow).
#
# Usage:
#   bash scripts/validate_docker.sh
#
set -euo pipefail

IMAGE_NAME="monopoly-economy:test"
PLATFORM="linux/amd64"

echo "=== Docker Build Validation ==="
echo "Platform: ${PLATFORM}"
echo "Image:    ${IMAGE_NAME}"
echo ""

# Verify Docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH."
    exit 1
fi

# Verify Docker daemon is running
if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon is not running."
    exit 1
fi

echo "Building Docker image for ${PLATFORM} (no cache)..."
docker build --platform "${PLATFORM}" -t "${IMAGE_NAME}" . --no-cache

echo ""
echo "Verifying image was created..."
docker image inspect "${IMAGE_NAME}" > /dev/null 2>&1

echo ""
echo "Docker build validation passed!"
