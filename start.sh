#!/bin/bash
# UnityBrain Quick Start

echo "🐛 UnityBrain — Quick Start"

# Check if installed
if [ ! -d "$HOME/.unitybrain" ]; then
    echo "❌ Not installed. Run install.sh first"
    exit 1
fi

# Start the service
cd "$HOME/.unitybrain"
python3 -m uvicorn openclaw_p2p_service:app --host 127.0.0.1 --port 8001 --log-level info