#!/usr/bin/env python3
"""
Basic volume testing tools for validating volume functionality.

This module provides tools for running I/O tests, validating mounts,
and testing volume permissions during troubleshooting.
"""

import json
import time
import re
from typing import Dict, Any
from langchain_core.tools import tool
from tools.core.config import validate_command, execute_command

@tool
def run_volume_io_test(pod_name: str, namespace: str = "default", 
                      mount_path: str = "/test-volume", 
                      test_size: str = "10M") -> str:
    """
    Run I/O tests on a volume mounted in a pod
    
    Args:
        pod_name: Name of the pod with mounted volume
        namespace: Kubernetes namespace
        mount_path: Path where volume is mounted, must have a valid path
        test_size: Size of test file (e.g., 10M, 100M)
        
    Returns:
        str: Results of I/O tests
    """
    results = []
    
    try:
        # Test 1: Write test
        write_cmd = f"dd if=/dev/zero of={mount_path}/AI_test_write.dat bs=1M count=10 2>&1"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", write_cmd]
        write_result = execute_command(cmd)
        results.append(f"Write Test:\n{write_result}")
        
        # Test 2: Read test
        read_cmd = f"dd if={mount_path}/AI_test_write.dat of=/dev/null bs=1M 2>&1"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", read_cmd]
        read_result = execute_command(cmd)
        results.append(f"Read Test:\n{read_result}")
        
        # Test 3: Random I/O test using dd
        random_cmd = f"dd if=/dev/urandom of={mount_path}/AI_test_random.dat bs=4k count=100 2>&1"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", random_cmd]
        random_result = execute_command(cmd)
        results.append(f"Random Write Test:\n{random_result}")
        
        # Test 4: File operations test
        file_ops_cmd = f"""
        echo 'Testing file operations...' > {mount_path}/AI_test_file.txt &&
        cat {mount_path}/AI_test_file.txt &&
        ls -la {mount_path}/ &&
        df -h {mount_path}
        """
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", file_ops_cmd]
        file_ops_result = execute_command(cmd)
        results.append(f"File Operations Test:\n{file_ops_result}")
        
        # Test 5: Cleanup test files
        cleanup_cmd = f"rm -f {mount_path}/AI_test_*.dat {mount_path}/AI_test_file.txt"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", cleanup_cmd]
        cleanup_result = execute_command(cmd)
        results.append(f"Cleanup:\n{cleanup_result}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error running volume I/O tests: {str(e)}"

@tool
def validate_volume_mount(pod_name: str, namespace: str = "default", 
                         mount_path: str = "/test-volume") -> str:
    """
    Validate that a volume is properly mounted in a pod
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        mount_path: Expected mount path, must be specified
        
    Returns:
        str: Volume mount validation results
    """
    results = []
    
    try:
        # Check if mount path exists
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "ls", "-la", mount_path]
        ls_result = execute_command(cmd)
        results.append(f"Mount Path Check ({mount_path}):\n{ls_result}")
        
        # Check mount information
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "mount"]
        mount_result = execute_command(cmd)
        results.append(f"Mount Information:\n{mount_result}")
        
        # Check disk space
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "df", "-h", mount_path]
        df_result = execute_command(cmd)
        results.append(f"Disk Space:\n{df_result}")
        
        # Check filesystem type
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "stat", "-f", mount_path]
        stat_result = execute_command(cmd)
        results.append(f"Filesystem Info:\n{stat_result}")
        
        # Check if volume is writable
        test_write_cmd = f"touch {mount_path}/write_test && rm {mount_path}/write_test && echo 'Volume is writable'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", test_write_cmd]
        write_test_result = execute_command(cmd)
        results.append(f"Write Test:\n{write_test_result}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error validating volume mount: {str(e)}"

@tool
def test_volume_permissions(pod_name: str, namespace: str = "default", 
                           mount_path: str = "/test-volume", 
                           test_user: str = None) -> str:
    """
    Test volume permissions and access rights
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        mount_path: Volume mount path, must be specified
        test_user: User to test permissions for (optional)
        
    Returns:
        str: Permission test results
    """
    results = []
    
    try:
        # Check current permissions
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "ls", "-la", mount_path]
        perm_result = execute_command(cmd)
        results.append(f"Current Permissions:\n{perm_result}")
        
        # Check who can access the mount
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "whoami"]
        user_result = execute_command(cmd)
        results.append(f"Current User:\n{user_result}")
        
        # Test read permissions
        read_test_cmd = f"ls {mount_path} && echo 'Read access: OK'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", read_test_cmd]
        read_test_result = execute_command(cmd)
        results.append(f"Read Permission Test:\n{read_test_result}")
        
        # Test write permissions
        write_test_cmd = f"touch {mount_path}/perm_test_file && echo 'Write access: OK'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", write_test_cmd]
        write_test_result = execute_command(cmd)
        results.append(f"Write Permission Test:\n{write_test_result}")
        
        # Test execute permissions (if applicable)
        exec_test_cmd = f"cd {mount_path} && echo 'Execute access: OK'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", exec_test_cmd]
        exec_test_result = execute_command(cmd)
        results.append(f"Execute Permission Test:\n{exec_test_result}")
        
        # Check file ownership
        try:
            if execute_command(["kubectl", "exec", pod_name, "-n", namespace, "--", "ls", f"{mount_path}/perm_test_file"]):
                owner_cmd = f"ls -la {mount_path}/perm_test_file"
                cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", owner_cmd]
                owner_result = execute_command(cmd)
                results.append(f"File Ownership:\n{owner_result}")
                
                # Cleanup test file
                cleanup_cmd = f"rm -f {mount_path}/perm_test_file"
                cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", cleanup_cmd]
                execute_command(cmd)
        except Exception as e:
            results.append(f"Error checking file ownership: {str(e)}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error testing volume permissions: {str(e)}"

@tool
def verify_volume_mount(pod_name: str, namespace: str = "default",
                       mount_path: str = "/test-volume") -> str:
    """
    Verify that a pod volume is correctly mounted and accessible
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        mount_path: Expected mount path, must be specified
        
    Returns:
        str: Volume mount verification results
    """
    results = []
    
    try:
        # Check if mount path exists
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "ls", "-la", mount_path]
        ls_result = execute_command(cmd)
        results.append(f"Mount Path Existence Check ({mount_path}):\n{ls_result}")
        
        # Get mount details with grep
        mount_grep_cmd = f"mount | grep '{mount_path}'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", mount_grep_cmd]
        mount_grep_result = execute_command(cmd)
        
        if mount_grep_result:
            results.append(f"Mount Entry Found:\n{mount_grep_result}")
        else:
            results.append(f"Warning: No mount entry found for {mount_path}")
        
        # Check mount options
        if mount_grep_result:
            # Extract mount options
            options_match = re.search(r'\((.*?)\)', mount_grep_result)
            if options_match:
                options = options_match.group(1)
                results.append(f"Mount Options: {options}")
                
                # Check for read-only mount
                if "ro" in options.split(","):
                    results.append("Warning: Volume is mounted read-only")
        
        # Check filesystem type
        fs_type_cmd = f"df -T {mount_path} | tail -n 1 | awk '{{print $2}}'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", fs_type_cmd]
        fs_type_result = execute_command(cmd)
        results.append(f"Filesystem Type: {fs_type_result}")
        
        # Check available space
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "df", "-h", mount_path]
        df_result = execute_command(cmd)
        results.append(f"Space Information:\n{df_result}")
        
        # Check if volume is writable
        write_test_cmd = f"touch {mount_path}/mount_verify_test && echo 'Write test successful' && rm {mount_path}/mount_verify_test"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", write_test_cmd]
        write_test_result = execute_command(cmd)
        
        if "Write test successful" in write_test_result:
            results.append("Write Test: Passed - Volume is writable")
        else:
            results.append(f"Write Test: Failed - Volume may not be writable\n{write_test_result}")
        
        # Check inode usage
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "df", "-i", mount_path]
        inode_result = execute_command(cmd)
        results.append(f"Inode Usage:\n{inode_result}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error verifying volume mount: {str(e)}"
