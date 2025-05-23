#!/usr/bin/env python3
"""
Knowledge Graph for Kubernetes Volume Troubleshooting

This module creates and maintains a graph of relationships between storage issues
to help identify root causes and relationships between different symptoms.
"""

import json
import logging
import yaml
from typing import Dict, List, Any, Optional, Set, Tuple

class KnowledgeGraph:
    """Models relationships between storage issues to identify root causes"""
    
    def __init__(self):
        """Initialize the knowledge graph"""
        self.nodes = {}  # Issue nodes by ID
        self.edges = []  # Relationships between issues
        self.root_causes = []  # List of identified root causes
        
        # Load predefined relationships and patterns
        self._load_patterns()
    
    def _load_patterns(self):
        """
        Load predefined issue relationships and root cause patterns
        
        These define known causal relationships between different types of issues,
        such as "disk errors often cause filesystem corruption" or
        "high inode usage can cause out of space errors even with free space".
        """
        self.patterns = {
            # Storage layer patterns (usually root causes)
            "storage_patterns": [
                {
                    "components": ["smart"],
                    "indicators": ["Bad sectors", "Pending bad sectors", "Uncorrectable sectors"],
                    "implies": ["linux.filesystem", "kubernetes.pod_logs"],
                    "root_cause": "Hardware disk failure detected by SMART - bad sectors",
                    "fix_plan": "1. Back up all data from the affected disk\n2. Replace the physical disk\n3. Restore data to new disk"
                },
                {
                    "components": ["smart"],
                    "indicators": ["SMART health check failed", "Device failed SMART self-test"],
                    "implies": ["linux.filesystem", "kubernetes.pod_logs"],
                    "root_cause": "Hardware disk failure detected by SMART - overall health check failure",
                    "fix_plan": "1. Back up all data from the affected disk\n2. Replace the physical disk\n3. Restore data to new disk"
                },
                {
                    "components": ["io_performance"],
                    "indicators": ["I/O test failed", "Low I/O performance"],
                    "implies": ["kubernetes.pod_logs"],
                    "root_cause": "Disk performance degradation",
                    "fix_plan": "1. Check for disk contention from other workloads\n2. Consider moving the workload to a different node or disk\n3. If persistent, replace the disk with a higher performance model"
                },
                {
                    "components": ["nvme"],
                    "indicators": ["NVMe device", "error logs"],
                    "implies": ["linux.filesystem", "kubernetes.pod_logs"],
                    "root_cause": "NVMe device error logs indicate hardware issues",
                    "fix_plan": "1. Review NVMe error logs to identify specific hardware issue\n2. Update NVMe firmware if available\n3. Replace the NVMe device if errors persist"
                },
            ],
            
            # Linux layer patterns (often intermediate causes)
            "linux_patterns": [
                {
                    "components": ["kernel_logs"],
                    "indicators": ["Disk errors detected"],
                    "implies": ["kubernetes.pod_logs"],
                    "root_cause": "Kernel-reported disk I/O errors",
                    "fix_plan": "1. Check disk health with smartctl\n2. Check for loose cabling or connection issues\n3. Replace disk if hardware issues confirmed"
                },
                {
                    "components": ["filesystem"],
                    "indicators": ["XFS filesystem errors", "corrupt"],
                    "implies": ["kubernetes.pod_logs"],
                    "root_cause": "Filesystem corruption",
                    "fix_plan": "1. Backup data if possible\n2. Unmount filesystem\n3. Run xfs_repair (with approval)\n4. Check disk hardware if corruption recurs"
                },
                {
                    "components": ["disk_space"],
                    "indicators": ["over 90% full"],
                    "implies": ["kubernetes.pod_logs"],
                    "root_cause": "Filesystem is nearly full",
                    "fix_plan": "1. Delete unnecessary files\n2. Move data to a larger volume\n3. Extend volume size if possible\n4. Implement disk usage monitoring"
                },
                {
                    "components": ["mounts"],
                    "indicators": ["Read-only filesystem"],
                    "implies": ["kubernetes.pod_logs"],
                    "root_cause": "Filesystem mounted read-only due to errors",
                    "fix_plan": "1. Check dmesg for filesystem errors\n2. Remount filesystem in read-write mode if no corruption\n3. Run filesystem check if corruption detected"
                },
                {
                    "components": ["inodes"],
                    "indicators": ["running out of inodes"],
                    "implies": ["kubernetes.pod_logs"],
                    "root_cause": "Filesystem inode exhaustion",
                    "fix_plan": "1. Delete small files\n2. If many small files are needed, recreate filesystem with more inodes\n3. Implement inode usage monitoring"
                },
            ],
            
            # Kubernetes layer patterns (usually symptoms)
            "kubernetes_patterns": [
                {
                    "components": ["csi_drive"],
                    "indicators": ["BAD health", "OFFLINE"],
                    "implies": ["linux.kernel_logs", "storage.smart"],
                    "root_cause": "CSI Baremetal drive reporting bad health",
                    "fix_plan": "1. Cordon the node to prevent new pods\n2. Migrate workloads to other nodes\n3. Replace the failing drive\n4. Uncordon node after replacement"
                },
                {
                    "components": ["csi_lvg"],
                    "indicators": ["BAD health"],
                    "implies": ["kubernetes.csi_drive"],
                    "root_cause": "CSI Baremetal LogicalVolumeGroup reporting bad health",
                    "fix_plan": "1. Check drive health for drives in the LVG\n2. If LVG is corrupted but drives are healthy, recreate LVG\n3. Replace any failing drives"
                },
                {
                    "components": ["csi_driver"],
                    "indicators": ["unhealthy state", "CrashLoopBackOff", "Error"],
                    "implies": ["kubernetes.pod_logs"],
                    "root_cause": "CSI Baremetal driver pods in unhealthy state",
                    "fix_plan": "1. Check CSI driver logs\n2. Restart CSI driver pods if allowed\n3. Check for misconfigurations\n4. Upgrade CSI driver if needed"
                },
                {
                    "components": ["node"],
                    "indicators": ["DiskPressure"],
                    "implies": ["linux.disk_space"],
                    "root_cause": "Node reporting DiskPressure condition",
                    "fix_plan": "1. Free disk space on node\n2. Check if kubelet logs directory is too large\n3. Consider adding storage to the node\n4. Implement pod resource limits"
                },
                {
                    "components": ["pvc"],
                    "indicators": ["not in Bound state"],
                    "implies": [],
                    "root_cause": "PVC binding failure",
                    "fix_plan": "1. Check PVC specification\n2. Verify storage class exists\n3. Check for available storage in the cluster\n4. Look for errors in volume provisioner"
                },
                {
                    "components": ["pv"],
                    "indicators": ["path mismatch"],
                    "implies": ["kubernetes.pod_logs"],
                    "root_cause": "Volume path mismatch between pod and PV",
                    "fix_plan": "1. Update PV path to match the correct path\n2. If using local volume, ensure path exists on the node\n3. Recreate resources with correct paths"
                },
                {
                    "components": ["pod_events"],
                    "indicators": ["FailedMount", "FailedAttachVolume"],
                    "implies": [],
                    "root_cause": "Volume mount failures in pod",
                    "fix_plan": "1. Check node for the volume path\n2. Verify filesystem is properly formatted\n3. Check PV/PVC configuration\n4. Look for errors in CSI driver logs"
                },
            ]
        }
    
    def add_issue(self, issue: Dict[str, Any]):
        """
        Add an issue node to the graph
        
        Args:
            issue: Issue data as a dictionary
        """
        issue_id = issue["id"]
        self.nodes[issue_id] = issue
        logging.info(f"Added issue node {issue_id} to knowledge graph")
    
    def add_relationship(self, source_id: str, target_id: str, relationship_type: str, confidence: float = 1.0):
        """
        Add a relationship between issues
        
        Args:
            source_id: ID of the source issue
            target_id: ID of the target issue
            relationship_type: Type of relationship (e.g., "causes", "related_to")
            confidence: Confidence score for this relationship (0.0 to 1.0)
        """
        # Skip if either node doesn't exist
        if source_id not in self.nodes or target_id not in self.nodes:
            logging.warning(f"Skipping relationship {source_id} -> {target_id}: Node(s) not found")
            return
        
        edge = {
            "source": source_id,
            "target": target_id,
            "type": relationship_type,
            "confidence": confidence
        }
        
        self.edges.append(edge)
        logging.info(f"Added relationship {source_id} -{relationship_type}-> {target_id}")
    
    def infer_relationships(self):
        """
        Infer relationships between issues based on predefined patterns
        
        This applies domain knowledge to connect related issues, such as:
        - Hardware issues causing filesystem errors
        - Filesystem errors causing pod mount failures
        - Node pressure causing pod evictions
        """
        for issue_id, issue in self.nodes.items():
            layer = issue.get("layer")
            component = issue.get("component")
            message = issue.get("message", "")
            
            # Apply patterns based on the layer
            if layer == "storage":
                patterns = self.patterns.get("storage_patterns", [])
            elif layer == "linux":
                patterns = self.patterns.get("linux_patterns", [])
            elif layer == "kubernetes":
                patterns = self.patterns.get("kubernetes_patterns", [])
            else:
                continue
            
            # Check each pattern
            for pattern in patterns:
                # Skip if component doesn't match
                if component not in pattern.get("components", []):
                    continue
                
                # Check if any indicator is in the message
                match = False
                for indicator in pattern.get("indicators", []):
                    if indicator in message:
                        match = True
                        break
                
                if not match:
                    continue
                
                # Pattern matched, create relationships
                for implied in pattern.get("implies", []):
                    # Look for issues that match the implied layer.component
                    implied_layer, implied_component = implied.split(".")
                    
                    for other_id, other in self.nodes.items():
                        if other_id == issue_id:  # Skip self
                            continue
                        
                        if (other.get("layer") == implied_layer and 
                            other.get("component") == implied_component):
                            # Create relationship
                            if layer == "storage":  # Storage issues cause other issues
                                self.add_relationship(issue_id, other_id, "causes", 0.8)
                            elif layer == "linux" and implied_layer == "kubernetes":
                                # Linux issues cause Kubernetes issues
                                self.add_relationship(issue_id, other_id, "causes", 0.7)
                            elif layer == "kubernetes" and implied_layer in ["linux", "storage"]:
                                # Kubernetes issues are symptoms of Linux/Storage issues
                                self.add_relationship(other_id, issue_id, "causes", 0.6)
                            else:
                                # Generic relationship
                                self.add_relationship(issue_id, other_id, "related_to", 0.5)
                
                # Add potential root cause
                if "root_cause" in pattern and "fix_plan" in pattern:
                    self.root_causes.append({
                        "issue_id": issue_id,
                        "pattern": pattern,
                        "confidence": 0.7,  # Base confidence
                        "root_cause": pattern["root_cause"],
                        "fix_plan": pattern["fix_plan"]
                    })
    
    def find_related_issues(self, issue_id: str) -> List[Dict[str, Any]]:
        """
        Find all issues directly related to a given issue
        
        Args:
            issue_id: ID of the issue to find relations for
            
        Returns:
            List[Dict[str, Any]]: List of related issues with relationship details
        """
        if issue_id not in self.nodes:
            return []
        
        related = []
        
        # Find outgoing relationships
        for edge in self.edges:
            if edge["source"] == issue_id:
                related.append({
                    "issue": self.nodes[edge["target"]],
                    "relationship": edge["type"],
                    "direction": "outgoing",
                    "confidence": edge["confidence"]
                })
        
        # Find incoming relationships
        for edge in self.edges:
            if edge["target"] == issue_id:
                related.append({
                    "issue": self.nodes[edge["source"]],
                    "relationship": edge["type"],
                    "direction": "incoming",
                    "confidence": edge["confidence"]
                })
        
        return related
    
    def identify_root_causes(self, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Identify the most likely root causes for the issues
        
        This uses graph analysis to find the most probable root causes:
        1. Issues with many outgoing "causes" edges are likely root causes
        2. Storage layer issues are more likely to be root causes than symptoms
        3. Known patterns from domain knowledge are matched
        
        Args:
            threshold: Confidence threshold for including a root cause
            
        Returns:
            List[Dict[str, Any]]: List of root causes sorted by confidence
        """
        # First check predefined root causes from patterns
        root_causes = self.root_causes.copy()
        
        # Add root causes based on graph structure
        # Count outgoing "causes" edges for each node
        causes_count = {}
        for edge in self.edges:
            if edge["type"] == "causes":
                source = edge["source"]
                causes_count[source] = causes_count.get(source, 0) + 1
        
        # Nodes with many outgoing "causes" edges are likely root causes
        for node_id, count in causes_count.items():
            node = self.nodes[node_id]
            
            # Skip if already in root_causes
            if any(rc["issue_id"] == node_id for rc in root_causes):
                continue
            
            # Calculate confidence based on count and layer
            confidence = min(0.3 + (count * 0.1), 0.9)  # More causation = higher confidence
            
            # Storage layer issues are more likely to be root causes
            if node["layer"] == "storage":
                confidence += 0.1
            
            # Add if above threshold
            if confidence >= threshold:
                root_causes.append({
                    "issue_id": node_id,
                    "issue": node,
                    "confidence": confidence,
                    "root_cause": node["message"],
                    "fix_plan": f"1. Investigate {node['layer']}.{node['component']} issue\n2. Check logs for details\n3. Consider restarting affected component"
                })
        
        # Sort by confidence
        root_causes.sort(key=lambda x: x["confidence"], reverse=True)
        
        return root_causes
    
    def identify_primary_root_cause(self) -> Dict[str, Any]:
        """
        Identify the primary root cause from all potential root causes
        
        Returns:
            Dict[str, Any]: Primary root cause information
        """
        root_causes = self.identify_root_causes()
        
        if not root_causes:
            return {
                "root_cause": "Unknown - insufficient information to determine root cause",
                "confidence": 0.0,
                "fix_plan": "1. Collect more diagnostic information\n2. Check all layers (K8s, Linux, Storage)"
            }
        
        # Return the highest confidence root cause
        primary = root_causes[0]
        return {
            "root_cause": primary.get("root_cause"),
            "confidence": primary.get("confidence"),
            "fix_plan": primary.get("fix_plan"),
            "issue_id": primary.get("issue_id")
        }
    
    def to_json(self) -> str:
        """
        Convert graph to JSON for LLM consumption
        
        Returns:
            str: JSON representation of the knowledge graph
        """
        graph_data = {
            "nodes": self.nodes,
            "edges": self.edges,
            "root_causes": self.identify_root_causes(),
            "primary_root_cause": self.identify_primary_root_cause()
        }
        
        return json.dumps(graph_data, indent=2)


def create_knowledge_graph(issues: List[Dict[str, Any]]) -> KnowledgeGraph:
    """
    Convenience function to create a knowledge graph from issues
    
    Args:
        issues: List of issue dictionaries
        
    Returns:
        KnowledgeGraph: Populated knowledge graph
    """
    graph = KnowledgeGraph()
    
    # Add all issues to the graph
    for issue in issues:
        graph.add_issue(issue)
    
    # Infer relationships between issues
    graph.infer_relationships()
    
    return graph


if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python knowledge_graph.py <issues_json_file>")
        sys.exit(1)
    
    issues_file = sys.argv[1]
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("troubleshoot.log"),
            logging.StreamHandler()
        ]
    )
    
    # Load issues from file
    try:
        with open(issues_file, 'r') as f:
            issues = json.load(f)
    except Exception as e:
        print(f"Failed to load issues: {e}")
        sys.exit(1)
    
    # Create knowledge graph
    graph = create_knowledge_graph(issues)
    
    # Print root causes
    root_causes = graph.identify_root_causes()
    print(f"Found {len(root_causes)} potential root causes:")
    for i, rc in enumerate(root_causes, 1):
        print(f"{i}. {rc['root_cause']} (confidence: {rc['confidence']:.2f})")
    
    # Print primary root cause
    primary = graph.identify_primary_root_cause()
    print(f"\nPrimary root cause: {primary['root_cause']} (confidence: {primary['confidence']:.2f})")
    print(f"Fix plan:\n{primary['fix_plan']}")
