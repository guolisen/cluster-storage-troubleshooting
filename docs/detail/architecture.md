# System Architecture

## Core Components

The Cluster Storage Troubleshooting System consists of several key components that work together to provide a comprehensive troubleshooting solution:

### 1. Monitoring Component

The monitoring component (`monitoring/monitor.py`) continuously checks for volume I/O errors in Kubernetes pods by monitoring pod annotations. When it detects the annotation `volume-io-error:<volume-path>`, it triggers the troubleshooting workflow.

Key features:
- Periodically queries pod annotations using the Kubernetes Python client
- Implements exponential backoff for API call retries
- Invokes the troubleshooting workflow with pod name, namespace, and volume path parameters

### 2. Information Collector

The information collector (`information_collector/`) is responsible for gathering all necessary diagnostic data upfront in Phase 0. It collects comprehensive information about the Kubernetes cluster, storage resources, and system state.

Key components:
- **Base Collector**: Core collection functionality
- **Volume Discovery**: Discovers volume dependency chains
- **Tool Executors**: Executes diagnostic tools and commands
- **Knowledge Builder**: Builds the knowledge graph from collected data
- **Metadata Parsers**: Parses Kubernetes resource metadata

### 3. Knowledge Graph

The knowledge graph (`knowledge_graph/`) is a central component that organizes diagnostic data into a structured graph representation. It models entities (Pods, PVCs, PVs, Drives, etc.) and their relationships.

Key features:
- NetworkX-based directed graph implementation
- Entity and relationship modeling
- Issue tracking and analysis
- Path finding and traversal
- Root cause analysis
- Fix plan generation

### 4. LangGraph ReAct Agent

The LangGraph ReAct agent (`troubleshooting/graph.py`) implements the reasoning and acting loop for investigation and remediation. It uses the LangGraph framework to create a state graph that orchestrates the LLM's interaction with tools.

Key components:
- **StateGraph**: Manages the flow of execution
- **Call Model Node**: Invokes the LLM with the current state
- **Execute Tool Node**: Executes tools based on LLM instructions
- **End Condition Node**: Determines when to terminate the graph

### 5. Phased Workflow System

The phased workflow system (`phases/`) implements the different phases of the troubleshooting process:

- **Phase 0**: Information Collection (`phase_information_collection.py`)
- **Plan Phase**: Investigation Planning (`phase_plan_phase.py`)
- **Phase 1**: ReAct Investigation (`phase_analysis.py`)
- **Phase 2**: Remediation (`phase_remediation.py`)

Additional components:
- **Chat Mode**: Interactive chat interface (`chat_mode.py`)
- **Investigation Planner**: Generates investigation plans (`investigation_planner.py`)
- **LLM Factory**: Creates LLM instances based on configuration (`llm_factory.py`)
- **Streaming Callbacks**: Handles streaming responses (`streaming_callbacks.py`)

### 6. Tool Registry

The tool registry (`tools/`) provides a collection of diagnostic and remediation tools that can be used by the LangGraph agent:

- **Core Tools**: Configuration, knowledge graph access, MCP adapter
- **Diagnostic Tools**: Disk analysis, monitoring, performance testing
- **Kubernetes Tools**: Core API, CSI Baremetal driver interaction
- **Testing Tools**: Pod creation, resource cleanup, volume testing

### 7. MCP Integration

The Model Context Protocol (MCP) integration (`tools/core/mcp_adapter.py`) enables communication with external MCP servers to extend the system's capabilities:

- Supports multiple MCP servers
- Provides access to server tools and resources
- Configurable per phase

## System Interactions

The components interact in the following ways:

1. **Monitoring → Troubleshooting**: The monitoring component detects volume I/O errors and triggers the troubleshooting workflow.

2. **Information Collector → Knowledge Graph**: The information collector gathers diagnostic data and builds the knowledge graph.

3. **Knowledge Graph → Investigation Planner**: The investigation planner uses the knowledge graph to generate an investigation plan.

4. **Investigation Planner → ReAct Agent**: The investigation plan guides the ReAct agent's investigation process.

5. **ReAct Agent → Tool Registry**: The ReAct agent uses tools from the tool registry to investigate and remediate issues.

6. **ReAct Agent → Knowledge Graph**: The ReAct agent queries and updates the knowledge graph during investigation and remediation.

7. **ReAct Agent → MCP Adapter**: The ReAct agent can use MCP tools and resources through the MCP adapter.

## Configuration

The system is highly configurable through the `config.yaml` file, which includes:

- **LLM Configuration**: Provider, model, API endpoint, temperature
- **Monitoring Configuration**: Interval, retries, backoff
- **Troubleshooting Configuration**: Timeout, interactive mode, auto-fix
- **SSH Configuration**: Credentials, target nodes
- **Command Configuration**: Allowed and disallowed commands
- **Logging Configuration**: File, stdout
- **Tool Execution Configuration**: Parallel and serial tools
- **Chat Mode Configuration**: Enabled/disabled, entry points
- **MCP Configuration**: Server configurations, enabled tools

## Deployment Model

The system is designed to be deployed on a Kubernetes master node, with the following requirements:

- Python 3.10+
- Access to the Kubernetes API
- SSH access to worker nodes (if needed)
- Access to LLM API (OpenAI, Google, or local Ollama)
