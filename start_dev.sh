#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "=== Smart Audiobook Reader: Starting Full-Stack Development Services ==="

# 1. Resolve Python binary from virtual environment
if [ -d "$PROJECT_ROOT/.venv" ]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON="python3"
fi

cd "$PROJECT_ROOT/backend"
# 2. Run database migrations
echo "Running database migrations..."
$PYTHON -m src.core.storage.migrations

# Cleanup handler for graceful shutdown
cleanup() {
    echo ""
    echo "Stopping all services..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
    echo "Services stopped cleanly."
    exit 0
}

trap cleanup SIGINT SIGTERM

# 3. Start FastAPI REST API backend
echo "Starting FastAPI (uvicorn) on http://localhost:5000..."
$PYTHON -m uvicorn src.api.app:app --port 5000 --reload &
BACKEND_PID=$!

# Wait briefly for backend to bind port
sleep 2

# 4. Start React Vite frontend
echo "Starting React SPA on http://localhost:5173..."
cd "$PROJECT_ROOT/apps/web"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=========================================================="
echo "  Smart Audiobook Reader is live!"
echo "  - Backend API:  http://localhost:5000"
echo "  - Frontend Web: http://localhost:5173"
echo "  Press Ctrl+C to terminate both servers."
echo "=========================================================="

# Wait for background processes
wait $BACKEND_PID $FRONTEND_PID
