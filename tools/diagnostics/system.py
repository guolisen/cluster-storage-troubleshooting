#!/usr/bin/env python3
"""
System diagnostic tools for volume troubleshooting.

This module contains tools for system-level diagnostics including
disk space, mount points, kernel messages, and system logs.
"""

import subprocess
from langchain_core.tools import tool
from tools.diagnostics.hardware import ssh_execute

@tool
def df_command(node_name: str, path: str = None, options: str = "-h") -> str:
    """
    Execute df command to show disk space usage
    
    Args:
        node_name: Node hostname or IP
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
    
    # Build command string
    cmd_str = " ".join(cmd)
    
    # Execute command via SSH
    try:
        return ssh_execute.invoke({"node_name": node_name, "command": cmd_str})
    except Exception as e:
        return f"Error executing df: {str(e)}"

@tool
def lsblk_command(node_name: str, options: str = "") -> str:
    """
    Execute lsblk command to list block devices
    
    Args:
        node_name: Node hostname or IP
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["lsblk"]
    
    if options:
        cmd.extend(options.split())
    
    # Build command string
    cmd_str = " ".join(cmd)
    
    # Execute command via SSH
    try:
        return ssh_execute.invoke({"node_name": node_name, "command": cmd_str})
    except Exception as e:
        return f"Error executing lsblk: {str(e)}"

@tool
def mount_command(node_name: str, options: str = "") -> str:
    """
    Execute mount command to show mounted filesystems
    
    Args:
        node_name: Node hostname or IP
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["mount"]
    
    if options:
        cmd.extend(options.split())
    
    # Build command string
    cmd_str = " ".join(cmd)
    
    # Execute command via SSH
    try:
        return ssh_execute.invoke({"node_name": node_name, "command": cmd_str})
    except Exception as e:
        return f"Error executing mount: {str(e)}"

@tool
def dmesg_command(node_name: str, options: str = "--since='5 minutes ago' -T") -> str:
    """
    Execute dmesg command to show kernel messages
    
    Args:
        node_name: Node hostname or IP
        options: Command options (default: show logs from last 5 minutes with timestamps)
        
    Returns:
        str: Command output
    """
    cmd = ["dmesg", "--since=5 minutes ago", "-T"]
    
    if options:
        cmd.extend(options.split())
    
    # Build command string
    cmd_str = " ".join(cmd)
    
    # Execute command via SSH
    try:
        return ssh_execute.invoke({"node_name": node_name, "command": cmd_str})
    except Exception as e:
        return f"Error executing dmesg: {str(e)}"

@tool
def journalctl_command(node_name: str, options: str = "--since='5 minutes ago'") -> str:
    """
    Execute journalctl command to show systemd journal logs from the last 5 minutes
    
    Args:
        node_name: Node hostname or IP
        options: Command options (default: show logs from last 5 minutes)
        
    Returns:
        str: Command output
    """
    cmd = ["journalctl", "--since=5 minutes ago"]
    
    if options:
        cmd.extend(options.split())
    
    # Build command string
    cmd_str = " ".join(cmd)
    
    # Execute command via SSH
    try:
        return ssh_execute.invoke({"node_name": node_name, "command": cmd_str})
    except Exception as e:
        return f"Error executing journalctl: {str(e)}"
