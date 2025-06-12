#!/usr/bin/env python3
"""
Disk analysis tools for volume troubleshooting.

This module contains tools for analyzing disk health, space usage,
and scanning system logs for disk-related errors.
"""

import re
import json
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any
from langchain_core.tools import tool

@tool
def check_disk_health(node_name: str, device_path: str) -> str:
    """
    Query disk SMART data to assess overall disk health
    
    This tool provides a comprehensive health assessment including
    attributes like reallocated sectors, temperature, and wear leveling.
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        
    Returns:
        str: Disk health assessment with key metrics and status
    """
    try:
        from tools.diagnostics.hardware import ssh_execute, smartctl_check
        
        # Get SMART data
        smart_output = smartctl_check.invoke({'node_name': node_name, 'device_path': device_path})

        # Parse SMART data for key health indicators
        health_status = "Unknown"
        temperature = "Unknown"
        power_on_hours = "Unknown"
        reallocated_sectors = "Unknown"
        pending_sectors = "Unknown"
        offline_uncorrectable = "Unknown"
        
        # Extract overall health status
        health_match = re.search(r"SMART overall-health self-assessment test result: (\w+)", smart_output)
        if health_match:
            health_status = health_match.group(1)
        
        # Extract key attributes
        attributes = {
            "Temperature": re.search(r"Temperature.*?(\d+)", smart_output),
            "Power_On_Hours": re.search(r"Power_On_Hours.*?(\d+)", smart_output),
            "Reallocated_Sector_Ct": re.search(r"Reallocated_Sector_Ct.*?(\d+)", smart_output),
            "Current_Pending_Sector": re.search(r"Current_Pending_Sector.*?(\d+)", smart_output),
            "Offline_Uncorrectable": re.search(r"Offline_Uncorrectable.*?(\d+)", smart_output),
            "Wear_Leveling_Count": re.search(r"Wear_Leveling_Count.*?(\d+)", smart_output)
        }
        
        # Extract values from matches
        for attr, match in attributes.items():
            if match:
                attributes[attr] = match.group(1)
        
        # Format health summary
        summary = [
            f"Disk Health Assessment for {device_path} on {node_name}:",
            f"Overall Health: {health_status}",
            f"Temperature: {attributes.get('Temperature', 'N/A')}°C",
            f"Power On Hours: {attributes.get('Power_On_Hours', 'N/A')}",
            f"Reallocated Sectors: {attributes.get('Reallocated_Sector_Ct', 'N/A')}",
            f"Current Pending Sectors: {attributes.get('Current_Pending_Sector', 'N/A')}",
            f"Offline Uncorrectable Sectors: {attributes.get('Offline_Uncorrectable', 'N/A')}",
            f"Wear Leveling Count: {attributes.get('Wear_Leveling_Count', 'N/A')}\n"
            f"Original SMART Output:\n{smart_output}"
        ]
        
        # Add recommendations based on health indicators
        recommendations = []
        
        if health_status.lower() != "passed":
            recommendations.append("Disk has failed SMART health assessment - immediate replacement recommended")
        
        # Check for concerning values in key attributes
        if attributes.get('Reallocated_Sector_Ct', '0') != '0':
            recommendations.append("Disk has reallocated sectors - monitor closely for further deterioration")
            
        if attributes.get('Current_Pending_Sector', '0') != '0':
            recommendations.append("Disk has pending sectors - data backup recommended")
            
        if attributes.get('Offline_Uncorrectable', '0') != '0':
            recommendations.append("Disk has uncorrectable sectors - consider replacement")
        
        # Add recommendations to summary if any
        if recommendations:
            summary.append("\nRecommendations:")
            summary.extend(recommendations)
        
        return "\n".join(summary)
        
    except Exception as e:
        return f"Error checking disk health: {str(e)}"

@tool
def analyze_disk_space_usage(node_name: str, mount_path: str = "/", 
                            min_file_size_mb: int = 100, 
                            show_top_n: int = 10) -> str:
    """
    Analyze disk space usage to identify large files and potential space issues
    
    This tool identifies large files, unused files, or potential space leaks,
    with options to generate a detailed report.
    
    Args:
        node_name: Node hostname or IP
        mount_path: Path to analyze (default: root)
        min_file_size_mb: Minimum file size to report in MB
        show_top_n: Number of largest files/directories to show
        
    Returns:
        str: Disk space analysis report
    """
    try:
        from tools.diagnostics.hardware import ssh_execute
        
        # Get overall disk usage
        df_cmd = f"df -h {mount_path}"
        df_output = ssh_execute.invoke({'node_name': node_name, 'command': df_cmd})
        
        # Get directory usage breakdown
        du_cmd = f"du -h --max-depth=2 {mount_path} | sort -hr | head -n {show_top_n}"
        du_output = ssh_execute.invoke({'node_name': node_name, 'command': du_cmd})

        # Find large files
        find_cmd = f"find {mount_path} -type f -size +{min_file_size_mb}M -exec ls -lh {{}} \\; | sort -k5hr | head -n {show_top_n}"
        find_output = ssh_execute.invoke({'node_name': node_name, 'command': find_cmd})

        # Find old unused files (not accessed in 90+ days)
        old_files_cmd = f"find {mount_path} -type f -atime +90 -size +{min_file_size_mb}M -exec ls -lh {{}} \\; | sort -k5hr | head -n {show_top_n}"
        old_files_output = ssh_execute.invoke({'node_name': node_name, 'command': old_files_cmd})

        # Format analysis report
        report = [
            f"Disk Space Analysis for {mount_path} on {node_name}:",
            "\n=== Overall Disk Usage ===",
            df_output,
            "\n=== Largest Directories ===",
            du_output,
            "\n=== Largest Files ===",
            find_output,
            "\n=== Large Unused Files (not accessed in 90+ days) ===",
            old_files_output
        ]
        
        # Add recommendations based on findings
        recommendations = []
        
        # Check if disk usage is high (over 85%)
        if "85%" in df_output or "9%" in df_output:
            recommendations.append("High disk usage detected (>85%) - consider cleanup")
        
        # Check for log files in largest files
        if ".log" in find_output:
            recommendations.append("Large log files detected - consider log rotation or cleanup")
            
        # Check for old unused files
        if len(old_files_output.strip()) > 0:
            recommendations.append("Large unused files detected - consider archiving or removing")
        
        # Add recommendations to report if any
        if recommendations:
            report.append("\n=== Recommendations ===")
            report.extend(recommendations)
        
        return "\n".join(report)
        
    except Exception as e:
        return f"Error analyzing disk space usage: {str(e)}"

