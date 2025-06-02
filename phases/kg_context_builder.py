#!/usr/bin/env python3
"""
Knowledge Graph Context Builder for Investigation Planning

This module contains utilities for preparing Knowledge Graph context
for consumption by the Investigation Planner and LLM.
"""

import logging
from typing import Dict, List, Any, Set
from knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

class KGContextBuilder:
    """
    Prepares Knowledge Graph context for Investigation Planning
    
    Extracts relevant nodes, relationships, and issues from the Knowledge Graph
    to provide context for investigation planning.
    """
    
    def __init__(self, knowledge_graph):
        """
        Initialize the Knowledge Graph Context Builder
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
        """
        self.kg = knowledge_graph
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Validate knowledge_graph is a KnowledgeGraph instance
        if not hasattr(self.kg, 'graph'):
            self.logger.error(f"Invalid Knowledge Graph: missing 'graph' attribute")
            raise ValueError(f"Invalid Knowledge Graph: missing 'graph' attribute")
        
        if not hasattr(self.kg, 'get_all_issues'):
            self.logger.error(f"Invalid Knowledge Graph: missing 'get_all_issues' method")
            raise ValueError(f"Invalid Knowledge Graph: missing 'get_all_issues' method")
    
    def prepare_kg_context(self, pod_name: str, namespace: str, volume_path: str) -> Dict[str, Any]:
        """
        Prepare Knowledge Graph context for LLM consumption
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            Dict[str, Any]: Structured Knowledge Graph context
        """
        # Extract relevant nodes and relationships from Knowledge Graph
        target_entities = self.identify_target_entities(pod_name, namespace)
        issues_analysis = self.analyze_existing_issues()
        
        # Format Knowledge Graph data for LLM
        kg_context = {
            "nodes": [],
            "relationships": [],
            "issues": self.kg.get_all_issues(),
            "historical_experiences": []
        }
        
        # Add target pod and related entities
        if "pod" in target_entities:
            pod_id = target_entities["pod"]
            kg_context["nodes"].append(self.format_node_for_llm(pod_id))
            
            # Add PVC, PV, Drive chain
            for entity_type in ["pvc", "pv", "drive", "node"]:
                if entity_type in target_entities:
                    entity_id = target_entities[entity_type]
                    kg_context["nodes"].append(self.format_node_for_llm(entity_id))
                    
                    # Add relationships
                    if entity_type == "pvc" and "pod" in target_entities:
                        kg_context["relationships"].append({
                            "source": target_entities["pod"],
                            "target": entity_id,
                            "type": "uses"
                        })
                    elif entity_type == "pv" and "pvc" in target_entities:
                        kg_context["relationships"].append({
                            "source": target_entities["pvc"],
                            "target": entity_id,
                            "type": "bound_to"
                        })
                    elif entity_type == "drive" and "pv" in target_entities:
                        kg_context["relationships"].append({
                            "source": target_entities["pv"],
                            "target": entity_id,
                            "type": "maps_to"
                        })
                    elif entity_type == "node" and "drive" in target_entities:
                        kg_context["relationships"].append({
                            "source": target_entities["drive"],
                            "target": entity_id,
                            "type": "located_on"
                        })
        
        # Add critical and high severity issues
        critical_issues = issues_analysis["by_severity"]["critical"]
        high_issues = issues_analysis["by_severity"]["high"]
        
        # Add nodes with issues
        issue_node_ids = set()
        for issue in critical_issues + high_issues:
            node_id = issue.get('node_id', '')
            if node_id and node_id not in issue_node_ids and self.kg.graph.has_node(node_id):
                kg_context["nodes"].append(self.format_node_for_llm(node_id))
                issue_node_ids.add(node_id)
        
        # Add all historical experience data
        historical_experience_nodes = self.kg.find_nodes_by_type('HistoricalExperience')
        for node_id in historical_experience_nodes:
            historical_exp = self.format_node_for_llm(node_id)
            kg_context["historical_experiences"].append(historical_exp)
            
            # Also add to nodes list
            kg_context["nodes"].append(historical_exp)
            
            # Add relationships between historical experience and related system components
            # These relationships will be created when loading the historical experience data
            related_nodes = self.kg.find_connected_nodes(node_id)
            for related_id in related_nodes:
                kg_context["relationships"].append({
                    "source": node_id,
                    "target": related_id,
                    "type": "related_to"
                })
        
        # Add summary statistics
        kg_context["summary"] = self.kg.get_summary()
        
        return kg_context
    
    def format_node_for_llm(self, node_id: str) -> Dict[str, Any]:
        """
        Format a node for LLM consumption
        
        Args:
            node_id: Node ID
            
        Returns:
            Dict[str, Any]: Formatted node
        """
        if not self.kg.graph.has_node(node_id):
            return {"id": node_id, "type": "unknown", "attributes": {}}
        
        node_attrs = dict(self.kg.graph.nodes[node_id])
        return {
            "id": node_id,
            "type": node_attrs.get("entity_type", "unknown"),
            "attributes": {k: v for k, v in node_attrs.items() 
                          if k not in ["entity_type", "issues"]},
            "issues": node_attrs.get("issues", [])
        }
    
    def analyze_existing_issues(self) -> Dict[str, Any]:
        """
        Analyze existing issues in the Knowledge Graph
        
        Returns:
            Dict[str, Any]: Analysis of current issues by severity and type
        """
        try:
            all_issues = self.kg.get_all_issues()
            
            # Categorize issues by severity and type
            issue_analysis = {
                "by_severity": {"critical": [], "high": [], "medium": [], "low": []},
                "by_type": {},
                "total_count": len(all_issues),
                "entities_with_issues": []  # Changed from set() to list for better serialization
            }
            
            for issue in all_issues:
                severity = issue.get('severity', 'unknown')
                issue_type = issue.get('type', 'unknown')
                node_id = issue.get('node_id', '')
                
                # Group by severity
                if severity in issue_analysis["by_severity"]:
                    issue_analysis["by_severity"][severity].append(issue)
                
                # Group by type
                if issue_type not in issue_analysis["by_type"]:
                    issue_analysis["by_type"][issue_type] = []
                issue_analysis["by_type"][issue_type].append(issue)
                
                # Track entities with issues
                if node_id and node_id not in issue_analysis["entities_with_issues"]:
                    issue_analysis["entities_with_issues"].append(node_id)
            
            return issue_analysis
            
        except Exception as e:
            self.logger.warning(f"Error analyzing existing issues: {str(e)}")
            return {"by_severity": {"critical": [], "high": [], "medium": [], "low": []}, 
                   "by_type": {}, "total_count": 0, "entities_with_issues": []}
    
    def identify_target_entities(self, pod_name: str, namespace: str) -> Dict[str, str]:
        """
        Identify target entities in the Knowledge Graph for the given pod
        
        Args:
            pod_name: Name of the pod
            namespace: Namespace of the pod
            
        Returns:
            Dict[str, str]: Dictionary mapping entity types to their IDs
        """
        target_entities = {"pod": f"Pod:{namespace}/{pod_name}"}
        
        try:
            # Look for the pod in the knowledge graph
            pod_node_id = f"Pod:{namespace}/{pod_name}"
            if not self.kg.graph.has_node(pod_node_id):
                # Try alternative formats
                pod_node_id = f"Pod:{pod_name}"
                if not self.kg.graph.has_node(pod_node_id):
                    # Search by name attribute
                    for node_id, attrs in self.kg.graph.nodes(data=True):
                        if (attrs.get('entity_type') == 'Pod' and 
                            attrs.get('name') == pod_name and
                            attrs.get('namespace') == namespace):
                            pod_node_id = node_id
                            break
            
            target_entities["pod"] = pod_node_id
            
            # Trace the volume chain: Pod -> PVC -> PV -> Drive
            if self.kg.graph.has_node(pod_node_id):
                # Find connected PVCs
                for _, target, edge_data in self.kg.graph.out_edges(pod_node_id, data=True):
                    target_attrs = self.kg.graph.nodes[target]
                    if target_attrs.get('entity_type') == 'PVC':
                        target_entities["pvc"] = target
                        
                        # Find connected PV
                        for _, pv_target, _ in self.kg.graph.out_edges(target, data=True):
                            pv_attrs = self.kg.graph.nodes[pv_target]
                            if pv_attrs.get('entity_type') == 'PV':
                                target_entities["pv"] = pv_target
                                
                                # Find connected Drive
                                for _, drive_target, _ in self.kg.graph.out_edges(pv_target, data=True):
                                    drive_attrs = self.kg.graph.nodes[drive_target]
                                    if drive_attrs.get('entity_type') == 'Drive':
                                        target_entities["drive"] = drive_target
                                        
                                        # Find the Node hosting the drive
                                        for _, node_target, _ in self.kg.graph.out_edges(drive_target, data=True):
                                            node_attrs = self.kg.graph.nodes[node_target]
                                            if node_attrs.get('entity_type') == 'Node':
                                                target_entities["node"] = node_target
                                        break
                                break
                        break
            
        except Exception as e:
            self.logger.warning(f"Error identifying target entities: {str(e)}")
        
        return target_entities
