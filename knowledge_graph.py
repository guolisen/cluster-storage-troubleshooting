#!/usr/bin/env python3
"""
Knowledge Graph Module for Kubernetes Volume Troubleshooting

This module builds and analyzes relationships between storage-related issues
to provide comprehensive root cause analysis and fix planning.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum


class IssueType(Enum):
    """Types of issues that can be tracked in the knowledge graph"""
    POD_VOLUME_IO = "pod_volume_io"
    NODE_DISK_HEALTH = "node_disk_health"
    CSI_DRIVER = "csi_driver"
    PVC_BINDING = "pvc_binding"
    PV_ATTACHMENT = "pv_attachment"
    STORAGE_CLASS = "storage_class"
    DRIVE_HEALTH = "drive_health"
    CAPACITY_SHORTAGE = "capacity_shortage"
    FILESYSTEM_CORRUPTION = "filesystem_corruption"
    NETWORK_CONNECTIVITY = "network_connectivity"
    PERMISSION_ISSUE = "permission_issue"
    RESOURCE_QUOTA = "resource_quota"


class IssueSeverity(Enum):
    """Severity levels for issues"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RelationshipType(Enum):
    """Types of relationships between issues"""
    CAUSED_BY = "caused_by"
    DEPENDS_ON = "depends_on"
    AFFECTS = "affects"
    RELATED_TO = "related_to"
    BLOCKS = "blocks"
    CASCADES_TO = "cascades_to"


@dataclass
class IssueNode:
    """Represents a single issue in the knowledge graph"""
    id: str
    issue_type: IssueType
    severity: IssueSeverity
    title: str
    description: str
    resource_name: str
    namespace: Optional[str] = None
    node_name: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    symptoms: List[str] = field(default_factory=list)
    diagnostic_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None
    resolved: bool = False
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class Relationship:
    """Represents a relationship between two issues"""
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    confidence: float  # 0.0 to 1.0
    description: str
    evidence: List[str] = field(default_factory=list)


