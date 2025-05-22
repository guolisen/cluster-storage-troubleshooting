#!/bin/bash

# Test script for the Kubernetes Volume I/O Error Troubleshooting System
# This script runs the test_troubleshoot.py script with different scenarios and options

# Function to display usage
function show_usage {
    echo "Usage: $0 [OPTIONS]"
    echo "Test the Kubernetes Volume I/O Error Troubleshooting System"
    echo ""
    echo "Options:"
    echo "  -s, --scenario SCENARIO  Test scenario to run (bad_sectors or permission_issue)"
    echo "                           Default: bad_sectors"
    echo "  -a, --auto-fix          Enable auto-fix mode (default: disabled)"
    echo "  -h, --help              Display this help message and exit"
}

# Default values
SCENARIO="bad_sectors"
AUTO_FIX=""

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--scenario)
            SCENARIO="$2"
            shift 2
            ;;
        -a|--auto-fix)
            AUTO_FIX="--auto-fix"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate scenario
if [[ "$SCENARIO" != "bad_sectors" && "$SCENARIO" != "permission_issue" ]]; then
    echo "Error: Invalid scenario '$SCENARIO'"
    echo "Valid scenarios are: bad_sectors, permission_issue"
    exit 1
fi

# Run the test script
echo "Running test with scenario: $SCENARIO, auto-fix: ${AUTO_FIX:+enabled}"
echo "---------------------------------------------------------"
python3 test_troubleshoot.py --scenario "$SCENARIO" $AUTO_FIX
