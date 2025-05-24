#!/usr/bin/env python3
"""
LangGraph Tools for Kubernetes Volume I/O Error Troubleshooting

This module contains tools and utility functions for executing LangGraph workflows
in the Kubernetes volume troubleshooting system.
"""

import json
import logging
import asyncio
import subprocess
from typing import Dict, List, Any, Optional, Tuple

from langgraph.graph import StateGraph
from langchain_core.tools import tool

# Import from graph.py
from graph import create_troubleshooting_graph_with_context

# Global variables
INTERACTIVE_MODE = False  # To be set by the caller

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
    global INTERACTIVE_MODE
    
    if not command_list:
        logging.error("execute_command received an empty command_list")
        return "Error: Empty command list provided"

    executable = command_list[0]
    command_display_str = ' '.join(command_list)
    
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

def define_remediation_tools() -> List[Any]:
    """
    Define tools needed for remediation and analysis phases
    
    Returns:
        List[Any]: List of tool callables for investigation and remediation
    """
    # Return LangGraph tools for Kubernetes operations and CSI Baremetal investigation
    return [
        kubectl_get,
        kubectl_describe,
        kubectl_apply,
        kubectl_delete,
        kubectl_exec,
        kubectl_logs,
        kubectl_get_drive,
        kubectl_get_csibmnode,
        kubectl_get_availablecapacity,
        kubectl_get_logicalvolumegroup,
        kubectl_get_storageclass,
        kubectl_get_csidrivers,
        smartctl_check,
        fio_performance_test,
        fsck_check,
        ssh_execute,
        df_command,
        lsblk_command,
        mount_command,
        dmesg_command
    ]


# LangGraph tools for Kubernetes operations

@tool
def kubectl_get(resource_type: str, resource_name: str = None, namespace: str = None, output_format: str = "yaml") -> str:
    """
    Execute kubectl get command
    
    Args:
        resource_type: Type of resource (pod, pvc, pv, node, etc.)
        resource_name: Name of resource (optional)
        namespace: Namespace (optional)
        output_format: Output format (yaml, json, wide, etc.)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "get", resource_type]
    
    if resource_name:
        cmd.append(resource_name)
    
    if namespace:
        cmd.extend(["-n", namespace])
        
    if output_format:
        cmd.extend(["-o", output_format])
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get: {str(e)}"

@tool
def kubectl_describe(resource_type: str, resource_name: str, namespace: str = None) -> str:
    """
    Execute kubectl describe command
    
    Args:
        resource_type: Type of resource (pod, pvc, pv, node, etc.)
        resource_name: Name of resource
        namespace: Namespace (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "describe", resource_type, resource_name]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl describe: {str(e)}"

@tool
def kubectl_apply(yaml_content: str, namespace: str = None) -> str:
    """
    Execute kubectl apply with provided YAML content
    
    Args:
        yaml_content: YAML content to apply
        namespace: Namespace (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "apply", "-f", "-"]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    # Execute command
    try:
        result = subprocess.run(cmd, input=yaml_content, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl apply: {str(e)}"

@tool
def kubectl_delete(resource_type: str, resource_name: str, namespace: str = None) -> str:
    """
    Execute kubectl delete command
    
    Args:
        resource_type: Type of resource (pod, pvc, pv, node, etc.)
        resource_name: Name of resource
        namespace: Namespace (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "delete", resource_type, resource_name]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl delete: {str(e)}"

@tool
def kubectl_exec(pod_name: str, command: str, namespace: str = None) -> str:
    """
    Execute command in a pod
    
    Args:
        pod_name: Pod name
        command: Command to execute
        namespace: Namespace (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "exec", pod_name]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    cmd.extend(["--", *command.split()])
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl exec: {str(e)}"

@tool
def kubectl_logs(pod_name: str, namespace: str = None, container: str = None, tail: int = 100) -> str:
    """
    Get logs from a pod
    
    Args:
        pod_name: Pod name
        namespace: Namespace (optional)
        container: Container name (optional)
        tail: Number of lines to show from the end (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "logs", pod_name]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    if container:
        cmd.extend(["-c", container])
    
    if tail:
        cmd.extend(["--tail", str(tail)])
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl logs: {str(e)}"

# CSI Baremetal-specific tools

@tool
def kubectl_get_drive(drive_uuid: str = None, output_format: str = "wide") -> str:
    """
    Get CSI Baremetal drive information
    
    Args:
        drive_uuid: Drive UUID (optional, gets all drives if not specified)
        output_format: Output format (wide, yaml, json)
        
    Returns:
        str: Command output showing drive status, health, path, etc.
    """
    cmd = ["kubectl", "get", "drive"]
    
    if drive_uuid:
        cmd.append(drive_uuid)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get drive: {str(e)}"

@tool
def kubectl_get_csibmnode(node_name: str = None, output_format: str = "wide") -> str:
    """
    Get CSI Baremetal node information
    
    Args:
        node_name: Node name (optional, gets all nodes if not specified)
        output_format: Output format (wide, yaml, json)
        
    Returns:
        str: Command output showing node mapping and drive associations
    """
    cmd = ["kubectl", "get", "csibmnode"]
    
    if node_name:
        cmd.append(node_name)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get csibmnode: {str(e)}"

