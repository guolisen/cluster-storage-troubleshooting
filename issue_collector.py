#!/usr/bin/env python3
"""
Issue Collector Module for Kubernetes Volume Troubleshooting

This module systematically collects all storage-related issues across
K8s/Linux/storage layers that are related to pod volume IO errors.
"""

import logging
import asyncio
import time
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from kubernetes import client
from knowledge_graph import (
    IssueKnowledgeGraph, IssueNode, IssueType, IssueSeverity, 
    Relationship, RelationshipType, create_issue_from_diagnostic_data
)


class ComprehensiveIssueCollector:
    """Collects all issues related to a storage problem across multiple layers"""
    
    def __init__(self, k8s_client: client.CoreV1Api, config_data: Dict[str, Any]):
        self.k8s_client = k8s_client
        self.config_data = config_data
        self.collected_issues = []
        self.resource_cache = {}
        self.tools_results = {}  # Cache for tool execution results
        
    async def collect_comprehensive_issues(self, 
                                         primary_pod_name: str,
                                         primary_namespace: str,
                                         primary_volume_path: str,
                                         tools_executor) -> IssueKnowledgeGraph:
        """
        Collect all issues related to the primary storage problem
        
        Args:
            primary_pod_name: Name of the pod with the primary issue
            primary_namespace: Namespace of the primary pod
            primary_volume_path: Volume path with the primary issue
            tools_executor: Function to execute troubleshooting tools
            
        Returns:
            IssueKnowledgeGraph: Complete knowledge graph of related issues
        """
        logging.info(f"Starting comprehensive issue collection for {primary_namespace}/{primary_pod_name}")
        
        # Initialize knowledge graph
        graph = IssueKnowledgeGraph()
        
        # 1. Start with primary issue
        primary_issue = await self._collect_primary_pod_issue(
            primary_pod_name, primary_namespace, primary_volume_path, tools_executor
        )
        graph.add_issue(primary_issue, is_primary=True)
        
        # 2. Collect related pod issues
        related_pod_issues = await self._collect_related_pod_issues(
            primary_pod_name, primary_namespace, tools_executor
        )
        for issue in related_pod_issues:
            graph.add_issue(issue)
        
        # 3. Collect node-level issues
        node_issues = await self._collect_node_health_issues(
            primary_issue.node_name, tools_executor
        )
        for issue in node_issues:
            graph.add_issue(issue)
        
        # 4. Collect CSI driver issues
        csi_issues = await self._collect_csi_driver_issues(tools_executor)
        for issue in csi_issues:
            graph.add_issue(issue)
        
        # 5. Collect storage resource issues (PVC, PV, StorageClass)
        storage_issues = await self._collect_storage_resource_issues(
            primary_pod_name, primary_namespace, tools_executor
        )
        for issue in storage_issues:
            graph.add_issue(issue)
        
        # 6. Collect hardware/drive issues
        drive_issues = await self._collect_drive_health_issues(
            primary_issue.node_name, tools_executor
        )
        for issue in drive_issues:
            graph.add_issue(issue)
        
        # 7. Build relationships between issues
        await self._build_issue_relationships(graph, tools_executor)
        
        logging.info(f"Comprehensive issue collection completed. Found {len(graph.nodes)} issues with {len(graph.relationships)} relationships")
        
        return graph
    
    async def _collect_primary_pod_issue(self, 
                                       pod_name: str, 
                                       namespace: str, 
                                       volume_path: str,
                                       tools_executor) -> IssueNode:
        """Collect the primary pod issue that triggered the analysis"""
        
        # Get pod details
        pod_describe = await tools_executor("kubectl_describe", {
            "resource": "pod",
            "name": pod_name,
            "namespace": namespace
        })
        
        pod_logs = await tools_executor("kubectl_logs", {
            "pod_name": pod_name,
            "namespace": namespace,
            "tail": 100
        })
        
        # Extract symptoms from logs and events
        symptoms = self._extract_symptoms_from_logs(pod_logs)
        symptoms.extend(self._extract_symptoms_from_describe(pod_describe))
        
        # Determine node name
        node_name = self._extract_node_name_from_describe(pod_describe)
        
        # Determine severity based on symptoms
        severity = self._determine_severity_from_symptoms(symptoms)
        
        issue = IssueNode(
            id=f"pod_{namespace}_{pod_name}",
            issue_type=IssueType.POD_VOLUME_IO,
            severity=severity,
            title=f"Volume I/O Error in pod {namespace}/{pod_name}",
            description=f"Pod {pod_name} in namespace {namespace} experiencing I/O errors on volume path {volume_path}",
            resource_name=pod_name,
            namespace=namespace,
            node_name=node_name,
            symptoms=symptoms,
            details={
                "volume_path": volume_path,
                "pod_describe": pod_describe,
                "pod_logs": pod_logs
            }
        )
        
        return issue
    
    async def _collect_related_pod_issues(self, 
                                        primary_pod_name: str,
                                        primary_namespace: str,
                                        tools_executor) -> List[IssueNode]:
        """Collect issues from pods that might be related to the primary issue"""
        
        related_issues = []
        
        # Get all pods in the same namespace
        namespace_pods = await tools_executor("kubectl_get", {
            "resource": "pods",
            "namespace": primary_namespace
        })
        
        # Get all pods on the same node
        primary_pod_node = await self._get_pod_node_name(primary_pod_name, primary_namespace, tools_executor)
        if primary_pod_node:
            all_pods = await tools_executor("kubectl_get", {
                "resource": "pods",
                "namespace": None  # All namespaces
            })
            
            # Find pods with storage-related errors
            for pod_info in self._parse_pod_list(all_pods):
                if pod_info['name'] == primary_pod_name and pod_info['namespace'] == primary_namespace:
                    continue  # Skip primary pod
                
                # Check if pod has storage-related issues
                pod_logs = await tools_executor("kubectl_logs", {
                    "pod_name": pod_info['name'],
                    "namespace": pod_info['namespace'],
                    "tail": 50
                })
                
                storage_symptoms = self._extract_storage_symptoms(pod_logs)
                if storage_symptoms:
                    issue = IssueNode(
                        id=f"pod_{pod_info['namespace']}_{pod_info['name']}",
                        issue_type=IssueType.POD_VOLUME_IO,
                        severity=self._determine_severity_from_symptoms(storage_symptoms),
                        title=f"Storage issues in pod {pod_info['namespace']}/{pod_info['name']}",
                        description=f"Pod {pod_info['name']} showing storage-related symptoms",
                        resource_name=pod_info['name'],
                        namespace=pod_info['namespace'],
                        node_name=pod_info.get('node'),
                        symptoms=storage_symptoms
                    )
                    related_issues.append(issue)
        
        return related_issues
    
    async def _collect_node_health_issues(self, 
                                        node_name: Optional[str],
                                        tools_executor) -> List[IssueNode]:
        """Collect node-level health issues"""
        
        if not node_name:
            return []
        
        node_issues = []
        
        # Get node description
        node_describe = await tools_executor("kubectl_describe", {
            "resource": "node",
            "name": node_name
        })
        
        # Check disk space
        df_output = await tools_executor("ssh_command", {
            "node": node_name,
            "command": "df -h"
        })
        
        # Check kernel messages
        dmesg_disk = await tools_executor("ssh_command", {
            "node": node_name,
            "command": "dmesg | grep -i 'disk\\|error\\|fail' | tail -20"
        })
        
        # Analyze node conditions
        node_symptoms = self._extract_node_symptoms(node_describe, df_output, dmesg_disk)
        
        if node_symptoms:
            issue = IssueNode(
                id=f"node_{node_name}",
                issue_type=IssueType.NODE_DISK_HEALTH,
                severity=self._determine_severity_from_symptoms(node_symptoms),
                title=f"Node health issues on {node_name}",
                description=f"Node {node_name} showing health problems affecting storage",
                resource_name=node_name,
                node_name=node_name,
                symptoms=node_symptoms,
                details={
                    "node_describe": node_describe,
                    "df_output": df_output,
                    "dmesg_output": dmesg_disk
                }
            )
            node_issues.append(issue)
        
        return node_issues
    
    async def _collect_csi_driver_issues(self, tools_executor) -> List[IssueNode]:
        """Collect CSI driver related issues"""
        
        csi_issues = []
        
        # Check CSI driver pods
        csi_pods = await tools_executor("kubectl_get", {
            "resource": "pods",
            "namespace": "kube-system"
        })
        
        # Check CSI drivers registration
        csi_drivers = await tools_executor("kubectl_get", {
            "resource": "csidrivers"
        })
        
        # Check for CSI driver pod issues
        for pod_info in self._parse_pod_list(csi_pods):
            if 'csi' in pod_info['name'].lower() or 'baremetal' in pod_info['name'].lower():
                pod_logs = await tools_executor("kubectl_logs", {
                    "pod_name": pod_info['name'],
                    "namespace": "kube-system",
                    "tail": 100
                })
                
                csi_symptoms = self._extract_csi_symptoms(pod_logs)
                if csi_symptoms:
                    issue = IssueNode(
                        id=f"csi_{pod_info['name']}",
                        issue_type=IssueType.CSI_DRIVER,
                        severity=self._determine_severity_from_symptoms(csi_symptoms),
                        title=f"CSI driver issues in {pod_info['name']}",
                        description=f"CSI driver pod {pod_info['name']} showing errors",
                        resource_name=pod_info['name'],
                        namespace="kube-system",
                        symptoms=csi_symptoms,
                        details={"pod_logs": pod_logs}
                    )
                    csi_issues.append(issue)
        
        return csi_issues
    
    async def _collect_storage_resource_issues(self, 
                                             primary_pod_name: str,
                                             primary_namespace: str,
                                             tools_executor) -> List[IssueNode]:
        """Collect PVC, PV, and StorageClass issues"""
        
        storage_issues = []
        
        # Get pod's PVCs
        pod_yaml = await tools_executor("kubectl_get", {
            "resource": "pod",
            "name": primary_pod_name,
            "namespace": primary_namespace
        })
        
        pvc_names = self._extract_pvc_names_from_pod(pod_yaml)
        
        for pvc_name in pvc_names:
            # Check PVC status
            pvc_describe = await tools_executor("kubectl_describe", {
                "resource": "pvc",
                "name": pvc_name,
                "namespace": primary_namespace
            })
            
            pvc_symptoms = self._extract_pvc_symptoms(pvc_describe)
            if pvc_symptoms:
                issue = IssueNode(
                    id=f"pvc_{primary_namespace}_{pvc_name}",
                    issue_type=IssueType.PVC_BINDING,
                    severity=self._determine_severity_from_symptoms(pvc_symptoms),
                    title=f"PVC issues with {pvc_name}",
                    description=f"PVC {pvc_name} in namespace {primary_namespace} has binding/provisioning issues",
                    resource_name=pvc_name,
                    namespace=primary_namespace,
                    symptoms=pvc_symptoms,
                    details={"pvc_describe": pvc_describe}
                )
                storage_issues.append(issue)
            
            # Check associated PV
            pv_name = self._extract_pv_name_from_pvc(pvc_describe)
            if pv_name:
                pv_describe = await tools_executor("kubectl_describe", {
                    "resource": "pv",
                    "name": pv_name
                })
                
                pv_symptoms = self._extract_pv_symptoms(pv_describe)
                if pv_symptoms:
                    issue = IssueNode(
                        id=f"pv_{pv_name}",
                        issue_type=IssueType.PV_ATTACHMENT,
                        severity=self._determine_severity_from_symptoms(pv_symptoms),
                        title=f"PV issues with {pv_name}",
                        description=f"PV {pv_name} has attachment/mounting issues",
                        resource_name=pv_name,
                        symptoms=pv_symptoms,
                        details={"pv_describe": pv_describe}
                    )
                    storage_issues.append(issue)
        
        return storage_issues
    
    async def _collect_drive_health_issues(self, 
                                         node_name: Optional[str],
                                         tools_executor) -> List[IssueNode]:
        """Collect hardware drive health issues"""
        
        if not node_name:
            return []
        
        drive_issues = []
        
        # Get CSI Baremetal drives
        drives_output = await tools_executor("kubectl_get", {
            "resource": "drives"
        })
        
        # Check available capacity
        ac_output = await tools_executor("kubectl_get", {
            "resource": "ac"
        })
        
        # Parse drive health from CSI resources
        drive_health_issues = self._extract_drive_health_issues(drives_output, ac_output, node_name)
        
        for drive_issue_data in drive_health_issues:
            issue = IssueNode(
                id=f"drive_{drive_issue_data['drive_id']}",
                issue_type=IssueType.DRIVE_HEALTH,
                severity=drive_issue_data['severity'],
                title=f"Drive health issue: {drive_issue_data['drive_id']}",
                description=drive_issue_data['description'],
                resource_name=drive_issue_data['drive_id'],
                node_name=node_name,
                symptoms=drive_issue_data['symptoms'],
                details=drive_issue_data.get('details', {})
            )
            drive_issues.append(issue)
        
        # Check hardware SMART data if SSH is available
        if self.config_data.get('troubleshoot', {}).get('ssh', {}).get('enabled'):
            smart_issues = await self._collect_smart_data_issues(node_name, tools_executor)
            drive_issues.extend(smart_issues)
        
        return drive_issues
    
    async def _collect_smart_data_issues(self, 
                                       node_name: str,
                                       tools_executor) -> List[IssueNode]:
        """Collect SMART data issues from hardware"""
        
        smart_issues = []
        
        # Get disk list
        lsblk_output = await tools_executor("ssh_command", {
            "node": node_name,
            "command": "lsblk -d -o NAME,TYPE | grep disk"
        })
        
        disk_devices = self._parse_disk_devices(lsblk_output)
        
        for device in disk_devices[:3]:  # Limit to first 3 devices to avoid timeout
            smart_output = await tools_executor("ssh_command", {
                "node": node_name,
                "command": f"smartctl -H /dev/{device}"
            })
            
            smart_symptoms = self._extract_smart_symptoms(smart_output, device)
            if smart_symptoms:
                issue = IssueNode(
                    id=f"smart_{node_name}_{device}",
                    issue_type=IssueType.DRIVE_HEALTH,
                    severity=self._determine_severity_from_symptoms(smart_symptoms),
                    title=f"SMART health issues on {device}",
                    description=f"Hardware disk {device} on node {node_name} showing SMART health problems",
                    resource_name=device,
                    node_name=node_name,
                    symptoms=smart_symptoms,
                    details={"smart_output": smart_output}
                )
                smart_issues.append(issue)
        
        return smart_issues
    
    async def _build_issue_relationships(self, 
                                       graph: IssueKnowledgeGraph,
                                       tools_executor) -> None:
        """Build relationships between collected issues"""
        
        # Build relationships based on Kubernetes resource hierarchy
        await self._build_k8s_resource_relationships(graph)
        
        # Build relationships based on node co-location
        await self._build_node_colocation_relationships(graph)
        
        # Build causal relationships based on symptoms
        await self._build_causal_relationships(graph)
    
    async def _build_k8s_resource_relationships(self, graph: IssueKnowledgeGraph) -> None:
        """Build relationships based on Kubernetes resource dependencies"""
        
        for issue_id, issue in graph.nodes.items():
            if issue.issue_type == IssueType.POD_VOLUME_IO:
                # Pod depends on PVC
                for other_id, other_issue in graph.nodes.items():
                    if (other_issue.issue_type == IssueType.PVC_BINDING and
                        other_issue.namespace == issue.namespace):
                        
                        graph.add_relationship(Relationship(
                            source_id=issue_id,
                            target_id=other_id,
                            relationship_type=RelationshipType.DEPENDS_ON,
                            confidence=0.8,
                            description=f"Pod {issue.resource_name} depends on PVC {other_issue.resource_name}"
                        ))
                
                # Pod runs on Node
                for other_id, other_issue in graph.nodes.items():
                    if (other_issue.issue_type == IssueType.NODE_DISK_HEALTH and
                        other_issue.node_name == issue.node_name):
                        
                        graph.add_relationship(Relationship(
                            source_id=issue_id,
                            target_id=other_id,
                            relationship_type=RelationshipType.DEPENDS_ON,
                            confidence=0.9,
                            description=f"Pod {issue.resource_name} runs on node {issue.node_name}"
                        ))
    
    async def _build_node_colocation_relationships(self, graph: IssueKnowledgeGraph) -> None:
        """Build relationships between issues on the same node"""
        
        # Group issues by node
        node_issues = {}
        for issue_id, issue in graph.nodes.items():
            if issue.node_name:
                if issue.node_name not in node_issues:
                    node_issues[issue.node_name] = []
                node_issues[issue.node_name].append((issue_id, issue))
        
        # Create relationships between issues on the same node
        for node_name, issues in node_issues.items():
            if len(issues) > 1:
                for i, (issue_id1, issue1) in enumerate(issues):
                    for issue_id2, issue2 in issues[i+1:]:
                        # If both are storage-related, they might affect each other
                        if self._are_storage_related(issue1, issue2):
                            graph.add_relationship(Relationship(
                                source_id=issue_id1,
                                target_id=issue_id2,
                                relationship_type=RelationshipType.RELATED_TO,
                                confidence=0.6,
                                description=f"Both issues occur on the same node {node_name}"
                            ))
    
    async def _build_causal_relationships(self, graph: IssueKnowledgeGraph) -> None:
        """Build causal relationships based on symptoms and severity"""
        
        for issue_id, issue in graph.nodes.items():
            for other_id, other_issue in graph.nodes.items():
                if issue_id == other_id:
                    continue
                
                # Drive health issues can cause pod I/O issues
                if (issue.issue_type == IssueType.DRIVE_HEALTH and
                    other_issue.issue_type == IssueType.POD_VOLUME_IO and
                    issue.node_name == other_issue.node_name):
                    
                    graph.add_relationship(Relationship(
                        source_id=other_id,
                        target_id=issue_id,
                        relationship_type=RelationshipType.CAUSED_BY,
                        confidence=0.8,
                        description=f"Pod I/O error likely caused by drive health issues"
                    ))
                
                # CSI driver issues can cause multiple pod issues
                if (issue.issue_type == IssueType.CSI_DRIVER and
                    other_issue.issue_type == IssueType.POD_VOLUME_IO):
                    
                    graph.add_relationship(Relationship(
                        source_id=other_id,
                        target_id=issue_id,
                        relationship_type=RelationshipType.CAUSED_BY,
                        confidence=0.7,
                        description=f"Pod I/O error potentially caused by CSI driver issues"
                    ))
    
    # Helper methods for parsing and symptom extraction
    
    def _extract_symptoms_from_logs(self, logs: str) -> List[str]:
        """Extract symptoms from pod logs"""
        symptoms = []
        
        error_patterns = [
            r"Input/output error",
            r"No space left on device",
            r"Permission denied",
            r"Transport endpoint is not connected",
            r"Device or resource busy",
            r"Read-only file system",
            r"Connection refused",
            r"Timeout",
            r"Failed to mount",
            r"Volume attach failed"
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, logs, re.IGNORECASE):
                symptoms.append(f"Log shows: {pattern}")
        
        return symptoms
    
    def _extract_symptoms_from_describe(self, describe_output: str) -> List[str]:
        """Extract symptoms from kubectl describe output"""
        symptoms = []
        
        event_patterns = [
            r"FailedMount",
            r"VolumeBindingFailed",
            r"ProvisioningFailed",
            r"AttachVolumeFailed",
            r"MountVolumeFailed",
            r"Failed to attach volume",
            r"Failed to mount volume"
        ]
        
        for pattern in event_patterns:
            if re.search(pattern, describe_output, re.IGNORECASE):
                symptoms.append(f"Event shows: {pattern}")
        
        return symptoms
    
    def _extract_node_name_from_describe(self, describe_output: str) -> Optional[str]:
        """Extract node name from pod describe output"""
        match = re.search(r"Node:\s+([^\s/]+)", describe_output)
        return match.group(1) if match else None
    
    def _determine_severity_from_symptoms(self, symptoms: List[str]) -> IssueSeverity:
        """Determine issue severity based on symptoms"""
        if not symptoms:
            return IssueSeverity.INFO
        
        critical_keywords = ['failed', 'error', 'critical', 'down', 'offline']
        high_keywords = ['warning', 'timeout', 'slow', 'degraded']
        
        symptom_text = ' '.join(symptoms).lower()
        
        if any(keyword in symptom_text for keyword in critical_keywords):
            return IssueSeverity.CRITICAL
        elif any(keyword in symptom_text for keyword in high_keywords):
            return IssueSeverity.HIGH
        else:
            return IssueSeverity.MEDIUM
    
    def _extract_storage_symptoms(self, logs: str) -> List[str]:
        """Extract storage-related symptoms from logs"""
        symptoms = []
        
        storage_patterns = [
            r"volume.*error",
            r"mount.*failed",
            r"disk.*error",
            r"I/O error",
            r"filesystem.*error"
        ]
        
        for pattern in storage_patterns:
            if re.search(pattern, logs, re.IGNORECASE):
                symptoms.append(f"Storage issue detected: {pattern}")
        
        return symptoms
    
    def _parse_pod_list(self, pod_list_output: str) -> List[Dict[str, str]]:
        """Parse kubectl get pods output into list of pod info"""
        pods = []
        lines = pod_list_output.strip().split('\n')
        
        for line in lines[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 7:
                pods.append({
                    'name': parts[0],
                    'namespace': parts[1] if len(parts) > 6 else 'default',
                    'ready': parts[1],
                    'status': parts[2],
                    'restarts': parts[3],
                    'age': parts[4],
                    'node': parts[6] if len(parts) > 6 else None
                })
        
        return pods
    
    def _extract_node_symptoms(self, node_describe: str, df_output: str, dmesg_output: str) -> List[str]:
        """Extract symptoms from node health data"""
        symptoms = []
        
        # Check node conditions
        if 'DiskPressure' in node_describe and 'True' in node_describe:
            symptoms.append("Node has DiskPressure condition")
        
        # Check disk space
        if '100%' in df_output or '9[0-9]%' in df_output:
            symptoms.append("Disk space critically low")
        
        # Check kernel messages
        if 'error' in dmesg_output.lower() or 'fail' in dmesg_output.lower():
            symptoms.append("Kernel messages show disk errors")
        
        return symptoms
    
    def _extract_csi_symptoms(self, logs: str) -> List[str]:
        """Extract CSI driver symptoms from logs"""
        symptoms = []
        
        csi_patterns = [
            r"failed to provision volume",
            r"failed to attach volume",
            r"failed to mount volume",
            r"driver.*error",
            r"csi.*failed",
            r"timeout.*csi"
        ]
        
        for pattern in csi_patterns:
            if re.search(pattern, logs, re.IGNORECASE):
                symptoms.append(f"CSI driver issue: {pattern}")
        
        return symptoms
    
    def _extract_pvc_names_from_pod(self, pod_yaml: str) -> List[str]:
        """Extract PVC names from pod YAML"""
        pvc_names = []
        
        # Simple regex to find PVC claim names
        matches = re.findall(r'claimName:\s+([^\s]+)', pod_yaml)
        pvc_names.extend(matches)
        
        return pvc_names
    
    def _extract_pvc_symptoms(self, pvc_describe: str) -> List[str]:
        """Extract symptoms from PVC describe output"""
        symptoms = []
        
        if 'Pending' in pvc_describe:
            symptoms.append("PVC is in Pending state")
        
        if 'ProvisioningFailed' in pvc_describe:
            symptoms.append("PVC provisioning failed")
        
        return symptoms
    
    def _extract_pv_name_from_pvc(self, pvc_describe: str) -> Optional[str]:
        """Extract PV name from PVC describe output"""
        match = re.search(r'Volume:\s+([^\s]+)', pvc_describe)
        return match.group(1) if match else None
    
    def _extract_pv_symptoms(self, pv_describe: str) -> List[str]:
        """Extract symptoms from PV describe output"""
        symptoms = []
        
        if 'Failed' in pv_describe:
            symptoms.append("PV shows failed status")
        
        return symptoms
    
    def _extract_drive_health_issues(self, drives_output: str, ac_output: str, node_name: str) -> List[Dict[str, Any]]:
        """Extract drive health issues from CSI Baremetal resources"""
        issues = []
        
        # Parse drives output to find health issues
        lines = drives_output.strip().split('\n')
        for line in lines[1:]:  # Skip header
            if node_name in line and ('BAD' in line or 'OFFLINE' in line):
                parts = line.split()
                if len(parts) >= 3:
                    issues.append({
                        'drive_id': parts[0],
                        'severity': IssueSeverity.CRITICAL,
                        'description': f"Drive {parts[0]} is in BAD or OFFLINE state",
                        'symptoms': ['Drive health check failed'],
                        'details': {'drives_line': line}
                    })
        
        return issues
    
    def _parse_disk_devices(self, lsblk_output: str) -> List[str]:
        """Parse disk devices from lsblk output"""
        devices = []
        lines = lsblk_output.strip().split('\n')
        
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == 'disk':
                devices.append(parts[0])
        
        return devices
    
    def _extract_smart_symptoms(self, smart_output: str, device: str) -> List[str]:
        """Extract symptoms from SMART data"""
        symptoms = []
        
        if 'PASSED' not in smart_output or 'FAILED' in smart_output:
            symptoms.append(f"SMART health check failed for {device}")
        
        return symptoms
    
    def _are_storage_related(self, issue1: IssueNode, issue2: IssueNode) -> bool:
        """Check if two issues are storage-related"""
        storage_types = {
            IssueType.POD_VOLUME_IO,
            IssueType.DRIVE_HEALTH,
            IssueType.PVC_BINDING,
            IssueType.PV_ATTACHMENT,
            IssueType.NODE_DISK_HEALTH,
            IssueType.CSI_DRIVER
        }
        
        return issue1.issue_type in storage_types and issue2.issue_type in storage_types
    
    async def _get_pod_node_name(self, pod_name: str, namespace: str, tools_executor) -> Optional[str]:
        """Get the node name where a pod is running"""
        try:
            pod_describe = await tools_executor("kubectl_describe", {
                "resource": "pod",
                "name": pod_name,
                "namespace": namespace
            })
            return self._extract_node_name_from_describe(pod_describe)
        except Exception as e:
            logging.warning(f"Failed to get node name for pod {namespace}/{pod_name}: {e}")
            return None
