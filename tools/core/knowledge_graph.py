#!/usr/bin/env python3
"""
Knowledge Graph tools for Kubernetes volume troubleshooting.

This module contains tools for interacting with the Knowledge Graph,
including entity queries, relationship analysis, and issue management.
"""

import json
import logging
from typing import Any
from langchain_core.tools import tool

# Configure logger for knowledge graph tools
kg_tools_logger = logging.getLogger('knowledge_graph.tools')
kg_tools_logger.setLevel(logging.INFO)
# Don't propagate to root logger to avoid console output
kg_tools_logger.propagate = False

# Import Knowledge Graph
from knowledge_graph import KnowledgeGraph

# Global Knowledge Graph instance
KNOWLEDGE_GRAPH = None

def initialize_knowledge_graph(kg_instance: 'KnowledgeGraph') -> 'KnowledgeGraph':
    """
    Initialize or set the global Knowledge Graph instance
    
    Args:
        kg_instance: Existing KnowledgeGraph instance from Phase0 (required)
        
    Returns:
        KnowledgeGraph: Global KnowledgeGraph instance
    """
    global KNOWLEDGE_GRAPH
    
    if kg_instance:
        KNOWLEDGE_GRAPH = kg_instance
        kg_tools_logger.info("Using Knowledge Graph instance from Phase0")
    else:
        error_msg = "Knowledge Graph instance must be provided from Phase0 (information collection)"
        kg_tools_logger.error(error_msg)
        raise ValueError(error_msg)
    
    return KNOWLEDGE_GRAPH

def get_knowledge_graph() -> 'KnowledgeGraph':
    """
    Get the global Knowledge Graph instance
    
    Returns:
        KnowledgeGraph: Global KnowledgeGraph instance from Phase0
        
    Raises:
        ValueError: If Knowledge Graph has not been initialized with a valid instance from Phase0
    """
    global KNOWLEDGE_GRAPH
    
    if KNOWLEDGE_GRAPH is None:
        error_msg = "Knowledge Graph has not been initialized. Use initialize_knowledge_graph() with the Knowledge Graph instance from Phase0 first."
        kg_tools_logger.error(error_msg)
        raise ValueError(error_msg)
    
    return KNOWLEDGE_GRAPH

