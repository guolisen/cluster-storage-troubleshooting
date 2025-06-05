#!/usr/bin/env python3
"""
Knowledge Graph tools for Kubernetes volume troubleshooting.

This module contains tools for interacting with the Knowledge Graph,
including entity queries, relationship analysis, and issue management.
"""

import json
import logging
from typing import Any, Optional # Added Optional
from langchain_core.tools import tool

# Configure logger for knowledge graph tools
kg_tools_logger = logging.getLogger('knowledge_graph.tools')
kg_tools_logger.setLevel(logging.INFO)
# Don't propagate to root logger to avoid console output
kg_tools_logger.propagate = False

# Import Knowledge Graph
from knowledge_graph import KnowledgeGraph

# Global Knowledge Graph instance (REMOVED)
# KNOWLEDGE_GRAPH = None

# initialize_knowledge_graph and get_knowledge_graph (REMOVED)
# These functions are no longer needed as KnowledgeGraph instances
# will be passed directly to tool functions.

def _find_node_id(kg_instance: KnowledgeGraph, entity_type: str, entity_id_or_name: str) -> Optional[str]:
    """
    Find the canonical node ID for a given entity type and its ID or name.
    
    Args:
        kg_instance: The KnowledgeGraph instance to use.
        entity_type: The type of the entity.
        entity_id_or_name: The ID (potentially prefixed) or name of the entity.
        
    Returns:
        The canonical node ID (e.g., "Pod:my-pod-uuid") or None if not found.
    """
    # Check if entity_id_or_name is already a full node ID and exists
    if ':' in entity_id_or_name:
        if kg_instance.graph.has_node(entity_id_or_name):
            # Verify entity_type if possible (some nodes might not have it, or it might mismatch)
            node_data = kg_instance.graph.nodes[entity_id_or_name]
            if node_data.get('entity_type') == entity_type:
                return entity_id_or_name
            # If entity_type mismatches, it's ambiguous or wrong, fall through to search

    # Try constructing a prefixed ID if not already prefixed
    potential_node_id = f"{entity_type}:{entity_id_or_name}"
    if kg_instance.graph.has_node(potential_node_id):
        return potential_node_id

    # If not found directly, iterate and check 'name' or 'uuid' attributes
    for n_id, attrs in kg_instance.graph.nodes(data=True):
        if attrs.get('entity_type') == entity_type:
            if attrs.get('name') == entity_id_or_name or attrs.get('uuid') == entity_id_or_name:
                return n_id
    return None

@tool
def kg_get_entity_info(kg_instance: KnowledgeGraph, entity_type: str, entity_id: str) -> str:
    """
    Get detailed information about an entity in the Knowledge Graph
    
    Args:
        kg_instance: The KnowledgeGraph instance to use.
        entity_type: Type of entity (Pod, PVC, PV, Drive, Node, etc.)
        entity_id: ID or name of the entity (e.g., "my-pod" or "Pod:my-pod-id")
        
    Returns:
        str: JSON serialized entity details with attributes and relationships
    """
    kg = kg_instance
    
    node_id = _find_node_id(kg, entity_type, entity_id)

    if node_id is None:
        return json.dumps({"error": f"Entity not found: {entity_type} with ID/name '{entity_id}'"})
    
    # Get node attributes
    node_attrs = dict(kg.graph.nodes[node_id])
    
    # Get incoming and outgoing relationships
    incoming_edges = []
    outgoing_edges = []
    
    for u, v, data in kg.graph.in_edges(node_id, data=True):
        source_type = kg.graph.nodes[u].get('entity_type', 'Unknown')
        source_name = kg.graph.nodes[u].get('name', u.split(':')[-1])
        incoming_edges.append({
            "source_id": u,
            "source_type": source_type,
            "source_name": source_name,
            "relationship": data.get('relationship', 'connected_to'),
            "attributes": {k: v for k, v in data.items() if k != 'relationship'}
        })
    
    for u, v, data in kg.graph.out_edges(node_id, data=True):
        target_type = kg.graph.nodes[v].get('entity_type', 'Unknown')
        target_name = kg.graph.nodes[v].get('name', v.split(':')[-1])
        outgoing_edges.append({
            "target_id": v,
            "target_type": target_type,
            "target_name": target_name,
            "relationship": data.get('relationship', 'connected_to'),
            "attributes": {k: v for k, v in data.items() if k != 'relationship'}
        })
    
    # Compile result
    result = {
        "node_id": node_id,
        "entity_type": entity_type,
        "attributes": node_attrs,
        "incoming_relationships": incoming_edges,
        "outgoing_relationships": outgoing_edges,
        "issues": node_attrs.get('issues', [])
    }
    
    return json.dumps(result, indent=2)

