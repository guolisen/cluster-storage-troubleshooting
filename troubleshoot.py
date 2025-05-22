#!/usr/bin/env python3
"""
Kubernetes Volume I/O Error Troubleshooting Script

This script uses LangGraph ReAct to diagnose and resolve volume I/O errors
in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver.
"""

import os
import sys
import yaml
import logging
import asyncio
import time
import subprocess
import json
import paramiko
import uuid
import shlex # Added import for shlex
from typing import Dict, List, Any, Optional, Tuple
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool # Changed import for @tool
from langchain.chat_models import init_chat_model

# Global variables
CONFIG_DATA = None
INTERACTIVE_MODE = False
SSH_CLIENTS = {}

def load_config():
    """Load configuration from config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        sys.exit(1)

def setup_logging(config_data):
    """Configure logging based on configuration"""
    log_file = config_data['logging']['file']
    log_to_stdout = config_data['logging']['stdout']
    
    handlers = []
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    if log_to_stdout:
        handlers.append(logging.StreamHandler())
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

def init_kubernetes_client():
    """Initialize Kubernetes client"""
    try:
        # Try to load in-cluster config first (when running inside a pod)
        if 'KUBERNETES_SERVICE_HOST' in os.environ:
            config.load_incluster_config()
            logging.info("Using in-cluster Kubernetes configuration")
        else:
            # Fall back to kubeconfig file
            config.load_kube_config()
            logging.info("Using kubeconfig file for Kubernetes configuration")
        
        return client.CoreV1Api()
    except Exception as e:
        logging.error(f"Failed to initialize Kubernetes client: {e}")
        sys.exit(1)

def validate_command(command: str) -> bool:
    """
    Validate if a command is allowed based on configuration with prefix/wildcard matching
    
    Args:
        command: Command to validate
        
    Returns:
        bool: True if command is allowed, False otherwise
    """
    global CONFIG_DATA
    
    # Ensure command_to_validate is a string, as it's now just the executable
    if not isinstance(command, str):
        logging.error(f"Invalid type for command validation: {type(command)}. Expected string.")
        return False

    # Check if command is explicitly disallowed (exact match first, then prefix/wildcard)
    for disallowed in CONFIG_DATA['commands']['disallowed']:
        # Handle exact match
        if disallowed == command:
            logging.warning(f"Command '{command}' is explicitly disallowed")
            return False
            
        # Handle wildcards
        if disallowed.endswith('*'):
            prefix = disallowed[:-1]  # Remove the * character
            if command.startswith(prefix):
                logging.warning(f"Command '{command}' matches disallowed wildcard pattern '{disallowed}'")
                return False
    
    # Check if command is allowed (exact match first, then prefix/wildcard)
    for allowed in CONFIG_DATA['commands']['allowed']:
        # Handle exact match
        if allowed == command:
            return True
            
        # Handle wildcards
        if allowed.endswith('*'):
            prefix = allowed[:-1]  # Remove the * character
            if command.startswith(prefix):
                return True
    
    logging.warning(f"Command '{command}' is not in the allowed list")
    return False

def prompt_for_approval(command_display: str, purpose: str) -> bool:
    """
    Prompt user for command approval in interactive mode
    
    Args:
        command_display: The command string to display to the user for approval
        purpose: Purpose of the command
        
    Returns:
        bool: True if approved, False otherwise
    """
    print(f"\nProposed command: {command_display}")
    print(f"Purpose: {purpose}")
    response = input("Approve? (y/n): ").strip().lower()
    return response == 'y' or response == 'yes'

def execute_command(command_list: List[str], purpose: str) -> str:
    """
    Execute a command and return its output
    
    Args:
        command_list: Command to execute as a list of strings
        purpose: Purpose of the command
        
    Returns:
        str: Command output
    """
    global CONFIG_DATA, INTERACTIVE_MODE
    
    if not command_list:
        logging.error("execute_command received an empty command_list")
        return "Error: Empty command list provided"

    executable = command_list[0]
    command_display_str = ' '.join(command_list) # For logging and prompting

    # Validate command
    if not validate_command(executable):
        return f"Error: Command executable '{executable}' is not allowed"
    
    # Prompt for approval in interactive mode
    if INTERACTIVE_MODE:
        if not prompt_for_approval(command_display_str, purpose):
            return "Command execution cancelled by user"
    
    # Execute command
    try:
        logging.info(f"Executing command: {command_display_str}")
        result = subprocess.run(command_list, shell=False, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
        output = result.stdout
        logging.debug(f"Command output: {output}")
        return output
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed with exit code {e.returncode}: {e.stderr}"
        logging.error(error_msg)
        return f"Error: {error_msg}"
    except FileNotFoundError:
        error_msg = f"Command not found: {executable}"
        logging.error(error_msg)
        return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Failed to execute command {command_display_str}: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}"

def get_ssh_client(node: str) -> Optional[paramiko.SSHClient]:
    """
    Get or create an SSH client for a node
    
    Args:
        node: Node hostname
        
    Returns:
        paramiko.SSHClient: SSH client or None if failed
    """
    global CONFIG_DATA, SSH_CLIENTS
    
    # Check if SSH is enabled
    if not CONFIG_DATA['troubleshoot']['ssh']['enabled']:
        logging.warning("SSH is disabled in configuration")
        return None
    
    # Check if node is in allowed nodes
    if node not in CONFIG_DATA['troubleshoot']['ssh']['nodes']:
        logging.warning(f"Node '{node}' is not in the allowed SSH nodes list")
        return None
    
    # Return existing client if available
    if node in SSH_CLIENTS:
        return SSH_CLIENTS[node]
    
    # Create new SSH client
    ssh_config = CONFIG_DATA['troubleshoot']['ssh']
    client = paramiko.SSHClient()
    # client.set_missing_host_key_policy(paramiko.AutoAddPolicy()) # Removed
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    
    # Try to connect with retries
    retries = ssh_config['retries']
    retry_backoff = ssh_config['retry_backoff_seconds']
    
    for attempt in range(retries + 1):
        try:
            client.connect(
                node,
                username=ssh_config['user'],
                key_filename=ssh_config['key_path']
            )
            SSH_CLIENTS[node] = client
            logging.info(f"SSH connection established to {node}")
            return client
        except Exception as e:
            if attempt < retries:
                wait_time = retry_backoff * (2 ** attempt)
                logging.warning(f"SSH connection to {node} failed: {e}. Retrying in {wait_time} seconds (attempt {attempt+1}/{retries})")
                time.sleep(wait_time)
            else:
                logging.error(f"SSH connection to {node} failed after {retries} attempts: {e}")
                return None

def ssh_execute(node: str, command: str, purpose: str) -> str:
    """
    Execute a command on a remote node via SSH
    
    Args:
        node: Node hostname
        command: Command to execute
        purpose: Purpose of the command
        
    Returns:
        str: Command output
    """
    global INTERACTIVE_MODE
    
    # Validate command
    executable = ""
    if command: # Ensure command is not an empty string
        executable = command.split()[0]
        if not validate_command(executable):
            return f"Error: SSH command executable '{executable}' is not allowed"
    else:
        return "Error: Empty command provided for SSH execution"
            
    # Prompt for approval in interactive mode
    if INTERACTIVE_MODE:
        ssh_command_display = f"ssh {node} '{command}'"
        if not prompt_for_approval(ssh_command_display, purpose):
            return "Command execution cancelled by user"
    
    # Get SSH client
    client = get_ssh_client(node)
    if not client:
        return f"Error: Failed to establish SSH connection to {node}"
    
    # Execute command
    try:
        logging.info(f"Executing SSH command on {node}: {command}")
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if error:
            logging.warning(f"SSH command produced errors: {error}")
            return f"Output:\n{output}\n\nErrors:\n{error}"
        
        logging.debug(f"SSH command output: {output}")
        return output
    except Exception as e:
        error_msg = f"Failed to execute SSH command: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}"

def close_ssh_connections():
    """Close all SSH connections"""
    global SSH_CLIENTS
    
    for node, client in SSH_CLIENTS.items():
        try:
            client.close()
            logging.info(f"SSH connection to {node} closed")
        except Exception as e:
            logging.warning(f"Error closing SSH connection to {node}: {e}")
    
    SSH_CLIENTS = {}

# Define tools for the LangGraph ReAct agent

@tool
def kubectl_get(resource: str, name: Optional[str] = None, namespace: Optional[str] = None) -> str:
    """Get Kubernetes resources in YAML format"""
    return execute_command(
        (
            ["kubectl", "get", resource] +
            ([name] if name else []) +
            (["-n", namespace] if namespace else []) +
            ["-o", "yaml"]
        ),
        f"Get {resource} {name or 'all'} {f'in namespace {namespace}' if namespace else ''} in YAML format"
    )

@tool
def kubectl_describe(resource: str, name: Optional[str] = None, namespace: Optional[str] = None) -> str:
    """Describe Kubernetes resources"""
    return execute_command(
        (
            ["kubectl", "describe", resource] +
            ([name] if name else []) +
            (["-n", namespace] if namespace else [])
        ),
        f"Describe {resource} {name or 'all'} {f'in namespace {namespace}' if namespace else ''}"
    )

@tool
def kubectl_logs(pod_name: str, namespace: str, container: Optional[str] = None, tail: Optional[int] = None) -> str:
    """Get logs from a pod"""
    return execute_command(
        (
            ["kubectl", "logs", pod_name] +
            (["-c", container] if container else []) +
            ["-n", namespace] +
            ([f"--tail={tail}"] if tail is not None else [])
        ),
        f"Get logs from pod {namespace}/{pod_name} {f'container {container}' if container else ''}"
    )

@tool
def kubectl_exec(pod_name: str, namespace: str, command: str) -> str:
    """Execute a command in a pod"""
    return execute_command(
        (["kubectl", "exec", pod_name, "-n", namespace, "--"] + shlex.split(command)),
        f"Execute command '{command}' in pod {namespace}/{pod_name}"
    )

@tool
def ssh_command(node: str, command: str) -> str:
    """Execute a command on a remote node via SSH"""
    return ssh_execute(
        node,
        command,
        f"Execute command '{command}' on node {node}"
    )

@tool
def create_test_pod_tool(name: str, namespace: str, pvc_name: str, node_name: str, test_type: str, storage_class: Optional[str] = None, storage_size: Optional[str] = None) -> str:
    """Create a test pod to validate storage functionality"""
    # Note: The original tool name was "create_test_pod".
    # We append "_tool" to avoid conflict with the helper function `create_test_pod`
    return create_test_pod(
        name, namespace, pvc_name, node_name, test_type, storage_class, storage_size
    )

def define_tools(pod_name: str, namespace: str, volume_path: str) -> List[Any]: # Changed return type
    """
    Define tools for the LangGraph ReAct agent
    
    Args:
        pod_name: Name of the pod with the error (unused in this refactored version but kept for signature consistency)
        namespace: Namespace of the pod (unused in this refactored version but kept for signature consistency)
        volume_path: Path of the volume with I/O error (unused in this refactored version but kept for signature consistency)
        
    Returns:
        List[Any]: List of tool callables
    """
    tools = [
        kubectl_get,
        kubectl_describe,
        kubectl_logs,
        kubectl_exec,
        ssh_command,
        create_test_pod_tool 
    ]
    return tools

def create_test_pod(name: str, namespace: str, pvc_name: str, node_name: str, 
                   test_type: str, storage_class: Optional[str] = None, 
                   storage_size: Optional[str] = None) -> str:
    """
    Create a test pod and optionally a PVC to validate storage functionality
    
    Args:
        name: Pod name
        namespace: Pod namespace
        pvc_name: PVC name to use or create
        node_name: Node name for pod scheduling
        test_type: Test type ('read_write' or 'disk_speed')
        storage_class: Storage class for new PVC (optional)
        storage_size: Storage size for new PVC (optional)
        
    Returns:
        str: Result of the operation
    """
    global INTERACTIVE_MODE
    
    unique_suffix = str(uuid.uuid4().hex)[:8]
    pvc_filename_full_path = None # Initialize to None
    pod_filename_full_path = f"{name}-{unique_suffix}.yaml" # pod_filename is always generated

    # Check if we need to create a new PVC
    create_pvc = storage_class is not None and storage_size is not None
    
    if create_pvc:
        pvc_filename_full_path = f"{pvc_name}-{unique_suffix}.yaml"
        pvc_yaml = f"""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {pvc_name}
  namespace: {namespace}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: {storage_size}
  storageClassName: {storage_class}