@tool
def kg_get_entity_info(entity_type: str, id: str) -> str:
    """
    Get detailed information about an entity in the Knowledge Graph
    
    Args:
        entity_type: Type of entity (Pod, PVC, PV, Drive, Node, etc.)
        id: ID or name of the entity. Can be provided in two formats:
           Examples: "gnode:Pod:default/nginx-pod", "gnode:PV:pv-00001", "gnode:Drive:drive-sda"
           
           Entity ID formats:
           - Pod: "gnode:Pod:<namespace>/<name>" (example: "gnode:Pod:default/test-pod-1-0")
           - PVC: "gnode:PVC:<namespace>/<name>" (example: "gnode:PVC:default/test-pvc-1")
           - PV: "gnode:PV:<name>" (example: "gnode:PV:pv-test-123")
           - Drive: "gnode:Drive:<uuid>" (example: "gnode:Drive:a1b2c3d4-e5f6")
           - Node: "gnode:Node:<name>" (example: "gnode:Node:kind-control-plane")
           - StorageClass: "gnode:StorageClass:<name>" (example: "gnode:StorageClass:csi-baremetal-sc")
           - LVG: "gnode:LVG:<name>" (example: "gnode:LVG:lvg-1")
           - AC: "gnode:AC:<name>" (example: "gnode:AC:ac-node1-ssd")
           - Volume: "gnode:Volume:<namespace>/<name>" (example: "gnode:Volume:default/vol-1")
           - System: "gnode:System:<entity_name>" (example: "gnode:System:kernel")
           - ClusterNode: "gnode:ClusterNode:<name>" (example: "gnode:ClusterNode:worker-1")
           - HistoricalExperience: "gnode:HistoricalExperience:<experience_id>" (example: "gnode:HistoricalExperience:exp-001")
        
    Returns:
        str: JSON serialized entity details with attributes and relationships
    """
    kg = get_knowledge_graph()
    
    # Construct the full node_id if only name was provided
    if ':' not in id:
        node_id = f"gnode:{entity_type}:{id}"
    else:
        node_id = id
    
    # Check if node exists in graph
    if not kg.graph.has_node(node_id):
        # Try to find by name or uuid attribute
        found = False
        for n_id, attrs in kg.graph.nodes(data=True):
            if (attrs.get('entity_type') == entity_type and 
                (attrs.get('name') == id or attrs.get('uuid') == id)):
                node_id = n_id
                found = True
                break
        
        if not found:
            return json.dumps({"error": f"Entity not found: gnode:{entity_type}:{id}"})
    
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
def kg_get_related_entities(entity_type: str, id: str, relationship_type: str = None, max_depth: int = 1) -> str:
    """
    Get entities related to a target entity in the Knowledge Graph
    
    Args:
        entity_type: Type of entity (Pod, PVC, PV, Drive, Node, etc.)
        id: ID or name of the entity. Can be provided in two formats:
           Examples: "gnode:Pod:default/nginx-pod", "gnode:PV:pv-00001", "gnode:Drive:drive-sda"
           
           Entity ID formats:
           - Pod: "gnode:Pod:<namespace>/<name>" (example: "gnode:Pod:default/test-pod-1-0")
           - PVC: "gnode:PVC:<namespace>/<name>" (example: "gnode:PVC:default/test-pvc-1")
           - PV: "gnode:PV:<name>" (example: "gnode:PV:pv-test-123")
           - Drive: "gnode:Drive:<uuid>" (example: "gnode:Drive:a1b2c3d4-e5f6")
           - Node: "gnode:Node:<name>" (example: "gnode:Node:kind-control-plane")
           - StorageClass: "gnode:StorageClass:<name>" (example: "gnode:StorageClass:csi-baremetal-sc")
           - LVG: "gnode:LVG:<name>" (example: "gnode:LVG:lvg-1")
           - AC: "gnode:AC:<name>" (example: "gnode:AC:ac-node1-ssd")
           - Volume: "gnode:Volume:<namespace>/<name>" (example: "gnode:Volume:default/vol-1")
           - System: "gnode:System:<entity_name>" (example: "gnode:System:kernel")
           - ClusterNode: "gnode:ClusterNode:<name>" (example: "gnode:ClusterNode:worker-1")
           - HistoricalExperience: "gnode:HistoricalExperience:<experience_id>" (example: "gnode:HistoricalExperience:exp-001")
        relationship_type: Optional relationship type to filter by (e.g., "uses", "bound_to", "runs_on")
        max_depth: Maximum traversal depth (1 = direct relationships only)
        
    Returns:
        str: JSON serialized list of related entities
    """
    kg = get_knowledge_graph()
    
    # Construct the full node_id if only name was provided
    if ':' not in id:
        node_id = f"gnode:{entity_type}:{id}"
    else:
        node_id = id
    
    # Check if node exists in graph
    if not kg.graph.has_node(node_id):
        # Try to find by name or uuid attribute
        found = False
        for n_id, attrs in kg.graph.nodes(data=True):
            if (attrs.get('entity_type') == entity_type and 
                (attrs.get('name') == id or attrs.get('uuid') == id)):
                node_id = n_id
                found = True
                break
        
        if not found:
            return json.dumps({"error": f"Entity not found: gnode:{entity_type}:{id}"})
    
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
def kg_get_all_issues(severity: str = None, issue_type: str = None) -> str:
    """
    Get all issues in the Knowledge Graph with optional filtering
    
    Args:
        severity: Optional severity filter (primary, critical, high, medium, low)
        issue_type: Optional issue type filter
        
    Returns:
        str: JSON serialized list of issues with entity information
    """
    kg = get_knowledge_graph()
    
    # Get all issues based on filters
    if severity and issue_type:
        issues = [issue for issue in kg.issues 
                 if issue['severity'] == severity and issue['type'] == issue_type]
    elif severity == 'primary':
        critical_issues = kg.get_issues_by_severity("critical")
        high_issues = kg.get_issues_by_severity("high")
        issues = critical_issues + high_issues
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
def kg_find_path(source_entity_type: str, source_id: str, 
                target_entity_type: str, target_id: str) -> str:
    """
    Find the shortest path between two entities in the Knowledge Graph
    
    Args:
        source_entity_type: Type of source entity (Pod, PVC, PV, Drive, Node, etc.)
        source_id: ID or name of the source entity. Can be provided in two formats:
                  Examples: "gnode:Pod:default/nginx-pod", "gnode:PV:pv-00001", "gnode:Drive:drive-sda"
                  
                  Entity ID formats:
                  - Pod: "gnode:Pod:<namespace>/<name>" (example: "gnode:Pod:default/test-pod-1-0")
                  - PVC: "gnode:PVC:<namespace>/<name>" (example: "gnode:PVC:default/test-pvc-1")
                  - PV: "gnode:PV:<name>" (example: "gnode:PV:pv-test-123")
                  - Drive: "gnode:Drive:<uuid>" (example: "gnode:Drive:a1b2c3d4-e5f6")
                  - Node: "gnode:Node:<name>" (example: "gnode:Node:kind-control-plane")
                  - StorageClass: "gnode:StorageClass:<name>" (example: "gnode:StorageClass:csi-baremetal-sc")
                  - LVG: "gnode:LVG:<name>" (example: "gnode:LVG:lvg-1")
                  - AC: "gnode:AC:<name>" (example: "gnode:AC:ac-node1-ssd")
                  - Volume: "gnode:Volume:<namespace>/<name>" (example: "gnode:Volume:default/vol-1")
                  - System: "gnode:System:<entity_name>" (example: "gnode:System:kernel")
                  - ClusterNode: "gnode:ClusterNode:<name>" (example: "gnode:ClusterNode:worker-1")
                  - HistoricalExperience: "gnode:HistoricalExperience:<experience_id>" (example: "gnode:HistoricalExperience:exp-001")
        target_entity_type: Type of target entity (Pod, PVC, PV, Drive, Node, etc.)
        target_id: ID or name of the target entity. Format is the same as source_id.
                  The system will construct the full node_id as "gnode:{target_entity_type}:{target_id}"
                  Examples: "gnode:Pod:default/nginx-pod", "gnode:PV:pv-00001", "gnode:Drive:drive-sda"
        
    Returns:
        str: JSON serialized path between entities with relationship details
    """
    kg = get_knowledge_graph()
    
    # Construct node IDs
    source_node_id = f"gnode:{source_entity_type}:{source_id}"
    target_node_id = f"gnode:{target_entity_type}:{target_id}"
    
    # Check if nodes exist
    if not kg.graph.has_node(source_node_id):
        # Try to find by name or uuid
        for n_id, attrs in kg.graph.nodes(data=True):
            if (attrs.get('entity_type') == source_entity_type and 
                (attrs.get('name') == source_id or attrs.get('uuid') == source_id)):
                source_node_id = n_id
                break
    
    if not kg.graph.has_node(target_node_id):
        # Try to find by name or uuid
        for n_id, attrs in kg.graph.nodes(data=True):
            if (attrs.get('entity_type') == target_entity_type and 
                (attrs.get('name') == target_id or attrs.get('uuid') == target_id)):
                target_node_id = n_id
                break
    
    # Return error if either node is not found
    if not kg.graph.has_node(source_node_id):
        return json.dumps({"error": f"Source entity not found: gnode:{source_entity_type}:{source_id}"})
    
    if not kg.graph.has_node(target_node_id):
        return json.dumps({"error": f"Target entity not found: gnode:{target_entity_type}:{target_id}"})
    
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
def kg_get_summary() -> str:
    """
    Get a summary of the Knowledge Graph including entity counts and issues
    
    Returns:
        str: JSON serialized summary of the Knowledge Graph
    """
    kg = get_knowledge_graph()
    summary = kg.get_summary()
    
    # Enhance with issue types distribution
    issue_types = {}
    for issue in kg.issues:
        issue_type = issue['type']
        issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
    
    # Use a safer way to get current timestamp
    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    result = {
        "graph_stats": summary,
        "issue_types": issue_types,
        "timestamp": current_time
    }
    
    return json.dumps(result, indent=2)

