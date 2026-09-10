#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( dirname "$SCRIPT_DIR" )"

cd "$PROJECT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo "Running pytest test suite..."
PYTHONPATH=. pytest -v tests/
