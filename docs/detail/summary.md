# Cluster Storage Troubleshooting System: Executive Summary

## Project Overview

The Cluster Storage Troubleshooting System is an intelligent, automated solution for diagnosing and resolving Kubernetes cluster storage issues. It leverages Large Language Models (LLMs) and a knowledge graph-based approach to provide comprehensive troubleshooting for volume I/O errors in Kubernetes pods backed by local storage managed by the CSI Baremetal driver.

## Key Innovations

1. **Knowledge Graph-Based Troubleshooting**: The system builds a comprehensive knowledge graph of system entities and relationships, enabling sophisticated root cause analysis and fix plan generation.

2. **LangGraph ReAct Agent**: Implements a reasoning and acting loop using the LangGraph framework, allowing the LLM to execute tools, analyze results, and make decisions based on the knowledge graph.

3. **Phased Workflow Approach**: The system follows a structured 3-phase approach (Information Collection, Investigation, Remediation) with an additional Planning phase, ensuring thorough and methodical troubleshooting.

4. **Historical Experience Integration**: The system learns from past troubleshooting experiences, incorporating them into the knowledge graph for improved diagnosis and remediation.

5. **Multi-Provider LLM Support**: Supports multiple LLM providers (OpenAI, Google Gemini, Ollama), offering flexibility in deployment.

## Architecture Highlights

### Core Components

1. **Knowledge Graph**: NetworkX-based directed graph representing system entities and relationships
2. **LangGraph ReAct Agent**: Orchestrates the LLM's interaction with tools using a state graph
3. **Phased Workflow System**: Implements the different phases of the troubleshooting process
4. **Information Collector**: Gathers diagnostic data and builds the knowledge graph
5. **Tool Registry**: Provides diagnostic and remediation tools
6. **MCP Integration**: Enables communication with external tools and resources
7. **Chat Mode**: Enables interactive troubleshooting

### Workflow Design

The system implements a sophisticated workflow:

1. **Monitoring**: Continuously monitors Kubernetes pods for volume I/O errors
2. **Phase 0**: Collects comprehensive diagnostic data and builds the knowledge graph
3. **Plan Phase**: Generates a structured investigation plan
4. **Phase 1**: Executes the investigation plan and performs root cause analysis
5. **Phase 2**: Implements the fix plan and validates the fixes

## Technical Implementation

### Knowledge Graph

- Represents entities (Pods, PVCs, PVs, Drives, etc.) and their relationships
- Tracks issues by severity and type
- Identifies root causes based on graph topology
- Generates prioritized fix plans

### LangGraph Implementation

- Uses StateGraph to manage execution flow
- Implements Call Model Node, Execute Tool Node, and End Condition Node
- Supports both parallel and serial tool execution
- Uses enhanced end conditions to determine when to terminate

### Tool System

- Categorizes tools as parallel or serial
- Validates tools against allowed/disallowed commands
- Executes tools and formats results
- Provides comprehensive diagnostic and remediation capabilities

## Key Strengths

1. **Comprehensive Analysis**: The knowledge graph approach enables thorough analysis of complex system relationships.
2. **Flexibility**: The modular design and multi-provider LLM support offer deployment flexibility.
3. **Safety**: Command validation and interactive approval modes ensure safe operation.
4. **Learning Capability**: Historical experience integration enables continuous improvement.
5. **Extensibility**: MCP integration allows for easy extension with external tools and resources.

## Use Cases

- Diagnosing volume I/O errors in Kubernetes pods
- Troubleshooting CSI Baremetal driver issues
- Identifying and resolving storage-related configuration problems
- Detecting and addressing hardware disk failures
- Resolving permission and access issues for volumes

## Future Directions

1. **Enhanced Automation**: Further automate the remediation process for common issues
2. **Expanded Knowledge Graph**: Incorporate more system components and relationships
3. **Improved Learning**: Enhance the historical experience integration for better learning
4. **Advanced Visualization**: Develop better visualization tools for the knowledge graph
5. **Additional Storage Providers**: Extend support to other storage providers beyond CSI Baremetal
