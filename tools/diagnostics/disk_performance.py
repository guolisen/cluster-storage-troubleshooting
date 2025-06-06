#!/usr/bin/env python3
"""
Disk performance testing tools for volume troubleshooting.

This module contains tools for testing disk performance, including
read-only tests and I/O performance measurements.
"""

import time
import json
import re
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from langchain_core.tools import tool

@tool
def run_disk_readonly_test(node_name: str, device_path: str, 
                          duration_minutes: int = 10, 
                          block_size: str = "4M",
                          compare_with_healthy: bool = True) -> str:
    """
    Perform a read-only test on the disk to verify readability
    
    This tool reads disk data continuously for a configurable duration
    to verify readability and detect any read errors or timeouts.
    If compare_with_healthy is True, it will also find and test another
    disk of the same model for performance comparison.
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        duration_minutes: Test duration in minutes
        block_size: Block size for reading (e.g., 4M, 8M)
        compare_with_healthy: Whether to compare with a healthy disk of same model
        
    Returns:
        str: Summary report with metrics and any errors encountered
    """
    try:
        from tools.diagnostics.hardware import ssh_execute
        
        # Calculate test parameters
        duration_seconds = duration_minutes * 60
        
        # First, get the model of the target disk
        disk_model = get_disk_model(node_name, device_path, ssh_execute)
        
        # Test the target disk
        print(f"Starting read-only test on {node_name}:{device_path} for {duration_minutes} minutes...")
        target_metrics = run_single_disk_test(node_name, device_path, duration_seconds, block_size, ssh_execute)
        
        # Initialize comparison metrics
        comparison_disk = None
        comparison_metrics = None
        
        # If comparison is requested and we found the disk model
        if compare_with_healthy and disk_model:
            # Find another disk of the same model
            comparison_disk = find_comparison_disk(node_name, device_path, disk_model, ssh_execute)
            
            if comparison_disk:
                print(f"Found comparison disk of same model: {comparison_disk}")
                print(f"Running comparison test on {comparison_disk}...")
                
                # Run the same test on the comparison disk
                comparison_metrics = run_single_disk_test(node_name, comparison_disk, duration_seconds, block_size, ssh_execute)
        
        # Generate report
        report = generate_report(node_name, device_path, target_metrics, comparison_disk, comparison_metrics)
        
        return report
        
    except Exception as e:
        return f"Error during disk read-only test: {str(e)}"

def get_disk_model(node_name: str, device_path: str, ssh_execute) -> str:
    """
    Get the model of a disk
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        ssh_execute: Function to execute SSH commands
        
    Returns:
        str: Disk model or empty string if not found
    """
    # Try to get disk model using lsblk
    cmd = f"lsblk -o NAME,MODEL,SERIAL {device_path} -n"
    result = ssh_execute(node_name, cmd)
    
    # Parse the output to extract the model
    model = ""
    for line in result.split('\n'):
        if line.strip():
            parts = line.strip().split()
            if len(parts) > 1:
                # The model is typically the second field
                model = parts[1]
                break
    
    # If lsblk didn't work, try smartctl
    if not model:
        cmd = f"smartctl -i {device_path} | grep 'Device Model'"
        result = ssh_execute(node_name, cmd)
        
        # Parse the output
        match = re.search(r'Device Model:\s+(.+)', result)
        if match:
            model = match.group(1).strip()
    
    return model

def find_comparison_disk(node_name: str, target_disk: str, disk_model: str, ssh_execute) -> str:
    """
    Find another disk of the same model
    
    Args:
        node_name: Node hostname or IP
        target_disk: The disk being tested (to exclude)
        disk_model: Model to match
        ssh_execute: Function to execute SSH commands
        
    Returns:
        str: Path to comparison disk or None if not found
    """
    # List all disks
    cmd = "lsblk -d -o NAME,MODEL,SIZE -n"
    result = ssh_execute(node_name, cmd)
    
    # Parse the output to find disks with the same model
    for line in result.split('\n'):
        if line.strip():
            parts = line.strip().split()
            if len(parts) >= 2:
                disk_name = parts[0]
                model = parts[1]
                
                # Check if this disk matches the model and is not the target disk
                if model == disk_model and f"/dev/{disk_name}" != target_disk:
                    return f"/dev/{disk_name}"
    
    return None

