#!/usr/bin/env python3
"""
System diagnostic tools for volume troubleshooting.

This module contains tools for system-level diagnostics including
disk space, mount points, kernel messages, and system logs.
"""

import subprocess
from typing import Dict, Any # Added typing imports
from langchain_core.tools import tool
from tools.core.config import execute_command # Added execute_command import

@tool
def df_command(path: str = None, options: str = "-h", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute df command to show disk space usage
    
    Args:
        path: Path to check (optional)
        options: Command options (optional)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output
    """
    cmd = ["df"]
    
    if options:
        cmd.extend(options.split()) # Note: options.split() might not be robust for complex shell quoting
    
    if path:
        cmd.append(path)
    
    purpose = f"Show disk space usage for path '{path if path else 'all filesystems'}' with options '{options}'"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def lsblk_command(options: str = "", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute lsblk command to list block devices
    
    Args:
        options: Command options (optional)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output
    """
    cmd = ["lsblk"]
    
    if options:
        cmd.extend(options.split())
    
    purpose = f"List block devices with options '{options}'"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def mount_command(options: str = "", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute mount command to show mounted filesystems
    
    Args:
        options: Command options (optional)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output
    """
    cmd = ["mount"]
    
    if options:
        cmd.extend(options.split())

    purpose = f"Show mounted filesystems with options '{options}'"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def dmesg_command(options: str = "", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute dmesg command to show kernel messages
    
    Args:
        options: Command options (optional)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output
    """
    cmd = ["dmesg"]
    
    if options:
        cmd.extend(options.split())

    purpose = f"Show kernel messages with options '{options}'"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)

@tool
def journalctl_command(options: str = "", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute journalctl command to show systemd journal logs. Output the logs from the last 5 minutes as much as possible.
    
    Args:
        options: Command options (optional)
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Command output
    """
    cmd = ["journalctl"]
    
    if options: # If options are provided, use them.
        cmd.extend(options.split())
    else: # Default to common useful options if none are given.
        cmd.extend(["--no-pager", "--since", "5 minutes ago"])

    purpose = f"Show systemd journal logs with options '{options if options else '--no-pager --since \"5 minutes ago\"'}'"
    return execute_command(command_list=cmd, config_data=config_data, interactive_mode=interactive_mode, purpose=purpose, requires_approval=False)
