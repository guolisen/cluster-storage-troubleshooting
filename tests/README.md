# LangGraph Tools Test Suite

This directory contains test scripts for verifying the functionality of all langgraph tools in the cluster-storage-troubleshooting system.

## Available Test Scripts

- `test_langgraph_tools.py`: Comprehensive test for all langgraph tools

## Running the Tests

You can run the tests using the wrapper script in the root directory:

```bash
./run_tool_tests.sh
```

Or run the test script directly:

```bash
python3 tests/test_langgraph_tools.py
```

## Test Output

The test script will:

1. Test each tool category:
   - Knowledge Graph tools
   - Kubernetes tools
   - Diagnostic tools
   - Testing tools
   - LangGraph components

2. Print the results for each tool (success or error)

3. Generate a summary report with:
   - Total number of tools tested
   - Number of successful tools
   - Number of failed tools
   - Success rate by category

4. Save detailed results to `tool_test_results.json` in the root directory

## Interpreting Results

The tests will show:

- Green status: Tool executed successfully
- Red status: Tool failed with an error

Failed tools will be listed at the end of the summary with their error messages, helping you identify which tools need attention.

## Extending Tests

To add new test cases:

1. Add the appropriate test arguments in the test functions
2. Add any new tools to the appropriate test function
3. Run the tests to verify the new tools work correctly
