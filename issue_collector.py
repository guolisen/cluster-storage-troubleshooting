#!/usr/bin/env python3
"""
Issue Collector for Kubernetes Volume Troubleshooting

This module collects all issues related to Kubernetes, Linux, and Storage layers
that might be contributing to pod volume I/O errors.
"""

import asyncio
import logging
import json
import os
import subprocess
import yaml
from typing import Dict, List, Any, Optional, Tuple, Set

class Issue:
    """Represents a detected issue with relevant metadata"""
    
    def __init__(self, issue_id: str, layer: str, component: str, severity: str, 
                 message: str, evidence: str, related_ids: List[str] = None):
        """
        Initialize an issue object
        
        Args:
            issue_id: Unique identifier for the issue
            layer: Layer where the issue was detected (kubernetes, linux, storage)
            component: Specific component with the issue
            severity: Severity level (critical, warning, info)
            message: Description of the issue
            evidence: Data or output that confirms the issue
            related_ids: IDs of related issues (if known)
        """
        self.id = issue_id
        self.layer = layer
        self.component = component
        self.severity = severity
        self.message = message
        self.evidence = evidence
        self.related_ids = related_ids or []
        self.timestamp = asyncio.get_event_loop().time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert issue to dictionary for serialization"""
        return {
            "id": self.id,
            "layer": self.layer,
            "component": self.component,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
            "related_ids": self.related_ids,
            "timestamp": self.timestamp
        }


class IssueCollector:
    """Collects issues from different layers (K8s, Linux, Storage)"""
    
    def __init__(self, config_data: Dict[str, Any]):
        """
        Initialize the issue collector
        
        Args:
            config_data: Configuration data from config.yaml
        """
        self.config_data = config_data
        self.issues = []
        self.tools = {}
        self.issue_count = 0
        
        # Track nodes involved in the issue
        self.involved_nodes = set()
        
        # Track if CSI Baremetal driver is available
        self.csi_baremetal_available = None
    
    def execute_command(self, command_list: List[str], purpose: str) -> str:
        """
        Execute a command and return its output
        
        Args:
            command_list: Command to execute as a list of strings
            purpose: Purpose of the command
            
        Returns:
            str: Command output
        """
        try:
            logging.info(f"Executing command: {' '.join(command_list)}")
            result = subprocess.run(command_list, shell=False, check=True, 
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True)
            output = result.stdout
            return output
        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed with exit code {e.returncode}: {e.stderr}"
            logging.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Failed to execute command {' '.join(command_list)}: {str(e)}"
            logging.error(error_msg)
            return f"Error: {error_msg}"
    
    def create_issue(self, layer: str, component: str, severity: str, 
                    message: str, evidence: str, related_ids: List[str] = None) -> str:
        """
        Create and store a new issue
        
        Args:
            layer: Layer where the issue was detected
            component: Specific component with the issue
            severity: Severity level
            message: Description of the issue
            evidence: Data or output that confirms the issue
            related_ids: IDs of related issues
            
        Returns:
            str: ID of the created issue
        """
        self.issue_count += 1
        issue_id = f"issue-{self.issue_count}"
        
        issue = Issue(
            issue_id=issue_id,
            layer=layer,
            component=component,
            severity=severity,
            message=message,
            evidence=evidence,
            related_ids=related_ids or []
        )
        
        self.issues.append(issue)
        logging.info(f"Created issue {issue_id}: {message}")
        
        return issue_id
    
    def check_csi_baremetal_available(self) -> bool:
        """
        Check if CSI Baremetal driver and CRDs are available
        
        Returns:
            bool: True if available, False otherwise
        """
        if self.csi_baremetal_available is not None:
            return self.csi_baremetal_available
            
        # Check for CSI driver
        csi_output = self.execute_command(
            ["kubectl", "get", "csidrivers"],
            "Check CSI drivers"
        )
        
        # Check for CRDs
        crd_output = self.execute_command(
            ["kubectl", "get", "crd"],
            "Check Custom Resource Definitions"
        )
        
        # Look for CSI Baremetal driver and CRDs
        self.csi_baremetal_available = (
            "csi-baremetal" in csi_output and 
            "csi-baremetal" in crd_output
        )
        
        return self.csi_baremetal_available
    
    async def get_node_for_pod(self, pod_name: str, namespace: str) -> str:
        """
        Get the node name where a pod is running
        
        Args:
            pod_name: Name of the pod
            namespace: Namespace of the pod
            
        Returns:
            str: Node name
        """
        pod_info = self.execute_command(
            ["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "json"],
            f"Get node information for pod {namespace}/{pod_name}"
        )
        
        try:
            pod_data = json.loads(pod_info)
            node_name = pod_data.get("spec", {}).get("nodeName", "")
            
            if node_name:
                self.involved_nodes.add(node_name)
                
            return node_name
        except json.JSONDecodeError:
            logging.error(f"Failed to parse pod information for {namespace}/{pod_name}")
            return ""
    
    async def get_pvc_for_pod(self, pod_name: str, namespace: str, volume_path: str) -> Tuple[str, str]:
        """
        Get the PVC and PV names for a pod's volume
        
        Args:
            pod_name: Name of the pod
            namespace: Namespace of the pod
            volume_path: Path of the volume in the pod
            
        Returns:
            Tuple[str, str]: PVC name and PV name
        """
        pod_info = self.execute_command(
            ["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "json"],
            f"Get volume information for pod {namespace}/{pod_name}"
        )
        
        try:
            pod_data = json.loads(pod_info)
            
            # Find volume mount that matches volume_path
            volume_mounts = pod_data.get("spec", {}).get("containers", [{}])[0].get("volumeMounts", [])
            volume_name = None
            
            for mount in volume_mounts:
                if mount.get("mountPath") == volume_path:
                    volume_name = mount.get("name")
                    break
            
            if not volume_name:
                return "", ""
            
            # Find volume that matches volume_name
            volumes = pod_data.get("spec", {}).get("volumes", [])
            pvc_name = None
            
            for volume in volumes:
                if volume.get("name") == volume_name and "persistentVolumeClaim" in volume:
                    pvc_name = volume.get("persistentVolumeClaim", {}).get("claimName")
                    break
            
            if not pvc_name:
                return "", ""
            
            # Get PV name from PVC
            pvc_info = self.execute_command(
                ["kubectl", "get", "pvc", pvc_name, "-n", namespace, "-o", "json"],
                f"Get PV information for PVC {namespace}/{pvc_name}"
            )
            
            pvc_data = json.loads(pvc_info)
            pv_name = pvc_data.get("spec", {}).get("volumeName", "")
            
            return pvc_name, pv_name
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logging.error(f"Failed to get PVC for pod {namespace}/{pod_name}: {str(e)}")
            return "", ""
    
    async def collect_kubernetes_issues(self, pod_name: str, namespace: str, volume_path: str) -> List[str]:
        """
        Collect issues at the Kubernetes layer
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            List[str]: List of created issue IDs
        """
        logging.info(f"Collecting Kubernetes layer issues for pod {namespace}/{pod_name}")
        issue_ids = []
        
        # Get pod logs and check for I/O errors
        pod_logs = self.execute_command(
            ["kubectl", "logs", pod_name, "-n", namespace, "--tail", "100"],
            f"Get logs for pod {namespace}/{pod_name}"
        )
        
        if "I/O error" in pod_logs or "Input/output error" in pod_logs:
            issue_id = self.create_issue(
                layer="kubernetes",
                component="pod_logs",
                severity="critical",
                message=f"I/O errors detected in pod logs",
                evidence=pod_logs
            )
            issue_ids.append(issue_id)
        
        # Get pod status and check for mount failures
        pod_describe = self.execute_command(
            ["kubectl", "describe", "pod", pod_name, "-n", namespace],
            f"Describe pod {namespace}/{pod_name}"
        )
        
        if "FailedMount" in pod_describe or "FailedAttachVolume" in pod_describe:
            issue_id = self.create_issue(
                layer="kubernetes",
                component="pod_events",
                severity="critical",
                message=f"Volume mount failures detected in pod events",
                evidence=pod_describe
            )
            issue_ids.append(issue_id)
        
        # Get PVC and PV information
        pvc_name, pv_name = await self.get_pvc_for_pod(pod_name, namespace, volume_path)
        
        if pvc_name and pv_name:
            # Check PVC status
            pvc_info = self.execute_command(
                ["kubectl", "get", "pvc", pvc_name, "-n", namespace, "-o", "yaml"],
                f"Get PVC {namespace}/{pvc_name} details"
            )
            
            if "Bound" not in pvc_info:
                issue_id = self.create_issue(
                    layer="kubernetes",
                    component="pvc",
                    severity="critical",
                    message=f"PVC is not in Bound state",
                    evidence=pvc_info
                )
                issue_ids.append(issue_id)
            
            # Check PV status
            pv_info = self.execute_command(
                ["kubectl", "get", "pv", pv_name, "-o", "yaml"],
                f"Get PV {pv_name} details"
            )
            
            # Check for local volume path issues
            if "local:" in pv_info:
                if volume_path not in pv_info:
                    issue_id = self.create_issue(
                        layer="kubernetes",
                        component="pv",
                        severity="critical",
                        message=f"Volume path mismatch between pod and PV definition",
                        evidence=pv_info
                    )
                    issue_ids.append(issue_id)
        
        # Check for CSI Baremetal resources if available
        if self.check_csi_baremetal_available():
            # Check drive status
            drive_info = self.execute_command(
                ["kubectl", "get", "drive", "-o", "wide"],
                "Get drive information"
            )
            
            if "BAD" in drive_info or "OFFLINE" in drive_info:
                issue_id = self.create_issue(
                    layer="kubernetes",
                    component="csi_drive",
                    severity="critical",
                    message=f"CSI Baremetal drive(s) reporting bad health",
                    evidence=drive_info
                )
                issue_ids.append(issue_id)
            
            # Check LogicalVolumeGroup status
            lvg_info = self.execute_command(
                ["kubectl", "get", "lvg", "-o", "wide"],
                "Get LogicalVolumeGroup information"
            )
            
            if "BAD" in lvg_info:
                issue_id = self.create_issue(
                    layer="kubernetes",
                    component="csi_lvg",
                    severity="critical",
                    message=f"CSI Baremetal LogicalVolumeGroup(s) reporting bad health",
                    evidence=lvg_info
                )
                issue_ids.append(issue_id)
        
        # Check CSI driver pod status
        csi_pods = self.execute_command(
            ["kubectl", "get", "pods", "-n", "kube-system", "-l", "app=csi-baremetal"],
            "Get CSI Baremetal driver pods"
        )
        
        if "CrashLoopBackOff" in csi_pods or "Error" in csi_pods:
            issue_id = self.create_issue(
                layer="kubernetes",
                component="csi_driver",
                severity="critical",
                message=f"CSI Baremetal driver pods in unhealthy state",
                evidence=csi_pods
            )
            issue_ids.append(issue_id)
        
        # Get node status for the affected pod
        node_name = await self.get_node_for_pod(pod_name, namespace)
        if node_name:
            node_info = self.execute_command(
                ["kubectl", "describe", "node", node_name],
                f"Describe node {node_name}"
            )
            
            if "DiskPressure" in node_info:
                issue_id = self.create_issue(
                    layer="kubernetes",
                    component="node",
                    severity="critical",
                    message=f"Node {node_name} is reporting DiskPressure",
                    evidence=node_info
                )
                issue_ids.append(issue_id)
        
        return issue_ids
    
    async def collect_linux_issues(self, node_name: str) -> List[str]:
        """
        Collect issues at the Linux OS layer
        
        Args:
            node_name: Name of the node to check
            
        Returns:
            List[str]: List of created issue IDs
        """
        logging.info(f"Collecting Linux layer issues for node {node_name}")
        issue_ids = []
        
        # Check disk errors in dmesg
        dmesg_output = self.execute_command(
            ["kubectl", "exec", "-it", f"node/{node_name}", "--", "dmesg", "|", "grep", "-i", "error"],
            f"Get disk errors from dmesg on node {node_name}"
        )
        
        disk_error_patterns = ["I/O error", "read error", "write error", "sector error", "ata error"]
        for pattern in disk_error_patterns:
            if pattern.lower() in dmesg_output.lower():
                issue_id = self.create_issue(
                    layer="linux",
                    component="kernel_logs",
                    severity="critical",
                    message=f"Disk errors detected in kernel logs on node {node_name}",
                    evidence=dmesg_output
                )
                issue_ids.append(issue_id)
                break
        
        # Check XFS filesystem errors
        xfs_errors = self.execute_command(
            ["kubectl", "exec", "-it", f"node/{node_name}", "--", "dmesg", "|", "grep", "-i", "xfs"],
            f"Get XFS errors from dmesg on node {node_name}"
        )
        
        if "error" in xfs_errors.lower() or "corrupt" in xfs_errors.lower():
            issue_id = self.create_issue(
                layer="linux",
                component="filesystem",
                severity="critical",
                message=f"XFS filesystem errors detected on node {node_name}",
                evidence=xfs_errors
            )
            issue_ids.append(issue_id)
        
        # Check for disk space issues
        df_output = self.execute_command(
            ["kubectl", "exec", "-it", f"node/{node_name}", "--", "df", "-h"],
            f"Check disk space on node {node_name}"
        )
        
        # Look for filesystems with >90% usage
        for line in df_output.splitlines()[1:]:  # Skip header line
            if line.strip():
                parts = line.split()
                if len(parts) >= 5:
                    usage = parts[4].rstrip('%')
                    try:
                        usage_pct = int(usage)
                        if usage_pct > 90:
                            issue_id = self.create_issue(
                                layer="linux",
                                component="disk_space",
                                severity="critical",
                                message=f"Filesystem on node {node_name} is over 90% full",
                                evidence=df_output
                            )
                            issue_ids.append(issue_id)
                            break
                    except ValueError:
                        continue
        
        # Check for disk mount issues
        mount_output = self.execute_command(
            ["kubectl", "exec", "-it", f"node/{node_name}", "--", "cat", "/proc/mounts"],
            f"Check mounted filesystems on node {node_name}"
        )
        
        if "ro," in mount_output:  # Look for read-only mounts
            issue_id = self.create_issue(
                layer="linux",
                component="mounts",
                severity="critical",
                message=f"Read-only filesystem mounts detected on node {node_name}",
                evidence=mount_output
            )
            issue_ids.append(issue_id)
        
        # Check for inode exhaustion
        df_inodes = self.execute_command(
            ["kubectl", "exec", "-it", f"node/{node_name}", "--", "df", "-i"],
            f"Check inode usage on node {node_name}"
        )
        
        # Look for filesystems with >90% inode usage
        for line in df_inodes.splitlines()[1:]:  # Skip header line
            if line.strip():
                parts = line.split()
                if len(parts) >= 5:
                    usage = parts[4].rstrip('%')
                    try:
                        usage_pct = int(usage)
                        if usage_pct > 90:
                            issue_id = self.create_issue(
                                layer="linux",
                                component="inodes",
                                severity="warning",
                                message=f"Filesystem on node {node_name} is running out of inodes",
                                evidence=df_inodes
                            )
                            issue_ids.append(issue_id)
                            break
                    except ValueError:
                        continue
        
        return issue_ids
    
    async def collect_storage_issues(self, node_name: str, volume_path: str) -> List[str]:
        """
        Collect issues at the storage hardware layer
        
        Args:
            node_name: Name of the node to check
            volume_path: Path of the volume with I/O error
            
        Returns:
            List[str]: List of created issue IDs
        """
        logging.info(f"Collecting storage layer issues for node {node_name}, volume {volume_path}")
        issue_ids = []
        
        # Get underlying device for volume path
        device_info = self.execute_command(
            ["kubectl", "exec", "-it", f"node/{node_name}", "--", "lsblk", "-n", "-o", "NAME,MOUNTPOINT"],
            f"Get device for volume {volume_path} on node {node_name}"
        )
        
        # Extract device name
        device_name = None
        for line in device_info.splitlines():
            if volume_path in line:
                parts = line.split()
                if parts:
                    device_name = parts[0]
                    break
        
        if not device_name:
            logging.warning(f"Could not determine device for volume {volume_path} on node {node_name}")
            return issue_ids
        
        # Get full device path
        if not device_name.startswith("/dev/"):
            device_name = f"/dev/{device_name}"
        
        # Check SMART data
        smart_output = self.execute_command(
            ["kubectl", "exec", "-it", f"node/{node_name}", "--", "smartctl", "-a", device_name],
            f"Check SMART data for {device_name} on node {node_name}"
        )
        
        # Look for bad sectors and SMART errors
        smart_issues = {
            "Reallocated_Sector_Ct": "Bad sectors detected",
            "Current_Pending_Sector": "Pending bad sectors detected",
            "Offline_Uncorrectable": "Uncorrectable sectors detected",
            "FAILING_NOW": "SMART health check failed",
            "SMART overall-health self-assessment test result: FAILED": "Device failed SMART self-test"
        }
        
        for indicator, message in smart_issues.items():
            if indicator in smart_output:
                # Extract the value if it's a SMART attribute
                value = "N/A"
                for line in smart_output.splitlines():
                    if indicator in line:
                        parts = line.split()
                        if len(parts) > 9:  # SMART attributes usually have at least 10 fields
                            try:
                                value = parts[9]  # Usually the raw value
                            except IndexError:
                                pass
                        break
                
                if value != "0" and value != "N/A":  # Only create issue if value is non-zero
                    issue_id = self.create_issue(
                        layer="storage",
                        component="smart",
                        severity="critical",
                        message=f"{message} on {device_name} (value: {value})",
                        evidence=smart_output
                    )
                    issue_ids.append(issue_id)
        
        # Check for NVMe errors if it's an NVMe device
        if "nvme" in device_name:
            nvme_errors = self.execute_command(
                ["kubectl", "exec", "-it", f"node/{node_name}", "--", "nvme", "error-log", device_name],
                f"Check NVMe error log for {device_name} on node {node_name}"
            )
            
            if "Error" in nvme_errors and "Count: 0" not in nvme_errors:
                issue_id = self.create_issue(
                    layer="storage",
                    component="nvme",
                    severity="critical",
                    message=f"NVMe device {device_name} has error logs",
                    evidence=nvme_errors
                )
                issue_ids.append(issue_id)
        
        # Test I/O performance with FIO
        fio_output = self.execute_command(
            ["kubectl", "exec", "-it", f"node/{node_name}", "--", "fio", "--name=read_test", 
             f"--filename={volume_path}/test.fio", "--rw=read", "--bs=4k", "--size=1M", 
             "--numjobs=1", "--iodepth=1", "--runtime=5", "--time_based", "--group_reporting"],
            f"Test I/O performance on {volume_path} on node {node_name}"
        )
        
        # Check for low IOPS or high latency
        if "error" in fio_output.lower() or "failed" in fio_output.lower():
            issue_id = self.create_issue(
                layer="storage",
                component="io_performance",
                severity="critical",
                message=f"I/O test failed on {volume_path}",
                evidence=fio_output
            )
            issue_ids.append(issue_id)
        else:
            # Parse FIO output for performance metrics
            # Simplified parsing - actual implementation would be more robust
            if "iops" in fio_output.lower():
                iops_match = None
                latency_match = None
                
                # Very simple parsing, would be more robust in real implementation
                for line in fio_output.splitlines():
                    if "iops" in line.lower():
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if "iops=" in part.lower():
                                iops_match = parts[i]
                    if "lat" in line.lower() and "avg" in line.lower():
                        latency_match = line
                
                if iops_match:
                    try:
                        iops_value = float(iops_match.split('=')[1].rstrip(','))
                        
                        # Thresholds depend on device type
                        device_type = "hdd"  # Default assumption
                        if "ssd" in device_name or "nvme" in device_name:
                            device_type = "ssd"
                        
                        threshold = 100 if device_type == "hdd" else 1000
                        
                        if iops_value < threshold:
                            issue_id = self.create_issue(
                                layer="storage",
                                component="io_performance",
                                severity="warning",
                                message=f"Low I/O performance detected on {volume_path} ({iops_value} IOPS)",
                                evidence=fio_output
                            )
                            issue_ids.append(issue_id)
                    except (ValueError, IndexError):
                        pass
        
        return issue_ids
    
    async def collect_all_issues(self, pod_name: str, namespace: str, volume_path: str) -> List[Dict[str, Any]]:
        """
        Collect all issues across all layers
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            List[Dict[str, Any]]: List of all issues as dictionaries
        """
        logging.info(f"Starting comprehensive issue collection for pod {namespace}/{pod_name}, volume {volume_path}")
        
        # Get node name
        node_name = await self.get_node_for_pod(pod_name, namespace)
        if not node_name:
            logging.warning(f"Could not determine node for pod {namespace}/{pod_name}")
            return [issue.to_dict() for issue in self.issues]
        
        # Collect issues from all layers
        k8s_issues = await self.collect_kubernetes_issues(pod_name, namespace, volume_path)
        linux_issues = await self.collect_linux_issues(node_name)
        storage_issues = await self.collect_storage_issues(node_name, volume_path)
        
        # Collect issues from other nodes if applicable (e.g. multi-node PVs)
        # This is simplified for now
        
        logging.info(f"Completed issue collection: {len(self.issues)} total issues found")
        
        # Convert issues to dictionaries
        return [issue.to_dict() for issue in self.issues]


async def collect_issues(config_data: Dict[str, Any], pod_name: str, namespace: str, volume_path: str) -> List[Dict[str, Any]]:
    """
    Convenience function to collect all issues
    
    Args:
        config_data: Configuration data from config.yaml
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        
    Returns:
        List[Dict[str, Any]]: List of all issues as dictionaries
    """
    collector = IssueCollector(config_data)
    return await collector.collect_all_issues(pod_name, namespace, volume_path)


if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) != 4:
        print("Usage: python issue_collector.py <pod_name> <namespace> <volume_path>")
        sys.exit(1)
    
    pod_name = sys.argv[1]
    namespace = sys.argv[2]
    volume_path = sys.argv[3]
    
    # Load configuration
    try:
        with open('config.yaml', 'r') as f:
            config_data = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("troubleshoot.log"),
            logging.StreamHandler()
        ]
    )
    
    # Collect issues
    issues = asyncio.run(collect_issues(config_data, pod_name, namespace, volume_path))
    
    # Print results
    print(json.dumps(issues, indent=2))
