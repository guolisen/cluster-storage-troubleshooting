#!/usr/bin/env python3
"""
Knowledge Graph Context Builder for Investigation Planning

This module contains utilities for preparing Knowledge Graph context
for consumption by the Investigation Planner and LLM.
"""

import logging
from typing import Dict, List, Any, Set, Optional, Tuple
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
            
        Raises:
            ValueError: If the provided knowledge_graph is invalid
        """
        self.kg = knowledge_graph
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Validate knowledge_graph is a KnowledgeGraph instance
        self._validate_knowledge_graph()
    
    def _validate_knowledge_graph(self) -> None:
        """
        Validate that the knowledge graph has the required attributes and methods
        
        Raises:
            ValueError: If the knowledge graph is invalid
        """
        required_attributes = ['graph']
        required_methods = [
            'get_all_issues', 
            'get_entity_info', 
            'get_related_entities',
            'find_nodes_by_type', 
            'find_connected_nodes', 
            'get_summary'
        ]
        
        for attr in required_attributes:
            if not hasattr(self.kg, attr):
                error_msg = f"Invalid Knowledge Graph: missing '{attr}' attribute"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
        
        for method in required_methods:
            if not hasattr(self.kg, method):
                error_msg = f"Invalid Knowledge Graph: missing '{method}' method"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
    
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
        # Initialize the context structure
        kg_context = self._initialize_context_structure()
        
        # Extract relevant nodes and relationships from Knowledge Graph
        target_entities = self.identify_target_entities(pod_name, namespace)
        issues_analysis = self.analyze_existing_issues()
        
        # Add target pod and related entities
        self._add_target_entities_to_context(kg_context, target_entities)
        
        # Add critical and high severity issues
        self._add_critical_issues_to_context(kg_context, issues_analysis)
        
        # Add historical experience data
        self._add_historical_experience_to_context(kg_context)
        
        # Add summary statistics
        kg_context["summary"] = self.kg.get_summary()
        
        return kg_context
    
    def _initialize_context_structure(self) -> Dict[str, Any]:
        """
        Initialize the basic structure of the Knowledge Graph context
        
        Returns:
            Dict[str, Any]: Empty context structure
        """
        return {
            "nodes": [],
            "relationships": [],
            "issues": self.kg.get_all_issues(),
            "historical_experiences": []
        }
    
    def _add_target_entities_to_context(self, kg_context: Dict[str, Any], 
                                       target_entities: Dict[str, str]) -> None:
        """
        Add target entities (pod, pvc, pv, drive, node) to the context
        
        Args:
            kg_context: Context dictionary to update
            target_entities: Dictionary mapping entity types to their IDs
        """
        if "pod" not in target_entities:
            return
            
        pod_id = target_entities["pod"]
        kg_context["nodes"].append(self.format_node_for_llm(pod_id))
        
        # Add PVC, PV, Drive, Node chain
        entity_chain = [
            ("pvc", "pod", "uses"),
            ("pv", "pvc", "bound_to"),
            ("drive", "pv", "maps_to"),
            ("node", "drive", "located_on")
        ]
        
        for entity_type, source_type, relationship_type in entity_chain:
            if entity_type in target_entities and source_type in target_entities:
                entity_id = target_entities[entity_type]
                source_id = target_entities[source_type]
                
                # Add node
                kg_context["nodes"].append(self.format_node_for_llm(entity_id))
                
                # Add relationship
                kg_context["relationships"].append({
                    "source": source_id,
                    "target": entity_id,
                    "type": relationship_type
                })
    
    def _add_critical_issues_to_context(self, kg_context: Dict[str, Any], 
                                       issues_analysis: Dict[str, Any]) -> None:
        """
        Add nodes with critical and high severity issues to the context
        
        Args:
            kg_context: Context dictionary to update
            issues_analysis: Analysis of issues by severity and type
        """
        critical_issues = issues_analysis["by_severity"]["critical"]
        high_issues = issues_analysis["by_severity"]["high"]
        
        # Add nodes with issues
        issue_node_ids = set()
        for issue in critical_issues + high_issues:
            node_id = issue.get('node_id', '')
            if node_id and node_id not in issue_node_ids and self.kg.graph.has_node(node_id):
                kg_context["nodes"].append(self.format_node_for_llm(node_id))
                issue_node_ids.add(node_id)
    
    def _add_historical_experience_to_context(self, kg_context: Dict[str, Any]) -> None:
        """
        Add historical experience data to the context
        
        Args:
            kg_context: Context dictionary to update
        """
        historical_experience_nodes = self.kg.find_nodes_by_type('HistoricalExperience')
        
        for node_id in historical_experience_nodes:
            historical_exp = self.format_node_for_llm(node_id)
            
            # Add to historical experiences list
            kg_context["historical_experiences"].append(historical_exp)
            
            # Also add to nodes list
            kg_context["nodes"].append(historical_exp)
            
            # Add relationships between historical experience and related system components
            self._add_historical_experience_relationships(kg_context, node_id)
    
    def _add_historical_experience_relationships(self, kg_context: Dict[str, Any], 
                                               experience_node_id: str) -> None:
        """
        Add relationships between historical experience and related system components
        
        Args:
            kg_context: Context dictionary to update
            experience_node_id: ID of the historical experience node
        """
        related_nodes = self.kg.find_connected_nodes(experience_node_id)
        
        for related_id in related_nodes:
            kg_context["relationships"].append({
                "source": experience_node_id,
                "target": related_id,
                "type": "related_to"
            })
    
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
            
            # Initialize issue analysis structure
            issue_analysis = self._initialize_issue_analysis()
            
            # Categorize issues
            for issue in all_issues:
                self._categorize_issue(issue, issue_analysis)
            
            return issue_analysis
            
        except Exception as e:
            self.logger.warning(f"Error analyzing existing issues: {str(e)}")
            return self._initialize_issue_analysis()
    
    def _initialize_issue_analysis(self) -> Dict[str, Any]:
        """
        Initialize the issue analysis structure
        
        Returns:
            Dict[str, Any]: Empty issue analysis structure
        """
        return {
            "by_severity": {"critical": [], "high": [], "medium": [], "low": []},
            "by_type": {},
            "total_count": 0,
            "entities_with_issues": []
        }
    
    def _categorize_issue(self, issue: Dict[str, Any], issue_analysis: Dict[str, Any]) -> None:
        """
        Categorize an issue by severity and type
        
        Args:
            issue: Issue to categorize
            issue_analysis: Issue analysis dictionary to update
        """
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
        
        # Update total count
        issue_analysis["total_count"] = sum(len(issues) for issues in issue_analysis["by_severity"].values())
    
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
            # Find the pod node
            pod_node_id = self._find_pod_node(pod_name, namespace)
            if not pod_node_id:
                return target_entities
                
            target_entities["pod"] = pod_node_id
            
            # Trace the volume chain: Pod -> PVC -> PV -> Drive -> Node
            self._trace_volume_chain(pod_node_id, target_entities)
            
        except Exception as e:
            self.logger.warning(f"Error identifying target entities: {str(e)}")
        
        return target_entities
    
    def _find_pod_node(self, pod_name: str, namespace: str) -> Optional[str]:
        """
        Find the pod node in the knowledge graph
        
        Args:
            pod_name: Name of the pod
            namespace: Namespace of the pod
            
        Returns:
            Optional[str]: Pod node ID if found, None otherwise
        """
        # Try standard format
        pod_node_id = f"Pod:{namespace}/{pod_name}"
        if self.kg.graph.has_node(pod_node_id):
            return pod_node_id
        
        # Try alternative format
        pod_node_id = f"Pod:{pod_name}"
        if self.kg.graph.has_node(pod_node_id):
            return pod_node_id
        
        # Search by name and namespace attributes
        for node_id, attrs in self.kg.graph.nodes(data=True):
            if (attrs.get('entity_type') == 'Pod' and 
                attrs.get('name') == pod_name and
                attrs.get('namespace') == namespace):
                return node_id
        
        return None
    
    def _trace_volume_chain(self, pod_node_id: str, target_entities: Dict[str, str]) -> None:
        """
        Trace the volume chain from Pod to Node
        
        Args:
            pod_node_id: ID of the pod node
            target_entities: Dictionary to update with found entities
        """
        # Find PVC connected to Pod
        pvc_node_id = self._find_connected_entity(pod_node_id, 'PVC')
        if pvc_node_id:
            target_entities["pvc"] = pvc_node_id
            
            # Find PV connected to PVC
            pv_node_id = self._find_connected_entity(pvc_node_id, 'PV')
            if pv_node_id:
                target_entities["pv"] = pv_node_id
                
                # Find Drive connected to PV
                drive_node_id = self._find_connected_entity(pv_node_id, 'Drive')
                if drive_node_id:
                    target_entities["drive"] = drive_node_id
                    
                    # Find Node connected to Drive
                    node_node_id = self._find_connected_entity(drive_node_id, 'Node')
                    if node_node_id:
                        target_entities["node"] = node_node_id
    
    def _find_connected_entity(self, source_node_id: str, entity_type: str) -> Optional[str]:
        """
        Find a connected entity of a specific type
        
        Args:
            source_node_id: ID of the source node
            entity_type: Type of entity to find
            
        Returns:
            Optional[str]: Entity node ID if found, None otherwise
        """
        for _, target, _ in self.kg.graph.out_edges(source_node_id, data=True):
            target_attrs = self.kg.graph.nodes[target]
            if target_attrs.get('entity_type') == entity_type:
                return target
        
        return None
