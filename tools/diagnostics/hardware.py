#!/usr/bin/env python3
"""
Hardware diagnostic tools for volume troubleshooting.

This module contains tools for hardware-level diagnostics including
disk health checks, performance testing, and file system validation.
"""

from langchain_core.tools import tool

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
    return ssh_execute.invoke({"node_name": node_name, "command": cmd})

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
    return ssh_execute.invoke({"node_name": node_name, "command": cmd})

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
    
    return ssh_execute.invoke({"node_name": node_name, "command": cmd})

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
    try:
        import paramiko
        import os
        
        # Get SSH configuration from global config (would be passed in real implementation)
        ssh_user = "root"  # Default, should come from config
        ssh_key_path = os.path.expanduser("~/.ssh/id_ed25519")  # Default, should come from config
        
        # Create SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Connect using SSH key
            ssh_client.connect(
                hostname=node_name,
                username=ssh_user,
                password='abc123',
                #key_filename=ssh_key_path,
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