@tool
def kg_get_related_entities(kg_instance: KnowledgeGraph, entity_type: str, entity_id: str, relationship_type: str = None, max_depth: int = 1) -> str:
    """
    Get entities related to a target entity in the Knowledge Graph
    
    Args:
        kg_instance: The KnowledgeGraph instance to use.
        entity_type: Type of entity (Pod, PVC, PV, Drive, Node, etc.)
        entity_id: ID or name of the entity (e.g., "my-pod" or "Pod:my-pod-id")
        relationship_type: Optional relationship type to filter by
        max_depth: Maximum traversal depth (1 = direct relationships only)
        
    Returns:
        str: JSON serialized list of related entities
    """
    kg = kg_instance
    
    node_id = _find_node_id(kg, entity_type, entity_id)

    if node_id is None:
        return json.dumps({"error": f"Entity not found: {entity_type} with ID/name '{entity_id}'"})
    
    # Find related entities recursively up to max_depth
    related_entities = []
    visited = set([node_id])
    
    def explore_neighbors(current_node, current_depth):
        if current_depth > max_depth:
            return
        
        # Outgoing edges
        for _, target, edge_data in kg.graph.out_edges(current_node, data=True):
            if target in visited:
                continue
                
            edge_rel_type = edge_data.get('relationship', 'connected_to')
            if relationship_type is None or edge_rel_type == relationship_type:
                target_attrs = dict(kg.graph.nodes[target])
                entity = {
                    "node_id": target,
                    "entity_type": target_attrs.get('entity_type', 'Unknown'),
                    "name": target_attrs.get('name', target.split(':')[-1]),
                    "relationship": {
                        "type": edge_rel_type,
                        "direction": "outgoing",
                        "from": current_node
                    },
                    "attributes": {k: v for k, v in target_attrs.items() 
                                if k not in ['entity_type', 'name', 'issues']},
                    "issues": target_attrs.get('issues', [])
                }
                related_entities.append(entity)
                visited.add(target)
                
                # Recursive exploration
                if current_depth < max_depth:
                    explore_neighbors(target, current_depth + 1)
        
        # Incoming edges
        for source, _, edge_data in kg.graph.in_edges(current_node, data=True):
            if source in visited:
                continue
                
            edge_rel_type = edge_data.get('relationship', 'connected_to')
            if relationship_type is None or edge_rel_type == relationship_type:
                source_attrs = dict(kg.graph.nodes[source])
                entity = {
                    "node_id": source,
                    "entity_type": source_attrs.get('entity_type', 'Unknown'),
                    "name": source_attrs.get('name', source.split(':')[-1]),
                    "relationship": {
                        "type": edge_rel_type,
                        "direction": "incoming",
                        "to": current_node
                    },
                    "attributes": {k: v for k, v in source_attrs.items() 
                                if k not in ['entity_type', 'name', 'issues']},
                    "issues": source_attrs.get('issues', [])
                }
                related_entities.append(entity)
                visited.add(source)
                
                # Recursive exploration
                if current_depth < max_depth:
                    explore_neighbors(source, current_depth + 1)
    
    # Start exploration from the target node
    explore_neighbors(node_id, 1)
    
    return json.dumps({
        "source_entity": {
            "node_id": node_id,
            "entity_type": entity_type,
            "name": kg.graph.nodes[node_id].get('name', node_id.split(':')[-1])
        },
        "relationship_filter": relationship_type,
        "max_depth": max_depth,
        "related_entities": related_entities,
        "total_count": len(related_entities)
    }, indent=2)

