#!/usr/bin/env python3
"""
LangGraph Tools for Kubernetes Volume I/O Error Troubleshooting

This module contains tools and utility functions for executing LangGraph workflows
in the Kubernetes volume troubleshooting system, including Knowledge Graph integration.
"""

import json
import logging
import asyncio
import subprocess
from typing import Dict, List, Any, Optional, Tuple

from langgraph.graph import StateGraph
from langchain_core.tools import tool

# Import from graph.py
from graph import create_troubleshooting_graph_with_context
# Import Knowledge Graph
from knowledge_graph import KnowledgeGraph

# Global variables
INTERACTIVE_MODE = False  # To be set by the caller
CONFIG_DATA = None  # To be set by the caller with configuration
KNOWLEDGE_GRAPH = None  # Global Knowledge Graph instance

def initialize_knowledge_graph(kg_instance: 'KnowledgeGraph' = None) -> 'KnowledgeGraph':
    """
    Initialize or set the global Knowledge Graph instance
    
    Args:
        kg_instance: Existing KnowledgeGraph instance (optional)
        
    Returns:
        KnowledgeGraph: Global KnowledgeGraph instance
    """
    global KNOWLEDGE_GRAPH
    
    if kg_instance:
        KNOWLEDGE_GRAPH = kg_instance
        logging.info("Using provided Knowledge Graph instance")
    elif KNOWLEDGE_GRAPH is None:
        KNOWLEDGE_GRAPH = KnowledgeGraph()
        logging.info("Created new Knowledge Graph instance")
    
    return KNOWLEDGE_GRAPH

def get_knowledge_graph() -> 'KnowledgeGraph':
    """
    Get the global Knowledge Graph instance
    
    Returns:
        KnowledgeGraph: Global KnowledgeGraph instance
    """
    global KNOWLEDGE_GRAPH
    
    if KNOWLEDGE_GRAPH is None:
        KNOWLEDGE_GRAPH = initialize_knowledge_graph()
    
    return KNOWLEDGE_GRAPH

def validate_command(command_list: List[str], config_data: Dict[str, Any] = None) -> Tuple[bool, str]:
    """
    Validate command against allowed/disallowed patterns in configuration
    
    Args:
        command_list: Command to validate as list of strings
        config_data: Configuration data containing command restrictions
        
    Returns:
        Tuple[bool, str]: (is_allowed, reason)
    """
    if not command_list:
        return False, "Empty command list"
    
    if config_data is None:
        config_data = CONFIG_DATA
    
    if config_data is None:
        return True, "No configuration available - allowing command"
    
    command_str = ' '.join(command_list)
    commands_config = config_data.get('commands', {})
    
    # Check disallowed commands first (higher priority)
    disallowed = commands_config.get('disallowed', [])
    for pattern in disallowed:
        if _matches_pattern(command_str, pattern):
            return False, f"Command matches disallowed pattern: {pattern}"
    
    # Check allowed commands
    allowed = commands_config.get('allowed', [])
    if allowed:  # If allowed list exists, command must match one of them
        for pattern in allowed:
            if _matches_pattern(command_str, pattern):
                return True, f"Command matches allowed pattern: {pattern}"
        return False, "Command does not match any allowed pattern"
    
    # If no allowed list, allow by default (only disallowed list matters)
    return True, "No allowed list specified - command permitted"

def _matches_pattern(command: str, pattern: str) -> bool:
    """
    Check if command matches a pattern (supports wildcards)
    
    Args:
        command: Full command string
        pattern: Pattern to match against (supports * wildcard)
        
    Returns:
        bool: True if command matches pattern
    """
    import fnmatch
    return fnmatch.fnmatch(command, pattern)

