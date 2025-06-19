# MCP Integration Guide

This guide explains how to use the Model Context Protocol (MCP) integration in the Kubernetes Cluster Storage Troubleshooting system.

## Overview

The MCP integration allows the troubleshooting system to communicate with external MCP servers to access additional tools and resources. These tools can be used in the Plan Phase, Phase1, and Phase2 of the troubleshooting process.

MCP servers can be configured to use either Server-Sent Events (SSE) or Standard I/O (stdio) for communication. The system supports multiple MCP servers, each with its own configuration.

## Configuration

MCP integration is configured in the `config.yaml` file. Here's an example configuration:

```yaml
# MCP Configuration
mcp_enabled: true  # Set to true to enable MCP integration
mcp_servers:
  k8s:
    type: sse
    url: http://10.227.104.51:32085/sse
    command: null
    args: []
    env: {}
    tools:
      plan_phase: true
      phase1: true
      phase2: false
  tavily:
    type: stdio
    url: ""
    command: npx
    args: ["-y", "tavily-mcp@0.1.4"]
    env:
      TAVILY_API_KEY: ""
    tools:
      plan_phase: false
      phase1: true
      phase2: true
```

### Configuration Options

- `mcp_enabled`: Boolean to enable/disable MCP integration (default: `false`).
- `mcp_servers`: Dictionary of MCP server configurations, each with:
  - Key: Server name (e.g., `k8s`, `tavily`).
  - Value: Dictionary containing:
    - `enable`: Boolean to enable/disable this specific MCP server (default: `true`).
    - `type`: Communication mode (`sse` or `stdio`, default: `sse`).
    - `url`: URL for SSE mode (required if `type: sse`, empty for `stdio`).
    - `command`: Command to run for stdio mode (required if `type: stdio`, null for `sse`).
    - `args`: List of command arguments for stdio mode (empty for `sse`).
    - `env`: Dictionary of environment variables for stdio mode (empty for `sse`).
    - `tools`: Dictionary specifying phase inclusion:
      - `plan_phase`: Boolean to enable/disable tools in Plan Phase.
      - `phase1`: Boolean to enable/disable tools in Phase1.
      - `phase2`: Boolean to enable/disable tools in Phase2.

## Communication Modes

### SSE Mode

In SSE mode, the system communicates with the MCP server via HTTP Server-Sent Events. The server must be running and accessible at the specified URL.

Example configuration:

```yaml
k8s:
  enable: true
  type: sse
  url: http://10.227.104.51:32085/sse
  command: null
  args: []
  env: {}
  tools:
    plan_phase: true
    phase1: true
    phase2: false
```

### stdio Mode

In stdio mode, the system launches a subprocess and communicates with it via standard input/output. The command must be installed on the system.

Example configuration:

```yaml
tavily:
  enable: true
  type: stdio
  url: ""
  command: npx
  args: ["-y", "tavily-mcp@0.1.4"]
  env:
    TAVILY_API_KEY: ""
  tools:
    plan_phase: false
    phase1: true
    phase2: true
```

## Integration in Phases

### Plan Phase

In the Plan Phase, MCP tools are used to gather information for the Investigation Plan. The tools are available to the LLM Plan Generator.

### Phase1

In Phase1, MCP tools are integrated into the LangGraph ReAct framework for sequential execution alongside existing tools. They can be used to gather additional information for the investigation.

### Phase2

In Phase2, MCP tools are integrated into the LangGraph workflow to execute Fix Plan steps. They can be used to perform remediation actions.

## Error Handling

The system includes error handling for:

- Invalid MCP configuration (e.g., missing `url` for SSE, invalid `command` for stdio, duplicate server names).
- MCP server communication failures (e.g., SSE connection errors, stdio process crashes).
- Tool invocation errors (e.g., invalid MCP tool responses).
- Graceful fallback to non-MCP tools if any MCP server fails.

## Example Usage

### Plan Phase

```
Querying k8s MCP tool for storage metrics...
Investigation Plan:
1. Check Kubernetes storage latency.
2. Verify disk health.
```

### Phase1

```
Executing k8s MCP tool: storage_diagnostic
Result: { "latency": "high" }
Executing tavily MCP tool: external_check
Result: { "status": "degraded" }
Fix Plan:
1. Reconfigure storage backend.
```

### Phase2

```
Executing tavily MCP tool: storage_reconfigure
Result: { "status": "success" }
```

## Implementation Details

The MCP integration is implemented using the `langchain_mcp_adapters` package. The main components are:

- `tools/core/mcp_adapter.py`: Handles MCP server initialization and tool routing.
- `phases/llm_plan_generator.py`: Integrates MCP tools into the Plan Phase.
- `phases/phase_analysis.py`: Integrates MCP tools into Phase1.
- `phases/phase_remediation.py`: Integrates MCP tools into Phase2.
- `troubleshooting/graph.py`: Integrates MCP tools into the LangGraph workflow.
- `troubleshooting/troubleshoot.py`: Initializes the MCP adapter.

## Troubleshooting

If you encounter issues with MCP integration, check the following:

- Ensure `mcp_enabled` is set to `true` in `config.yaml`.
- For SSE mode, ensure the server is running and accessible at the specified URL.
- For stdio mode, ensure the command is installed on the system.
- Check the logs for error messages related to MCP initialization or tool invocation.