@tool
def kubectl_get_availablecapacity(ac_name: str = None, output_format: str = "wide") -> str:
    """
    Get CSI Baremetal available capacity information
    
    Args:
        ac_name: Available capacity name (optional, gets all if not specified)
        output_format: Output format (wide, yaml, json)
        
    Returns:
        str: Command output showing available capacity and storage class mapping
    """
    cmd = ["kubectl", "get", "ac"]
    
    if ac_name:
        cmd.append(ac_name)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get ac: {str(e)}"

@tool
def kubectl_get_logicalvolumegroup(lvg_name: str = None, output_format: str = "wide") -> str:
    """
    Get CSI Baremetal logical volume group information
    
    Args:
        lvg_name: Logical volume group name (optional, gets all if not specified)
        output_format: Output format (wide, yaml, json)
        
    Returns:
        str: Command output showing LVG health and associated drives
    """
    cmd = ["kubectl", "get", "lvg"]
    
    if lvg_name:
        cmd.append(lvg_name)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get lvg: {str(e)}"

@tool
def kubectl_get_storageclass(sc_name: str = None, output_format: str = "yaml") -> str:
    """
    Get storage class information
    
    Args:
        sc_name: Storage class name (optional, gets all if not specified)
        output_format: Output format (yaml, json, wide)
        
    Returns:
        str: Command output showing storage class configuration
    """
    cmd = ["kubectl", "get", "storageclass"]
    
    if sc_name:
        cmd.append(sc_name)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get storageclass: {str(e)}"

@tool
def kubectl_get_csidrivers(output_format: str = "wide") -> str:
    """
    Get CSI driver registration information
    
    Args:
        output_format: Output format (wide, yaml, json)
        
    Returns:
        str: Command output showing registered CSI drivers
    """
    cmd = ["kubectl", "get", "csidrivers", "-o", output_format]
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get csidrivers: {str(e)}"

# Hardware diagnostic tools

@tool
def smartctl_check(node_name: str, device_path: str) -> str:
    """
    Check disk health using smartctl via SSH
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        
    Returns:
        str: SMART data showing disk health, reallocated sectors, etc.
    """
    cmd = f"sudo smartctl -a {device_path}"
    return ssh_execute(node_name, cmd)

@tool
def fio_performance_test(node_name: str, device_path: str, test_type: str = "read") -> str:
    """
    Test disk performance using fio via SSH
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        test_type: Test type (read, write, randread, randwrite)
        
    Returns:
        str: Performance test results showing IOPS and throughput
    """
    cmd = f"sudo fio --name={test_type}_test --filename={device_path} --rw={test_type} --bs=4k --size=100M --numjobs=1 --iodepth=1 --runtime=60 --time_based --group_reporting"
    return ssh_execute(node_name, cmd)

@tool
def fsck_check(node_name: str, device_path: str, check_only: bool = True) -> str:
    """
    Check file system integrity using fsck via SSH
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda1)
        check_only: If True, only check without fixing (safer)
        
    Returns:
        str: File system check results
    """
    if check_only:
        cmd = f"sudo fsck -n {device_path}"  # -n flag means no changes, check only
    else:
        cmd = f"sudo fsck -y {device_path}"  # -y flag means auto-fix (requires approval)
    
    return ssh_execute(node_name, cmd)

@tool
def ssh_execute(node_name: str, command: str) -> str:
    """
    Execute command on remote node via SSH
    
    Args:
        node_name: Node hostname or IP
        command: Command to execute
        
    Returns:
        str: Command output
    """
    # Note: In a real implementation, this would use paramiko or similar
    # For now, this is a placeholder that shows the command that would be executed
    return f"SSH command to {node_name}: {command}\n[Note: Actual SSH execution requires proper credential configuration]"

# System diagnostic tools

@tool
def df_command(path: str = None, options: str = "-h") -> str:
    """
    Execute df command to show disk space usage
    
    Args:
        path: Path to check (optional)
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["df"]
    
    if options:
        cmd.extend(options.split())
    
    if path:
        cmd.append(path)
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing df: {str(e)}"

@tool
def lsblk_command(options: str = "") -> str:
    """
    Execute lsblk command to list block devices
    
    Args:
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["lsblk"]
    
    if options:
        cmd.extend(options.split())
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing lsblk: {str(e)}"

@tool
def mount_command(options: str = "") -> str:
    """
    Execute mount command to show mounted filesystems
    
    Args:
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["mount"]
    
    if options:
        cmd.extend(options.split())
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing mount: {str(e)}"

@tool
def dmesg_command(options: str = "") -> str:
    """
    Execute dmesg command to show kernel messages
    
    Args:
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["dmesg"]
    
    if options:
        cmd.extend(options.split())
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing dmesg: {str(e)}"