@tool
def kg_analyze_issues() -> str:
    """
    Analyze issues in the Knowledge Graph to identify patterns and root causes
    
    Returns:
        str: JSON serialized analysis results with potential root causes and fix plans
    """
    kg = get_knowledge_graph()
    
    # Run analysis
    analysis = kg.analyze_issues()
    
    # Generate fix plan based on analysis
    fix_plan = kg.generate_fix_plan(analysis)
    
    # Use a safer way to get current timestamp
    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    result = {
        "analysis": analysis,
        "fix_plan": fix_plan,
        "timestamp": current_time
    }
    
    return json.dumps(result, indent=2)

@tool
def kg_print_graph(include_details: bool = True, include_issues: bool = True) -> str:
    """
    Get a human-friendly formatted representation of the Knowledge Graph
    
    Args:
        include_details: Whether to include detailed entity information
        include_issues: Whether to include issues in the output
        
    Returns:
        str: Formatted representation of the Knowledge Graph
    """
    kg = get_knowledge_graph()
    return kg.print_graph(
        include_detailed_entities=include_details,
        include_issues=include_issues,
        include_analysis=True,
        include_relationships=True
    )

@tool
def kg_list_entity_types() -> str:
    """
    Get a list of all entity types in the Knowledge Graph with their counts
    
    This tool helps discover what types of entities are available in the Knowledge Graph.
    Common entity types include: Pod, PVC, PV, Drive, Node, StorageClass, CSIDriver, etc.
    
    Returns:
        str: JSON serialized list of entity types and their counts
    """
    kg = get_knowledge_graph()
    
    # Count entities by type
    entity_types = {}
    for node_id, attrs in kg.graph.nodes(data=True):
        entity_type = attrs.get('entity_type', 'Unknown')
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
    
    result = {
        "entity_types": [
            {"type": entity_type, "count": count}
            for entity_type, count in entity_types.items()
        ],
        "total_entity_types": len(entity_types),
        "total_entities": kg.graph.number_of_nodes()
    }
    
    return json.dumps(result, indent=2)