"""
    
    # Define Pod YAML based on test type
    if test_type == "read_write":
        pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {name}
  namespace: {namespace}
spec:
  containers:
  - name: test-container
    image: busybox
    command: ["/bin/sh", "-c", "echo 'Test' > /mnt/test.txt && cat /mnt/test.txt && sleep 3600"]
    volumeMounts:
    - mountPath: "/mnt"
      name: test-volume
  volumes:
  - name: test-volume
    persistentVolumeClaim:
      claimName: {pvc_name}
  nodeName: {node_name}
"""
    elif test_type == "disk_speed":
        pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {name}
  namespace: {namespace}
spec:
  containers:
  - name: test-container
    image: busybox
    command: ["/bin/sh", "-c", "dd if=/dev/zero of=/mnt/testfile bs=1M count=100 && echo 'Write OK' && dd if=/mnt/testfile of=/dev/null bs=1M && echo 'Read OK' && sleep 3600"]
    volumeMounts:
    - mountPath: "/mnt"
      name: test-volume
  volumes:
  - name: test-volume
    persistentVolumeClaim:
      claimName: {pvc_name}
  nodeName: {node_name}
"""
    else:
        return f"Error: Invalid test type '{test_type}'"
    
    
    try:
        # --- Start of try block ---
        if create_pvc and pvc_filename_full_path:
            logging.debug(f"Writing temporary PVC YAML to: {pvc_filename_full_path}")
            with open(pvc_filename_full_path, "w") as f:
                f.write(pvc_yaml)
        
        logging.debug(f"Writing temporary Pod YAML to: {pod_filename_full_path}")
        with open(pod_filename_full_path, "w") as f:
            f.write(pod_yaml)
        
        # Apply YAML files
        result = ""
        if create_pvc and pvc_filename_full_path:
            pvc_display_name = pvc_filename_full_path.split('/')[-1]
            pvc_apply_cmd = ["kubectl", "apply", "-f", pvc_filename_full_path]
            pvc_purpose = f"Create PVC {namespace}/{pvc_display_name}"
            if INTERACTIVE_MODE:
                if not prompt_for_approval(' '.join(pvc_apply_cmd), pvc_purpose):
                    return "Operation cancelled by user" # Cleanup will happen in finally
            
            pvc_result = execute_command(pvc_apply_cmd, pvc_purpose)
            result += f"PVC creation result:\n{pvc_result}\n\n"
        
        pod_display_name = pod_filename_full_path.split('/')[-1]
        pod_apply_cmd = ["kubectl", "apply", "-f", pod_filename_full_path]
        pod_purpose = f"Create test pod {namespace}/{pod_display_name}"
        if INTERACTIVE_MODE:
            if not prompt_for_approval(' '.join(pod_apply_cmd), pod_purpose):
                return "Operation cancelled by user" # Cleanup will happen in finally
        
        pod_result = execute_command(pod_apply_cmd, pod_purpose)
        result += f"Pod creation result:\n{pod_result}\n\n"
        
        # Wait for pod to start
        result += "Waiting for pod to start...\n"
        time.sleep(5) # time module is imported
        
        # Get pod status
        pod_get_cmd = ["kubectl", "get", "pod", name, "-n", namespace]
        pod_get_purpose = f"Check status of pod {namespace}/{name}"
        pod_status = execute_command(pod_get_cmd, pod_get_purpose)
        result += f"Pod status:\n{pod_status}\n\n"
        
        return result
        # --- End of try block ---
    except Exception as e: # Catching broader exceptions during pod/PVC creation steps
        error_msg = f"Failed during test pod/PVC creation or execution: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}" # The error string will be returned, and finally will execute
    finally:
        # --- Start of finally block ---
        if pvc_filename_full_path and os.path.exists(pvc_filename_full_path):
            try:
                os.remove(pvc_filename_full_path)
                logging.debug(f"Successfully deleted temporary file: {pvc_filename_full_path}")
            except Exception as e:
                logging.warning(f"Failed to delete temporary file {pvc_filename_full_path}: {e}")
            
        if os.path.exists(pod_filename_full_path): # pod_filename_full_path is always defined
            try:
                os.remove(pod_filename_full_path)
                logging.debug(f"Successfully deleted temporary file: {pod_filename_full_path}")
            except Exception as e:
                logging.warning(f"Failed to delete temporary file {pod_filename_full_path}: {e}")
        # --- End of finally block ---

def create_troubleshooting_graph(pod_name: str, namespace: str, volume_path: str, phase: str = "analysis"):
    """
    Create a LangGraph ReAct graph for troubleshooting
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        phase: Current troubleshooting phase ("analysis" or "remediation")
        
    Returns:
        StateGraph: LangGraph StateGraph
    """
    global CONFIG_DATA
    
    # Initialize language model
    model = init_chat_model(
        CONFIG_DATA['llm']['model'],
        api_key=CONFIG_DATA['llm']['api_key'],
        base_url=CONFIG_DATA['llm']['api_endpoint'],
        temperature=CONFIG_DATA['llm']['temperature'],
        max_tokens=CONFIG_DATA['llm']['max_tokens']
    )
    
    # Get tools
    tools = define_tools(pod_name, namespace, volume_path)
    
    # Define function to call the model
    def call_model(state: MessagesState):
        # Add system prompt with CSI Baremetal knowledge and phase-specific guidance
        phase_specific_guidance = ""
        if phase == "analysis":
            phase_specific_guidance = """
