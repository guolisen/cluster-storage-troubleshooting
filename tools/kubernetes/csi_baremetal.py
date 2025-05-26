#!/usr/bin/env python3
"""
CSI Baremetal specific tools for Kubernetes volume troubleshooting.

This module contains tools for interacting with CSI Baremetal custom resources
and storage-specific operations.
"""

import subprocess
from langchain_core.tools import tool

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
