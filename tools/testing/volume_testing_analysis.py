#!/usr/bin/env python3
"""
Analysis-related volume testing tools.

This module provides tools for analyzing volume space usage
and checking data integrity on pod volumes.
"""

import re
from datetime import datetime
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from tools.core.config import validate_command, execute_command

@tool
def analyze_volume_space_usage(pod_name: str, namespace: str = "default",
                              mount_path: str = "Need to specify mount path",
                              detect_large_files: bool = True) -> str:
    """
    Analyze volume space usage within a pod, identifying large files and usage patterns
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        mount_path: Volume mount path must be specified
        detect_large_files: Whether to identify large files (may be slower for large volumes)
        
    Returns:
        str: Volume space usage analysis results
    """
    results = []
    
    try:
        # Check overall space usage
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "df", "-h", mount_path]
        df_result = execute_command(cmd)
        results.append(f"Volume Space Overview:\n{df_result}")
        
        # Check inode usage
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "df", "-i", mount_path]
        inode_result = execute_command(cmd)
        results.append(f"Inode Usage:\n{inode_result}")
        
        # Get directory usage summary
        du_cmd = f"du -h --max-depth=1 {mount_path} | sort -hr"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", du_cmd]
        du_result = execute_command(cmd)
        results.append(f"Directory Usage Summary:\n{du_result}")
        
        # Find largest directories (top 5)
        du_dirs_cmd = f"find {mount_path} -type d -exec du -h --max-depth=0 {{}} \\; 2>/dev/null | sort -hr | head -5"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", du_dirs_cmd]
        du_dirs_result = execute_command(cmd)
        results.append(f"Largest Directories (Top 5):\n{du_dirs_result}")
        
        # Find largest files if requested
        if detect_large_files:
            large_files_cmd = f"find {mount_path} -type f -exec ls -lh {{}} \\; 2>/dev/null | sort -k 5 -hr | head -10"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", large_files_cmd]
            large_files_result = execute_command(cmd)
            results.append(f"Largest Files (Top 10):\n{large_files_result}")
        
        # Check for files that might grow quickly (logs)
        try:
            log_files_cmd = f"find {mount_path} -name '*.log' -o -name '*.log.*' -o -path '*/logs/*' | xargs ls -lh 2>/dev/null | sort -k 5 -hr | head -5"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", log_files_cmd]
            log_files_result = execute_command(cmd)
            
            if log_files_result and not "No such file" in log_files_result:
                results.append(f"Potential Log Files (may grow over time):\n{log_files_result}")
        except Exception as e:
            results.append(f"Error checking log files: {str(e)}")
        
        # Check for temporary files
        try:
            temp_files_cmd = f"find {mount_path} -name '*.tmp' -o -name 'temp*' -o -name 'tmp*' | xargs ls -lh 2>/dev/null | sort -k 5 -hr | head -5"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", temp_files_cmd]
            temp_files_result = execute_command(cmd)
            
            if temp_files_result and not "No such file" in temp_files_result:
                results.append(f"Temporary Files:\n{temp_files_result}")
        except Exception as e:
            results.append(f"Error checking temporary files: {str(e)}")
        
        # File type distribution
        file_types_cmd = f"find {mount_path} -type f | grep -v '^$' | grep -o '\\.[^\\./]*$' | sort | uniq -c | sort -nr | head -10"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", file_types_cmd]
        file_types_result = execute_command(cmd)
        results.append(f"File Type Distribution (Top 10):\n{file_types_result}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error analyzing volume space usage: {str(e)}"

@tool
def check_volume_data_integrity(pod_name: str, namespace: str = "default",
                               mount_path: str = "/test-volume",
                               file_pattern: str = None,
                               create_baseline: bool = False) -> str:
    """
    Perform a checksum-based integrity check on critical files in the pod volume
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        mount_path: Volume mount path, must be specified
        file_pattern: Optional file pattern to check (e.g., "*.db" or "data/*.json")
        create_baseline: Whether to create a new baseline rather than verifying
        
    Returns:
        str: Data integrity check results
    """
    results = []
    
    try:
        # Determine files to check
        file_list_cmd = None
        if file_pattern:
            file_list_cmd = f"find {mount_path} -path '{mount_path}/{file_pattern}' -type f | sort"
        else:
            # Limit to reasonable number of files if no pattern provided
            file_list_cmd = f"find {mount_path} -type f -size -10M | grep -v '.checksum' | head -50 | sort"
        
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", file_list_cmd]
        file_list_result = execute_command(cmd)
        
        if not file_list_result or "No such file" in file_list_result:
            return f"No files found matching pattern in {mount_path}"
        
        files = file_list_result.strip().split('\n')
        if not files or files[0] == '':
            return f"No files found matching pattern in {mount_path}"
        
        results.append(f"Found {len(files)} files to check for integrity")
        
        # Check if checksum tools are available
        check_cmd = "which sha256sum || which md5sum || echo 'No checksum tools found'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", check_cmd]
        check_result = execute_command(cmd)
        
        if "No checksum tools found" in check_result:
            return "Error: No checksum tools (sha256sum or md5sum) found in the pod"
        
        # Determine which tool to use
        checksum_tool = "sha256sum"  # prefer sha256sum
        if "sha256sum" not in check_result:
            checksum_tool = "md5sum"
        
        results.append(f"Using {checksum_tool} for integrity verification")
        
        # Define checksum file location
        checksum_file = f"{mount_path}/.volume_checksums_{checksum_tool.replace('sum', '')}"
        
        if create_baseline:
            # Create new baseline checksums
            checksum_cmd = f"{checksum_tool} {' '.join(files)} > {checksum_file}"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", checksum_cmd]
            checksum_result = execute_command(cmd)
            
            # Verify the checksum file was created
            verify_cmd = f"ls -la {checksum_file}"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", verify_cmd]
            verify_result = execute_command(cmd)
            
            if "No such file" in verify_result:
                results.append(f"Error: Failed to create checksum baseline file {checksum_file}")
            else:
                results.append(f"Successfully created checksum baseline with {len(files)} files")
                results.append(f"Baseline stored at: {checksum_file}")
                
                # Show sample of created checksums
                sample_cmd = f"head -5 {checksum_file}"
                cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", sample_cmd]
                sample_result = execute_command(cmd)
                results.append(f"Sample checksums:\n{sample_result}")
        else:
            # Verify against existing checksums
            check_exists_cmd = f"test -f {checksum_file} && echo 'exists' || echo 'not found'"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", check_exists_cmd]
            exists_result = execute_command(cmd).strip()
            
            if exists_result != "exists":
                results.append(f"No baseline checksum file found at {checksum_file}")
                results.append("Run this tool with create_baseline=True to create a baseline first")
                return "\n" + "="*50 + "\n".join(results)
            
            # Verify files against baseline
            verify_cmd = f"cd / && {checksum_tool} -c {checksum_file} 2>&1"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", verify_cmd]
            verify_result = execute_command(cmd)
            
            # Analyze results
            failed_count = verify_result.count("FAILED")
            ok_count = verify_result.count("OK")
            
            results.append(f"Integrity Check Results: {ok_count} files OK, {failed_count} files FAILED")
            
            if failed_count > 0:
                # Extract and show failed files
                failed_files_cmd = f"cd / && {checksum_tool} -c {checksum_file} 2>&1 | grep FAILED"
                cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", failed_files_cmd]
                failed_files_result = execute_command(cmd)
                results.append(f"Failed Files:\n{failed_files_result}")
            elif "No such file" in verify_result:
                results.append(f"Warning: Some files in the baseline no longer exist")
                
            # Check for new files not in the baseline
            new_files_cmd = f"find {mount_path} -type f -newer {checksum_file} | grep -v '{checksum_file}' | head -10"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", new_files_cmd]
            new_files_result = execute_command(cmd)
            
            if new_files_result and new_files_result.strip():
                results.append(f"Warning: New files found that are not in the baseline (created after baseline):\n{new_files_result}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error checking volume data integrity: {str(e)}"
