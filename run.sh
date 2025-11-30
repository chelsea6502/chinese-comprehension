#!/bin/bash

# Chinese Checker - Docker Run Script
# This script builds and runs the Chinese Checker application in Docker

set -e

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    exit 1
fi

# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ Error: docker-compose is not available"
    exit 1
fi

# Create directories if they don't exist
mkdir -p input known unknown

# Check if we need to build (first run or --build flag)
if [ "$1" == "--build" ] || [ "$1" == "-b" ]; then
    $COMPOSE_CMD build --quiet
elif ! docker images | grep -q "chinese-checker"; then
    $COMPOSE_CMD build --quiet
fi

# Run with minimal output and strip container name prefix
$COMPOSE_CMD up 2>&1 | grep -v "View in Docker Desktop" | grep -v "View Config" | grep -v "Enable Watch" | grep -v "Attaching to" | sed 's/^chinese-checker  | //'