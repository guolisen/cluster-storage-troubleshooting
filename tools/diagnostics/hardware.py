#!/usr/bin/env python3
"""
Hardware diagnostic tools for volume troubleshooting.

This module contains tools for hardware-level diagnostics including
disk health checks, performance testing, and file system validation.
"""

import os
import logging # For informational messages
from typing import Dict, Any # Added typing imports
from langchain_core.tools import tool

# Attempt to import paramiko at the module level
try:
    import paramiko
except ImportError:
    # This allows functions to be defined but they will fail at runtime if paramiko is needed.
    paramiko = None

@tool
def smartctl_check(node_name: str, device_path: str, config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Check disk health using smartctl via SSH
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        config_data: Configuration data, potentially containing ssh_config.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: SMART data showing disk health, reallocated sectors, etc.
    """
    cmd = f"sudo smartctl -a {device_path}"
    return ssh_execute.invoke({"node_name": node_name, "command": cmd, "config_data": config_data, "interactive_mode": interactive_mode})

@tool
def fio_performance_test(node_name: str, device_path: str, test_type: str = "read", config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Test disk performance using fio via SSH
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        test_type: Test type (read, write, randread, randwrite)
        config_data: Configuration data, potentially containing ssh_config.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: Performance test results showing IOPS and throughput
    """
    cmd = f"sudo fio --name={test_type}_test --filename={device_path} --rw={test_type} --bs=4k --size=100M --numjobs=1 --iodepth=1 --runtime=60 --time_based --group_reporting"
    return ssh_execute.invoke({"node_name": node_name, "command": cmd, "config_data": config_data, "interactive_mode": interactive_mode})

@tool
def fsck_check(node_name: str, device_path: str, check_only: bool = True, config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Check file system integrity using fsck via SSH
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda1)
        check_only: If True, only check without fixing (safer)
        config_data: Configuration data, potentially containing ssh_config.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: File system check results
    """
    if check_only:
        cmd = f"sudo fsck -n {device_path}"  # -n flag means no changes, check only
    else:
        cmd = f"sudo fsck -y {device_path}"  # -y flag means auto-fix (requires approval)
    
    return ssh_execute.invoke({"node_name": node_name, "command": cmd, "config_data": config_data, "interactive_mode": interactive_mode})

@tool
def xfs_repair_check(node_name: str, device_path: str, config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Check XFS file system integrity using xfs_repair via SSH
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda1)
        config_data: Configuration data, potentially containing ssh_config.
        interactive_mode: Flag for interactive mode.
        
    Returns:
        str: XFS file system check results
    """
    cmd = f"sudo xfs_repair -n {device_path}"  # -n flag means no changes, check only
    return ssh_execute.invoke({"node_name": node_name, "command": cmd, "config_data": config_data, "interactive_mode": interactive_mode})

@tool
def ssh_execute(node_name: str, command: str, config_data: Dict[str, Any] = None, interactive_mode: bool = False) -> str:
    """
    Execute command on remote node via SSH
    
    Args:
        node_name: Node hostname or IP
        command: Command to execute
        config_data: Configuration data, used for ssh_user and ssh_key_path from ssh_config.
        interactive_mode: If true, logs SSH attempt information.
        
    Returns:
        str: Command output
    """
    if paramiko is None:
        return "Error: paramiko library is not installed. Please install it with 'pip install paramiko'."

    ssh_config = (config_data or {}).get('ssh_config', {})
    ssh_user = ssh_config.get('ssh_user', 'root') # Default to 'root' if not in config
    # Default to '~/.ssh/id_rsa' if not in config, more common default than id_ed25519 for wider compatibility
    ssh_key_path = os.path.expanduser(ssh_config.get('ssh_key_path', '~/.ssh/id_rsa'))

    if interactive_mode:
        logging.info(f"Attempting SSH connection to {node_name} as user {ssh_user} with key {ssh_key_path} to execute: {command}")
        # As per subtask, not adding a blocking prompt here, just logging.

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Connect using SSH key
        ssh_client.connect(
            hostname=node_name,
            username=ssh_user,
            key_filename=ssh_key_path, # Use key_filename, remove password
            timeout=30
        )
        
        # Execute command
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=60)
            
            # Get output
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            # Return combined output
            if error:
                return f"Output:\n{output}\nError:\n{error}"
            return output
            
        except Exception as e:
            return f"SSH execution failed: {str(e)}"
        finally:
            ssh_client.close()
            
    except ImportError:
        return f"Error: paramiko not available. Install with: pip install paramiko"
    except Exception as e:
        return f"SSH setup error: {str(e)}"
