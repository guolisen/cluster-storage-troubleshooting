#!/usr/bin/env python3
"""
Kubernetes Volume I/O Error Troubleshooting Script

This script uses LangGraph ReAct to diagnose and resolve volume I/O errors
in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver.

Enhanced with comprehensive mode for multi-issue analysis using knowledge graphs.
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
import shlex
from typing import Dict, List, Any, Optional, Tuple
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langchain.chat_models import init_chat_model

# Import knowledge graph components
from knowledge_graph import IssueKnowledgeGraph, IssueNode, IssueType, IssueSeverity
from issue_collector import ComprehensiveIssueCollector

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

def execute_command(command_list: List[str], purpose: str, requires_approval: bool = True) -> str:
    """
    Execute a command and return its output
    
    Args:
        command_list: Command to execute as a list of strings
        purpose: Purpose of the command
        requires_approval: Whether this command requires user approval in interactive mode
        
    Returns:
        str: Command output
    """
    global CONFIG_DATA, INTERACTIVE_MODE
    
    if not command_list:
        logging.error("execute_command received an empty command_list")
        return "Error: Empty command list provided"

    executable = command_list[0]
    command_display_str = ' '.join(command_list)

    # Check if command is explicitly disallowed
    if CONFIG_DATA['commands']['disallowed']:
        for disallowed in CONFIG_DATA['commands']['disallowed']:
            # Handle exact match
            if disallowed == executable:
                logging.warning(f"Command '{executable}' is explicitly disallowed")
                return f"Error: Command executable '{executable}' is not allowed"
                
            # Handle wildcards
            if disallowed.endswith('*'):
                prefix = disallowed[:-1]  # Remove the * character
                if executable.startswith(prefix):
                    logging.warning(f"Command '{executable}' matches disallowed wildcard pattern '{disallowed}'")
                    return f"Error: Command executable '{executable}' is not allowed"
    
    # Prompt for approval in interactive mode if required
    if INTERACTIVE_MODE and requires_approval:
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
    if command:
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

# Mock tool executor for comprehensive mode
async def execute_tool_mock(tool_name: str, params: Dict[str, Any]) -> str:
    """
    Mock tool executor for comprehensive mode
    In a real implementation, this would execute the actual kubectl/ssh commands
    """
    logging.info(f"Executing tool: {tool_name} with params: {params}")
    
    # Simulate tool execution results based on tool type
    if tool_name == "kubectl_describe":
        if params.get("resource") == "pod":
            return f"""
Name:         {params.get('name', 'test-pod')}
Namespace:    {params.get('namespace', 'default')}
Node:         kind-control-plane
Status:       Running
Events:
  Warning  FailedMount  10m  kubelet  MountVolume.SetUp failed for volume "test-volume": mount failed: exit status 32
"""
        elif params.get("resource") == "node":
            return f"""
Name:         {params.get('name', 'kind-control-plane')}
Conditions:
  Ready            True
  DiskPressure     False
  MemoryPressure   False
"""
    
    elif tool_name == "kubectl_logs":
        return f"""
[ERROR] Failed to write to /mnt/data: Input/output error
[ERROR] Volume mount failed with error: Transport endpoint is not connected
"""
    
    elif tool_name == "kubectl_get":
        resource = params.get("resource", "")
        if resource == "drives":
            return """
NAME                                          HEALTH   STATUS    SIZE      STORAGECLASS   NODE
drive-8f9b5c4d-e1a2-4b3c-9d8e-f7a6b5c4d3e2  GOOD     ONLINE    100Gi     ssd            kind-control-plane
drive-1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p  BAD      OFFLINE   100Gi     ssd            kind-control-plane
"""
        elif resource == "ac":
            return """
NAME                                          SIZE      STORAGECLASS   NODE
ac-8f9b5c4d-e1a2-4b3c-9d8e-f7a6b5c4d3e2     100Gi     ssd            kind-control-plane
"""
        elif resource == "pods":
            return """
NAME                READY   STATUS    RESTARTS   AGE    NODE
test-pod           0/1     Running   0          10m    kind-control-plane
app-pod            1/1     Running   0          5m     kind-control-plane
"""
    
    elif tool_name == "ssh_command":
        command = params.get("command", "")
        if "df -h" in command:
            return """
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        20G   18G  1.2G  94% /
/dev/sdb1       100G   45G   50G  48% /var/lib/kubelet
"""
        elif "dmesg" in command:
            return """
[12345.678] sd 0:0:0:1: [sdb] tag#0 FAILED Result: hostbyte=DID_OK driverbyte=DRIVER_SENSE
[12346.789] sd 0:0:0:1: [sdb] tag#0 Sense Key : Medium Error [current]
[12347.890] EXT4-fs error (device sdb1): ext4_journal_check_start:83: Detected aborted journal
"""
        elif "smartctl" in command:
            return """
