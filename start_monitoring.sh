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

# Start the monitoring script
python3 monitoring/monitor.py
