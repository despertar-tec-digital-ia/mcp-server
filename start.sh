#!/bin/bash
set -e

mkdir -p logs

echo "Building and starting GHL MCP Calendario..."
docker compose up --build -d

echo "Done. Logs: docker compose logs -f"