SMART Health Status: PASSED
5 Reallocated_Sector_Ct   0x0033   100   100   036    Pre-fail  Always       -       0
197 Current_Pending_Sector  0x0032   100   100   000    Old_age   Always       -       12
"""
    
    # Default response
    await asyncio.sleep(0.1)  # Simulate command execution time
    return f"Mock output for {tool_name} with {params}"

# Define tools for the LangGraph ReAct agent

@tool
def kubectl_get(resource: str, name: Optional[str] = None, namespace: Optional[str] = None) -> str:
    """Get Kubernetes resources in YAML format"""
    # First check if this is a custom resource by checking if it's singular
    if resource.lower() in ["drive", "drives", "csibmnode", "csibmnodes", "ac", "acs", "lvg", "lvgs", "acr", "acrs"]:
        # Try to verify CRD exists first
        crd_check = execute_command(
            ["kubectl", "get", "crd", f"{resource}.csi-baremetal.dell.com"],
            f"Check if CRD {resource}.csi-baremetal.dell.com exists"
        )
        if crd_check.startswith("Error:"):
            return f"Resource type '{resource}' is not available in this cluster. This may be because the CSI Baremetal driver is not installed or its CRDs are not properly registered. Continuing with other diagnostics. Error details: {crd_check}"
    
    # Execute the original command
    result = execute_command(
        (
            ["kubectl", "get", resource] +
            ([name] if name else []) +
            (["-n", namespace] if namespace else []) +
            ["-o", "yaml"]
        ),
        f"Get {resource} {name or 'all'} {f'in namespace {namespace}' if namespace else ''} in YAML format",
        requires_approval=False
    )
    
    # If the command failed with "resource type not found" error, provide a more helpful message
    if "the server doesn't have a resource type" in result:
        return f"Resource type '{resource}' is not available in this cluster. This may be because the CSI Baremetal driver is not installed or its CRDs are not properly registered. Continuing with other diagnostics."
    
    return result

@tool
def kubectl_describe(resource: str, name: Optional[str] = None, namespace: Optional[str] = None) -> str:
    """Describe Kubernetes resources"""
    return execute_command(
        (
            ["kubectl", "describe", resource] +
            ([name] if name else []) +
            (["-n", namespace] if namespace else [])
        ),
        f"Describe {resource} {name or 'all'} {f'in namespace {namespace}' if namespace else ''}",
        requires_approval=False
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
        f"Get logs from pod {namespace}/{pod_name} {f'container {container}' if container else ''}",
        requires_approval=False
    )

@tool
def kubectl_exec(pod_name: str, namespace: str, command: str) -> str:
    """Execute a command in a pod"""
    return execute_command(
        (["kubectl", "exec", pod_name, "-n", namespace, "--"] + shlex.split(command)),
        f"Execute command '{command}' in pod {namespace}/{pod_name}",
        requires_approval=False
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
    return create_test_pod(
        name, namespace, pvc_name, node_name, test_type, storage_class, storage_size
    )

def define_tools(pod_name: str, namespace: str, volume_path: str) -> List[Any]:
    """
    Define tools for the LangGraph ReAct agent
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        
    Returns:
        List[Any]: List of tool callables
    """
    tools = [
        kubectl_get,
        kubectl_describe,
        kubectl_logs,
        kubectl_exec,
        ssh_command,
        create_test_pod_tool,
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
    pvc_filename_full_path = None
    pod_filename_full_path = f"{name}-{unique_suffix}.yaml"

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
                    return "Operation cancelled by user"
            
            pvc_result = execute_command(pvc_apply_cmd, pvc_purpose)
            result += f"PVC creation result:\n{pvc_result}\n\n"
        
        pod_display_name = pod_filename_full_path.split('/')[-1]
        pod_apply_cmd = ["kubectl", "apply", "-f", pod_filename_full_path]
        pod_purpose = f"Create test pod {namespace}/{pod_display_name}"
        if INTERACTIVE_MODE:
            if not prompt_for_approval(' '.join(pod_apply_cmd), pod_purpose):
                return "Operation cancelled by user"
        
        pod_result = execute_command(pod_apply_cmd, pod_purpose)
        result += f"Pod creation result:\n{pod_result}\n\n"
        
        # Wait for pod to start
        result += "Waiting for pod to start...\n"
        time.sleep(5)
        
        # Get pod status
        pod_get_cmd = ["kubectl", "get", "pod", name, "-n", namespace]
        pod_get_purpose = f"Check status of pod {namespace}/{name}"
        pod_status = execute_command(pod_get_cmd, pod_get_purpose)
        result += f"Pod status:\n{pod_status}\n\n"
        
        return result
    except Exception as e:
        error_msg = f"Failed during test pod/PVC creation or execution: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}"
    finally:
        if pvc_filename_full_path and os.path.exists(pvc_filename_full_path):
            try:
                os.remove(pvc_filename_full_path)
                logging.debug(f"Successfully deleted temporary file: {pvc_filename_full_path}")
            except Exception as e:
                logging.warning(f"Failed to delete temporary file {pvc_filename_full_path}: {e}")
            
        if os.path.exists(pod_filename_full_path):
            try:
                os.remove(pod_filename_full_path)
                logging.debug(f"Successfully deleted temporary file: {pod_filename_full_path}")
            except Exception as e:
                logging.warning(f"Failed to delete temporary file {pod_filename_full_path}: {e}")

async def run_comprehensive_analysis(pod_name: str, namespace: str, volume_path: str) -> str:
    """
    Run comprehensive troubleshooting with knowledge graph analysis
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        
    Returns:
        str: Comprehensive analysis results
    """
    global CONFIG_DATA
    
    try:
        # Initialize Kubernetes client
        k8s_client = init_kubernetes_client()
        
        # Initialize comprehensive issue collector
        collector = ComprehensiveIssueCollector(k8s_client, CONFIG_DATA)
        
        # Collect all related issues using knowledge graph
        logging.info("Starting comprehensive issue collection...")
        knowledge_graph = await collector.collect_comprehensive_issues(
            pod_name, namespace, volume_path, execute_tool_mock
        )
        
        # Generate comprehensive analysis
        logging.info("Generating comprehensive analysis...")
        analysis = knowledge_graph.generate_comprehensive_analysis()
        
        # Format results
        result = format_comprehensive_results(analysis, knowledge_graph)
        
        return result
        
    except Exception as e:
        error_msg = f"Error during comprehensive troubleshooting: {str(e)}"
        logging.error(error_msg)
        return f"Comprehensive troubleshooting failed: {error_msg}"

def format_comprehensive_results(analysis: Dict[str, Any], graph: IssueKnowledgeGraph) -> str:
    """Format comprehensive analysis results for display"""
    
    result = "=== COMPREHENSIVE STORAGE TROUBLESHOOTING RESULTS ===\n\n"
    
    # Summary
    summary = analysis["summary"]
    result += f"SUMMARY:\n"
    result += f"  Total Issues Found: {summary['total_issues']}\n"
    result += f"  Critical Issues: {summary['critical_issues']}\n"
    result += f"  High Priority Issues: {summary['high_priority_issues']}\n"
    
    if summary.get('primary_issue'):
        primary = summary['primary_issue']
        result += f"  Primary Issue: {primary['title']} ({primary['severity']})\n"
    
    result += "\n"
    
    # Knowledge Graph Visualization
    result += graph.visualize_graph()
    result += "\n"
    
    # Root Causes
    if analysis["root_causes"]:
        result += "ROOT CAUSES (Ordered by Impact):\n"
        for i, cause in enumerate(analysis["root_causes"][:3], 1):
            result += f"  {i}. {cause['title']} ({cause['severity']})\n"
            result += f"     Resource: {cause['resource']}\n"
            result += f"     Description: {cause['description']}\n"
            if cause.get('node'):
                result += f"     Node: {cause['node']}\n"
            result += "\n"
    
    # Cascading Failures
    if analysis["cascading_failures"]:
        result += "CASCADING FAILURE PATTERNS:\n"
        for cascade in analysis["cascading_failures"]:
            result += f"  Source: {cascade['source']}\n"
            result += f"  Impact Chain: {' → '.join(cascade['path'])}\n"
            result += f"  Affected Components: {cascade['impact_count']}\n\n"
    
    # Issue Clusters
    if analysis["issue_clusters"]:
        result += "ISSUE CLUSTERS:\n"
        for cluster in analysis["issue_clusters"]:
            result += f"  Cluster: {cluster['cluster_id']} ({cluster['dominant_type']})\n"
            result += f"  Severity: {cluster['severity'].value}\n"
            result += f"  Issues: {', '.join(cluster['issues'])}\n\n"
    
    # Comprehensive Root Cause Analysis
    result += "=== COMPREHENSIVE ROOT CAUSE ANALYSIS ===\n"
    result += analysis["comprehensive_root_cause"]
    result += "\n\n"
    
    # Comprehensive Fix Plan
    result += "=== COMPREHENSIVE FIX PLAN ===\n"
    result += analysis["comprehensive_fix_plan"]
    result += "\n"
    
    # Fix Priority Order
    if analysis["fix_priority_order"]:
        result += "RECOMMENDED FIX ORDER:\n"
        for i, fix in enumerate(analysis["fix_priority_order"], 1):
            result += f"  {i}. {fix['title']} ({fix['severity']})\n"