class IssueKnowledgeGraph:
    """Knowledge graph for tracking and analyzing storage-related issues"""
    
    def __init__(self):
        self.nodes: Dict[str, IssueNode] = {}
        self.relationships: List[Relationship] = []
        self.primary_issue_id: Optional[str] = None
        
    def add_issue(self, issue: IssueNode, is_primary: bool = False) -> None:
        """Add an issue to the knowledge graph"""
        self.nodes[issue.id] = issue
        if is_primary:
            self.primary_issue_id = issue.id
        logging.info(f"Added issue to knowledge graph: {issue.id} - {issue.title}")
    
    def add_relationship(self, relationship: Relationship) -> None:
        """Add a relationship between two issues"""
        if relationship.source_id not in self.nodes or relationship.target_id not in self.nodes:
            logging.warning(f"Cannot add relationship: one or both nodes not found")
            return
        
        self.relationships.append(relationship)
        logging.info(f"Added relationship: {relationship.source_id} {relationship.relationship_type.value} {relationship.target_id}")
    
    def get_related_issues(self, issue_id: str, max_depth: int = 2) -> Set[str]:
        """Get all issues related to a given issue up to max_depth"""
        related = set()
        current_level = {issue_id}
        
        for depth in range(max_depth):
            next_level = set()
            for current_id in current_level:
                for rel in self.relationships:
                    if rel.source_id == current_id and rel.target_id not in related:
                        next_level.add(rel.target_id)
                        related.add(rel.target_id)
                    elif rel.target_id == current_id and rel.source_id not in related:
                        next_level.add(rel.source_id)
                        related.add(rel.source_id)
            
            current_level = next_level
            if not current_level:
                break
        
        return related
    
    def find_root_causes(self) -> List[IssueNode]:
        """Identify potential root causes by analyzing relationships"""
        root_candidates = []
        
        # Find nodes that have outgoing "CAUSED_BY" relationships but few incoming ones
        for node_id, node in self.nodes.items():
            incoming_causes = sum(1 for rel in self.relationships 
                                if rel.target_id == node_id and rel.relationship_type == RelationshipType.CAUSED_BY)
            outgoing_causes = sum(1 for rel in self.relationships 
                                if rel.source_id == node_id and rel.relationship_type == RelationshipType.AFFECTS)
            
            # Root cause candidates: low incoming causes, high outgoing effects
            if incoming_causes <= 1 and outgoing_causes >= 1:
                root_candidates.append(node)
        
        # Sort by severity and impact
        root_candidates.sort(key=lambda x: (x.severity.value, len(self.get_related_issues(x.id))), reverse=True)
        
        return root_candidates
    
    def get_fix_priority_order(self) -> List[IssueNode]:
        """Get issues ordered by fix priority based on dependencies"""
        # Topological sort based on dependencies
        visited = set()
        temp_visited = set()
        result = []
        
        def visit(node_id: str):
            if node_id in temp_visited:
                return  # Cycle detected, skip
            if node_id in visited:
                return
            
            temp_visited.add(node_id)
            
            # Visit dependencies first
            for rel in self.relationships:
                if (rel.target_id == node_id and 
                    rel.relationship_type in [RelationshipType.DEPENDS_ON, RelationshipType.CAUSED_BY]):
                    visit(rel.source_id)
            
            temp_visited.remove(node_id)
            visited.add(node_id)
            if node_id in self.nodes:
                result.append(self.nodes[node_id])
        
        # Start with critical issues
        critical_issues = [node for node in self.nodes.values() 
                         if node.severity == IssueSeverity.CRITICAL]
        
        for issue in critical_issues:
            visit(issue.id)
        
        # Then process remaining issues
        for node_id in self.nodes:
            visit(node_id)
        
        return result
    
    def generate_comprehensive_analysis(self) -> Dict[str, Any]:
        """Generate comprehensive analysis of all issues and relationships"""
        root_causes = self.find_root_causes()
        fix_order = self.get_fix_priority_order()
        
        # Calculate impact metrics
        total_issues = len(self.nodes)
        critical_issues = len([n for n in self.nodes.values() if n.severity == IssueSeverity.CRITICAL])
        high_issues = len([n for n in self.nodes.values() if n.severity == IssueSeverity.HIGH])
        
        # Identify cascading failures
        cascading_paths = self._find_cascading_paths()
        
        analysis = {
            "summary": {
                "total_issues": total_issues,
                "critical_issues": critical_issues,
                "high_priority_issues": high_issues,
                "primary_issue": self.nodes.get(self.primary_issue_id) if self.primary_issue_id else None
            },
            "root_causes": [self._node_to_dict(node) for node in root_causes],
            "cascading_failures": cascading_paths,
            "fix_priority_order": [self._node_to_dict(node) for node in fix_order],
            "issue_clusters": self._identify_issue_clusters(),
            "comprehensive_root_cause": self._generate_comprehensive_root_cause(root_causes),
            "comprehensive_fix_plan": self._generate_comprehensive_fix_plan(fix_order)
        }
        
        return analysis
    
    def _find_cascading_paths(self) -> List[Dict[str, Any]]:
        """Find cascading failure paths in the graph"""
        cascading_paths = []
        
        for rel in self.relationships:
            if rel.relationship_type == RelationshipType.CASCADES_TO:
                path = self._trace_cascade_path(rel.source_id, set())
                if len(path) > 1:
                    cascading_paths.append({
                        "source": self.nodes[rel.source_id].title,
                        "path": [self.nodes[node_id].title for node_id in path],
                        "impact_count": len(path) - 1
                    })
        
        return cascading_paths
    
    def _trace_cascade_path(self, start_id: str, visited: Set[str]) -> List[str]:
        """Trace a cascading failure path from a starting point"""
        if start_id in visited:
            return [start_id]
        
        visited.add(start_id)
        path = [start_id]
        
        for rel in self.relationships:
            if (rel.source_id == start_id and 
                rel.relationship_type in [RelationshipType.CASCADES_TO, RelationshipType.AFFECTS]):
                sub_path = self._trace_cascade_path(rel.target_id, visited.copy())
                if len(sub_path) > 1:
                    path.extend(sub_path[1:])  # Avoid duplicate starting node
                    break
        
        return path
    
    def _identify_issue_clusters(self) -> List[Dict[str, Any]]:
        """Identify clusters of related issues"""
        clusters = []
        visited = set()
        
        for node_id in self.nodes:
            if node_id not in visited:
                cluster_nodes = self._get_connected_component(node_id, visited)
                if len(cluster_nodes) > 1:
                    clusters.append({
                        "cluster_id": f"cluster_{len(clusters)}",
                        "issues": [self.nodes[nid].title for nid in cluster_nodes],
                        "dominant_type": self._get_dominant_issue_type(cluster_nodes),
                        "severity": max(self.nodes[nid].severity for nid in cluster_nodes)
                    })
        
        return clusters
    
    def _get_connected_component(self, start_id: str, global_visited: Set[str]) -> Set[str]:
        """Get all nodes in the same connected component"""
        component = set()
        stack = [start_id]
        
        while stack:
            current = stack.pop()
            if current in global_visited:
                continue
            
            global_visited.add(current)
            component.add(current)
            
            # Add connected nodes
            for rel in self.relationships:
                if rel.source_id == current and rel.target_id not in global_visited:
                    stack.append(rel.target_id)
                elif rel.target_id == current and rel.source_id not in global_visited:
                    stack.append(rel.source_id)
        
        return component
    
    def _get_dominant_issue_type(self, node_ids: Set[str]) -> str:
        """Get the most common issue type in a cluster"""
        type_counts = {}
        for node_id in node_ids:
            issue_type = self.nodes[node_id].issue_type.value
            type_counts[issue_type] = type_counts.get(issue_type, 0) + 1
        
        return max(type_counts, key=type_counts.get) if type_counts else "unknown"
    
    def _generate_comprehensive_root_cause(self, root_causes: List[IssueNode]) -> str:
        """Generate comprehensive root cause analysis"""
        if not root_causes:
            return "Unable to determine root cause from available data"
        
        if len(root_causes) == 1:
            primary = root_causes[0]
            return f"Primary root cause: {primary.title}. {primary.description}"
        
        # Multiple root causes
        analysis = "Multiple interconnected root causes identified:\n"
        for i, cause in enumerate(root_causes[:3], 1):  # Top 3
            related_count = len(self.get_related_issues(cause.id))
            analysis += f"{i}. {cause.title} (affects {related_count} related issues)\n"
        
        return analysis
    
    def _generate_comprehensive_fix_plan(self, fix_order: List[IssueNode]) -> str:
        """Generate comprehensive fix plan based on priority order"""
        if not fix_order:
            return "No specific fix plan could be generated"
        
        plan = "Comprehensive Fix Plan (in priority order):\n\n"
        
        for i, issue in enumerate(fix_order, 1):
            plan += f"Step {i}: {issue.title}\n"
            plan += f"  Priority: {issue.severity.value.upper()}\n"
            plan += f"  Action: {issue.description}\n"
            
            if issue.details.get('recommended_action'):
                plan += f"  Recommendation: {issue.details['recommended_action']}\n"
            
            plan += "\n"
        
        return plan
    
    def _node_to_dict(self, node: IssueNode) -> Dict[str, Any]:
        """Convert an IssueNode to a dictionary representation"""
        return {
            "id": node.id,
            "type": node.issue_type.value,
            "severity": node.severity.value,
            "title": node.title,
            "description": node.description,
            "resource": node.resource_name,
            "namespace": node.namespace,
            "node": node.node_name,
            "symptoms": node.symptoms,
            "resolved": node.resolved
        }
    
    def export_graph(self) -> Dict[str, Any]:
        """Export the entire knowledge graph to a serializable format"""
        return {
            "nodes": [self._node_to_dict(node) for node in self.nodes.values()],
            "relationships": [
                {
                    "source": rel.source_id,
                    "target": rel.target_id,
                    "type": rel.relationship_type.value,
                    "confidence": rel.confidence,
                    "description": rel.description,
                    "evidence": rel.evidence
                }
                for rel in self.relationships
            ],
            "primary_issue": self.primary_issue_id
        }
    
    def visualize_graph(self) -> str:
        """Generate a text-based visualization of the graph"""
        output = "=== KNOWLEDGE GRAPH VISUALIZATION ===\n\n"
        
        # Show primary issue
        if self.primary_issue_id and self.primary_issue_id in self.nodes:
            primary = self.nodes[self.primary_issue_id]
            output += f"PRIMARY ISSUE: {primary.title} ({primary.severity.value})\n"
            output += f"  {primary.description}\n\n"
        
        # Show relationships
        output += "ISSUE RELATIONSHIPS:\n"
        for rel in self.relationships:
            source = self.nodes.get(rel.source_id)
            target = self.nodes.get(rel.target_id)
            if source and target:
                output += f"  {source.title} --[{rel.relationship_type.value}]--> {target.title}\n"
        
        output += "\n"
        
        # Show all issues grouped by severity
        for severity in IssueSeverity:
            issues = [node for node in self.nodes.values() if node.severity == severity]
            if issues:
                output += f"{severity.value.upper()} ISSUES:\n"
                for issue in issues:
                    output += f"  - {issue.title} ({issue.resource_name})\n"
                output += "\n"
        
        return output