You are currently in Phase 1 (Analysis). Your task is to:
1. Diagnose the root cause of the volume I/O error.
2. Create a clear fix plan with step-by-step remediation actions.
3. Present your findings as a JSON object with two keys: "root_cause" and "fix_plan". For example:
   {
     "root_cause": "The disk is full due to excessive log files.",
     "fix_plan": "Step 1: Identify large log files in volume X. Step 2: Archive and delete old log files. Step 3: Implement log rotation."
   }
4. Ensure this JSON object is the final part of your response.
5. DO NOT attempt to execute any remediation actions yet.

Focus only on diagnostics and analysis in this phase. The remediation actions will be executed in Phase 2 if approved.
"""
        elif phase == "remediation":
            phase_specific_guidance = """
You are currently in Phase 2 (Remediation). Your task is to:
1. Execute the fix plan from Phase 1
2. Implement remediation actions while respecting allowed/disallowed commands
3. Verify that the issue is resolved after implementing fixes
4. Report the final resolution status

Focus on implementing the fix plan safely and effectively. Validate that each fix resolves the underlying issue.
"""
        
        system_message = {
            "role": "system",
            "content": f"""You are an AI assistant powering a Kubernetes volume troubleshooting system using LangGraph ReAct. Your role is to monitor and resolve volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver (csi-baremetal.dell.com). Exclude remote storage (e.g., NFS, Ceph). 

