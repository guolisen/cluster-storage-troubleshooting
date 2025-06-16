#!/usr/bin/env python3
"""
Mock Knowledge Graph implementation for testing and demonstration purposes
"""

from typing import Dict, Any, List, Optional, Set, Tuple
import networkx as nx
import json

class MockKnowledgeGraph:
    """
    Mock implementation of the Knowledge Graph for testing and demonstration
    """
    
    def __init__(self):
        """
        Initialize the mock Knowledge Graph
        """
        self.graph = nx.DiGraph()
        self.issues = []
        self._initialize_mock_graph()
    
    def _initialize_mock_graph(self):
        """
        Initialize the mock graph with sample data
        """
        # Add nodes
        self._add_pod_node()
        self._add_pvc_node()
        self._add_pv_node()
        self._add_node_node()
        self._add_drive_node()
        self._add_volume_node()
        self._add_storage_class_node()
        self._add_system_node()
        
        # Add edges
        self._add_relationships()
        
        # Add issues
        self._add_issues()
    
    def _add_pod_node(self):
        """
        Add a Pod node to the graph
        """
        self.graph.add_node(
            "gnode:Pod:default/test-pod",
            entity_type="Pod",
            id="gnode:Pod:default/test-pod",
            name="test-pod",
            namespace="default",
            node="worker-1",
            status="Running",
            volumes=[
                {
                    "name": "test-volume",
                    "persistentVolumeClaim": {
                        "claimName": "test-pvc"
                    }
                }
            ],
            containers=[
                {
                    "name": "test-container",
                    "volumeMounts": [
                        {
                            "name": "test-volume",
                            "mountPath": "/data"
                        }
                    ]
                }
            ],
            last_error="I/O error on volume"
        )
    
    def _add_pvc_node(self):
        """
        Add a PVC node to the graph
        """
        self.graph.add_node(
            "gnode:PVC:default/test-pvc",
            entity_type="PVC",
            id="gnode:PVC:default/test-pvc",
            name="test-pvc",
            namespace="default",
            storage_class="csi-baremetal-sc",
            volume_name="test-pv",
            status="Bound",
            capacity="10Gi",
            access_modes=["ReadWriteOnce"]
        )
    
    def _add_pv_node(self):
        """
        Add a PV node to the graph
        """
        self.graph.add_node(
            "gnode:PV:test-pv",
            entity_type="PV",
            id="gnode:PV:test-pv",
            name="test-pv",
            storage_class="csi-baremetal-sc",
            capacity="10Gi",
            access_modes=["ReadWriteOnce"],
            reclaim_policy="Delete",
            status="Bound",
            csi_driver="csi-baremetal",
            volume_handle="volume-123-456",
            fs_type="xfs",
            node="worker-1"
        )
    
    def _add_node_node(self):
        """
        Add a Node node to the graph
        """
        self.graph.add_node(
            "gnode:Node:worker-1",
            entity_type="Node",
            id="gnode:Node:worker-1",
            name="worker-1",
            status="Ready",
            ip="192.168.1.10",
            capacity={
                "cpu": "8",
                "memory": "32Gi",
                "pods": "110"
            },
            conditions=[
                {
                    "type": "Ready",
                    "status": "True"
                },
                {
                    "type": "DiskPressure",
                    "status": "False"
                }
            ]
        )
    
    def _add_drive_node(self):
        """
        Add a Drive node to the graph
        """
        self.graph.add_node(
            "gnode:Drive:drive-abc-123",
            entity_type="Drive",
            id="gnode:Drive:drive-abc-123",
            uuid="drive-abc-123",
            node="worker-1",
            path="/dev/sda",
            size="100Gi",
            type="HDD",
            status="Online",
            health="Warning",
            error_log=[
                {
                    "timestamp": "2025-06-16T04:28:00Z",
                    "error": "I/O errors detected",
                    "details": "Multiple read failures recorded"
                }
            ]
        )
    
    def _add_volume_node(self):
        """
        Add a Volume node to the graph
        """
        self.graph.add_node(
            "gnode:Volume:default/volume-123-456",
            entity_type="Volume",
            id="gnode:Volume:default/volume-123-456",
            name="volume-123-456",
            namespace="default",
            pv_name="test-pv",
            node="worker-1",
            status="Available",
            health="Warning",
            drive_uuid="drive-abc-123"
        )
    
    def _add_storage_class_node(self):
        """
        Add a StorageClass node to the graph
        """
        self.graph.add_node(
            "gnode:StorageClass:csi-baremetal-sc",
            entity_type="StorageClass",
            id="gnode:StorageClass:csi-baremetal-sc",
            name="csi-baremetal-sc",
            provisioner="csi-baremetal",
            parameters={
                "storageType": "HDD",
                "fsType": "xfs"
            },
            reclaim_policy="Delete",
            volume_binding_mode="WaitForFirstConsumer"
        )
    
    def _add_system_node(self):
        """
        Add a System node to the graph
        """
        self.graph.add_node(
            "gnode:System:filesystem",
            entity_type="System",
            id="gnode:System:filesystem",
            name="filesystem",
            type="xfs",
            mount_point="/var/lib/kubelet/pods/pod-123-456/volumes/kubernetes.io~csi/test-pv/mount",
            status="Error",
            error_log=[
                {
                    "timestamp": "2025-06-16T04:28:00Z",
                    "error": "XFS metadata corruption detected",
                    "details": "XFS_CORRUPT_INODES error found during filesystem check"
                }
            ]
        )
    
    def _add_relationships(self):
        """
        Add relationships between nodes
        """
        # Pod uses PVC
        self.graph.add_edge(
            "gnode:Pod:default/test-pod",
            "gnode:PVC:default/test-pvc",
            relationship="USES",
            mount_path="/data"
        )
        
        # PVC bound to PV
        self.graph.add_edge(
            "gnode:PVC:default/test-pvc",
            "gnode:PV:test-pv",
            relationship="BOUND_TO"
        )
        
        # PV uses Volume
        self.graph.add_edge(
            "gnode:PV:test-pv",
            "gnode:Volume:default/volume-123-456",
            relationship="USES"
        )
        
        # Volume uses Drive
        self.graph.add_edge(
            "gnode:Volume:default/volume-123-456",
            "gnode:Drive:drive-abc-123",
            relationship="USES"
        )
        
        # PV uses StorageClass
        self.graph.add_edge(
            "gnode:PV:test-pv",
            "gnode:StorageClass:csi-baremetal-sc",
            relationship="USES"
        )
        
        # PV uses System (filesystem)
        self.graph.add_edge(
            "gnode:PV:test-pv",
            "gnode:System:filesystem",
            relationship="USES"
        )
        
        # Pod runs on Node
        self.graph.add_edge(
            "gnode:Pod:default/test-pod",
            "gnode:Node:worker-1",
            relationship="RUNS_ON"
        )
        
        # Drive is on Node
        self.graph.add_edge(
            "gnode:Drive:drive-abc-123",
            "gnode:Node:worker-1",
            relationship="IS_ON"
        )
    
    def _add_issues(self):
        """
        Add issues to the graph
        """
        self.issues = [
            {
                "id": "issue-001",
                "entity_id": "gnode:System:filesystem",
                "entity_type": "System",
                "severity": "critical",
                "category": "filesystem",
                "message": "XFS filesystem corruption detected on volume test-pv",
                "details": "XFS metadata corruption found during filesystem check. This can lead to I/O errors and data loss.",
                "timestamp": "2025-06-16T04:28:00Z",
                "related_entities": ["gnode:PV:test-pv", "gnode:Pod:default/test-pod"],
                "possible_causes": [
                    "Sudden power loss",
                    "Hardware failure",
                    "Kernel bugs",
                    "Improper unmounting"
                ],
                "recommended_actions": [
                    "Run xfs_repair to attempt filesystem repair",
                    "Check disk health with SMART tools",
                    "Backup data if possible before repair"
                ]
            },
            {
                "id": "issue-002",
                "entity_id": "gnode:Drive:drive-abc-123",
                "entity_type": "Drive",
                "severity": "warning",
                "category": "hardware",
                "message": "Multiple I/O errors detected on drive /dev/sda",
                "details": "The drive has reported multiple read failures which may indicate hardware degradation.",
                "timestamp": "2025-06-16T04:28:00Z",
                "related_entities": ["gnode:Volume:default/volume-123-456", "gnode:Node:worker-1"],
                "possible_causes": [
                    "Drive hardware failure",
                    "Loose connections",
                    "Controller issues"
                ],
                "recommended_actions": [
                    "Run SMART diagnostics on the drive",
                    "Check drive connections",
                    "Consider replacing the drive if errors persist"
                ]
            }
        ]
    
    # Knowledge Graph API methods
    def print_graph(self, use_rich=False):
        """
        Print the graph structure
        
        Args:
            use_rich: Whether to use rich formatting
            
        Returns:
            str: Formatted graph output
        """
        output = []
        output.append("Knowledge Graph Summary:")
        output.append(f"Total nodes: {self.graph.number_of_nodes()}")
        output.append(f"Total edges: {self.graph.number_of_edges()}")
        output.append(f"Total issues: {len(self.issues)}")
        output.append("\nNode types:")
        
        # Count node types
        node_types = {}
        for node in self.graph.nodes:
            entity_type = self.graph.nodes[node].get('entity_type')
            if entity_type not in node_types:
                node_types[entity_type] = 0
            node_types[entity_type] += 1
        
        for node_type, count in node_types.items():
            output.append(f"  - {node_type}: {count}")
        
        output.append("\nRelationship types:")
        # Count relationship types
        rel_types = {}
        for u, v, data in self.graph.edges(data=True):
            rel_type = data.get('relationship')
            if rel_type not in rel_types:
                rel_types[rel_type] = 0
            rel_types[rel_type] += 1
        
        for rel_type, count in rel_types.items():
            output.append(f"  - {rel_type}: {count}")
        
        output.append("\nIssues by severity:")
        # Count issues by severity
        severity_counts = {}
        for issue in self.issues:
            severity = issue.get('severity')
            if severity not in severity_counts:
                severity_counts[severity] = 0
            severity_counts[severity] += 1
        
        for severity, count in severity_counts.items():
            output.append(f"  - {severity}: {count}")
        
        return "\n".join(output)
    
    def get_entity_info(self, entity_type: str, id: str) -> Dict[str, Any]:
        """
        Get entity information
        
        Args:
            entity_type: Type of entity
            id: Entity ID
            
        Returns:
            Dict[str, Any]: Entity information
        """
        if id in self.graph.nodes:
            return dict(self.graph.nodes[id])
        return {}
    
    def get_related_entities(self, entity_type: str, id: str) -> List[Dict[str, Any]]:
        """
        Get related entities
        
        Args:
            entity_type: Type of entity
            id: Entity ID
            
        Returns:
            List[Dict[str, Any]]: Related entities
        """
        related = []
        
        # Outgoing edges
        for _, v, data in self.graph.out_edges(id, data=True):
            related.append({
                "entity_id": v,
                "entity_type": self.graph.nodes[v].get('entity_type'),
                "relationship": data.get('relationship'),
                "direction": "outgoing"
            })
        
        # Incoming edges
        for u, _, data in self.graph.in_edges(id, data=True):
            related.append({
                "entity_id": u,
                "entity_type": self.graph.nodes[u].get('entity_type'),
                "relationship": data.get('relationship'),
                "direction": "incoming"
            })
        
        return related
    
    def get_all_issues(self, severity: str = None) -> List[Dict[str, Any]]:
        """
        Get all issues
        
        Args:
            severity: Optional severity filter
            
        Returns:
            List[Dict[str, Any]]: Issues
        """
        if severity:
            return [issue for issue in self.issues if issue.get('severity') == severity]
        return self.issues
    
    def find_path(self, source_entity_type: str, source_id: str, target_entity_type: str, target_id: str) -> List[Dict[str, Any]]:
        """
        Find path between entities
        
        Args:
            source_entity_type: Source entity type
            source_id: Source entity ID
            target_entity_type: Target entity type
            target_id: Target entity ID
            
        Returns:
            List[Dict[str, Any]]: Path between entities
        """
        # If target_id is wildcard, find all entities of target_entity_type
        if target_id == "*":
            target_nodes = [
                node for node in self.graph.nodes 
                if self.graph.nodes[node].get('entity_type') == target_entity_type
            ]
            
            # Find shortest path to each target
            paths = []
            for target in target_nodes:
                try:
                    path = nx.shortest_path(self.graph, source=source_id, target=target)
                    path_info = []
                    
                    # Convert path to path info
                    for i in range(len(path) - 1):
                        u = path[i]
                        v = path[i + 1]
                        edge_data = self.graph.get_edge_data(u, v)
                        
                        path_info.append({
                            "source": u,
                            "source_type": self.graph.nodes[u].get('entity_type'),
                            "target": v,
                            "target_type": self.graph.nodes[v].get('entity_type'),
                            "relationship": edge_data.get('relationship')
                        })
                    
                    paths.append(path_info)
                except nx.NetworkXNoPath:
                    # No path found
                    pass
            
            return paths
        else:
            # Find shortest path between source and target
            try:
                path = nx.shortest_path(self.graph, source=source_id, target=target_id)
                path_info = []
                
                # Convert path to path info
                for i in range(len(path) - 1):
                    u = path[i]
                    v = path[i + 1]
                    edge_data = self.graph.get_edge_data(u, v)
                    
                    path_info.append({
                        "source": u,
                        "source_type": self.graph.nodes[u].get('entity_type'),
                        "target": v,
                        "target_type": self.graph.nodes[v].get('entity_type'),
                        "relationship": edge_data.get('relationship')
                    })
                
                return path_info
            except nx.NetworkXNoPath:
                # No path found
                return []
    
    def list_entity_types(self) -> Dict[str, int]:
        """
        List entity types and counts
        
        Returns:
            Dict[str, int]: Entity types and counts
        """
        entity_types = {}
        for node in self.graph.nodes:
            entity_type = self.graph.nodes[node].get('entity_type')
            if entity_type not in entity_types:
                entity_types[entity_type] = 0
            entity_types[entity_type] += 1
        
        return entity_types
    
    def list_entities(self, entity_type: str) -> List[str]:
        """
        List entities of a specific type
        
        Args:
            entity_type: Entity type
            
        Returns:
            List[str]: Entity IDs
        """
        return [
            node for node in self.graph.nodes 
            if self.graph.nodes[node].get('entity_type') == entity_type
        ]
    
    def list_relationship_types(self) -> Dict[str, int]:
        """
        List relationship types and counts
        
        Returns:
            Dict[str, int]: Relationship types and counts
        """
        rel_types = {}
        for u, v, data in self.graph.edges(data=True):
            rel_type = data.get('relationship')
            if rel_type not in rel_types:
                rel_types[rel_type] = 0
            rel_types[rel_type] += 1
        
        return rel_types
    
    def analyze_issues(self) -> Dict[str, Any]:
        """
        Analyze issues and provide insights
        
        Returns:
            Dict[str, Any]: Issue analysis
        """
        return {
            "root_cause": {
                "entity_id": "gnode:System:filesystem",
                "entity_type": "System",
                "issue_id": "issue-001",
                "message": "XFS filesystem corruption detected on volume test-pv",
                "confidence": 0.9
            },
            "contributing_factors": [
                {
                    "entity_id": "gnode:Drive:drive-abc-123",
                    "entity_type": "Drive",
                    "issue_id": "issue-002",
                    "message": "Multiple I/O errors detected on drive /dev/sda",
                    "confidence": 0.7
                }
            ],
            "impact": {
                "affected_entities": [
                    "gnode:Pod:default/test-pod",
                    "gnode:PV:test-pv",
                    "gnode:Volume:default/volume-123-456"
                ],
                "severity": "critical",
                "description": "The filesystem corruption is causing I/O errors in the pod, preventing normal operation."
            },
            "recommendations": [
                {
                    "action": "Run xfs_repair to fix filesystem corruption",
                    "priority": "high",
                    "details": "Use xfs_repair -L on the affected volume to attempt repair of the filesystem."
                },
                {
                    "action": "Check drive health",
                    "priority": "medium",
                    "details": "Run SMART diagnostics on the drive to check for hardware issues."
                },
                {
                    "action": "Consider replacing the drive",
                    "priority": "low",
                    "details": "If errors persist after repair, consider replacing the drive."
                }
            ]
        }

def create_mock_knowledge_graph():
    """
    Create a mock Knowledge Graph instance
    
    Returns:
        MockKnowledgeGraph: Mock Knowledge Graph instance
    """
    return MockKnowledgeGraph()
