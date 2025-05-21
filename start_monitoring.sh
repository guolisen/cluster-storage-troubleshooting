#!/bin/bash
# Start the Kubernetes Volume I/O Error Monitoring Workflow

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is required but not installed."
    echo "Install it with: pip install uv"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Check if required packages are installed
echo "Checking dependencies..."
if ! python3 -c "import kubernetes, langgraph, paramiko, yaml" &> /dev/null; then
    echo "Installing required packages..."
    uv pip install -e .
fi

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo "Error: config.yaml not found. Please create a configuration file."
    exit 1
fi

# Start monitoring
echo "Starting Kubernetes Volume I/O Error Monitoring..."
python3 monitor.py

# This script will run until interrupted with Ctrl+C