{phase_specific_guidance}

Follow these strict guidelines for safe, reliable, and effective troubleshooting:

1. **Safety and Security**:
   - Only execute commands listed in `commands.allowed` in `config.yaml` (e.g., `kubectl get drive`, `smartctl -a`, `fio`).
   - Never execute commands in `commands.disallowed` (e.g., `fsck`, `chmod`, `dd`, `kubectl delete pod`) unless explicitly enabled in `config.yaml` and approved by the user in interactive mode.
   - Validate all commands for safety and relevance before execution.
   - Log all SSH commands and outputs for auditing, using secure credential handling as specified in `config.yaml`.

2. **Interactive Mode**:
   - If `troubleshoot.interactive_mode` is `true` in `config.yaml`, prompt the user before executing any command or tool with: "Proposed command: <command>. Purpose: <purpose>. Approve? (y/n)". Include a clear purpose (e.g., "Check drive health with kubectl get drive").
   - If disabled, execute allowed commands automatically, respecting `config.yaml` restrictions.

3. **Troubleshooting Process**:
   - Use the LangGraph ReAct module to reason about volume I/O errors based on parameters: `PodName`, `PodNamespace`, and `VolumePath`.
   - Follow this structured diagnostic process for local HDD/SSD/NVMe disks managed by CSI Baremetal:
     a. **Confirm Issue**: Run `kubectl logs <pod-name> -n <namespace>` and `kubectl describe pod <pod-name> -n <namespace>` to identify errors (e.g., "Input/Output Error", "Permission Denied", "FailedMount").
     b. **Verify Configurations**: Check Pod, PVC, and PV with `kubectl get pod/pvc/pv -o yaml`. Confirm PV uses local volume, valid disk path (e.g., `/dev/sda`), and correct `nodeAffinity`. Verify mount points with `kubectl exec <pod-name> -n <namespace> -- df -h` and `ls -ld <mount-path>`.
     c. **Check CSI Baremetal Driver and Resources**:
        - Identify driver: `kubectl get storageclass <storageclass-name> -o yaml` (e.g., `csi-baremetal-sc-ssd`).
        - Verify driver pod: `kubectl get pods -n kube-system -l app=csi-baremetal` and `kubectl logs <driver-pod-name> -n kube-system`. Check for errors like "failed to mount".
        - Confirm driver registration: `kubectl get csidrivers`.
        - Check drive status: `kubectl get drive -o wide` and `kubectl get drive <drive-uuid> -o yaml`. Verify `Health: GOOD`, `Status: ONLINE`, `Usage: IN_USE`, and match `Path` (e.g., `/dev/sda`) with `VolumePath`.
        - Map drive to node: `kubectl get csibmnode` to correlate `NodeId` with hostname/IP.
        - Check AvailableCapacity: `kubectl get ac -o wide` to confirm size, storage class, and location (drive UUID).
        - Check LogicalVolumeGroup: `kubectl get lvg` to verify `Health: GOOD` and associated drive UUIDs.
     d. **Test Driver**: Create a test PVC/Pod using `csi-baremetal-sc-ssd` storage class (use provided YAML template). Check logs and events for read/write errors.
     e. **Verify Node Health**: Run `kubectl describe node <node-name>` to ensure `Ready` state and no `DiskPressure`. Verify disk mounting via SSH: `mount | grep <disk-path>`.
     f. **Check Permissions**: Verify file system permissions with `kubectl exec <pod-name> -n <namespace> -- ls -ld <mount-path>` and Pod `SecurityContext` settings.
     g. **Inspect Control Plane**: Check `kube-controller-manager` and `kube-scheduler` logs for provisioning/scheduling issues.
     h. **Test Hardware Disk**:
        - Identify disk: `kubectl get pv -o yaml` and `kubectl get drive <drive-uuid> -o yaml` to confirm `Path`.
        - Check health: `kubectl get drive <drive-uuid> -o yaml` and `ssh <node-name> sudo smartctl -a /dev/<disk-device>`. Verify `Health: GOOD`, zero `Reallocated_Sector_Ct` or `Current_Pending_Sector`.
        - Test performance: `ssh <node-name> sudo fio --name=read_test --filename=/dev/<disk-device> --rw=read --bs=4k --size=100M --numjobs=1 --iodepth=1 --runtime=60 --time_based --group_reporting`.
        - Check file system (if unmounted): `ssh <node-name> sudo fsck /dev/<disk-device>` (requires approval).
        - Test via Pod: Create a test Pod (use provided YAML) and check logs for "Write OK" and "Read OK".
     i. **Propose Remediations**:
        - Bad sectors: Recommend disk replacement if `kubectl get drive` or SMART shows `Health: BAD` or non-zero `Reallocated_Sector_Ct`.
        - Performance issues: Suggest optimizing I/O scheduler or replacing disk if `fio` results show low IOPS (HDD: 100–200, SSD: thousands, NVMe: tens of thousands).
        - File system corruption: Recommend `fsck` (if enabled/approved) after data backup.
        - Driver issues: Suggest restarting CSI Baremetal driver pod (if enabled/approved) if logs indicate errors.
   - Only propose remediations after analyzing diagnostic data. Ensure write/change commands (e.g., `fsck`, `kubectl delete pod`) are allowed and approved.