def create_issue_from_diagnostic_data(diagnostic_data: Dict[str, Any]) -> IssueNode:
    """Create an IssueNode from diagnostic data"""
    issue_id = diagnostic_data.get('id', f"issue_{hash(str(diagnostic_data))}")
    
    # Determine issue type based on diagnostic data
    issue_type = IssueType.POD_VOLUME_IO  # Default
    if 'drive' in diagnostic_data.get('resource_type', '').lower():
        issue_type = IssueType.DRIVE_HEALTH
    elif 'node' in diagnostic_data.get('resource_type', '').lower():
        issue_type = IssueType.NODE_DISK_HEALTH
    elif 'pvc' in diagnostic_data.get('resource_type', '').lower():
        issue_type = IssueType.PVC_BINDING
    elif 'csi' in diagnostic_data.get('resource_type', '').lower():
        issue_type = IssueType.CSI_DRIVER
    
    # Determine severity based on symptoms
    severity = IssueSeverity.MEDIUM  # Default
    symptoms = diagnostic_data.get('symptoms', [])
    if any('critical' in str(symptom).lower() or 'failed' in str(symptom).lower() for symptom in symptoms):
        severity = IssueSeverity.CRITICAL
    elif any('error' in str(symptom).lower() for symptom in symptoms):
        severity = IssueSeverity.HIGH
    
    return IssueNode(
        id=issue_id,
        issue_type=issue_type,
        severity=severity,
        title=diagnostic_data.get('title', 'Unknown Issue'),
        description=diagnostic_data.get('description', ''),
        resource_name=diagnostic_data.get('resource_name', ''),
        namespace=diagnostic_data.get('namespace'),
        node_name=diagnostic_data.get('node_name'),
        details=diagnostic_data.get('details', {}),
        symptoms=symptoms,
        diagnostic_data=diagnostic_data,
        timestamp=diagnostic_data.get('timestamp')
    )


