#!/usr/bin/env python3
"""
Volume testing tools for validating volume functionality.

This module provides tools for running I/O tests, validating mounts,
and testing volume permissions during troubleshooting.
"""

import json
import time
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
        mount_path: Path where volume is mounted
        test_size: Size of test file (e.g., 10M, 100M)
        
    Returns:
        str: Results of I/O tests
    """
    results = []
    
    try:
        # Test 1: Write test
        write_cmd = f"dd if=/dev/zero of={mount_path}/test_write.dat bs=1M count=10 2>&1"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", write_cmd]
        write_result = execute_command(cmd)
        results.append(f"Write Test:\n{write_result}")
        
        # Test 2: Read test
        read_cmd = f"dd if={mount_path}/test_write.dat of=/dev/null bs=1M 2>&1"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", read_cmd]
        read_result = execute_command(cmd)
        results.append(f"Read Test:\n{read_result}")
        
        # Test 3: Random I/O test using dd
        random_cmd = f"dd if=/dev/urandom of={mount_path}/test_random.dat bs=4k count=100 2>&1"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", random_cmd]
        random_result = execute_command(cmd)
        results.append(f"Random Write Test:\n{random_result}")
        
        # Test 4: File operations test
        file_ops_cmd = f"""
        echo 'Testing file operations...' > {mount_path}/test_file.txt &&
        cat {mount_path}/test_file.txt &&
        ls -la {mount_path}/ &&
        df -h {mount_path}
        """
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", file_ops_cmd]
        file_ops_result = execute_command(cmd)
        results.append(f"File Operations Test:\n{file_ops_result}")
        
        # Test 5: Cleanup test files
        cleanup_cmd = f"rm -f {mount_path}/test_*.dat {mount_path}/test_file.txt"
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
        mount_path: Expected mount path
        
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
        mount_path: Volume mount path
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
        if execute_command(["kubectl", "exec", pod_name, "-n", namespace, "--", "ls", f"{mount_path}/perm_test_file"]):
            owner_cmd = f"ls -la {mount_path}/perm_test_file"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", owner_cmd]
            owner_result = execute_command(cmd)
            results.append(f"File Ownership:\n{owner_result}")
            
            # Cleanup test file
            cleanup_cmd = f"rm -f {mount_path}/perm_test_file"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", cleanup_cmd]
            execute_command(cmd)
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error testing volume permissions: {str(e)}"

@tool
def run_volume_stress_test(pod_name: str, namespace: str = "default", 
                          mount_path: str = "/test-volume", 
                          duration: int = 60) -> str:
    """
    Run a stress test on the volume to check for I/O errors under load
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        mount_path: Volume mount path
        duration: Test duration in seconds
        
    Returns:
        str: Stress test results
    """
    results = []
    
    try:
        # Check available space first
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "df", "-h", mount_path]
        space_result = execute_command(cmd)
        results.append(f"Available Space:\n{space_result}")
        
        # Run concurrent I/O operations
        stress_cmd = f"""
        echo 'Starting stress test for {duration} seconds...' &&
        for i in $(seq 1 5); do
            (dd if=/dev/zero of={mount_path}/stress_$i.dat bs=1M count=50 2>/dev/null; 
             dd if={mount_path}/stress_$i.dat of=/dev/null bs=1M 2>/dev/null;
             rm {mount_path}/stress_$i.dat) &
        done &&
        sleep {duration} &&
        wait &&
        echo 'Stress test completed'
        """
        
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", stress_cmd]
        stress_result = execute_command(cmd)
        results.append(f"Stress Test Results:\n{stress_result}")
        
        # Check for any errors in pod logs during the test
        cmd = ["kubectl", "logs", pod_name, "-n", namespace, "--tail=50"]
        log_result = execute_command(cmd)
        results.append(f"Pod Logs (last 50 lines):\n{log_result}")
        
        # Final space check
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "df", "-h", mount_path]
        final_space_result = execute_command(cmd)
        results.append(f"Final Space Check:\n{final_space_result}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error running volume stress test: {str(e)}"