@tool
def kg_list_entities(entity_type: str = None) -> str:
    """
    Get a list of all entities of a specific type (or all entities if type is None)
    
    This tool helps discover what specific entities are available in the Knowledge Graph.
    Use this after kg_list_entity_types() to find entities of a particular type.
    
    Args:
        entity_type: Type of entity to list (Pod, PVC, PV, Drive, Node, etc.)
                    If None, lists all entities in the Knowledge Graph
    
    Returns:
        str: JSON serialized list of entities with their IDs, names, and key attributes
    """
    kg = get_knowledge_graph()
    
    entities = []
    for node_id, attrs in kg.graph.nodes(data=True):
        node_entity_type = attrs.get('entity_type', 'Unknown')
        
        # Filter by entity_type if specified
        if entity_type is not None and node_entity_type != entity_type:
            continue
            
        # Extract key information
        entity = {
            "node_id": node_id,
            "entity_type": node_entity_type,
            "name": attrs.get('name', node_id.split(':')[-1]),
            "has_issues": bool(attrs.get('issues', [])),
            "issue_count": len(attrs.get('issues', [])),
            "key_attributes": {k: v for k, v in attrs.items() 
                             if k not in ['entity_type', 'name', 'issues'] 
                             and not isinstance(v, (dict, list)) 
                             and len(str(v)) < 100}
        }
        entities.append(entity)
    
    result = {
        "filter_type": entity_type if entity_type else "All",
        "entities": entities,
        "total_count": len(entities)
    }
    
    return json.dumps(result, indent=2)

@tool
def kg_list_relationship_types() -> str:
    """
    Get a list of all relationship types in the Knowledge Graph with their counts
    
    This tool helps discover what types of relationships exist between entities.
    Common relationship types include: uses, bound_to, runs_on, located_on, maps_to, etc.
    
    Returns:
        str: JSON serialized list of relationship types and their counts
    """
    kg = get_knowledge_graph()
    
    # Count relationships by type
    relationship_types = {}
    for _, _, edge_data in kg.graph.edges(data=True):
        rel_type = edge_data.get('relationship', 'connected_to')
        relationship_types[rel_type] = relationship_types.get(rel_type, 0) + 1
    
    result = {
        "relationship_types": [
            {"type": rel_type, "count": count}
            for rel_type, count in relationship_types.items()
        ],
        "total_relationship_types": len(relationship_types),
        "total_relationships": kg.graph.number_of_edges()
    }
    
    return json.dumps(result, indent=2)

# Entity ID helper tools

