#!/usr/bin/env python3
"""
Kubernetes Volume I/O Error Troubleshooting Script

This script uses LangGraph ReAct to diagnose and resolve volume I/O errors
in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver.

Enhanced with Knowledge Graph integration for comprehensive root cause analysis.
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
import re
from typing import Dict, List, Any, Optional, Tuple
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from knowledge_graph import KnowledgeGraph

# Global variables
CONFIG_DATA = None
INTERACTIVE_MODE = False
SSH_CLIENTS = {}
KNOWLEDGE_GRAPH = None

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

def validate_command_prefix_wildcard(command: str, patterns: List[str]) -> bool:
    """
    Validate command against patterns with prefix/wildcard matching
    
    Args:
        command: Command to validate
        patterns: List of patterns to match against
        
    Returns:
        bool: True if command matches any pattern
    """
    if not isinstance(command, str):
        return False
        
    for pattern in patterns:
        # Handle exact match first
        if pattern == command:
            return True
            
        # Handle wildcards
        if pattern.endswith('*'):
            prefix = pattern[:-1]  # Remove the * character
            if command.startswith(prefix):
                return True
    
    return False

def validate_command(command: str) -> bool:
    """
    Validate if a command is allowed based on configuration with prefix/wildcard matching
    
    Args:
        command: Command to validate
        
    Returns:
        bool: True if command is allowed, False otherwise
    """
    global CONFIG_DATA
    
    if not isinstance(command, str):
        logging.error(f"Invalid type for command validation: {type(command)}. Expected string.")
        return False

    # Check if command is explicitly disallowed
    disallowed_patterns = CONFIG_DATA['commands'].get('disallowed', [])
    if validate_command_prefix_wildcard(command, disallowed_patterns):
        logging.warning(f"Command '{command}' matches disallowed pattern")
        return False
    
    # Check if command is allowed (if allowed list exists)
    allowed_patterns = CONFIG_DATA['commands'].get('allowed', [])
    if allowed_patterns:
        if not validate_command_prefix_wildcard(command, allowed_patterns):
            logging.warning(f"Command '{command}' is not in the allowed list")
            return False
    
    return True

def prompt_for_approval(tool_name: str, purpose: str) -> bool:
    """
    Prompt user for tool approval in interactive mode
    
    Args:
        tool_name: Name of the tool
        purpose: Purpose of the tool
        
    Returns:
        bool: True if approved, False otherwise
    """
    if not INTERACTIVE_MODE:
        return True
        
    print(f"\nProposed tool: {tool_name}")
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

    # Validate command
    #if not validate_command(executable):
    #    logging.warning(f"Command '{executable}' is not allowed")
    #    return f"Error: Command executable '{executable}' is not allowed"
    
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
            key_path = os.path.expanduser(ssh_config['key_path'])
            client.connect(
                node,
                username=ssh_config['user'],
                key_filename=key_path
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
    if not command:
        return "Error: Empty command provided for SSH execution"
        
    executable = command.split()[0]
    if not validate_command(executable):
        return f"Error: SSH command executable '{executable}' is not allowed"
            
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

# Enhanced LangGraph Tools

@tool
def kubectl_get(resource: str, name: Optional[str] = None, namespace: Optional[str] = None) -> str:
    """Get Kubernetes resources in YAML format"""
    # Check for CSI Baremetal custom resources
    csi_resources = ["drive", "drives", "csibmnode", "csibmnodes", "ac", "acs", "lvg", "lvgs", "acr", "acrs"]
    if resource.lower() in csi_resources:
        # Verify CRD exists first
        crd_check = execute_command(
            ["kubectl", "get", "crd", f"{resource}.csi-baremetal.dell.com"],
            f"Check if CRD {resource}.csi-baremetal.dell.com exists",
            requires_approval=False
        )
        if crd_check.startswith("Error:"):
            return f"Resource type '{resource}' is not available in this cluster. This may be because the CSI Baremetal driver is not installed or its CRDs are not properly registered. Continuing with other diagnostics."
    
    # Execute the kubectl command
    cmd = ["kubectl", "get", resource]
    if name:
        cmd.append(name)
    if namespace:
        cmd.extend(["-n", namespace])
    cmd.extend(["-o", "yaml"])
    
    result = execute_command(
        cmd,
        f"Get {resource} {name or 'all'} {f'in namespace {namespace}' if namespace else ''} in YAML format",
        requires_approval=False
    )
    
    # Handle resource not found errors gracefully
    if "the server doesn't have a resource type" in result:
        return f"Resource type '{resource}' is not available in this cluster. This may be because the CSI Baremetal driver is not installed or its CRDs are not properly registered."
    
    return result

@tool
def kubectl_describe(resource: str, name: Optional[str] = None, namespace: Optional[str] = None) -> str:
    """Describe Kubernetes resources"""
    cmd = ["kubectl", "describe", resource]
    if name:
        cmd.append(name)
    if namespace:
        cmd.extend(["-n", namespace])
    
    return execute_command(
        cmd,
        f"Describe {resource} {name or 'all'} {f'in namespace {namespace}' if namespace else ''}",
        requires_approval=False
    )

@tool
def kubectl_logs(pod_name: str, namespace: str, container: Optional[str] = None, tail: Optional[int] = None) -> str:
    """Get logs from a pod"""
    cmd = ["kubectl", "logs", pod_name, "-n", namespace]
    if container:
        cmd.extend(["-c", container])
    if tail is not None:
        cmd.append(f"--tail={tail}")
    
    return execute_command(
        cmd,
        f"Get logs from pod {namespace}/{pod_name} {f'container {container}' if container else ''}",
        requires_approval=False
    )

@tool
def kubectl_exec(pod_name: str, namespace: str, command: str) -> str:
    """Execute a command in a pod"""
    cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--"] + shlex.split(command)
    return execute_command(
        cmd,
        f"Execute command '{command}' in pod {namespace}/{pod_name}",
        requires_approval=False
    )

@tool
def kubectl_get_drive() -> str:
    """Get CSI Baremetal drive information"""
    return kubectl_get.invoke({"resource": "drive"})

@tool
def kubectl_get_csibmnode() -> str:
    """Get CSI Baremetal node information"""
    return kubectl_get.invoke({"resource": "csibmnode"})

@tool
def kubectl_get_ac() -> str:
    """Get CSI Baremetal AvailableCapacity information"""
    return kubectl_get.invoke({"resource": "ac"})

@tool
def kubectl_get_lvg() -> str:
    """Get CSI Baremetal LogicalVolumeGroup information"""
    return kubectl_get.invoke({"resource": "lvg"})

@tool
def kubectl_get_pods_csi() -> str:
    """Get CSI Baremetal driver pods"""
    return execute_command(
        ["kubectl", "get", "pods", "-n", "kube-system", "-l", "app=csi-baremetal"],
        "Get CSI Baremetal driver pods",
        requires_approval=False
    )

@tool
def kubectl_logs_csi(pod_name: str) -> str:
    """Get logs from CSI Baremetal driver pod"""
    return kubectl_logs(pod_name, "kube-system", tail=100)

@tool
def kubectl_get_csidrivers() -> str:
    """Get registered CSI drivers"""
    return kubectl_get.invoke({"resource": "csidrivers"})

@tool
def kubectl_logs_control_plane(component: str, tail: int = 100) -> str:
    """Get control plane component logs"""
    return execute_command(
        ["kubectl", "logs", "-n", "kube-system", "-l", f"component={component}", f"--tail={tail}"],
        f"Get {component} logs from control plane",
        requires_approval=False
    )

@tool
def kubectl_exec_df_h(pod_name: str, namespace: str) -> str:
    """Check disk usage in a pod"""
    return kubectl_exec(pod_name, namespace, "df -h")

@tool
def kubectl_exec_ls_ld(pod_name: str, namespace: str, path: str) -> str:
    """Check directory permissions in a pod"""
    return kubectl_exec(pod_name, namespace, f"ls -ld {path}")

@tool
def kubectl_get_pod_securitycontext(pod_name: str, namespace: str) -> str:
    """Get pod SecurityContext information"""
    result = kubectl_get.invoke({"resource": "pod", "name": pod_name, "namespace": namespace})
    # Extract SecurityContext from the YAML output
    if "securityContext:" in result:
        return result
    else:
        return f"No SecurityContext found for pod {namespace}/{pod_name}"

@tool
def ssh_smartctl(node: str, device: str) -> str:
    """Run SMART check on a device via SSH"""
    return ssh_execute(node, f"smartctl -a /dev/{device}", f"Run SMART check on device /dev/{device}")

@tool
def ssh_fio_read(node: str, device: str, params: str = "--rw=read --bs=4k --size=100M --numjobs=1 --iodepth=1 --runtime=60 --time_based --group_reporting") -> str:
    """Run FIO read test on a device via SSH"""
    return ssh_execute(node, f"fio --name=read_test --filename=/dev/{device} {params}", f"Run FIO read test on /dev/{device}")

@tool
def ssh_mount(node: str) -> str:
    """Check mounted filesystems on a node via SSH"""
    return ssh_execute(node, "mount", "Check mounted filesystems")

@tool
def ssh_xfs_repair_n(node: str, device: str) -> str:
    """Run XFS repair in diagnostic mode via SSH"""
    return ssh_execute(node, f"xfs_repair -n /dev/{device}", f"Run XFS repair diagnostic on /dev/{device}")

@tool
def df_h() -> str:
    """Show disk space usage with human-readable sizes"""
    return execute_command(
        ["df", "-h"],
        "Show disk space usage with human-readable sizes",
        requires_approval=False
    )

@tool
def lsblk() -> str:
    """List information about block devices"""
    return execute_command(
        ["lsblk"],
        "List information about block devices",
        requires_approval=False
    )

@tool
def dmesg_grep_error() -> str:
    """Get error-related kernel messages from dmesg"""
    return execute_command(
        ["sh", "-c", "dmesg | grep -i error | tail -50"],
        "Get recent error messages from kernel logs",
        requires_approval=False
    )

@tool
def dmesg_grep_disk() -> str:
    """Get disk-related kernel messages from dmesg"""
    return execute_command(
        ["sh", "-c", "dmesg | grep -i disk | tail -50"],
        "Get recent disk-related messages from kernel logs",
        requires_approval=False
    )

@tool
def journalctl_kubelet(params: str = "--since='1 hour ago' --no-pager") -> str:
    """Get kubelet logs from journalctl"""
    cmd = ["journalctl", "-u", "kubelet"]
    if params:
        cmd.extend(shlex.split(params))
    
    return execute_command(
        cmd,
        f"Get kubelet logs with parameters: {params if params else 'default'}",
        requires_approval=False
    )

@tool
def create_test_pod_yaml(name: str, namespace: str, pvc_name: str, node_name: str, test_type: str = "read_write") -> str:
    """Create a test pod YAML for storage validation"""
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
    command: ["/bin/sh", "-c", "echo 'Test' > /mnt/test.txt && cat /mnt/test.txt && echo 'Write OK' && sleep 3600"]
    volumeMounts:
    - mountPath: "/mnt"
      name: test-volume
  volumes:
  - name: test-volume
    persistentVolumeClaim:
      claimName: {pvc_name}
  nodeName: {node_name}
  restartPolicy: Never
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
    command: ["/bin/sh", "-c", "dd if=/dev/zero of=/mnt/testfile bs=1M count=100 && echo 'Write Test OK' && dd if=/mnt/testfile of=/dev/null bs=1M && echo 'Read Test OK' && sleep 3600"]
    volumeMounts:
    - mountPath: "/mnt"
      name: test-volume
  volumes:
  - name: test-volume
    persistentVolumeClaim:
      claimName: {pvc_name}
  nodeName: {node_name}
  restartPolicy: Never
"""
    else:
        return f"Error: Invalid test type '{test_type}'"
    
    return f"Test Pod YAML generated:\n{pod_yaml}"