def execute_command(command_list: List[str], purpose: str, requires_approval: bool = True) -> str:
    """
    Execute a command and return its output
    
    Args:
        command_list: Command to execute as a list of strings
        purpose: Purpose of the command
        requires_approval: Whether this command requires user approval in interactive mode
        
    Returns:
        str: Command output
    """
    global INTERACTIVE_MODE
    
    if not command_list:
        logging.error("execute_command received an empty command_list")
        return "Error: Empty command list provided"

    executable = command_list[0]
    command_display_str = ' '.join(command_list)
    
    # Execute command
    try:
        logging.info(f"Executing command: {command_display_str}")
        result = subprocess.run(command_list, shell=False, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
        output = result.stdout
        logging.debug(f"Command output: {output}")
        return output
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed with exit code {e.returncode}: {e.stderr}"
        logging.error(error_msg)
        return f"Error: {error_msg}"
    except FileNotFoundError:
        error_msg = f"Command not found: {executable}"
        logging.error(error_msg)
        return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Failed to execute command {command_display_str}: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}"

# Knowledge Graph tools

@tool
def kg_get_entity_info(entity_type: str, entity_id: str) -> str:
    """
    Get detailed information about an entity in the Knowledge Graph
    
    Args:
        entity_type: Type of entity (Pod, PVC, PV, Drive, Node, etc.)
        entity_id: ID or name of the entity
        
    Returns:
        str: JSON serialized entity details with attributes and relationships
    """
    kg = get_knowledge_graph()
    
    # Construct the full node_id if only name was provided
    if ':' not in entity_id:
        node_id = f"{entity_type}:{entity_id}"
    else:
        node_id = entity_id
    
    # Check if node exists in graph
    if not kg.graph.has_node(node_id):
        # Try to find by name or uuid attribute
        found = False
        for n_id, attrs in kg.graph.nodes(data=True):
            if (attrs.get('entity_type') == entity_type and 
                (attrs.get('name') == entity_id or attrs.get('uuid') == entity_id)):
                node_id = n_id
                found = True
                break
        
        if not found:
            return json.dumps({"error": f"Entity not found: {entity_type}:{entity_id}"})
    
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
def kg_get_related_entities(entity_type: str, entity_id: str, relationship_type: str = None, max_depth: int = 1) -> str:
    """
    Get entities related to a target entity in the Knowledge Graph
    
    Args:
        entity_type: Type of entity (Pod, PVC, PV, Drive, Node, etc.)
        entity_id: ID or name of the entity
        relationship_type: Optional relationship type to filter by
        max_depth: Maximum traversal depth (1 = direct relationships only)
        
    Returns:
        str: JSON serialized list of related entities
    """
    kg = get_knowledge_graph()
    
    # Construct the full node_id if only name was provided
    if ':' not in entity_id:
        node_id = f"{entity_type}:{entity_id}"
    else:
        node_id = entity_id
    
    # Check if node exists in graph
    if not kg.graph.has_node(node_id):
        # Try to find by name or uuid attribute
        found = False
        for n_id, attrs in kg.graph.nodes(data=True):
            if (attrs.get('entity_type') == entity_type and 
                (attrs.get('name') == entity_id or attrs.get('uuid') == entity_id)):
                node_id = n_id
                found = True
                break
        
        if not found:
            return json.dumps({"error": f"Entity not found: {entity_type}:{entity_id}"})
    
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
    Get all issues from the Knowledge Graph, optionally filtered by severity or type
    
    Args:
        severity: Optional filter by issue severity (critical, high, medium, low)
        issue_type: Optional filter by issue type (disk_health, permission, etc.)
        
    Returns:
        str: JSON serialized list of issues with related entities
    """
    kg = get_knowledge_graph()
    
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
def kg_find_path(source_entity_type: str, source_entity_id: str, 
                target_entity_type: str, target_entity_id: str) -> str:
    """
    Find the shortest path between two entities in the Knowledge Graph
    
    Args:
        source_entity_type: Type of source entity (Pod, PVC, PV, Drive, Node, etc.)
        source_entity_id: ID or name of the source entity
        target_entity_type: Type of target entity (Pod, PVC, PV, Drive, Node, etc.)
        target_entity_id: ID or name of the target entity
        
    Returns:
        str: JSON serialized path between entities with relationship details
    """
    kg = get_knowledge_graph()
    
    # Construct node IDs
    source_node_id = f"{source_entity_type}:{source_entity_id}"
    target_node_id = f"{target_entity_type}:{target_entity_id}"
    
    # Check if nodes exist
    if not kg.graph.has_node(source_node_id):
        # Try to find by name or uuid
        for n_id, attrs in kg.graph.nodes(data=True):
            if (attrs.get('entity_type') == source_entity_type and 
                (attrs.get('name') == source_entity_id or attrs.get('uuid') == source_entity_id)):
                source_node_id = n_id
                break
    
    if not kg.graph.has_node(target_node_id):
        # Try to find by name or uuid
        for n_id, attrs in kg.graph.nodes(data=True):
            if (attrs.get('entity_type') == target_entity_type and 
                (attrs.get('name') == target_entity_id or attrs.get('uuid') == target_entity_id)):
                target_node_id = n_id
                break
    
    # Return error if either node is not found
    if not kg.graph.has_node(source_node_id):
        return json.dumps({"error": f"Source entity not found: {source_entity_type}:{source_entity_id}"})
    
    if not kg.graph.has_node(target_node_id):
        return json.dumps({"error": f"Target entity not found: {target_entity_type}:{target_entity_id}"})
    
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
    
    result = {
        "graph_stats": summary,
        "issue_types": issue_types,
        "timestamp": logging.Formatter("%Y-%m-%d %H:%M:%S").format(logging.LogRecord("", 0, "", 0, "", (), None))
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
    
    result = {
        "analysis": analysis,
        "fix_plan": fix_plan,
        "timestamp": logging.Formatter("%Y-%m-%d %H:%M:%S").format(logging.LogRecord("", 0, "", 0, "", (), None))
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

def define_remediation_tools() -> List[Any]:
    """
    Define tools needed for remediation and analysis phases
    
    Returns:
        List[Any]: List of tool callables for investigation and remediation
    """
    # Return LangGraph tools for Kubernetes operations and CSI Baremetal investigation
    return [
        # Knowledge Graph tools
        kg_get_entity_info,
        kg_get_related_entities,
        kg_get_all_issues,
        kg_find_path,
        kg_get_summary,
        kg_analyze_issues,
        kg_print_graph,
        
        # Kubernetes tools
        #kubectl_get,
        #kubectl_describe,
        #kubectl_apply,
        #kubectl_delete,
        kubectl_exec,
        kubectl_logs,
        #kubectl_get_drive,
        #kubectl_get_csibmnode,
        #kubectl_get_availablecapacity,
        #kubectl_get_logicalvolumegroup,
        #kubectl_get_storageclass,
        #kubectl_get_csidrivers,
        
        # Hardware diagnostic tools
        smartctl_check,
        fio_performance_test,
        fsck_check,
        
        # System tools
        ssh_execute,
        df_command,
        lsblk_command,
        mount_command,
        dmesg_command,
        journalctl_command
    ]


# LangGraph tools for Kubernetes operations

@tool
def kubectl_get(resource_type: str, resource_name: str = None, namespace: str = None, output_format: str = "yaml") -> str:
    """
    Execute kubectl get command
    
    Args:
        resource_type: Type of resource (pod, pvc, pv, node, etc.)
        resource_name: Name of resource (optional)
        namespace: Namespace (optional)
        output_format: Output format (yaml, json, wide, etc.)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "get", resource_type]
    
    if resource_name:
        cmd.append(resource_name)
    
    if namespace:
        cmd.extend(["-n", namespace])
        
    if output_format:
        cmd.extend(["-o", output_format])
    else:
        cmd.append("-o=wide")

    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get: {str(e)}"