@tool
def kg_get_entity_of_pod(namespace: str, name: str) -> str:
    """
    Get the entity ID for a Pod in the Knowledge Graph
    
    Args:
        namespace: Namespace of the Pod
        name: Name of the Pod
        
    Returns:
        str: Entity ID in the format 'gnode:Pod:<namespace>/<name>'
             Example: 'gnode:Pod:default/test-pod-1-0'
    """
    return f"gnode:Pod:{namespace}/{name}"

@tool
def kg_get_entity_of_pvc(namespace: str, name: str) -> str:
    """
    Get the entity ID for a PVC in the Knowledge Graph
    
    Args:
        namespace: Namespace of the PVC
        name: Name of the PVC
        
    Returns:
        str: Entity ID in the format 'gnode:PVC:<namespace>/<name>'
             Example: 'gnode:PVC:default/test-pvc-1'
    """
    return f"gnode:PVC:{namespace}/{name}"

@tool
def kg_get_entity_of_pv(name: str) -> str:
    """
    Get the entity ID for a PV in the Knowledge Graph
    
    Args:
        name: Name of the PV
        
    Returns:
        str: Entity ID in the format 'gnode:PV:<name>'
             Example: 'gnode:PV:pv-test-123'
    """
    return f"gnode:PV:{name}"

@tool
def kg_get_entity_of_drive(uuid: str) -> str:
    """
    Get the entity ID for a Drive in the Knowledge Graph
    
    Args:
        uuid: UUID of the Drive
        
    Returns:
        str: Entity ID in the format 'gnode:Drive:<uuid>'
             Example: 'gnode:Drive:a1b2c3d4-e5f6'
    """
    return f"gnode:Drive:{uuid}"

@tool
def kg_get_entity_of_node(name: str) -> str:
    """
    Get the entity ID for a Node in the Knowledge Graph
    
    Args:
        name: Name of the Node
        
    Returns:
        str: Entity ID in the format 'gnode:Node:<name>'
             Example: 'gnode:Node:kind-control-plane'
    """
    return f"gnode:Node:{name}"

@tool
def kg_get_entity_of_storage_class(name: str) -> str:
    """
    Get the entity ID for a StorageClass in the Knowledge Graph
    
    Args:
        name: Name of the StorageClass
        
    Returns:
        str: Entity ID in the format 'gnode:StorageClass:name'
    """
    return f"gnode:StorageClass:{name}"

@tool
def kg_get_entity_of_lvg(name: str) -> str:
    """
    Get the entity ID for a LogicalVolumeGroup in the Knowledge Graph
    
    Args:
        name: Name of the LVG
        
    Returns:
        str: Entity ID in the format 'gnode:LVG:name'
    """
    return f"gnode:LVG:{name}"

@tool
def kg_get_entity_of_ac(name: str) -> str:
    """
    Get the entity ID for an AvailableCapacity in the Knowledge Graph
    
    Args:
        name: Name of the AC
        
    Returns:
        str: Entity ID in the format 'gnode:AC:name'
    """
    return f"gnode:AC:{name}"

@tool
def kg_get_entity_of_volume(namespace: str, name: str) -> str:
    """
    Get the entity ID for a Volume in the Knowledge Graph
    
    Args:
        namespace: Namespace of the Volume
        name: Name of the Volume
        
    Returns:
        str: Entity ID in the format 'gnode:Volume:namespace/name'
    """
    return f"gnode:Volume:{namespace}/{name}"

@tool
def kg_get_entity_of_system(entity_name: str) -> str:
    """
    Get the entity ID for a System entity in the Knowledge Graph
    
    Args:
        entity_name: Name of the System entity
        
    Returns:
        str: Entity ID in the format 'gnode:System:entity_name'
    """
    return f"gnode:System:{entity_name}"

@tool
def kg_get_entity_of_cluster_node(name: str) -> str:
    """
    Get the entity ID for a ClusterNode in the Knowledge Graph
    
    Args:
        name: Name of the ClusterNode
        
    Returns:
        str: Entity ID in the format 'gnode:ClusterNode:name'
    """
    return f"gnode:ClusterNode:{name}"

@tool
def kg_get_entity_of_historical_experience(experience_id: str) -> str:
    """
    Get the entity ID for a HistoricalExperience in the Knowledge Graph
    
    Args:
        experience_id: ID of the HistoricalExperience
        
    Returns:
        str: Entity ID in the format 'gnode:HistoricalExperience:experience_id'
    """
    return f"gnode:HistoricalExperience:{experience_id}"