@tool
def build_knowledge_graph(pod_name: str, namespace: str, volume_path: str) -> str:
    """Build and populate the Knowledge Graph with diagnostic data"""
    global KNOWLEDGE_GRAPH
    
    try:
        # Initialize or reset the Knowledge Graph
        KNOWLEDGE_GRAPH = KnowledgeGraph()
        
        # Start building the graph by adding the primary pod
        pod_id = KNOWLEDGE_GRAPH.add_pod(pod_name, namespace, volume_path=volume_path)
        
        # Get pod information to build relationships
        try:
            pod_yaml = kubectl_get.invoke({"resource": "pod", "name": pod_name, "namespace": namespace})
        except Exception as e:
            logging.warning(f"Failed to get pod information: {e}")
            pod_yaml = "Error: Failed to retrieve pod information"
        
        if not pod_yaml.startswith("Error:"):
            # Extract PVC information from pod YAML
            pvc_matches = re.findall(r'claimName:\s*(\S+)', pod_yaml)
            for pvc_name in pvc_matches:
                pvc_id = KNOWLEDGE_GRAPH.add_pvc(pvc_name, namespace)
                KNOWLEDGE_GRAPH.add_relationship(pod_id, pvc_id, "uses")
                
                # Get PVC information
                try:
                    pvc_yaml = kubectl_get.invoke({"resource": "pvc", "name": pvc_name, "namespace": namespace})
                except Exception as e:
                    logging.warning(f"Failed to get PVC information for {pvc_name}: {e}")
                    pvc_yaml = "Error: Failed to retrieve PVC information"
                
                if not pvc_yaml.startswith("Error:"):
                    # Extract PV and storage class from PVC
                    pv_match = re.search(r'volumeName:\s*(\S+)', pvc_yaml)
                    sc_match = re.search(r'storageClassName:\s*(\S+)', pvc_yaml)
                    
                    if pv_match:
                        pv_name = pv_match.group(1)
                        pv_id = KNOWLEDGE_GRAPH.add_pv(pv_name)
                        KNOWLEDGE_GRAPH.add_relationship(pvc_id, pv_id, "bound_to")
                        
                        # Get PV information
                        try:
                            pv_yaml = kubectl_get.invoke({"resource": "pv", "name": pv_name})
                        except Exception as e:
                            logging.warning(f"Failed to get PV information for {pv_name}: {e}")
                            pv_yaml = "Error: Failed to retrieve PV information"
                        
                        if not pv_yaml.startswith("Error:"):
                            # Extract disk path and node affinity
                            disk_path_match = re.search(r'path:\s*(\S+)', pv_yaml)
                            node_match = re.search(r'kubernetes.io/hostname:\s*(\S+)', pv_yaml)
                            
                            if disk_path_match:
                                disk_path = disk_path_match.group(1)
                                KNOWLEDGE_GRAPH.graph.nodes[pv_id]['disk_path'] = disk_path
                            
                            if node_match:
                                node_name = node_match.group(1)
                                node_id = KNOWLEDGE_GRAPH.add_node(node_name)
                                KNOWLEDGE_GRAPH.add_relationship(pv_id, node_id, "affinity_to")
                    
                    if sc_match:
                        sc_name = sc_match.group(1)
                        sc_id = KNOWLEDGE_GRAPH.add_storage_class(sc_name)
                        KNOWLEDGE_GRAPH.add_relationship(pvc_id, sc_id, "uses_storage_class")
        
        # Get CSI Baremetal drive information if available
        try:
            drives_yaml = kubectl_get_drive.invoke({})
        except Exception as e:
            logging.warning(f"Failed to get drive information: {e}")
            drives_yaml = "Error: Failed to retrieve drive information"
        
        if not drives_yaml.startswith("Error:") and "items:" in drives_yaml:
            # Parse drive information and add to graph
            drive_matches = re.findall(r'uuid:\s*(\S+)', drives_yaml)
            health_matches = re.findall(r'Health:\s*(\S+)', drives_yaml)
            status_matches = re.findall(r'Status:\s*(\S+)', drives_yaml)
            path_matches = re.findall(r'Path:\s*(\S+)', drives_yaml)
            
            for i, drive_uuid in enumerate(drive_matches):
                drive_id = KNOWLEDGE_GRAPH.add_drive(
                    drive_uuid,
                    Health=health_matches[i] if i < len(health_matches) else "UNKNOWN",
                    Status=status_matches[i] if i < len(status_matches) else "UNKNOWN",
                    Path=path_matches[i] if i < len(path_matches) else "UNKNOWN"
                )
                
                # Add issues for unhealthy drives
                if i < len(health_matches) and health_matches[i] in ['SUSPECT', 'BAD']:
                    KNOWLEDGE_GRAPH.add_issue(
                        drive_id,
                        "disk_health",
                        f"Drive has health status: {health_matches[i]}",
                        "high"
                    )
        
        # Get node information
        try:
            nodes_yaml = kubectl_get.invoke({"resource": "nodes"})
        except Exception as e:
            logging.warning(f"Failed to get nodes information: {e}")
            nodes_yaml = "Error: Failed to retrieve nodes information"
        
        if not nodes_yaml.startswith("Error:"):
            node_names = re.findall(r'name:\s*(\S+)', nodes_yaml)
            for node_name in node_names:
                if not KNOWLEDGE_GRAPH.find_nodes_by_type('Node') or f"Node:{node_name}" not in [n for n in KNOWLEDGE_GRAPH.find_nodes_by_type('Node')]:
                    node_id = KNOWLEDGE_GRAPH.add_node(node_name)
                    
                    # Check node status
                    try:
                        node_desc = kubectl_describe.invoke({"resource": "node", "name": node_name})
                    except Exception as e:
                        logging.warning(f"Failed to describe node {node_name}: {e}")
                        node_desc = "Error: Failed to describe node"
                    
                    if not node_desc.startswith("Error:"):
                        ready_status = "Ready" in node_desc and "Ready=True" in node_desc
                        disk_pressure = "DiskPressure=True" in node_desc
                        
                        KNOWLEDGE_GRAPH.graph.nodes[node_id]['Ready'] = ready_status
                        KNOWLEDGE_GRAPH.graph.nodes[node_id]['DiskPressure'] = disk_pressure
                        
                        if not ready_status or disk_pressure:
                            KNOWLEDGE_GRAPH.add_issue(
                                node_id,
                                "node_health",
                                f"Node issues: Ready={ready_status}, DiskPressure={disk_pressure}",
                                "high"
                            )
        
        # Log Knowledge Graph construction
        summary = KNOWLEDGE_GRAPH.get_summary()
        logging.info(f"Knowledge Graph built: {summary}")
        
        print("=" * 80)
        print("KNOWLEDGE GRAPH - FORMATTED OUTPUT")
        print("=" * 80)
        print()
        
        # Print the formatted graph
        formatted_output = KNOWLEDGE_GRAPH.print_graph()
        print(formatted_output)
        
        print("\n" + "=" * 80)
        print("Knowledge Graph")
        print("=" * 80)

        return f"Knowledge Graph successfully built with {summary['total_nodes']} nodes, {summary['total_edges']} edges, and {summary['total_issues']} issues identified."
        
    except Exception as e:
        error_msg = f"Error building Knowledge Graph: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}"

