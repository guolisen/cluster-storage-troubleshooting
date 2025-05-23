#!/bin/bash

# Start the Kubernetes Volume I/O Error Monitoring System
# This script starts the monitoring service which periodically checks for
# volume I/O errors in Kubernetes pods and triggers the troubleshooting workflow.

echo "Starting Kubernetes Volume I/O Error Monitoring System..."

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo "Error: config.yaml not found!"
    exit 1
fi

# Check and display current troubleshooting mode
MODE=$(grep "mode:" config.yaml | awk -F'"' '{print $2}')
if [ -z "$MODE" ]; then
    MODE="standard"
fi
echo "Troubleshooting mode: $MODE"
echo "To change mode, edit config.yaml and set troubleshoot.mode to 'standard' or 'comprehensive'"

# Start the monitoring script
python3 monitor.py
