#!/usr/bin/env python3
"""
Disk monitoring tools for volume troubleshooting.

This module contains tools for monitoring disk status changes and detecting
jitter in disk hardware status.
"""

import time
from datetime import datetime
from typing import Dict, List, Optional
from langchain_core.tools import tool

@tool
def detect_disk_jitter(duration_minutes: int = 5, check_interval_seconds: int = 30, 
                      jitter_threshold: int = 3, node_name: str = None, 
                      drive_uuid: str = None) -> str:
    """
    Detect intermittent online/offline jitter in disk hardware status
    
    This tool monitors disk status changes by periodically running 'kubectl get drive -o wide'
    and detects if a disk frequently switches between online and offline states within
    the specified time window.
    
    Args:
        duration_minutes: Monitoring duration in minutes
        check_interval_seconds: Interval between status checks in seconds
        jitter_threshold: Number of status changes that constitute jitter
        node_name: Specific K8s node to check (optional)
        drive_uuid: Specific drive UUID to monitor (optional, monitors all if not specified)
        
    Returns:
        str: Jitter detection report with timestamps and frequency
    """
    try:
        from tools.kubernetes.csi_baremetal import kubectl_get_drive
        from tools.diagnostics.hardware import ssh_execute
        # todo
        duration_minutes = 1
        # Calculate iterations based on duration and interval
        iterations = int((duration_minutes * 60) / check_interval_seconds)
        
        # Initialize tracking dictionaries
        status_history = {}  # {drive_uuid: [(timestamp, status), ...]}
        status_changes = {}  # {drive_uuid: count}
        drive_info = {}     # {drive_uuid: {node, serial, etc}}
        
        print(f"Starting disk jitter detection for {duration_minutes} minutes "
              f"(checking every {check_interval_seconds} seconds)...")
        
        # Run monitoring loop
        for i in range(iterations):
            # Get current timestamp
            current_time = datetime.now()
            timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Get drive status
            drive_output = kubectl_get_drive.invoke({
                    'resource_type': 'drive',
                    'resource_name': drive_uuid,
                    'output_format': 'wide'
                })
            
            # Parse drive status output
            for line in drive_output.strip().split('\n')[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 5:  # Ensure we have enough parts
                    current_uuid = parts[0]
                    current_status = parts[4]  # STATUS column
                    
                    # Skip if we're monitoring a specific drive and this isn't it
                    if drive_uuid and current_uuid != drive_uuid:
                        continue
                        
                    # Skip if we're monitoring a specific node and this isn't it
                    if node_name:
                        drive_node = parts[9] if len(parts) > 9 else ""
                        if node_name not in drive_node:
                            continue
                    
                    # Store drive info if we don't have it yet
                    if current_uuid not in drive_info:
                        drive_info[current_uuid] = {
                            "serial": parts[8] if len(parts) > 8 else "Unknown",
                            "node": parts[9] if len(parts) > 9 else "Unknown",
                            "path": parts[7] if len(parts) > 7 else "Unknown"
                        }
                    
                    # Initialize history if needed
                    if current_uuid not in status_history:
                        status_history[current_uuid] = []
                        status_changes[current_uuid] = 0
                    
                    # Check for status change
                    if status_history[current_uuid] and status_history[current_uuid][-1][1] != current_status:
                        status_changes[current_uuid] += 1
                        print(f"[{timestamp}] Drive {current_uuid} changed from "
                              f"{status_history[current_uuid][-1][1]} to {current_status}")
                    
                    # Record current status
                    status_history[current_uuid].append((timestamp, current_status))
            
            # Sleep before next check (unless it's the last iteration)
            if i < iterations - 1:
                time.sleep(check_interval_seconds)
        
        # Generate report
        report_lines = [f"Disk Jitter Detection Report ({duration_minutes} minutes monitoring period):"]
        report_lines.append("-" * 80)
        
        jitter_detected = False
        for uuid, changes in status_changes.items():
            if changes >= jitter_threshold:
                jitter_detected = True
                info = drive_info.get(uuid, {})
                serial = info.get("serial", "Unknown")
                node = info.get("node", "Unknown")
                
                # Get status change details
                status_sequence = [f"{ts}: {status}" for ts, status in status_history[uuid]]
                
                report_lines.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Disk Jitter Detected: "
                                   f"Disk {uuid} (Serial: {serial}) switched status "
                                   f"{changes} times in {duration_minutes} minutes on node {node}.")
                report_lines.append(f"Status change sequence: {' -> '.join(s[1] for s in status_history[uuid])}")
                report_lines.append(f"Detailed timeline: {', '.join(status_sequence)}")
                report_lines.append("-" * 80)
        
        if not jitter_detected:
            report_lines.append("No disk jitter detected during the monitoring period.")
        
        return "\n".join(report_lines)
    
    except Exception as e:
        return f"Error during disk jitter detection: {str(e)}"