def run_single_disk_test(node_name: str, device_path: str, duration_seconds: int, block_size: str, ssh_execute) -> Dict[str, Any]:
    """
    Run a read-only test on a single disk
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        duration_seconds: Test duration in seconds
        block_size: Block size for reading
        ssh_execute: Function to execute SSH commands
        
    Returns:
        Dict[str, Any]: Test metrics
    """
    # Start time
    start_time = datetime.now()
    
    # Command to read from disk continuously without writing
    cmd = (
        f"timeout {duration_seconds}s dd if={device_path} of=/dev/null bs={block_size} "
        f"iflag=direct status=progress 2>&1"
    )
    
    # Execute command
    result = ssh_execute(node_name, cmd)
    
    # End time
    end_time = datetime.now()
    test_duration = (end_time - start_time).total_seconds()
    
    # Parse results to extract metrics
    read_bytes = 0
    read_speed = "0 MB/s"
    read_speed_value = 0
    
    # Look for lines like "1073741824 bytes (1.1 GB, 1.0 GiB) copied, 1.12345 s, 954 MB/s"
    for line in result.split('\n'):
        if "bytes" in line and "copied" in line:
            parts = line.split(',')
            if len(parts) >= 3:
                # Extract bytes read
                bytes_part = parts[0].strip()
                read_bytes = int(bytes_part.split()[0])
                
                # Extract speed
                speed_part = parts[2].strip()
                read_speed = speed_part
                
                # Try to extract the numeric value from the speed
                speed_match = re.search(r'(\d+\.?\d*)', speed_part)
                if speed_match:
                    read_speed_value = float(speed_match.group(1))
    
    # Check for read errors in the output
    read_errors = []
    error_keywords = ["error", "failed", "timeout", "i/o error", "cannot read"]
    for line in result.lower().split('\n'):
        if any(keyword in line for keyword in error_keywords):
            read_errors.append(line.strip())
    
    # Return metrics
    return {
        "device_path": device_path,
        "test_duration": test_duration,
        "read_bytes": read_bytes,
        "read_speed": read_speed,
        "read_speed_value": read_speed_value,
        "read_errors": read_errors
    }

def generate_report(node_name: str, device_path: str, target_metrics: Dict[str, Any], 
                   comparison_disk: str, comparison_metrics: Dict[str, Any]) -> str:
    """
    Generate a report comparing the test results
    
    Args:
        node_name: Node hostname or IP
        device_path: Target device path
        target_metrics: Metrics for the target disk
        comparison_disk: Path to comparison disk
        comparison_metrics: Metrics for the comparison disk
        
    Returns:
        str: Formatted report
    """
    # Generate summary report
    report = [
        f"Disk Read-Only Test Report for {node_name}:{device_path}",
        f"=" * 70,
        f"Test Duration: {target_metrics['test_duration']:.2f} seconds",
        f"Total Data Read: {target_metrics['read_bytes']} bytes ({target_metrics['read_bytes'] / (1024**3):.2f} GB)",
        f"Average Read Speed: {target_metrics['read_speed']}",
        f"Read Errors Detected: {len(target_metrics['read_errors'])}"
    ]
    
    # Add error details if any
    if target_metrics['read_errors']:
        report.append("\nError Details:")
        for i, error in enumerate(target_metrics['read_errors'], 1):
            report.append(f"{i}. {error}")
    else:
        report.append("\nNo read errors detected during the test.")
    
    # Add comparison results if available
    if comparison_disk and comparison_metrics:
        report.append("\nComparison with Healthy Disk:")
        report.append("-" * 50)
        report.append(f"Comparison Disk: {comparison_disk}")
        report.append(f"Comparison Disk Read Speed: {comparison_metrics['read_speed']}")
        
        # Calculate speed difference
        if target_metrics['read_speed_value'] > 0 and comparison_metrics['read_speed_value'] > 0:
            speed_ratio = target_metrics['read_speed_value'] / comparison_metrics['read_speed_value']
            percentage_diff = abs(1 - speed_ratio) * 100
            
            if speed_ratio < 0.8:  # Target disk is significantly slower
                report.append(f"\nWARNING: Target disk is {percentage_diff:.1f}% slower than the comparison disk of the same model.")
                report.append(f"Target: {target_metrics['read_speed']} vs Comparison: {comparison_metrics['read_speed']}")
                report.append("This significant performance difference may indicate hardware degradation.")
            elif speed_ratio > 1.2:  # Target disk is significantly faster
                report.append(f"\nNote: Target disk is {percentage_diff:.1f}% faster than the comparison disk of the same model.")
                report.append(f"Target: {target_metrics['read_speed']} vs Comparison: {comparison_metrics['read_speed']}")
            else:
                report.append(f"\nPerformance is within normal range compared to the same model disk.")
                report.append(f"Difference: {percentage_diff:.1f}%")
    
    # Add test result summary
    if len(target_metrics['read_errors']) == 0:
        if comparison_metrics and target_metrics['read_speed_value'] < 0.7 * comparison_metrics['read_speed_value']:
            report.append("\nTest Result: WARNING - Disk is readable but performance is significantly lower than expected")
        else:
            report.append("\nTest Result: PASSED - Disk is readable without errors")
    else:
        report.append("\nTest Result: FAILED - Disk has read errors")
    
    return "\n".join(report)

