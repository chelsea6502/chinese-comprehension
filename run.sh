#!/bin/bash

# Chinese Checker - Docker Run Script
# This script builds and runs the Chinese Checker application in Docker

set -e

echo "🐳 Chinese Checker - Docker Runner"
echo "=================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Please install Docker from https://www.docker.com/get-started"
    exit 1
fi

# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ Error: docker-compose is not available"
    echo "Please install docker-compose or use Docker Desktop"
    exit 1
fi

# Create directories if they don't exist
echo "📁 Ensuring directories exist..."
mkdir -p input known unknown

# Check if input directory has files
if [ -z "$(ls -A input/*.txt 2>/dev/null)" ]; then
    echo "⚠️  Warning: No .txt files found in input/ directory"
    echo "   Please add Chinese text files to analyze"
fi

# Check if we need to build (first run or --build flag)
if [ "$1" == "--build" ] || [ "$1" == "-b" ]; then
    echo ""
    echo "🔨 Building Docker image..."
    $COMPOSE_CMD build
    BUILD_DONE=true
elif ! docker images | grep -q "chinese-checker"; then
    echo ""
    echo "🔨 Building Docker image (first run)..."
    $COMPOSE_CMD build
    BUILD_DONE=true
else
    echo ""
    echo "⚡ Using cached Docker image (use --build to rebuild)"
    BUILD_DONE=false
fi

echo ""
echo "🚀 Running Chinese Checker..."
echo "=================================="
echo ""
$COMPOSE_CMD up

echo ""
if [ "$BUILD_DONE" = true ]; then
    echo "✅ Done! Next runs will be faster (no rebuild needed)"
else
    echo "✅ Done!"
fi
echo ""
echo "💡 Tip: Only rebuild with './run.sh --build' when requirements.txt changes"