@tool
def analyze_knowledge_graph() -> str:
    """Analyze the Knowledge Graph to identify root causes and generate fix plan"""
    global KNOWLEDGE_GRAPH
    
    if not KNOWLEDGE_GRAPH:
        return "Error: Knowledge Graph not initialized. Run build_knowledge_graph first."
    
    try:
        # Perform analysis
        analysis = KNOWLEDGE_GRAPH.analyze_issues()
        
        # Generate fix plan
        fix_plan = KNOWLEDGE_GRAPH.generate_fix_plan(analysis)
        
        # Format results
        result = {
            "root_cause": "Analysis completed",
            "fix_plan": "Generated based on Knowledge Graph analysis"
        }
        
        if analysis['potential_root_causes']:
            primary_cause = analysis['potential_root_causes'][0]
            result["root_cause"] = f"Primary: {primary_cause['description']}. Total issues: {analysis['total_issues']}"
        
        if fix_plan:
            steps = [f"Step {step['step']}: {step['description']}" for step in fix_plan]
            result["fix_plan"] = ". ".join(steps)
        
        # Log analysis results
        logging.info(f"Knowledge Graph analysis: {len(analysis['potential_root_causes'])} root causes, {len(fix_plan)} fix steps")
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        error_msg = f"Error analyzing Knowledge Graph: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}"