@tool
def kubectl_describe(resource_type: str, resource_name: str, namespace: str = None) -> str:
    """
    Execute kubectl describe command
    
    Args:
        resource_type: Type of resource (pod, pvc, pv, node, etc.)
        resource_name: Name of resource
        namespace: Namespace (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "describe", resource_type, resource_name]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl describe: {str(e)}"

@tool
def kubectl_apply(yaml_content: str, namespace: str = None) -> str:
    """
    Execute kubectl apply with provided YAML content
    
    Args:
        yaml_content: YAML content to apply
        namespace: Namespace (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "apply", "-f", "-"]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    # Execute command
    try:
        result = subprocess.run(cmd, input=yaml_content, check=True, 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl apply: {str(e)}"

@tool
def kubectl_delete(resource_type: str, resource_name: str, namespace: str = None) -> str:
    """
    Execute kubectl delete command
    
    Args:
        resource_type: Type of resource (pod, pvc, pv, node, etc.)
        resource_name: Name of resource
        namespace: Namespace (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "delete", resource_type, resource_name]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl delete: {str(e)}"

@tool
def kubectl_exec(pod_name: str, command: str, namespace: str = None) -> str:
    """
    Execute command in a pod
    
    Args:
        pod_name: Pod name
        command: Command to execute
        namespace: Namespace (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "exec", pod_name]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    cmd.extend(["--", *command.split()])
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl exec: {str(e)}"

@tool
def kubectl_logs(pod_name: str, namespace: str = None, container: str = None, tail: int = 100) -> str:
    """
    Get logs from a pod
    
    Args:
        pod_name: Pod name
        namespace: Namespace (optional)
        container: Container name (optional)
        tail: Number of lines to show from the end (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["kubectl", "logs", pod_name]
    
    if namespace:
        cmd.extend(["-n", namespace])
    
    if container:
        cmd.extend(["-c", container])
    
    if tail:
        cmd.extend(["--tail", str(tail)])
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl logs: {str(e)}"

# CSI Baremetal-specific tools

@tool
def kubectl_get_drive(drive_uuid: str = None, output_format: str = "wide") -> str:
    """
    Get CSI Baremetal drive information
    
    Args:
        drive_uuid: Drive UUID (optional, gets all drives if not specified)
        output_format: Output format (wide, yaml, json)
        
    Returns:
        str: Command output showing drive status, health, path, etc.
    """
    cmd = ["kubectl", "get", "drive"]
    
    if drive_uuid:
        cmd.append(drive_uuid)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get drive: {str(e)}"

@tool
def kubectl_get_csibmnode(node_name: str = None, output_format: str = "wide") -> str:
    """
    Get CSI Baremetal node information
    
    Args:
        node_name: Node name (optional, gets all nodes if not specified)
        output_format: Output format (wide, yaml, json)
        
    Returns:
        str: Command output showing node mapping and drive associations
    """
    cmd = ["kubectl", "get", "csibmnode"]
    
    if node_name:
        cmd.append(node_name)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get csibmnode: {str(e)}"

@tool
def kubectl_get_availablecapacity(ac_name: str = None, output_format: str = "wide") -> str:
    """
    Get CSI Baremetal available capacity information
    
    Args:
        ac_name: Available capacity name (optional, gets all if not specified)
        output_format: Output format (wide, yaml, json)
        
    Returns:
        str: Command output showing available capacity and storage class mapping
    """
    cmd = ["kubectl", "get", "ac"]
    
    if ac_name:
        cmd.append(ac_name)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get ac: {str(e)}"

@tool
def kubectl_get_logicalvolumegroup(lvg_name: str = None, output_format: str = "wide") -> str:
    """
    Get CSI Baremetal logical volume group information
    
    Args:
        lvg_name: Logical volume group name (optional, gets all if not specified)
        output_format: Output format (wide, yaml, json)
        
    Returns:
        str: Command output showing LVG health and associated drives
    """
    cmd = ["kubectl", "get", "lvg"]
    
    if lvg_name:
        cmd.append(lvg_name)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get lvg: {str(e)}"

@tool
def kubectl_get_storageclass(sc_name: str = None, output_format: str = "yaml") -> str:
    """
    Get storage class information
    
    Args:
        sc_name: Storage class name (optional, gets all if not specified)
        output_format: Output format (yaml, json, wide)
        
    Returns:
        str: Command output showing storage class configuration
    """
    cmd = ["kubectl", "get", "storageclass"]
    
    if sc_name:
        cmd.append(sc_name)
    
    cmd.extend(["-o", output_format])
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get storageclass: {str(e)}"

@tool
def kubectl_get_csidrivers(output_format: str = "wide") -> str:
    """
    Get CSI driver registration information
    
    Args:
        output_format: Output format (wide, yaml, json)
        
    Returns:
        str: Command output showing registered CSI drivers
    """
    cmd = ["kubectl", "get", "csidrivers", "-o", output_format]
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing kubectl get csidrivers: {str(e)}"

# Hardware diagnostic tools

@tool
def smartctl_check(node_name: str, device_path: str) -> str:
    """
    Check disk health using smartctl via SSH
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        
    Returns:
        str: SMART data showing disk health, reallocated sectors, etc.
    """
    cmd = f"sudo smartctl -a {device_path}"
    return ssh_execute(node_name, cmd)

@tool
def fio_performance_test(node_name: str, device_path: str, test_type: str = "read") -> str:
    """
    Test disk performance using fio via SSH
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda)
        test_type: Test type (read, write, randread, randwrite)
        
    Returns:
        str: Performance test results showing IOPS and throughput
    """
    cmd = f"sudo fio --name={test_type}_test --filename={device_path} --rw={test_type} --bs=4k --size=100M --numjobs=1 --iodepth=1 --runtime=60 --time_based --group_reporting"
    return ssh_execute(node_name, cmd)

@tool
def fsck_check(node_name: str, device_path: str, check_only: bool = True) -> str:
    """
    Check file system integrity using fsck via SSH
    
    Args:
        node_name: Node hostname or IP
        device_path: Device path (e.g., /dev/sda1)
        check_only: If True, only check without fixing (safer)
        
    Returns:
        str: File system check results
    """
    if check_only:
        cmd = f"sudo fsck -n {device_path}"  # -n flag means no changes, check only
    else:
        cmd = f"sudo fsck -y {device_path}"  # -y flag means auto-fix (requires approval)
    
    return ssh_execute(node_name, cmd)

@tool
def ssh_execute(node_name: str, command: str) -> str:
    """
    Execute command on remote node via SSH
    
    Args:
        node_name: Node hostname or IP
        command: Command to execute
        
    Returns:
        str: Command output
    """
    try:
        import paramiko
        import os
        
        # Get SSH configuration from global config (would be passed in real implementation)
        ssh_user = "root"  # Default, should come from config
        ssh_key_path = os.path.expanduser("~/.ssh/id_ed25519")  # Default, should come from config
        
        # Create SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Connect using SSH key
            ssh_client.connect(
                hostname=node_name,
                username=ssh_user,
                key_filename=ssh_key_path,
                timeout=30
            )
            
            # Execute command
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=60)
            
            # Get output
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            # Return combined output
            if error:
                return f"Output:\n{output}\nError:\n{error}"
            return output
            
        except Exception as e:
            return f"SSH execution failed: {str(e)}"
        finally:
            ssh_client.close()
            
    except ImportError:
        return f"Error: paramiko not available. Install with: pip install paramiko"
    except Exception as e:
        return f"SSH setup error: {str(e)}"

# System diagnostic tools

@tool
def df_command(path: str = None, options: str = "-h") -> str:
    """
    Execute df command to show disk space usage
    
    Args:
        path: Path to check (optional)
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["df"]
    
    if options:
        cmd.extend(options.split())
    
    if path:
        cmd.append(path)
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing df: {str(e)}"

@tool
def lsblk_command(options: str = "") -> str:
    """
    Execute lsblk command to list block devices
    
    Args:
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["lsblk"]
    
    if options:
        cmd.extend(options.split())
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing lsblk: {str(e)}"

@tool
def mount_command(options: str = "") -> str:
    """
    Execute mount command to show mounted filesystems
    
    Args:
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["mount"]
    
    if options:
        cmd.extend(options.split())
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing mount: {str(e)}"

@tool
def dmesg_command(options: str = "") -> str:
    """
    Execute dmesg command to show kernel messages
    
    Args:
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["dmesg"]
    
    if options:
        cmd.extend(options.split())
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing dmesg: {str(e)}"

@tool
def journalctl_command(options: str = "") -> str:
    """
    Execute journalctl command to show systemd journal logs
    
    Args:
        options: Command options (optional)
        
    Returns:
        str: Command output
    """
    cmd = ["journalctl"]
    
    if options:
        cmd.extend(options.split())
    
    # Execute command
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except Exception as e:
        return f"Error executing journalctl: {str(e)}"
