#!/usr/bin/env bash
set -e

echo "=== LocalCoder Setup Script ==="
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( dirname "$SCRIPT_DIR" )"

cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment (.venv)..."
    python3 -m venv .venv
fi

echo "Installing / updating dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env" ]; then
    echo "Copying default .env config..."
    cp .env.example .env
fi

echo "✅ Setup completed successfully!"
echo "Run './scripts/run.sh' or 'python3 main.py' to launch."
