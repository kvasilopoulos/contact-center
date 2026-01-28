#!/bin/bash

# Start the FastAPI server in the background
echo "Starting FastAPI server..."
make run &
SERVER_PID=$!

# Wait for the server to be ready
echo "Waiting for server to start..."
sleep 3

# Start cloudflared and capture output
echo "Starting cloudflared tunnel..."
cloudflared tunnel --url http://localhost:8000 2>&1 | while IFS= read -r line; do
    echo "$line"
    
    # Extract the tunnel URL (looks like: https://xxxxx.trycloudflare.com)
    if [[ "$line" =~ https://[a-z0-9-]+\.trycloudflare\.com ]]; then
        TUNNEL_URL="${BASH_REMATCH[0]}"
        echo ""
        echo "================================================"
        echo "Tunnel URL: $TUNNEL_URL"
        echo "Opening in browser..."
        echo "================================================"
        echo ""
        
        # Open the URL in the default browser
        if command -v xdg-open &> /dev/null; then
            xdg-open "$TUNNEL_URL"
        elif command -v open &> /dev/null; then
            open "$TUNNEL_URL"
        elif command -v start &> /dev/null; then
            start "$TUNNEL_URL"
        else
            echo "Could not detect browser command. Please open manually: $TUNNEL_URL"
        fi
    fi
done

# Cleanup on script exit
trap "kill $SERVER_PID 2>/dev/null" EXIT