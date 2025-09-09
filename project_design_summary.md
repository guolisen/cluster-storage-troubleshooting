# Cluster Storage Troubleshooting - Project Design Summary

## Project Overview

The `cluster-storage-troubleshooting` project is an intelligent system designed to automatically detect and resolve Kubernetes volume I/O errors. It operates through a multi-stage workflow: first collecting comprehensive diagnostic data into a Knowledge Graph, then using an AI agent to plan investigations and analyze root causes, and finally proposing and executing remediation steps. A monitoring component continuously watches for new issues, triggering the entire process when necessary.

## System Architecture

The system consists of several key components that work together to provide a comprehensive troubleshooting solution:

1. **Monitoring Component**: Continuously checks for volume I/O errors in Kubernetes pods by monitoring pod annotations.

2. **Troubleshooting Workflow**: The central orchestrator that manages the entire process through multiple phases.

3. **Information Collector**: Gathers comprehensive diagnostic data about the Kubernetes cluster, storage resources, and system state.

4. **Knowledge Graph**: Organizes diagnostic data into a structured graph representation, modeling entities and their relationships.

5. **Investigation Planner**: Generates a detailed, step-by-step plan for the AI to follow during root cause analysis.

6. **LangGraph ReAct Agent**: Implements the reasoning and acting loop for investigation and remediation using the LangGraph framework.

7. **Diagnostic Tools**: Specialized functions that allow the AI to interact with the Kubernetes cluster.

8. **Prompt Management**: Ensures the AI has clear instructions and context.

9. **MCP Integration**: Enables communication with external MCP servers to extend the system's capabilities.

## Workflow Phases

The system follows a structured workflow with multiple phases:

1. **Phase 0: Information Collection**: Gathers all relevant data about the problem and builds the Knowledge Graph.

2. **Plan Phase: Investigation Planning**: Creates a step-by-step plan for the investigation.

3. **Phase 1: Root Cause Analysis**: Executes the plan to find the real problem and generates a fix plan.

4. **Phase 2: Remediation**: Applies the fix if needed and validates the resolution.

## Key Features

- **Automated Monitoring**: Continuously watches for volume I/O errors in Kubernetes pods.
- **Comprehensive Data Collection**: Gathers detailed information about the Kubernetes cluster and storage resources.
- **Intelligent Knowledge Graph**: Organizes diagnostic data into a structured, interconnected representation.
- **AI-Driven Investigation**: Uses a LangGraph ReAct agent to analyze problems and make decisions.
- **Structured Planning**: Generates detailed investigation plans combining rule-based steps, mandatory checks, and AI refinement.
- **Automated Remediation**: Can automatically apply fixes based on the analysis.
- **Extensible Tool System**: Provides a collection of diagnostic and remediation tools.
- **MCP Integration**: Supports communication with external MCP servers for extended capabilities.

## Detailed Diagrams

For a more detailed understanding of the system, refer to the following documents:

1. [Main Workflow Chart](main_workflow_chart.md): Provides a visual representation of the main workflow in the system, including detailed phase workflows and sequence diagrams.

2. [Components Relationship Chart](components_relationship_chart.md): Illustrates the high-level components and their relationships, including detailed component relationships and system integration.

## Technical Implementation

The system is implemented in Python and uses several key technologies:

- **LangGraph**: For building the AI agent workflow.
- **NetworkX**: For implementing the Knowledge Graph.
- **Kubernetes Python Client**: For interacting with the Kubernetes API.
- **Large Language Models**: For AI reasoning and planning.

## Deployment Model

The system is designed to be deployed on a Kubernetes master node, with the following requirements:

- Python 3.10+
- Access to the Kubernetes API
- SSH access to worker nodes (if needed)
- Access to LLM API (OpenAI, Google, or local Ollama)

## Conclusion

The cluster-storage-troubleshooting project provides a comprehensive, intelligent solution for automatically detecting and resolving Kubernetes volume I/O errors. By combining structured workflows, knowledge graph representation, and AI-driven investigation, it offers a powerful tool for maintaining the health of Kubernetes storage systems.
