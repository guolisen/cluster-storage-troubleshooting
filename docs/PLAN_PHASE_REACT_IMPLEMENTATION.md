# Plan Phase ReAct Graph Implementation

This document describes the implementation of a ReAct (Reasoning and Acting) graph for the plan phase of the Kubernetes volume troubleshooting system.

## Overview

The plan phase has been enhanced with a ReAct graph implementation that exclusively utilizes MCP (Multi-Component Platform) tools for function calling. This enables the plan phase to gather additional information when it encounters knowledge gaps, leading to more comprehensive investigation plans.

The ReAct graph follows the standard ReAct pattern:
1. **Reasoning**: LLM analyzes the current state and decides what information is needed
2. **Acting**: Invoke MCP tools to gather missing information
3. **Observing**: Process tool outputs and update state
4. **Loop**: Continue until query is resolved or stopping condition is met

## Architecture

The ReAct graph implementation consists of the following components:

### 1. PlanPhaseState

A TypedDict that tracks the state of the ReAct graph, including:
- `messages`: Conversation history
- `iteration_count`: Number of iterations
- `tool_call_count`: Number of tool calls
- `knowledge_gathered`: Knowledge gathered from tools
- `plan_complete`: Whether the plan is complete
- `pod_name`, `namespace`, `volume_path`: Context information
- `knowledge_graph`: Knowledge graph from Phase 0

### 2. PlanPhaseReActGraph

A class that implements the ReAct graph using LangGraph. It includes:
- `build_graph()`: Builds the LangGraph StateGraph
- `call_model()`: LLM reasoning node
- `execute_tools()`: Tool execution node
- `check_end_conditions()`: End condition checker

### 3. Integration with PlanPhase

The existing `PlanPhase` class has been updated to support both the traditional approach and the ReAct graph approach. The approach is determined by the `use_react` configuration option.

## Configuration

To enable the ReAct graph for the plan phase, set the `use_react` option to `true` in the `plan_phase` section of the `config.yaml` file:

```yaml
plan_phase:
  use_llm: true  
  timeout_seconds: 1800
  static_plan_step_path: "data/static_plan_step.json"
  use_react: true  # Enable ReAct graph for plan phase
```

## MCP Tool Integration

The ReAct graph exclusively uses MCP tools for function calling. It retrieves the tools from the MCP adapter using:

```python
mcp_tools = mcp_adapter.get_tools_for_phase('plan_phase')
```

The MCP tools are used by the LLM to gather additional information when it encounters knowledge gaps. The LLM can call these tools and process their results to build a more comprehensive investigation plan.

## ReAct Loop Operation

Here's how the ReAct loop operates:

1. **Initial State**: LLM receives query about Kubernetes volume I/O error
2. **Reasoning**: LLM analyzes the current state and decides what information is needed
3. **Acting**: LLM calls MCP tools to gather missing information
4. **Observing**: LLM processes tool outputs and updates state
5. **Loop**: Continue until the plan is complete or a stopping condition is met

## End Conditions

The ReAct graph ends when one of the following conditions is met:
- The `plan_complete` flag is set to `true`
- The maximum number of iterations is reached
- Explicit end markers are detected in the LLM output
- Completion indicators are detected in the LLM output
- Convergence is detected (model repeating itself)

## Usage

To use the ReAct graph for the plan phase:

1. Ensure MCP integration is enabled and MCP tools are available for the plan phase
2. Set `use_react: true` in the `plan_phase` section of `config.yaml`
3. Run the plan phase as usual

Example:

```python
# Initialize and execute Plan Phase
plan_phase = PlanPhase(config_data)
results = await plan_phase._generate_investigation_plan_react(
    knowledge_graph, pod_name, namespace, volume_path, message_list
)
```

## Testing

A test script is provided in `tests/test_plan_phase_react.py` to demonstrate the ReAct graph implementation. To run the test:

```bash
python tests/test_plan_phase_react.py
```

## Benefits

The ReAct graph implementation offers several benefits:

1. **Dynamic Information Gathering**: The LLM can gather additional information as needed
2. **Improved Investigation Plans**: More comprehensive plans based on gathered information
3. **MCP Tool Integration**: Leverage external tools and services through MCP
4. **Modularity**: The ReAct graph is standalone and can be used independently

## Limitations

The ReAct graph implementation has the following limitations:

1. **MCP Dependency**: Requires MCP integration to be enabled and MCP tools to be available
2. **Performance**: May be slower than the traditional approach due to tool calls
3. **Tool Availability**: Limited to the tools provided by MCP servers

## Future Enhancements

Potential future enhancements include:

1. **Hybrid Approach**: Combine traditional and ReAct approaches
2. **Tool Selection**: Smarter tool selection based on the problem
3. **State Persistence**: Save and resume ReAct graph state
4. **Parallel Tool Execution**: Execute multiple tools in parallel