4. **Error Handling**:
   - Log all actions, command outputs, SSH results, and errors to the configured log file and stdout (if enabled).
   - Handle Kubernetes API or SSH failures with retries as specified in `config.yaml`.
   - If unresolved, provide a detailed report of findings (e.g., logs, drive status, SMART data, test results) and suggest manual intervention.

5. **Constraints**:
   - Restrict operations to the Kubernetes cluster and configured worker nodes; do not access external networks or resources.
   - Do not modify cluster state (e.g., delete pods, change configurations) unless explicitly allowed and approved.
   - Adhere to `troubleshoot.timeout_seconds` for the troubleshooting workflow.
   - Always recommend data backup before suggesting write/change operations (e.g., `fsck`).

6. **Output**:
   - Provide clear, concise explanations of diagnostic steps, findings, and remediation proposals.
   - In interactive mode, format prompts as: "Proposed command: <command>. Purpose: <purpose>. Approve? (y/n)".
   - Include performance benchmarks in reports (e.g., HDD: 100–200 IOPS, SSD: thousands, NVMe: tens of thousands).
   - Log all outputs with timestamps and context for traceability.

You must adhere to these guidelines at all times to ensure safe, reliable, and effective troubleshooting of local disk issues in Kubernetes with the CSI Baremetal driver.
"""
        }
        
        # Handle case where state["messages"] might be a HumanMessage object (not subscriptable)
        # Check if state["messages"] exists and is a list before trying to access elements
        if state["messages"]:
            # Check if state["messages"] is a list
            if isinstance(state["messages"], list):
                # If it's a list and the first message is not a system message, add the system message
                if state["messages"][0].type != "system":
                    state["messages"] = [system_message] + state["messages"]
            else:
                # If it's not a list (likely a HumanMessage object), convert to a list with system message first
                state["messages"] = [system_message, state["messages"]]
        else:
            # If state["messages"] is empty or None, initialize with just the system message
            state["messages"] = [system_message]
        
        # Call the model and bind tools
        response = model.bind_tools(tools).invoke(state["messages"])
        return {"messages": state["messages"] + [response]}
    
    # Build state graph
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges(
        "call_model",
        tools_condition,
        {
            "tools": "tools",
            "none": END
        }
    )
    builder.add_edge("tools", "call_model")
    graph = builder.compile()
    
    return graph

async def run_analysis_phase(pod_name: str, namespace: str, volume_path: str) -> Tuple[str, str]:
    """
    Run Phase 1: Analysis to identify root cause and generate fix plan
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        
    Returns:
        Tuple[str, str]: Root cause and fix plan
    """
    global CONFIG_DATA
    
    try:
        # Create troubleshooting graph for analysis phase
        graph = create_troubleshooting_graph(pod_name, namespace, volume_path, phase="analysis")
        
        # Initial query with problem details for analysis phase
        query = f"Phase 1 - Analysis: Identify the root cause of volume I/O error for pod {pod_name} in namespace {namespace} at volume path {volume_path}. Focus on diagnosis and root cause analysis ONLY. Do not attempt to fix the issue yet."
        formatted_query = {"messages": [{"role": "user", "content": query}]}
        
        # Set timeout
        timeout_seconds = CONFIG_DATA['troubleshoot']['timeout_seconds']
        
        # Run graph to process analysis with timeout
        logging.info(f"Starting analysis phase with timeout of {timeout_seconds} seconds")
        response = await asyncio.wait_for(
            graph.ainvoke(formatted_query),
            timeout=timeout_seconds
        )
        
        # Extract analysis results
        # Handle case where response["messages"] might not be a list or might be empty
        if response["messages"]:
            if isinstance(response["messages"], list):
                final_message = response["messages"][-1]["content"]
            else:
                # If it's not a list (e.g., a single message object), try to get content directly
                final_message = response["messages"].get("content", "Failed to extract content from non-list messages")
        else:
            final_message = "Failed to generate analysis results"
        
        # Parse root cause and fix plan from the analysis results
        final_message_content = final_message # Assuming final_message is the string content
        root_cause = "Unknown" # Default value
        fix_plan = "No specific fix plan generated" # Default value

        try:
            # Attempt to find and parse the JSON block
            json_start_index = final_message_content.find('{')
            # Ensure rfind starts search from where json_start_index was found, if found.
            json_end_index = final_message_content.rfind('}', json_start_index if json_start_index != -1 else 0) + 1
            
            if json_start_index != -1 and json_end_index != -1 and json_start_index < json_end_index:
                json_str = final_message_content[json_start_index:json_end_index]
                parsed_json = json.loads(json_str)
                root_cause = parsed_json.get("root_cause", "Unknown root cause (key 'root_cause' missing from JSON)")
                fix_plan = parsed_json.get("fix_plan", "No fix plan provided (key 'fix_plan' missing from JSON)")
                logging.info("Successfully parsed root cause and fix plan from LLM JSON output.")
            else:
                # This custom exception helps differentiate from json.loads actual decoding error
                raise json.JSONDecodeError("No JSON object found in LLM output", final_message_content, 0)

        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse LLM output as JSON: {e}. Content: '{final_message_content}'")
            logging.info("Attempting fallback to string parsing for root cause and fix plan.")
            # Fallback to old string parsing method
            if "Root cause:" in final_message_content:
                parts = final_message_content.split("Root cause:", 1)
                if len(parts) > 1:
                    root_cause_section = parts[1].strip()
                    if "Fix plan:" in root_cause_section:
                        root_cause = root_cause_section.split("Fix plan:", 1)[0].strip()
                        fix_plan = root_cause_section.split("Fix plan:", 1)[1].strip()
                    else:
                        root_cause = root_cause_section
                else: # Should not happen if "Root cause:" is in final_message_content
                    root_cause = "Unknown (fallback parsing error after 'Root cause:' detected)"
                    fix_plan = "Unknown (fallback parsing error after 'Root cause:' detected)"
            else:
                root_cause = "Unknown (Failed to parse LLM output, no JSON or 'Root cause:' keyword)"
                fix_plan = "Unknown (Failed to parse LLM output, no JSON or 'Root cause:' keyword)"
        
        logging.info(f"Analysis completed for pod {namespace}/{pod_name}, volume {volume_path}")
        logging.info(f"Root cause: {root_cause}")
        logging.info(f"Fix plan: {fix_plan}")
        
        return root_cause, fix_plan
        
    except asyncio.TimeoutError:
        error_msg = f"Analysis phase timed out after {timeout_seconds} seconds"
        logging.error(error_msg)
        return f"Error: {error_msg}", "Timeout occurred during analysis"
    except Exception as e:
        error_msg = f"Error during analysis phase: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}", "Error occurred during analysis"

async def run_remediation_phase(pod_name: str, namespace: str, volume_path: str, root_cause: str, fix_plan: str) -> str:
    """
    Run Phase 2: Remediation to resolve the identified issue
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        root_cause: Identified root cause from analysis phase
        fix_plan: Generated fix plan from analysis phase
        
    Returns:
        str: Result of remediation
    """
    global CONFIG_DATA
    
    try:
        # Create troubleshooting graph for remediation phase
        graph = create_troubleshooting_graph(pod_name, namespace, volume_path, phase="remediation")
        
        # Initial query with problem details for remediation phase
        query = f"""Phase 2 - Remediation: Resolve volume I/O error for pod {pod_name} in namespace {namespace} at volume path {volume_path}.
