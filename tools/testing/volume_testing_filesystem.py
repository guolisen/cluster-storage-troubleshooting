#!/usr/bin/env python3
"""
Filesystem-related volume testing tools.

This module provides tools for checking filesystem health
and performing filesystem-related diagnostics on pod volumes.
"""

import re
from datetime import datetime
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from tools.core.config import validate_command, execute_command

@tool
def check_pod_volume_filesystem(pod_name: str, namespace: str = "default",
                               mount_path: str = "/test-volume",
                               device_path: str = None) -> str:
    """
    Perform a non-destructive filesystem check on pod volume with XFS filesystem
    
    Args:
        pod_name: Name of the pod with mounted volume
        namespace: Kubernetes namespace
        mount_path: Path where volume is mounted
        device_path: Optional device path for the volume. If not provided, it will be detected
        
    Returns:
        str: Filesystem check results
    """
    results = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Add timestamp to log
        results.append(f"[{timestamp}] Filesystem Check on Pod Volume - Pod: {pod_name}")
        
        # If device path is not provided, try to detect it
        if not device_path:
            try:
                # Get device path from mount
                find_device_cmd = f"mount | grep '{mount_path}' | awk '{{print $1}}'"
                cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", find_device_cmd]
                device_result = execute_command(cmd)
                
                if not device_result or "Error" in device_result:
                    return f"Error: Unable to detect device path for mount {mount_path}. Please provide device_path explicitly."
                
                device_path = device_result.strip()
                results.append(f"Detected volume device path: {device_path}")
            except Exception as e:
                return f"Error detecting device path: {str(e)}"
        
        # Verify it's an XFS filesystem
        fs_type_cmd = f"df -T {mount_path} | tail -n 1 | awk '{{print $2}}'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", fs_type_cmd]
        fs_type_result = execute_command(cmd).strip()
        
        results.append(f"Filesystem type: {fs_type_result}")
        
        if fs_type_result.lower() != "xfs":
            results.append(f"Warning: Filesystem is not XFS ({fs_type_result}). XFS check may not be appropriate.")
        
        # Check if xfs_repair is available
        check_tool_cmd = "which xfs_repair || echo 'xfs_repair not found'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", check_tool_cmd]
        tool_check_result = execute_command(cmd)
        
        if "not found" in tool_check_result:
            results.append(f"Error: xfs_repair tool not found in the pod. Please install xfs utilities.")
            return "\n" + "="*50 + "\n".join(results)
        
        # Run non-destructive filesystem check
        check_cmd = f"xfs_repair -n {device_path} 2>&1 || echo 'xfs_repair failed with error code $?'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", check_cmd]
        check_result = execute_command(cmd)
        
        # Process and analyze results
        if "xfs_repair failed" in check_result:
            results.append(f"XFS Filesystem Check Failed:\n{check_result}")
        elif "No modify flag set" in check_result and "would have been fixed" in check_result:
            results.append(f"XFS Filesystem Check found issues that need repair:\n{check_result}")
        elif "Phase" in check_result and not "bad" in check_result.lower() and not "error" in check_result.lower():
            results.append(f"XFS Filesystem Check Results:\nPhase checks completed. No issues found. Filesystem is clean.")
        else:
            results.append(f"XFS Filesystem Check Results:\n{check_result}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error checking pod volume filesystem: {str(e)}"