@tool
def test_disk_io_performance(node_name: str, device_path: str, 
                            test_types: List[str] = ["read", "write", "randread", "randwrite"],
                            duration_seconds: int = 30,
                            block_sizes: List[str] = ["4k", "128k", "1m"]) -> str:
    """
    Measure disk I/O performance under different workloads
    
    This tool tests disk I/O performance, including read/write speeds and IOPS,
    under different workloads (sequential and random access).
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        test_types: List of test types to run (read, write, randread, randwrite)
        duration_seconds: Duration for each test in seconds
        block_sizes: List of block sizes to test with
        
    Returns:
        str: Performance test results showing IOPS and throughput
    """
    try:
        from tools.diagnostics.hardware import ssh_execute
        
        results = []
        results.append(f"Disk I/O Performance Test for {node_name}:{device_path}")
        results.append("=" * 70)
        
        # Ensure test_types contains valid values
        valid_test_types = ["read", "randread"]
        test_types = [t for t in test_types if t in valid_test_types]
        
        # If no valid test types, use defaults
        if not test_types:
            test_types = ["read", "randread"]
        
        # Run tests for each combination of test type and block size
        for test_type in test_types:
            results.append(f"\n{test_type.upper()} Tests:")
            results.append("-" * 50)
            
            for block_size in block_sizes:
                results.append(f"\nBlock Size: {block_size}")
                
                # Build fio command
                cmd = (
                    f"sudo fio --name=test --filename={device_path} --direct=1 "
                    f"--rw={test_type} --bs={block_size} --ioengine=libaio "
                    f"--iodepth=16 --runtime={duration_seconds} --numjobs=4 "
                    f"--time_based --group_reporting --size=1G "
                    f"--output-format=json"
                )
                
                # Execute command
                print(f"Running {test_type} test with {block_size} block size...")
                output = ssh_execute.invoke({"node_name": node_name, "command": cmd})
                
                # Parse JSON output if available
                try:
                    # Extract JSON part from output (may have other text before/after)
                    json_start = output.find('{')
                    json_end = output.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_data = json.loads(output[json_start:json_end])
                        
                        # Extract key metrics
                        job_data = json_data.get("jobs", [{}])[0]
                        
                        # Read metrics
                        read_iops = job_data.get("read", {}).get("iops", 0)
                        read_bw = job_data.get("read", {}).get("bw", 0)  # KiB/s
                        read_bw_mb = read_bw / 1024  # Convert to MiB/s
                        
                        # Write metrics
                        write_iops = job_data.get("write", {}).get("iops", 0)
                        write_bw = job_data.get("write", {}).get("bw", 0)  # KiB/s
                        write_bw_mb = write_bw / 1024  # Convert to MiB/s
                        
                        # Latency metrics (in nanoseconds)
                        lat_ns = job_data.get(test_type, {}).get("lat_ns", {})
                        avg_lat_us = lat_ns.get("mean", 0) / 1000  # Convert to microseconds
                        max_lat_us = lat_ns.get("max", 0) / 1000  # Convert to microseconds
                        
                        # Add metrics to results
                        if test_type.startswith("read"):
                            results.append(f"  Read IOPS: {read_iops:.2f}")
                            results.append(f"  Read Bandwidth: {read_bw_mb:.2f} MiB/s")
                            results.append(f"  Avg Latency: {avg_lat_us:.2f} μs")
                            results.append(f"  Max Latency: {max_lat_us:.2f} μs")
                        else:
                            results.append(f"  Write IOPS: {write_iops:.2f}")
                            results.append(f"  Write Bandwidth: {write_bw_mb:.2f} MiB/s")
                            results.append(f"  Avg Latency: {avg_lat_us:.2f} μs")
                            results.append(f"  Max Latency: {max_lat_us:.2f} μs")
                    else:
                        # If JSON parsing fails, include raw output
                        results.append("  Failed to parse JSON output")
                        results.append(f"  Raw output: {output[:200]}...")
                except Exception as e:
                    results.append(f"  Error parsing results: {str(e)}")
                    results.append(f"  Raw output: {output[:200]}...")
        
        # Add summary
        results.append("\nPerformance Test Summary:")
        results.append("=" * 50)
        results.append("Tests completed successfully. Review the metrics above to evaluate disk performance.")
        results.append("Higher IOPS and bandwidth values indicate better performance.")
        results.append("Lower latency values indicate better responsiveness.")
        
        return "\n".join(results)
        
    except Exception as e:
        return f"Error during disk I/O performance test: {str(e)}"