@tool
def kg_get_all_issues(kg_instance: KnowledgeGraph, severity: str = None, issue_type: str = None) -> str:
    """
    Get all issues from the Knowledge Graph, optionally filtered by severity or type
    
    Args:
        kg_instance: The KnowledgeGraph instance to use.
        severity: Optional filter by issue severity (critical, high, medium, low)
        issue_type: Optional filter by issue type (disk_health, permission, etc.)
        
    Returns:
        str: JSON serialized list of issues with related entities
    """
    kg = kg_instance
    
    # Get all issues based on filters
    if severity and issue_type:
        issues = [issue for issue in kg.issues 
                 if issue['severity'] == severity and issue['type'] == issue_type]
    elif severity:
        issues = kg.get_issues_by_severity(severity)
    elif issue_type:
        issues = [issue for issue in kg.issues if issue['type'] == issue_type]
    else:
        issues = kg.get_all_issues()
    
    # Enhance issues with entity information
    enhanced_issues = []
    for issue in issues:
        node_id = issue['node_id']
        entity_info = {}
        
        if kg.graph.has_node(node_id):
            node_attrs = kg.graph.nodes[node_id]
            entity_type = node_attrs.get('entity_type', 'Unknown')
            entity_name = node_attrs.get('name', node_id.split(':')[-1])
            entity_info = {
                "entity_type": entity_type,
                "name": entity_name,
                "attributes": {k: v for k, v in node_attrs.items() 
                             if k not in ['entity_type', 'name', 'issues']}
            }
        
        enhanced_issues.append({
            "issue": issue,
            "entity": entity_info
        })
    
    result = {
        "total_issues": len(enhanced_issues),
        "severity_filter": severity,
        "type_filter": issue_type,
        "issues": enhanced_issues
    }
    
    return json.dumps(result, indent=2)

