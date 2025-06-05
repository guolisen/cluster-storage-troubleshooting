#!/usr/bin/env python3
"""
CSI Baremetal specific tools for Kubernetes volume troubleshooting.

This module contains tools for interacting with CSI Baremetal custom resources
and storage-specific operations.
"""

import subprocess
from typing import Dict, Any # Added typing imports
from langchain_core.tools import tool
from tools.core.config import execute_command # Added execute_command import

@tool
def kubectl_get_drive(drive_uuid: str = None, output_format: str = "wide", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Get CSI Baremetal drive information
    
    Args:
        drive_uuid: Drive UUID (optional, gets all drives if not specified)
        output_format: Output format (wide, yaml, json)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output showing drive status, health, path, etc.
    """
    cmd = ["kubectl", "get", "drive"]
    
    if drive_uuid:
        cmd.append(drive_uuid)
    
    cmd.extend(["-o", output_format])
    
    purpose = f"Get CSI Baremetal drive(s) information, UUID: {drive_uuid if drive_uuid else 'all'}"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def kubectl_get_csibmnode(node_name: str = None, output_format: str = "wide", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Get CSI Baremetal node information
    
    Args:
        node_name: Node name (optional, gets all nodes if not specified)
        output_format: Output format (wide, yaml, json)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output showing node mapping and drive associations
    """
    cmd = ["kubectl", "get", "csibmnode"]
    
    if node_name:
        cmd.append(node_name)
    
    cmd.extend(["-o", output_format])

    purpose = f"Get CSI Baremetal node(s) information, Node: {node_name if node_name else 'all'}"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def kubectl_get_availablecapacity(ac_name: str = None, output_format: str = "wide", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Get CSI Baremetal available capacity information
    
    Args:
        ac_name: Available capacity name (optional, gets all if not specified)
        output_format: Output format (wide, yaml, json)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output showing available capacity and storage class mapping
    """
    cmd = ["kubectl", "get", "ac"] # ac is short for availablecapacity
    
    if ac_name:
        cmd.append(ac_name)
    
    cmd.extend(["-o", output_format])

    purpose = f"Get CSI Baremetal available capacity information, Name: {ac_name if ac_name else 'all'}"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def kubectl_get_logicalvolumegroup(lvg_name: str = None, output_format: str = "wide", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Get CSI Baremetal logical volume group information
    
    Args:
        lvg_name: Logical volume group name (optional, gets all if not specified)
        output_format: Output format (wide, yaml, json)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output showing LVG health and associated drives
    """
    cmd = ["kubectl", "get", "lvg"]
    
    if lvg_name:
        cmd.append(lvg_name)
    
    cmd.extend(["-o", output_format])

    purpose = f"Get CSI Baremetal logical volume group information, Name: {lvg_name if lvg_name else 'all'}"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def kubectl_get_storageclass(sc_name: str = None, output_format: str = "yaml", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Get storage class information
    
    Args:
        sc_name: Storage class name (optional, gets all if not specified)
        output_format: Output format (yaml, json, wide)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output showing storage class configuration
    """
    cmd = ["kubectl", "get", "storageclass"]
    
    if sc_name:
        cmd.append(sc_name)
    
    cmd.extend(["-o", output_format])

    purpose = f"Get Kubernetes storage class information, Name: {sc_name if sc_name else 'all'}"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def kubectl_get_csidrivers(output_format: str = "wide", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Get CSI driver registration information
    
    Args:
        output_format: Output format (wide, yaml, json)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output showing registered CSI drivers
    """
    cmd = ["kubectl", "get", "csidrivers", "-o", output_format]
    
    purpose = "Get registered CSI drivers information"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)
