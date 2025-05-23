# Kubernetes Volume Troubleshooting System

A Python-based system for monitoring and resolving volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver.

**Now with Comprehensive Mode for holistic multi-layer analysis!**

## Overview

This system consists of two main components:

1. **Monitoring Workflow (`monitor.py`)**: Periodically checks all pods in the Kubernetes cluster for volume I/O errors by looking for the `volume-io-error:<volume-path>` annotation.

2. **Troubleshooting Workflow (`troubleshoot.py`)**: Uses LangGraph ReAct to diagnose and resolve volume I/O errors through a structured diagnostic process.

The system focuses on local storage (excluding remote storage like NFS, Ceph, or cloud-based solutions) and covers Pod, PersistentVolumeClaim (PVC), PersistentVolume (PV), CSI Baremetal driver, AvailableCapacity (AC), LogicalVolumeGroup (LVG), and hardware disk diagnostics.

## Features

- **Automated Monitoring**: Periodically checks for volume I/O errors in Kubernetes pods
- **Structured Diagnostics**: Follows a comprehensive troubleshooting process for CSI Baremetal-managed disks
- **Interactive Mode**: Optionally prompts for approval before executing commands
- **Security Controls**: Validates commands against allowed/disallowed lists
- **SSH Support**: Executes diagnostic commands on worker nodes
- **Comprehensive Logging**: Logs all actions, command outputs, and errors

## Requirements

- Python 3.8+
- Kubernetes cluster with CSI Baremetal driver
- Access to the Kubernetes API server
- SSH access to worker nodes (optional)

## Dependencies

```
kubernetes
langgraph
paramiko
pyyaml
```

Install dependencies with:

```bash
# Create a virtual environment using uv
uv venv

# Activate the virtual environment
source .venv/bin/activate  # On Linux/macOS
# or
# .venv\Scripts\activate  # On Windows

# Install dependencies using uv and pyproject.toml
uv pip install -e .
```

## Configuration

The system is configured through `config.yaml`, which includes:

- LLM settings (model, API endpoint, temperature)
- Monitoring settings (interval, retries)
- Troubleshooting settings (timeout, interactive mode)
- SSH configuration (credentials, target nodes)
- Allowed and disallowed commands
- Logging configuration

Example configuration:

```yaml
# LLM Configuration
llm:
  model: "gpt4-o4-mini"
  api_endpoint: "https://x.ai/api"
  api_key: ''
  temperature: 0.7
  max_tokens: 1000

# Monitoring Configuration
monitor:
  interval_seconds: 60
  api_retries: 3
  retry_backoff_seconds: 5

# Troubleshooting Configuration
troubleshoot:
  timeout_seconds: 300
  interactive_mode: true
  ssh:
    enabled: true
    user: "admin"
    key_path: "/path/to/ssh/key"
    nodes:
      - "workernode1"
      - "workernode2"
      - "masternode1"
    retries: 3
    retry_backoff_seconds: 5

# Allowed Commands
commands:
  allowed:
    - "kubectl get pod"
    - "kubectl describe pod"
    # ... more allowed commands
  disallowed:
    - "fsck"
    - "chmod"
    # ... more disallowed commands

# Logging Configuration
logging:
  file: "troubleshoot.log"
  stdout: true
```

## Troubleshooting Modes

The system supports two troubleshooting modes:

### Standard Mode (Default)
- Focuses on identifying a single root cause
- Two-phase approach: Analysis followed by Remediation
- Quick and efficient for straightforward issues
- Uses the original diagnostic workflow

### Comprehensive Mode (New)
- Collects ALL issues across Kubernetes, Linux, and Storage layers before analysis
- Builds a knowledge graph to model relationships between issues
- Identifies primary root causes and contributing factors
- Provides a holistic fix plan addressing all related issues
- Includes verification steps to ensure complete resolution
- Ideal for complex scenarios with multiple interrelated issues

You can select the mode in `config.yaml`:

```yaml
troubleshoot:
  mode: "standard"  # Options: "standard" or "comprehensive"
```

## Usage

### Monitoring Workflow

Run the monitoring script to continuously check for volume I/O errors:

```bash
./start_monitoring.sh
```

Or manually:

```bash
python3 monitor.py
```

This will:
1. Monitor all pods for the `volume-io-error:<volume-path>` annotation
2. Invoke the troubleshooting workflow when errors are detected

### Troubleshooting Workflow

#### Standard Mode

You can run the standard troubleshooting workflow directly:

```bash
python3 troubleshoot.py <pod_name> <namespace> <volume_path>
```

For example:

```bash
python3 troubleshoot.py app-1 default /data
```

This will:
1. Diagnose the volume I/O error using the LangGraph ReAct agent
2. Follow a structured diagnostic process for CSI Baremetal-managed disks
3. Propose remediation actions based on findings

#### Comprehensive Mode

To run the comprehensive troubleshooting workflow:

```bash
# Using the convenience script:
./run_comprehensive_troubleshoot.sh <pod_name> <namespace> <volume_path> [options]

# Or directly:
python3 troubleshoot.py <pod_name> <namespace> <volume_path> --mode comprehensive
```

Options for `run_comprehensive_troubleshoot.sh`:
- `--output/-o FORMAT`: Output format - "text" (default) or "json"
- `--output-file/-f FILE`: Write output to specified file

For example:

```bash
./run_comprehensive_troubleshoot.sh database-0 app /var/lib/mysql --output json --output-file report.json
```

This will:
1. Collect ALL issues across Kubernetes, Linux, and Storage layers
2. Build a knowledge graph to model relationships between issues
3. Identify primary and contributing root causes
4. Provide a comprehensive fix plan addressing all related issues
5. Include verification steps to ensure all issues are resolved

### Testing

To test the system with a simulated volume I/O error:

```bash
./run_test.sh [options]
```

Options:
- `--namespace NAMESPACE`: Namespace to create test resources in (default: "default")
- `--cleanup`: Clean up test resources after running
- `--existing-pod POD_NAME`: Use an existing pod instead of creating a new one
- `--volume-path VOLUME_PATH`: Volume path to use for the error (default: "/mnt")

Example:

```bash
./run_test.sh --namespace test-ns --cleanup
```

This will:
1. Create a test pod with a volume in the specified namespace
2. Simulate a volume I/O error by adding an annotation to the pod
3. Run the troubleshooting workflow
4. Clean up the test resources if requested

## Troubleshooting Process

The system follows this structured diagnostic process:

1. **Confirm the Issue**: Check pod logs and events for error types
2. **Verify Pod and Volume Configuration**: Inspect PVC, PV, and mount points
3. **Check CSI Baremetal Driver and Resources**: Verify driver status, drive health, and capacity
4. **Test Driver Functionality**: Create test pods to validate read/write operations
5. **Verify Node Health**: Check node status and disk mounting
6. **Check Permissions**: Verify file system permissions and security context
7. **Inspect Kubernetes Control Plane**: Check controller and scheduler logs
8. **Test Hardware Disk**: Verify drive health, performance, and file system
9. **Propose Remediations**: Recommend actions based on diagnostic findings

## Security Considerations

- SSH credentials are stored securely
- Write/change commands are disabled by default
- All commands are validated against allowed/disallowed lists
- Interactive mode requires explicit user approval for potentially impactful operations

## Logging

All actions, command outputs, and errors are logged to:
- `troubleshoot.log` (configurable)
- stdout (optional)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
