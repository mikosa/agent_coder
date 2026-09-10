#!/usr/bin/env bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( dirname "$SCRIPT_DIR" )"

if [ -x "$PROJECT_DIR/.venv/bin/python3" ]; then
    exec "$PROJECT_DIR/.venv/bin/python3" "$PROJECT_DIR/main.py" "$@"
fi

exec python3 "$PROJECT_DIR/main.py" "$@"