def build_relationships_from_kubernetes_topology(graph: IssueKnowledgeGraph, 
                                                topology_data: Dict[str, Any]) -> None:
    """Build relationships based on Kubernetes resource topology"""
    
    # Example: Pod -> PVC -> PV -> Node relationships
    for pod_issue_id, pod_data in topology_data.get('pods', {}).items():
        if pod_issue_id not in graph.nodes:
            continue
            
        # Pod depends on PVC
        for pvc_name in pod_data.get('pvcs', []):
            pvc_issue_id = f"pvc_{pvc_name}"
            if pvc_issue_id in graph.nodes:
                graph.add_relationship(Relationship(
                    source_id=pod_issue_id,
                    target_id=pvc_issue_id,
                    relationship_type=RelationshipType.DEPENDS_ON,
                    confidence=0.9,
                    description=f"Pod {pod_data['name']} depends on PVC {pvc_name}"
                ))
        
        # Pod runs on Node
        if pod_data.get('node_name'):
            node_issue_id = f"node_{pod_data['node_name']}"
            if node_issue_id in graph.nodes:
                graph.add_relationship(Relationship(
                    source_id=pod_issue_id,
                    target_id=node_issue_id,
                    relationship_type=RelationshipType.DEPENDS_ON,
                    confidence=0.8,
                    description=f"Pod {pod_data['name']} runs on node {pod_data['node_name']}"
                ))
