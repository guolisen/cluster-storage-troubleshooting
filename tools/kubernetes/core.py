#!/usr/bin/env python3
"""
Core Kubernetes tools for volume troubleshooting.

This module contains basic kubectl operations and general Kubernetes
resource management tools.
"""

import subprocess
from typing import List, Dict, Any # Added Dict, Any
from langchain_core.tools import tool
from tools.core.config import execute_command # Added import

@tool
def kubectl_get(resource_type: str, resource_name: str = None, namespace: str = None, output_format: str = "yaml", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute kubectl get command
    
    Args:
        resource_type: Type of resource (pod, pvc, pv, node, etc.)
        resource_name: Name of resource (optional)
        namespace: Namespace (optional)
        output_format: Output format (yaml, json, wide, etc.)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
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
    else:
        cmd.append("-o=wide")

    purpose = f"Get Kubernetes {resource_type}"
    if resource_name:
        purpose += f" {resource_name}"
    if namespace:
        purpose += f" in namespace {namespace}"

    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def kubectl_describe(resource_type: str, resource_name: str, namespace: str = None, config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute kubectl describe command
    
    Args:
        resource_type: Type of resource (pod, pvc, pv, node, etc.)
        resource_name: Name of resource
        namespace: Namespace (optional)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "describe", resource_type, resource_name]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    purpose = f"Describe Kubernetes {resource_type} {resource_name}"
    if namespace:
        purpose += f" in namespace {namespace}"

    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def kubectl_apply(yaml_content: str, namespace: str = None, config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute kubectl apply with provided YAML content
    
    Args:
        yaml_content: YAML content to apply
        namespace: Namespace (optional)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output
    """
    # TODO: This function uses subprocess.run directly because execute_command
    # from tools.core.config does not currently support passing 'input'
    # to the subprocess. This means it bypasses command validation and
    # standardized execution. Consider enhancing execute_command or finding
    # an alternative for applying YAML content via the centralized function.
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
def kubectl_delete(resource_type: str, resource_name: str, namespace: str = None, config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute kubectl delete command
    
    Args:
        resource_type: Type of resource (pod, pvc, pv, node, etc.)
        resource_name: Name of resource
        namespace: Namespace (optional)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "delete", resource_type, resource_name]
    
    if namespace:
        cmd.extend(["-n", namespace])

    purpose = f"Delete Kubernetes {resource_type} {resource_name}"
    if namespace:
        purpose += f" in namespace {namespace}"

    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def kubectl_exec(pod_name: str, command_args: List[str], namespace: str = None, config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute command in a pod
    
    Args:
        pod_name: Pod name
        command_args: Command to execute, as a list of arguments.
                      Example: ["ls", "-l", "/app"]
        namespace: Namespace (optional)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "exec", pod_name]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    if command_args: # Ensure command_args is not empty
        cmd.extend(["--"] + command_args)
    else:
        # Handle empty command_args, perhaps return an error or specific message
        return "Error: No command provided to kubectl_exec."
    
    purpose = f"Execute command in pod {pod_name}"
    if namespace:
        purpose += f" in namespace {namespace}"

    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def kubectl_logs(pod_name: str, namespace: str = None, container: str = None, tail: int = 100, config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Get logs from a pod
    
    Args:
        pod_name: Pod name
        namespace: Namespace (optional)
        container: Container name (optional)
        tail: Number of lines to show from the end (optional)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
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
    
    purpose = f"Get logs for pod {pod_name}"
    if container:
        purpose += f" container {container}"
    if namespace:
        purpose += f" in namespace {namespace}"

    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)
