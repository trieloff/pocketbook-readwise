#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Run the sync script
python "$SCRIPT_DIR/pocketbook_sync.py"

# Deactivate virtual environment
deactivate