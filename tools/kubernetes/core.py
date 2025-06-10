#!/usr/bin/env python3
"""
Core Kubernetes tools for volume troubleshooting.

This module contains basic kubectl operations and general Kubernetes
resource management tools.
"""

import subprocess
from langchain_core.tools import tool

@tool
def kubectl_get(resource_type: str, resource_name: str = None, namespace: str = None, output_format: str = "yaml") -> str:
    """
    Execute kubectl get command
    
    Args:
        resource_type: Type of resource (pod, pvc, pv, node, etc.)
        resource_name: Name of resource (optional) (e.g. test-pod-1)
        namespace: Namespace (optional) (e.g. default)
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
    else:
        cmd.append("-o=wide")

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
        resource_name: Name of resource (e.g. test-pod-1)
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
        resource_name: Name of resource (e.g. test-pod-1)
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
        pod_name: Pod name (e.g. test-pod-1)
        command: Command to execute
        namespace: Namespace (optional) (e.g. default)
        
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
        pod_name: Pod name (e.g. test-pod-1)
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