@tool
def scan_disk_error_logs(node_name: str, hours_back: int = 24, 
                         log_paths: List[str] = None) -> str:
    """
    Scan system logs for disk-related errors or warnings
    
    This tool scans system logs for disk-related errors or warnings,
    summarizing findings with actionable insights.
    
    Args:
        node_name: Node hostname or IP
        hours_back: Hours of logs to scan
        log_paths: List of log paths to scan (default: common system logs)
        
    Returns:
        str: Summary of disk-related errors with insights
    """
    try:
        from tools.diagnostics.hardware import ssh_execute
        
        # Default log paths if not specified
        if log_paths is None:
            log_paths = [
                "/var/log/syslog",
                "/var/log/kern.log",
                "/var/log/dmesg",
                "/var/log/messages"
            ]
        
        # Keywords to search for
        disk_error_keywords = [
            "I/O error", "read error", "write error", "sector error",
            "disk failure", "drive failure", "bad sector", "failed command",
            "ata error", "scsi error", "medium error", "sense key",
            "timeout", "reset", "offline", "uncorrectable", "ECC"
        ]
        
        # Build grep pattern
        grep_pattern = "|".join(disk_error_keywords)
        
        # Results storage
        results = []
        error_count = 0
        
        # Process each log file
        for log_path in log_paths:
            # Check if log file exists
            check_cmd = f"test -f {log_path} && echo exists || echo not found"
            check_result = ssh_execute.invoke({'node_name': node_name, 'command': check_cmd}).strip()
            
            if check_result == "not found":
                results.append(f"Log file {log_path} not found")
                continue
            
            # Get timestamp for hours_back
            time_cmd = f"date -d '{hours_back} hours ago' +'%Y-%m-%d %H:%M:%S'"
            time_result = ssh_execute.invoke({'node_name': node_name, 'command': time_cmd}).strip()
            
            # Search log file for disk errors after the timestamp
            grep_cmd = f"grep -E '{grep_pattern}' {log_path} | grep -A 2 -B 2 '{grep_pattern}'"
            grep_result = ssh_execute.invoke({'node_name': node_name, 'command': grep_cmd}).strip()
            
            # Count errors
            error_lines = grep_result.strip().split('\n')
            if error_lines and error_lines[0]:
                file_error_count = len(error_lines)
                error_count += file_error_count
                results.append(f"\n=== {log_path} ({file_error_count} errors) ===")
                
                # Limit output to avoid overwhelming
                if file_error_count > 20:
                    results.append(f"First 20 of {file_error_count} errors:")
                    results.append(grep_result.split('\n')[:20])
                else:
                    results.append(grep_result)
            else:
                results.append(f"\n=== {log_path} (No errors) ===")
        
        # Create summary
        summary = [
            f"Disk Error Log Scan for {node_name} (past {hours_back} hours):",
            f"Total errors found: {error_count}",
            f"Logs scanned: {', '.join(log_paths)}"
        ]
        
        # Add recommendations based on findings
        recommendations = []
        
        if error_count > 0:
            recommendations.append("Disk errors detected - further investigation recommended")
            
            # Check for common patterns
            if "I/O error" in ' '.join(results):
                recommendations.append("I/O errors detected - possible hardware failure")
                
            if "timeout" in ' '.join(results):
                recommendations.append("Disk timeout errors detected - check disk connectivity")
                
            if "bad sector" in ' '.join(results) or "uncorrectable" in ' '.join(results):
                recommendations.append("Bad sectors detected - backup data and consider replacement")
        
        # Add recommendations to summary if any
        if recommendations:
            summary.append("\n=== Recommendations ===")
            summary.extend(recommendations)
        
        # Combine summary and results
        return "\n".join(summary + ["\n=== Detailed Log Analysis ==="] + results)
        
    except Exception as e:
        return f"Error scanning disk error logs: {str(e)}"
