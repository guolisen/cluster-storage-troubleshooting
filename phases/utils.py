#!/usr/bin/env python3
"""
Common Utilities for Kubernetes Volume Troubleshooting Phases

This module contains common utility functions used across different phases
of the troubleshooting process to reduce code duplication and improve maintainability.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def validate_knowledge_graph(knowledge_graph: Any, caller_name: str = "Unknown") -> bool:
    """
    Validate that the provided object is a valid KnowledgeGraph instance

    Args:
        knowledge_graph: Object to validate
        caller_name: Name of the calling module/class for logging

    Returns:
        bool: True if valid, False otherwise

    Raises:
        ValueError: If the knowledge graph is invalid
    """
    logger.debug(f"Validating knowledge graph from {caller_name}")
    
    if not hasattr(knowledge_graph, 'graph'):
        error_msg = "Invalid Knowledge Graph: missing 'graph' attribute"
        logger.error(f"{caller_name}: {error_msg}")
        raise ValueError(error_msg)
    
    if not hasattr(knowledge_graph, 'get_all_issues'):
        error_msg = "Invalid Knowledge Graph: missing 'get_all_issues' method"
        logger.error(f"{caller_name}: {error_msg}")
        raise ValueError(error_msg)
    
    return True


def format_historical_experiences(knowledge_graph: Any) -> str:
    """
    Format historical experience data from a Knowledge Graph

    Args:
        knowledge_graph: Knowledge Graph containing historical experience data

    Returns:
        str: Formatted historical experience data for LLM consumption
    """
    try:
        # Check if knowledge graph is valid
        if not knowledge_graph or not hasattr(knowledge_graph, 'graph'):
            return "No historical experience data available."
        
        # Find historical experience nodes
        historical_experience_nodes = []
        for node_id, attrs in knowledge_graph.graph.nodes(data=True):
            if attrs.get('gnode_subtype') == 'HistoricalExperience':
                historical_experience_nodes.append((node_id, attrs))
        
        if not historical_experience_nodes:
            return "No historical experience data available."
        
        # Format historical experiences in a clear, structured way
        formatted_entries = []
        
        for idx, (node_id, attrs) in enumerate(historical_experience_nodes, 1):
            # Get attributes from the experience
            phenomenon = attrs.get('phenomenon', 'Unknown phenomenon')
            root_cause = attrs.get('root_cause', 'Unknown root cause')
            localization_method = attrs.get('localization_method', 'No localization method provided')
            resolution_method = attrs.get('resolution_method', 'No resolution method provided')
            
            # Format the entry
            entry = f"""HISTORICAL EXPERIENCE #{idx}:
Phenomenon: {phenomenon}
Root Cause: {root_cause}
Localization Method: {localization_method}
Resolution Method: {resolution_method}
"""
            formatted_entries.append(entry)
        
        return "\n".join(formatted_entries)
        
    except Exception as e:
        logger.warning(f"Error formatting historical experiences: {str(e)}")
        return "Error formatting historical experience data."


def format_historical_experiences_from_collected_info(collected_info: Dict[str, Any]) -> str:
    """
    Format historical experience data from collected information

    Args:
        collected_info: Pre-collected diagnostic information from Phase 0

    Returns:
        str: Formatted historical experience data for LLM consumption
    """
    try:
        # Extract historical experiences from knowledge graph in collected_info
        kg = collected_info.get('knowledge_graph', None)
        return format_historical_experiences(kg)
        
    except Exception as e:
        logger.warning(f"Error formatting historical experiences from collected info: {str(e)}")
        return "Error formatting historical experience data."


def generate_basic_fallback_plan(pod_name: str, namespace: str, volume_path: str) -> str:
    """
    Generate a basic fallback investigation plan when all else fails

    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error

    Returns:
        str: Basic fallback Investigation Plan
    """
    basic_plan = f"""Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}
Generated Steps: 4 basic steps (fallback mode)

Step 1: Get all critical issues from Knowledge Graph | Tool: kg_get_all_issues(severity='critical') | Expected: List of critical issues affecting the system
Step 2: Analyze existing issues and patterns | Tool: kg_analyze_issues() | Expected: Root cause analysis and issue relationships  
Step 3: Get system overview | Tool: kg_get_summary() | Expected: Overall system health and entity statistics
Step 4: Print complete Knowledge Graph for manual analysis | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Full system visualization for troubleshooting

Fallback Steps (if main steps fail):
Step F1: Search for any Pod entities | Tool: kg_get_related_entities(entity_type='Pod', entity_id='any', max_depth=1) | Expected: List of all Pods | Trigger: entity_not_found
Step F2: Search for any Drive entities | Tool: kg_get_related_entities(entity_type='Drive', entity_id='any', max_depth=1) | Expected: List of all Drives | Trigger: no_target_found
"""
    return basic_plan


def handle_exception(func_name: str, exception: Exception, logger_instance: Optional[logging.Logger] = None) -> str:
    """
    Standardized exception handling with proper logging

    Args:
        func_name: Name of the function where the exception occurred
        exception: The exception that was raised
        logger_instance: Logger instance to use, defaults to module logger if None

    Returns:
        str: Formatted error message
    """
    log = logger_instance or logger
    error_msg = f"Error in {func_name}: {str(exception)}"
    log.error(error_msg)
    return error_msg


def format_json_safely(data: Any, indent: int = 2, fallback_message: str = "Unable to format data") -> str:
    """
    Safely format data as JSON with fallback for non-serializable objects

    Args:
        data: Data to format as JSON
        indent: JSON indentation level
        fallback_message: Message to use if formatting fails

    Returns:
        str: JSON-formatted string or fallback message
    """
    import json
    
    try:
        # Try to convert to JSON using custom serializer
        def json_serializer(obj):
            """Custom JSON serializer to handle non-serializable objects"""
            try:
                # Try to convert to a simple dict first
                if hasattr(obj, "__dict__"):
                    return obj.__dict__
                # Handle sets
                elif isinstance(obj, set):
                    return list(obj)
                # Handle other non-serializable types
                else:
                    return str(obj)
            except:
                return str(obj)
        
        return json.dumps(data, indent=indent, default=json_serializer)
    except Exception as e:
        logger.warning(f"Error serializing data to JSON: {str(e)}")
        # Fallback to a simpler representation
        return fallback_message
