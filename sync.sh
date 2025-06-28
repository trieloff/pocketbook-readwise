#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the sync script with uv
cd "$SCRIPT_DIR"
uv run pocketbook_sync.py