def define_tools() -> List[Any]:
    """
    Define comprehensive tools for the LangGraph ReAct agent
    
    Returns:
        List[Any]: List of tool callables
    """
    tools = [
        # Kubernetes core tools
        kubectl_get,
        kubectl_describe,
        kubectl_logs,
        kubectl_exec,
        
        # CSI Baremetal specific tools
        kubectl_get_drive,
        kubectl_get_csibmnode,
        kubectl_get_ac,
        kubectl_get_lvg,
        kubectl_get_pods_csi,
        kubectl_logs_csi,
        kubectl_get_csidrivers,
        
        # Kubernetes diagnostic tools
        kubectl_logs_control_plane,
        kubectl_exec_df_h,
        kubectl_exec_ls_ld,
        kubectl_get_pod_securitycontext,
        
        # SSH-based tools
        ssh_smartctl,
        ssh_fio_read,
        ssh_mount,
        ssh_xfs_repair_n,
        
        # System diagnostic tools
        df_h,
        lsblk,
        dmesg_grep_error,
        dmesg_grep_disk,
        journalctl_kubelet,
        
        # Test and utility tools
        create_test_pod_yaml,
        
        # Knowledge Graph tools
        build_knowledge_graph,
        analyze_knowledge_graph
    ]
    return tools

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
    tools = define_tools()
    
    # Define function to call the model
    def call_model(state: MessagesState):
        # Add comprehensive system prompt based on design requirements
        phase_specific_guidance = ""
        if phase == "analysis":
            phase_specific_guidance = """
You are currently in Phase 1 (Analysis). Your task is to:
1. Build a Knowledge Graph using build_knowledge_graph tool with the provided pod, namespace, and volume path
2. Execute comprehensive diagnostic steps using available LangGraph tools
3. Analyze the Knowledge Graph using analyze_knowledge_graph tool
4. Present your findings as a JSON object with "root_cause" and "fix_plan" keys
5. DO NOT attempt to execute any remediation actions yet

Focus on comprehensive diagnostics and Knowledge Graph-based analysis. Use the Knowledge Graph to identify patterns and root causes.
"""
        elif phase == "remediation":
            phase_specific_guidance = """
You are currently in Phase 2 (Remediation). Your task is to:
1. Execute the fix plan from Phase 1 using available tools
2. Respect command validation and interactive mode settings
3. Verify that issues are resolved after implementing fixes
4. Report final resolution status

Implement the fix plan safely and effectively while following security constraints.
"""
        
        system_message = {
            "role": "system", 
            "content": f"""You are an AI assistant powering an enhanced Kubernetes volume troubleshooting system using LangGraph ReAct. Your role is to monitor and resolve volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver (csi-baremetal.dell.com). Exclude remote storage (e.g., NFS, Ceph). The troubleshooting process is split into two phases: Analysis (Phase 1) and Remediation (Phase 2). All diagnostic and remediation commands are implemented as LangGraph tools, validated against `commands.disallowed` in `config.yaml` using prefix/wildcard matching. In Phase 1, a Knowledge Graph is constructed to organize diagnostic data, which you query for root cause analysis and fix plan generation.

{phase_specific_guidance}

Follow these strict guidelines for safe, reliable, and comprehensive troubleshooting:

1. **Safety and Security**:
   - Only execute predefined LangGraph tools. All tools are validated against `commands.disallowed`.
   - Never execute tools whose commands match disallowed patterns unless explicitly enabled and approved.
   - Validate all tool executions for safety and relevance.
   - Log all tool executions, SSH commands, and outputs for auditing.

2. **Interactive and Auto-Fix Modes**:
   - In interactive mode, some tools may prompt for user approval with: "Proposed tool: <tool_name>. Purpose: <purpose>. Approve? (y/n)".
   - If auto-fix mode is disabled, prompt after Phase 1: "Issues found: <list>. Fix plan: <plan>. Proceed to remediation phase? (y/n)".
   - Execute allowed tools while respecting configuration restrictions.

3. **Knowledge Graph Integration**:
   - In Phase 1, ALWAYS start by using build_knowledge_graph tool to construct the Knowledge Graph
   - Use analyze_knowledge_graph tool to perform comprehensive analysis
   - The Knowledge Graph organizes entities (Pod, PVC, PV, Drive, Node, StorageClass, LVG, AC) and relationships
   - Use graph analysis results for root cause identification and fix plan generation

4. **Comprehensive Diagnostic Process**:
   - **Confirm Issue**: Use kubectl_logs and kubectl_describe tools to identify errors (e.g., "Input/Output Error", "Permission Denied", "FailedMount")
   - **Verify Configurations**: Check Pod, PVC, and PV with kubectl_get tools. Verify mount points with kubectl_exec_df_h and kubectl_exec_ls_ld
   - **Check CSI Baremetal Driver and Resources**:
     - Use kubectl_get_drive for drive status (Health: GOOD, Status: ONLINE, Usage: IN_USE)
     - Use kubectl_get_csibmnode for drive-to-node mapping
     - Use kubectl_get_ac for AvailableCapacity
     - Use kubectl_get_lvg for LogicalVolumeGroup health
     - Use kubectl_get_pods_csi and kubectl_logs_csi for driver pod status
   - **Test Hardware**: Use ssh_smartctl for SMART data, ssh_fio_read for performance testing
   - **Check Permissions**: Use kubectl_exec_ls_ld and kubectl_get_pod_securitycontext
   - **Verify Node Health**: Use kubectl_describe for node status, ssh_mount for disk mounting

5. **Error Handling**:
   - Log all actions, outputs, and errors
   - Handle failures gracefully - some commands may fail due to missing resources or permissions
   - If CSI Baremetal resources are not available, continue with alternative diagnostic approaches
   - Provide useful analysis even if some commands fail

6. **Output Requirements**:
   - In Phase 1: Provide comprehensive analysis with JSON format containing "root_cause" and "fix_plan"
   - In Phase 2: Report remediation results and resolution status
   - Include performance benchmarks (HDD: 100-200 IOPS, SSD: thousands, NVMe: tens of thousands)
   - Always provide actionable recommendations

You must adhere to these guidelines to ensure safe, reliable, and effective troubleshooting of local disk issues in Kubernetes with the CSI Baremetal driver using Knowledge Graph analysis.
"""
        }
        
        # Ensure system message is first
        if state["messages"]:
            if isinstance(state["messages"], list):
                if state["messages"][0].type != "system":
                    state["messages"] = [system_message] + state["messages"]
            else:
                state["messages"] = [system_message, state["messages"]]
        else:
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
    Run Phase 1: Analysis with Knowledge Graph integration
    
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
        
        # Initial query for analysis phase with Knowledge Graph integration
        query = f"""Phase 1 - Analysis: Diagnose volume I/O error for pod {pod_name} in namespace {namespace} at volume path {volume_path}.

IMPORTANT STEPS:
1. First, use build_knowledge_graph tool to construct the Knowledge Graph with the provided parameters
2. Execute comprehensive diagnostic steps using available LangGraph tools
3. Use analyze_knowledge_graph tool to perform Knowledge Graph analysis
4. Present findings as JSON with "root_cause" and "fix_plan" keys

Notes:
- Some commands may fail due to missing CSI Baremetal resources - this is expected
- Continue with available diagnostic approaches even if some tools fail
- Focus on comprehensive analysis, NOT remediation actions
- The Knowledge Graph will help identify patterns and relationships between entities
"""
        formatted_query = {"messages": [{"role": "user", "content": query}]}
        
        # Set timeout
        timeout_seconds = CONFIG_DATA['troubleshoot']['timeout_seconds']
        
        # Run graph with timeout
        logging.info(f"Starting analysis phase with Knowledge Graph integration, timeout: {timeout_seconds}s")
        try:
            response = await asyncio.wait_for(
                graph.ainvoke(formatted_query, config={"recursion_limit": 100}),
                timeout=timeout_seconds
            )
        except Exception as e:
            logging.error(f"Error during analysis graph execution: {str(e)}")
            return (
                "Analysis encountered an error, possibly due to missing CSI Baremetal resources",
                "Verify cluster configuration and CSI Baremetal driver installation"
            )
        
        # Extract analysis results
        if response["messages"]:
            if isinstance(response["messages"], list):
                final_message = response["messages"][-1].content
            else:
                final_message = response["messages"].content
        else:
            final_message = "Failed to generate analysis results"
        
        # Parse root cause and fix plan
        root_cause = "Unknown"
        fix_plan = "No specific fix plan generated"

        try:
            # Look for JSON block in the response
            json_start = final_message.find('{')
            json_end = final_message.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = final_message[json_start:json_end]
                parsed_json = json.loads(json_str)
                root_cause = parsed_json.get("root_cause", "Unknown root cause")
                fix_plan = parsed_json.get("fix_plan", "No fix plan provided")
                logging.info("Successfully parsed root cause and fix plan from LLM JSON output")
            else:
                raise json.JSONDecodeError("No JSON object found", final_message, 0)

        except json.JSONDecodeError:
            logging.warning("Failed to parse JSON, attempting fallback parsing")
            # Fallback to string parsing
            if "Root cause:" in final_message:
                parts = final_message.split("Root cause:", 1)
                if len(parts) > 1:
                    root_cause_section = parts[1].strip()
                    if "Fix plan:" in root_cause_section:
                        root_cause = root_cause_section.split("Fix plan:", 1)[0].strip()
                        fix_plan = root_cause_section.split("Fix plan:", 1)[1].strip()
                    else:
                        root_cause = root_cause_section
            else:
                root_cause = "Analysis completed but specific root cause not clearly identified"
                fix_plan = "Review diagnostic results and Knowledge Graph analysis for detailed insights"
        
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
    Run Phase 2: Remediation to resolve identified issues
    
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
        
        # Initial query for remediation phase
        query = f"""Phase 2 - Remediation: Resolve volume I/O error for pod {pod_name} in namespace {namespace} at volume path {volume_path}.

Root cause identified: {root_cause}
Fix plan to implement: {fix_plan}

IMPORTANT:
1. Implement the fix plan using available LangGraph tools
2. Respect command validation and interactive mode settings
3. Some commands may fail due to permissions or missing resources - handle gracefully
4. Verify resolution after implementing fixes
5. Provide clear summary of what was accomplished

Execute remediation steps while following security constraints and configuration settings."""
        formatted_query = {"messages": [{"role": "user", "content": query}]}
        
        # Set timeout
        timeout_seconds = CONFIG_DATA['troubleshoot']['timeout_seconds']
        
        # Run graph with timeout
        logging.info(f"Starting remediation phase, timeout: {timeout_seconds}s")
        try:
            response = await asyncio.wait_for(
                graph.ainvoke(formatted_query),
                timeout=timeout_seconds
            )
        except Exception as e:
            logging.error(f"Error during remediation graph execution: {str(e)}")
            return f"Remediation phase encountered an error: {str(e)}. Manual intervention may be required."
        
        # Extract remediation results
        if response["messages"]:
            if isinstance(response["messages"], list):
                final_message = response["messages"][-1].content
            else:
                final_message = response["messages"].content
        else:
            final_message = "Failed to generate remediation results"
        
        logging.info(f"Remediation completed for pod {namespace}/{pod_name}, volume {volume_path}")
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
    Enhanced two-phase troubleshooting process with Knowledge Graph integration
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
    """
    global CONFIG_DATA, INTERACTIVE_MODE
    
    try:
        # Phase 1: Analysis with Knowledge Graph
        logging.info("Starting Phase 1: Analysis with Knowledge Graph integration")
        try:
            root_cause, fix_plan = await run_analysis_phase(pod_name, namespace, volume_path)
            
            # Check if analysis was successful
            if root_cause.startswith("Error:"):
                logging.warning(f"Analysis phase reported an error: {root_cause}")
                return f"""Troubleshooting Summary:
