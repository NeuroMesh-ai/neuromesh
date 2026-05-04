#!/bin/bash
# UnityBrain Start — loads .env and starts the node

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# Load .env if exists
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

NODE=${1:-pinky}
cd "$SCRIPT_DIR/src"
exec python3 unitybrain_v4.py "$NODE"