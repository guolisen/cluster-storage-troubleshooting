# Project Structure

This document provides an overview of the project structure for the Kubernetes Volume Troubleshooting System.

## Core Components

- `monitor.py`: The monitoring workflow that checks for volume I/O errors in Kubernetes pods
- `troubleshoot.py`: The troubleshooting workflow that diagnoses and resolves volume I/O errors
- `issue_collector.py`: Collects issues across all layers (Kubernetes, Linux, Storage)
- `knowledge_graph.py`: Models relationships between issues to identify root causes
- `run_comprehensive_mode.py`: Orchestrates comprehensive troubleshooting process
- `config.yaml`: Configuration file for the system
- `pyproject.toml`: Project metadata and Python dependencies
- `requirements.txt`: Legacy Python dependencies (for reference)

## Helper Scripts

- `start_monitoring.sh`: Shell script to start the monitoring workflow
- `run_comprehensive_troubleshoot.sh`: Shell script to run the comprehensive troubleshooting workflow
- `run_test.sh`: Shell script to run the test workflow
- `test_troubleshoot.py`: Test script that simulates a volume I/O error

## Documentation

- `README.md`: Main documentation file
- `PROJECT_STRUCTURE.md`: This file
- `LICENSE`: License information

## File Descriptions

### Core Components

#### `monitor.py`
- Periodically checks all pods for the `volume-io-error:<volume-path>` annotation
- Invokes the troubleshooting workflow when errors are detected
- Handles API errors with exponential backoff

#### `troubleshoot.py`
- Implements a LangGraph ReAct agent to diagnose and resolve volume I/O errors
- Follows a structured diagnostic process for CSI Baremetal-managed disks
- Provides tools for executing commands, querying Kubernetes resources, and SSH operations
- Supports interactive mode for user approval of commands

#### `config.yaml`
- LLM settings (model, API endpoint, temperature)
- Monitoring settings (interval, retries)
- Troubleshooting settings (timeout, interactive mode)
- SSH configuration (credentials, target nodes)
- Allowed and disallowed commands
- Logging configuration

### Helper Scripts

#### `start_monitoring.sh`
- Checks for Python and required packages
- Verifies that `config.yaml` exists
- Starts the monitoring workflow

#### `run_test.sh`
- Checks for Python and required packages
- Verifies that `config.yaml` exists
- Parses command line arguments
- Runs the test workflow with the specified options

#### `test_troubleshoot.py`
- Creates a test pod with a volume
- Simulates a volume I/O error by adding an annotation to the pod
- Runs the troubleshooting workflow
- Cleans up test resources if requested

### Comprehensive Mode Components

#### `issue_collector.py`
- Systematically collects issues across all three layers (Kubernetes, Linux, Storage)
- Each issue includes layer, component, severity, message, and evidence
- Provides a structured approach to gather all potential factors in a volume I/O error

#### `knowledge_graph.py`
- Models relationships between issues as a directed graph
- Applies predefined patterns to infer causal relationships 
- Uses graph algorithms to identify primary and secondary root causes
- Assigns confidence scores to potential root causes

#### `run_comprehensive_mode.py`
- Orchestrates the comprehensive troubleshooting process
- Invokes the issue collector, builds the knowledge graph
- Leverages LLM for enhanced analysis of complex relationships
- Generates consolidated reports with root causes, fix plans, and verification steps

#### `run_comprehensive_troubleshoot.sh`
- Simplified interface to run comprehensive troubleshooting
- Supports output format selection (text or JSON)
- Allows specifying an output file for the report

## Workflow Diagrams

### Standard Mode Workflow

```
                                +----------------+
                                |                |
                                |   monitor.py   |
                                |                |
                                +-------+--------+
                                        |
                                        | Detects volume I/O error
                                        |
                                        v
                    +------------------+----------------+
                    |                                   |
                    |          troubleshoot.py          |
                    |                                   |
                    +------------------+----------------+
                                       |
                                       | Uses
                                       |
                                       v
                    +------------------+----------------+
                    |                                   |
                    |       LangGraph ReAct Agent       |
                    |                                   |
                    +------------------+----------------+
                                       |
                                       | Uses
                                       |
                                       v
        +-------------+----------------+----------------+-------------+
        |             |                |                |             |
        v             v                v                v             v
+---------------+ +--------+  +----------------+  +----------+ +-------------+
|               | |        |  |                |  |          | |             |
| Kubernetes API | |  SSH  |  | Linux Commands |  | Testing  | | Remediation |
|               | |        |  |                |  |          | |             |
+---------------+ +--------+  +----------------+  +----------+ +-------------+
```

### Comprehensive Mode Workflow

```
                              +--------------------+
                              |                    |
                              |     monitor.py     |
                              |                    |
                              +----------+---------+
                                         |
                                         | Detects volume I/O error
                                         | (comprehensive mode)
                                         v
          +-------------------------+---------------------------+
          |                                                     |
          |                 troubleshoot.py                     |
          |                                                     |
          +-------------------------+---------------------------+
                                    |
                                    | Invokes
                                    v
          +-------------------------+---------------------------+
          |                                                     |
          |             run_comprehensive_mode.py               |
          |                                                     |
          +------+-------------------+----------------+----------+
                 |                   |                |
                 v                   v                v
        +----------------+  +----------------+  +--------------+
        |                |  |                |  |              |
        | issue_collector |  | knowledge_graph |  | LLM Analysis |
        |                |  |                |  |              |
        +----------------+  +----------------+  +--------------+
                 |                   |                |
                 v                   v                v
        +----------------+  +----------------+  +--------------+
        | Kubernetes     |  | Root Cause     |  | Comprehensive|
        | Linux & Storage|  | Identification |  | Fix Plan     |
        | Issues         |  |                |  |              |
        +----------------+  +----------------+  +--------------+
                                    |
                                    v
                         +---------------------+
                         |                     |
                         | Comprehensive Report|
                         |                     |
                         +---------------------+
```

## Development Guidelines

1. **Configuration**: Always validate new commands against the allowed/disallowed lists in `config.yaml`
2. **Security**: Ensure that write/change commands require explicit user approval in interactive mode
3. **Error Handling**: Implement proper error handling and retries for API calls and SSH operations
4. **Logging**: Log all actions, command outputs, and errors with appropriate context
5. **Testing**: Use `test_troubleshoot.py` to test new features and changes
6. **Dependency Management**: Use `uv` for virtual environment creation and package installation with pyproject.toml:
   ```bash
   # Create a virtual environment
   uv venv
   
   # Activate the virtual environment
   source .venv/bin/activate  # On Linux/macOS
   # or
   # .venv\Scripts\activate  # On Windows
   
   # Install dependencies using pyproject.toml
   uv pip install -e .
   ```