Analysis phase encountered an issue: {root_cause}

Recommendations:
1. Verify that the CSI Baremetal driver is properly installed
2. Check if CRDs are registered with 'kubectl get crd | grep csi-baremetal'
3. Ensure the pod {namespace}/{pod_name} exists and has storage issues
4. Review the troubleshoot.log file for detailed error messages"""
                
        except Exception as e:
            logging.error(f"Exception during analysis phase: {str(e)}")
            return f"""Troubleshooting Summary:
Analysis phase encountered an unexpected error: {str(e)}

Recommendations:
1. Check if the Kubernetes API server is accessible
2. Verify kubectl configuration is correct
3. Ensure the pod {namespace}/{pod_name} exists
4. Review the troubleshoot.log file for detailed error messages"""
        
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
            try:
                result = await run_remediation_phase(pod_name, namespace, volume_path, root_cause, fix_plan)
                
                return f"""Troubleshooting Summary:
Analysis completed (with Knowledge Graph):
- Root cause: {root_cause}
- Fix plan: {fix_plan}

Remediation results:
{result}"""
                
            except Exception as e:
                logging.error(f"Exception during remediation phase: {str(e)}")
                return f"""Troubleshooting Summary:
Analysis completed (with Knowledge Graph):
- Root cause: {root_cause}
- Fix plan: {fix_plan}

