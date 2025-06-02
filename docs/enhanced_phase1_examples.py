#!/usr/bin/env python3
"""
Enhanced Phase1 Examples

This module provides examples of the enhanced Phase1 functionality, demonstrating
the three possible cases:
1. No issues detected
2. Manual intervention required
3. Automatic fix possible

These examples can be used for testing and documentation purposes.
"""

import asyncio
from typing import Dict, Any, Tuple

# Sample outputs for the three cases

def get_no_issues_example() -> str:
    """
    Get an example of the 'No issues detected' case output
    
    Returns:
        str: Formatted output for the 'No issues detected' case
    """
    return """
Summary Finding: No issues detected in the system.
Evidence: Knowledge Graph query `kg_get_all_issues()` returned no error logs. Service status query `kg_get_entity_info(entity_type='service')` shows all services operational. Drive health check `kg_get_entity_info(entity_type='Drive', entity_id='drive-123')` shows Health=GOOD. Node status check `kg_get_entity_info(entity_type='Node', entity_id='node-1')` shows Ready=True, DiskPressure=False.
Advice: No action required. Continue monitoring system metrics for any future anomalies. Consider running periodic health checks using `kubectl get pods,pvc,pv` to ensure continued normal operation.
SKIP_PHASE2: YES
"""

def get_manual_intervention_example() -> str:
    """
    Get an example of the 'Manual intervention required' case output
    
    Returns:
        str: Formatted output for the 'Manual intervention required' case
    """
    return """
Summary Finding: Issue detected, but requires manual intervention.
Evidence: Knowledge Graph query `kg_get_all_issues()` indicates a hardware failure in drive 'drive-123'. Drive health check `kg_get_entity_info(entity_type='Drive', entity_id='drive-123')` shows Health=BAD. Relationship query `kg_find_path(source_entity_type='Drive', source_entity_id='drive-123', target_entity_type='Pod', target_entity_id='storage-pod')` confirms impact on 'storage-pod'.
Advice: 
1. Backup data from affected volumes using: `kubectl exec storage-pod -- tar -czf /backup/data.tar.gz /data`
2. Drain the affected node: `kubectl drain node-1 --ignore-daemonsets`
3. Replace the faulty drive 'drive-123' following hardware replacement procedures
4. Verify drive replacement with: `smartctl -a /dev/sda`
5. Uncordon the node: `kubectl uncordon node-1`
6. Verify pod rescheduling: `kubectl get pods -o wide | grep storage-pod`
SKIP_PHASE2: YES
"""

def get_automatic_fix_example() -> str:
    """
    Get an example of the 'Automatic fix possible' case output
    
    Returns:
        str: Formatted output for the 'Automatic fix possible' case
    """
    return """
# Summary of Findings
The pod "storage-pod" in namespace "default" is experiencing I/O errors on volume path "/data" due to filesystem corruption on the underlying PV.

# Detailed Analysis
Primary Issues:
- Filesystem corruption detected on PV "pv-123" bound to PVC "pvc-456" used by pod "storage-pod"
- The drive "drive-789" shows good health but the filesystem has inconsistencies

# Relationship Analysis
- Pod "storage-pod" uses PVC "pvc-456"
- PVC "pvc-456" is bound to PV "pv-123"
- PV "pv-123" is mapped to drive "drive-789"

# Investigation Process
- Executed Investigation Plan steps 1-5 successfully
- Identified filesystem corruption through log analysis
- Verified drive hardware is healthy

# Potential Root Causes
- Unexpected pod termination during write operations
- Power loss during write operations
- Filesystem aging and fragmentation

# Open Questions
- Was there a recent power outage or node restart?
- Are there other pods experiencing similar issues?

# Next Steps
- Run filesystem check and repair
- Monitor for recurrence
- Consider enabling journaling

# Root Cause
Filesystem corruption on PV "pv-123" due to improper pod termination during write operations.

# Fix Plan
1. Backup data: `kubectl exec backup-pod -- tar -czf /backup/data.tar.gz /data`
2. Unmount filesystem: `kubectl delete pod storage-pod`
3. Run filesystem check: `fsck.ext4 -y /dev/sda1`
4. Remount and verify: `kubectl apply -f storage-pod.yaml`
5. Verify data integrity: `kubectl exec storage-pod -- ls -la /data`
"""

async def simulate_phase1_execution(case: str) -> Tuple[str, bool]:
    """
    Simulate the execution of Phase1 with different cases
    
    Args:
        case: The case to simulate ('no_issues', 'manual_intervention', or 'automatic_fix')
        
    Returns:
        Tuple[str, bool]: (Analysis result, Skip Phase2 flag)
    """
    # Simulate some processing time
    await asyncio.sleep(1)
    
    if case == 'no_issues':
        result = get_no_issues_example()
        skip_phase2 = "SKIP_PHASE2: YES" in result
        if skip_phase2:
            result = result.replace("SKIP_PHASE2: YES", "").strip()
        return result, skip_phase2
    
    elif case == 'manual_intervention':
        result = get_manual_intervention_example()
        skip_phase2 = "SKIP_PHASE2: YES" in result
        if skip_phase2:
            result = result.replace("SKIP_PHASE2: YES", "").strip()
        return result, skip_phase2
    
    elif case == 'automatic_fix':
        result = get_automatic_fix_example()
        skip_phase2 = "SKIP_PHASE2: YES" in result
        if skip_phase2:
            result = result.replace("SKIP_PHASE2: YES", "").strip()
        return result, skip_phase2
    
    else:
        raise ValueError(f"Unknown case: {case}")

async def main():
    """
    Main function to demonstrate the enhanced Phase1 functionality
    """
    print("=== Enhanced Phase1 Examples ===\n")
    
    # Case 1: No issues detected
    print("Case 1: No issues detected")
    result, skip_phase2 = await simulate_phase1_execution('no_issues')
    print(f"Result:\n{result}")
    print(f"Skip Phase2: {skip_phase2}")
    print("\n" + "=" * 80 + "\n")
    
    # Case 2: Manual intervention required
    print("Case 2: Manual intervention required")
    result, skip_phase2 = await simulate_phase1_execution('manual_intervention')
    print(f"Result:\n{result}")
    print(f"Skip Phase2: {skip_phase2}")
    print("\n" + "=" * 80 + "\n")
    
    # Case 3: Automatic fix possible
    print("Case 3: Automatic fix possible")
    result, skip_phase2 = await simulate_phase1_execution('automatic_fix')
    print(f"Result:\n{result}")
    print(f"Skip Phase2: {skip_phase2}")
    print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
