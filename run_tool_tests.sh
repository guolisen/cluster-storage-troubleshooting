#!/bin/bash
# Run the langgraph tools test script
# This script runs the test_langgraph_tools.py script and displays the results

# Parse command line arguments
VERBOSE=""
CATEGORY=""
OUTPUT="tool_test_results.json"

# Display help message
function show_help {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help             Show this help message"
    echo "  -v, --verbose          Enable verbose output"
    echo "  -c, --category CATEGORY Test only a specific category (knowledge_graph, kubernetes, diagnostic, testing)"
    echo "  -o, --output FILE      Output file path for test results"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE="--verbose"
            shift
            ;;
        -c|--category)
            CATEGORY="--category $2"
            shift
            shift
            ;;
        -o|--output)
            OUTPUT="$2"
            shift
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

echo "Starting LangGraph Tools Test..."
echo "================================"
echo ""

# Run the test script with arguments
python3 tests/test_langgraph_tools.py $VERBOSE $CATEGORY --output "$OUTPUT" 

# Check the exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "Tests completed successfully!"
    echo "See $OUTPUT for detailed results."
else
    echo ""
    echo "Tests failed with errors."
    echo "Check the console output above for details."
fi

echo ""
echo "================================"
