#!/bin/bash
# Run the Kubernetes Volume I/O Error Troubleshooting Test

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

# Parse command line arguments
NAMESPACE="default"
CLEANUP=false
EXISTING_POD=""
VOLUME_PATH="/mnt"

while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --existing-pod)
            EXISTING_POD="$2"
            shift 2
            ;;
        --volume-path)
            VOLUME_PATH="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--namespace NAMESPACE] [--cleanup] [--existing-pod POD_NAME] [--volume-path VOLUME_PATH]"
            exit 1
            ;;
    esac
done

# Build command
CMD="python3 test_troubleshoot.py --namespace $NAMESPACE"

if [ "$CLEANUP" = true ]; then
    CMD="$CMD --cleanup"
fi

if [ -n "$EXISTING_POD" ]; then
    CMD="$CMD --existing-pod $EXISTING_POD"
fi

if [ -n "$VOLUME_PATH" ]; then
    CMD="$CMD --volume-path $VOLUME_PATH"
fi

# Run test
echo "Running test with command: $CMD"
eval $CMD