Remediation phase encountered an unexpected error: {str(e)}

Recommendations:
1. Review the troubleshoot.log file for detailed error messages
2. Consider manually implementing the fix plan based on analysis results"""
        else:
            logging.info("Remediation phase skipped per user request")
            return f"""Troubleshooting Summary:
Analysis completed (with Knowledge Graph):
- Root cause: {root_cause}
- Fix plan: {fix_plan}

Remediation phase was skipped per user request."""
            
    except Exception as e:
        error_msg = f"Unexpected error during troubleshooting: {str(e)}"
        logging.error(error_msg)
        return f"""Troubleshooting Summary:
An unexpected error occurred: {str(e)}

Recommendations:
1. Review the troubleshoot.log file for detailed error messages
2. Check if the Kubernetes API server is accessible
3. Verify kubectl configuration is correct
4. Ensure required resources and permissions are available"""
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
    
    logging.info(f"Starting enhanced troubleshooting with Knowledge Graph for pod {namespace}/{pod_name}, volume {volume_path}")
    logging.info(f"Interactive mode: {INTERACTIVE_MODE}")
    logging.info(f"Auto-fix mode: {CONFIG_DATA['troubleshoot']['auto_fix']}")
    
    # Run troubleshooting
    try:
        result = asyncio.run(troubleshoot(pod_name, namespace, volume_path))
        print("\n=== Enhanced Troubleshooting Results ===")
        print(result)
        print("=======================================\n")
    except KeyboardInterrupt:
        logging.info("Troubleshooting stopped by user")
        print("\nTroubleshooting stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        print(f"\nFatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