@tool
def kg_find_path(kg_instance: KnowledgeGraph, source_entity_type: str, source_entity_id: str,
                target_entity_type: str, target_entity_id: str) -> str:
    """
    Find the shortest path between two entities in the Knowledge Graph
    
    Args:
        kg_instance: The KnowledgeGraph instance to use.
        source_entity_type: Type of source entity (Pod, PVC, PV, Drive, Node, etc.)
        source_entity_id: ID or name of the source entity
        target_entity_type: Type of target entity (Pod, PVC, PV, Drive, Node, etc.)
        target_entity_id: ID or name of the target entity
        
    Returns:
        str: JSON serialized path between entities with relationship details
    """
    kg = kg_instance
    
    source_node_id = _find_node_id(kg, source_entity_type, source_entity_id)
    if source_node_id is None:
        return json.dumps({"error": f"Source entity not found: {source_entity_type} with ID/name '{source_entity_id}'"})

    target_node_id = _find_node_id(kg, target_entity_type, target_entity_id)
    if target_node_id is None:
        return json.dumps({"error": f"Target entity not found: {target_entity_type} with ID/name '{target_entity_id}'"})

    # Find shortest path
    path_nodes = kg.find_path(source_node_id, target_node_id)
    
    if not path_nodes:
        return json.dumps({
            "source_entity": {
                "node_id": source_node_id,
                "entity_type": source_entity_type,
                "name": kg.graph.nodes[source_node_id].get('name', source_node_id.split(':')[-1])
            },
            "target_entity": {
                "node_id": target_node_id,
                "entity_type": target_entity_type,
                "name": kg.graph.nodes[target_node_id].get('name', target_node_id.split(':')[-1])
            },
            "path_exists": False,
            "path": []
        })
    
    # Construct detailed path
    path_details = []
    for i in range(len(path_nodes) - 1):
        source = path_nodes[i]
        target = path_nodes[i + 1]
        
        # Get edge data
        edge_data = kg.graph.edges[source, target]
        relationship = edge_data.get('relationship', 'connected_to')
        
        # Get node data
        source_attrs = kg.graph.nodes[source]
        source_type = source_attrs.get('entity_type', 'Unknown')
        source_name = source_attrs.get('name', source.split(':')[-1])
        
        target_attrs = kg.graph.nodes[target]
        target_type = target_attrs.get('entity_type', 'Unknown')
        target_name = target_attrs.get('name', target.split(':')[-1])
        
        path_details.append({
            "source": {
                "node_id": source,
                "entity_type": source_type,
                "name": source_name
            },
            "target": {
                "node_id": target,
                "entity_type": target_type,
                "name": target_name
            },
            "relationship": relationship,
            "edge_attributes": {k: v for k, v in edge_data.items() if k != 'relationship'}
        })
    
    result = {
        "source_entity": {
            "node_id": source_node_id,
            "entity_type": source_entity_type,
            "name": kg.graph.nodes[source_node_id].get('name', source_node_id.split(':')[-1])
        },
        "target_entity": {
            "node_id": target_node_id,
            "entity_type": target_entity_type,
            "name": kg.graph.nodes[target_node_id].get('name', target_node_id.split(':')[-1])
        },
        "path_exists": True,
        "path_length": len(path_nodes) - 1,
        "path": path_details
    }
    
    return json.dumps(result, indent=2)

@tool
def kg_get_summary(kg_instance: KnowledgeGraph) -> str:
    """
    Get a summary of the Knowledge Graph including entity counts and issues
    
    Args:
        kg_instance: The KnowledgeGraph instance to use.

    Returns:
        str: JSON serialized summary of the Knowledge Graph
    """
    kg = kg_instance
    summary = kg.get_summary()
    
    # Enhance with issue types distribution
    issue_types = {}
    for issue in kg.issues:
        issue_type = issue['type']
        issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
    
    result = {
        "graph_stats": summary,
        "issue_types": issue_types,
        "timestamp": logging.Formatter("%Y-%m-%d %H:%M:%S").format(logging.LogRecord("", 0, "", 0, "", (), None))
    }
    
    return json.dumps(result, indent=2)

@tool
def kg_analyze_issues(kg_instance: KnowledgeGraph) -> str:
    """
    Analyze issues in the Knowledge Graph to identify patterns and root causes
    
    Args:
        kg_instance: The KnowledgeGraph instance to use.

    Returns:
        str: JSON serialized analysis results with potential root causes and fix plans
    """
    kg = kg_instance
    
    # Run analysis
    analysis = kg.analyze_issues()
    
    # Generate fix plan based on analysis
    fix_plan = kg.generate_fix_plan(analysis)
    
    result = {
        "analysis": analysis,
        "fix_plan": fix_plan,
        "timestamp": logging.Formatter("%Y-%m-%d %H:%M:%S").format(logging.LogRecord("", 0, "", 0, "", (), None))
    }
    
    return json.dumps(result, indent=2)

@tool
def kg_print_graph(kg_instance: KnowledgeGraph, include_details: bool = True, include_issues: bool = True) -> str:
    """
    Get a human-friendly formatted representation of the Knowledge Graph
    
    Args:
        kg_instance: The KnowledgeGraph instance to use.
        include_details: Whether to include detailed entity information
        include_issues: Whether to include issues in the output
        
    Returns:
        str: Formatted representation of the Knowledge Graph
    """
    kg = kg_instance
    return kg.print_graph(
        include_detailed_entities=include_details,
        include_issues=include_issues,
        include_analysis=True,
        include_relationships=True
    )