Root cause: {root_cause}
Fix plan: {fix_plan}

Implement the fix plan while respecting allowed/disallowed commands. After implementing fixes, verify that the issue is resolved."""
        formatted_query = {"messages": [{"role": "user", "content": query}]}
        
        # Set timeout
        timeout_seconds = CONFIG_DATA['troubleshoot']['timeout_seconds']
        
        # Run graph to process remediation with timeout
        logging.info(f"Starting remediation phase with timeout of {timeout_seconds} seconds")
        response = await asyncio.wait_for(
            graph.ainvoke(formatted_query),
            timeout=timeout_seconds
        )
        
        # Extract remediation results
        # Handle case where response["messages"] might not be a list or might be empty
        if response["messages"]:
            if isinstance(response["messages"], list):
                final_message = response["messages"][-1]["content"]
            else:
                # If it's not a list (e.g., a single message object), try to get content directly
                final_message = response["messages"].get("content", "Failed to extract content from non-list messages")
        else:
            final_message = "Failed to generate remediation results"
        
        logging.info(f"Remediation completed for pod {namespace}/{pod_name}, volume {volume_path}")
        logging.info(f"Result: {final_message}")
        
        return final_message
        
    except asyncio.TimeoutError:
        error_msg = f"Remediation phase timed out after {timeout_seconds} seconds"
        logging.error(error_msg)
        return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Error during remediation phase: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}"

async def troubleshoot(pod_name: str, namespace: str, volume_path: str):
    """
    Two-phase troubleshooting process: Analysis and Remediation
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
    """
    global CONFIG_DATA, INTERACTIVE_MODE
    
    try:
        # Initialize Kubernetes client
        #init_kubernetes_client()
        
        # Phase 1: Analysis
        logging.info("Starting Phase 1: Analysis")
        root_cause, fix_plan = await run_analysis_phase(pod_name, namespace, volume_path)
        
        # Check if analysis was successful
        if root_cause.startswith("Error:"):
            return f"Analysis phase failed: {root_cause}"
        
        # Check if we should proceed to remediation
        proceed_to_remediation = CONFIG_DATA['troubleshoot']['auto_fix']
        
        if not proceed_to_remediation:
            # Prompt user for confirmation to proceed to remediation
            print("\n=== Analysis Results ===")
            print(f"Root cause: {root_cause}")
            print(f"Fix plan: {fix_plan}")
            response = input("\nProceed to remediation phase? (y/n): ").strip().lower()
            proceed_to_remediation = response == 'y' or response == 'yes'
        
        # Phase 2: Remediation (if approved)
        if proceed_to_remediation:
            logging.info("Starting Phase 2: Remediation")
            result = await run_remediation_phase(pod_name, namespace, volume_path, root_cause, fix_plan)
            
            if result.startswith("Error:"):
                return f"Remediation phase failed: {result}"
            
            return result
        else:
            logging.info("Remediation phase skipped per user request")
            return f"Analysis completed. Root cause: {root_cause}\nFix plan: {fix_plan}\nRemediation skipped per user request."
    except Exception as e:
        error_msg = f"Error during troubleshooting: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}"
    finally:
        # Close SSH connections
        close_ssh_connections()

def main():
    """Main function"""
    global CONFIG_DATA, INTERACTIVE_MODE
    
    # Check command line arguments
    if len(sys.argv) != 4:
        print("Usage: python troubleshoot.py <pod_name> <namespace> <volume_path>")
        sys.exit(1)
    
    pod_name = sys.argv[1]
    namespace = sys.argv[2]
    volume_path = sys.argv[3]
    
    # Load configuration
    CONFIG_DATA = load_config()
    
    # Set up logging
    setup_logging(CONFIG_DATA)
    
    # Set interactive mode
    INTERACTIVE_MODE = CONFIG_DATA['troubleshoot']['interactive_mode']
    
    logging.info(f"Starting troubleshooting for pod {namespace}/{pod_name}, volume {volume_path}")
    logging.info(f"Interactive mode: {INTERACTIVE_MODE}")
    
    # Run troubleshooting
    try:
        result = asyncio.run(troubleshoot(pod_name, namespace, volume_path))
        print("\n=== Troubleshooting Results ===")
        print(result)
        print("==============================\n")
    except KeyboardInterrupt:
        logging.info("Troubleshooting stopped by user")
        print("\nTroubleshooting stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        print(f"\nFatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
