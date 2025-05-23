#!/bin/bash
# Run comprehensive Kubernetes volume troubleshooting
# This script runs the comprehensive troubleshooting mode which collects
# issues across all layers and provides a consolidated analysis

# Check if the correct number of arguments are provided
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <pod_name> <namespace> <volume_path> [--output-file <file>] [--json]"
    echo "Example: $0 mysql-0 default /var/lib/mysql"
    exit 1
fi

# Parse arguments
POD_NAME=$1
NAMESPACE=$2
VOLUME_PATH=$3
shift 3

# Parse optional arguments
OUTPUT_FORMAT="text"
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --json)
            OUTPUT_FORMAT="json"
            shift
            ;;
        --output-file|--output|-f)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Set up log output
LOG_FILE="troubleshoot.log"
echo "Starting comprehensive troubleshooting for pod $NAMESPACE/$POD_NAME volume $VOLUME_PATH" >> $LOG_FILE
echo "$(date)" >> $LOG_FILE

# Run the comprehensive troubleshooting
echo "Starting comprehensive troubleshooting..."
echo "This may take a few minutes to complete as we collect issues across all layers."

# Build the command
CMD="python3 run_comprehensive_mode.py $POD_NAME $NAMESPACE $VOLUME_PATH -o $OUTPUT_FORMAT"
if [ -n "$OUTPUT_FILE" ]; then
    CMD="$CMD -f $OUTPUT_FILE"
    echo "Report will be saved to: $OUTPUT_FILE"
fi

# Execute the command
echo "Running: $CMD"
$CMD

# Check exit status
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo "Troubleshooting failed with status $STATUS"
    echo "Check $LOG_FILE for more details"
    exit $STATUS
fi

echo "Comprehensive troubleshooting completed"
if [ -n "$OUTPUT_FILE" ]; then
    echo "Report saved to: $OUTPUT_FILE"
fi

exit 0
