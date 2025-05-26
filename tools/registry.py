#!/usr/bin/env python3
"""
Tool registry for Kubernetes volume troubleshooting.

This module provides centralized tool registration and discovery,
making it easy to access all available tools from different categories.
"""

from typing import List, Any

# Import all tool modules
from tools.core.knowledge_graph import (
    kg_get_entity_info,
    kg_get_related_entities,
    kg_get_all_issues,
    kg_find_path,
    kg_get_summary,
    kg_analyze_issues,
    kg_print_graph,
    initialize_knowledge_graph,
    get_knowledge_graph
)

from tools.kubernetes.core import (
    kubectl_get,
    kubectl_describe,
    kubectl_apply,
    kubectl_delete,
    kubectl_exec,
    kubectl_logs
)

from tools.kubernetes.csi_baremetal import (
    kubectl_get_drive,
    kubectl_get_csibmnode,
    kubectl_get_availablecapacity,
    kubectl_get_logicalvolumegroup,
    kubectl_get_storageclass,
    kubectl_get_csidrivers
)

from tools.diagnostics.hardware import (
    smartctl_check,
    fio_performance_test,
    fsck_check,
    ssh_execute
)

from tools.diagnostics.system import (
    df_command,
    lsblk_command,
    mount_command,
    dmesg_command,
    journalctl_command
)

def get_all_tools() -> List[Any]:
    """
    Get all available tools for troubleshooting
    
    Returns:
        List[Any]: List of all tool callables
    """
    return [
        # Knowledge Graph tools
        kg_get_entity_info,
        kg_get_related_entities,
        kg_get_all_issues,
        kg_find_path,
        kg_get_summary,
        kg_analyze_issues,
        kg_print_graph,
        
        # Kubernetes core tools
        kubectl_get,
        kubectl_describe,
        kubectl_apply,
        kubectl_delete,
        kubectl_exec,
        kubectl_logs,
        
        # CSI Baremetal specific tools
        kubectl_get_drive,
        kubectl_get_csibmnode,
        kubectl_get_availablecapacity,
        kubectl_get_logicalvolumegroup,
        kubectl_get_storageclass,
        kubectl_get_csidrivers,
        
        # Hardware diagnostic tools
        smartctl_check,
        fio_performance_test,
        fsck_check,
        ssh_execute,
        
        # System diagnostic tools
        df_command,
        lsblk_command,
        mount_command,
        dmesg_command,
        journalctl_command
    ]

def get_knowledge_graph_tools() -> List[Any]:
    """
    Get Knowledge Graph specific tools
    
    Returns:
        List[Any]: List of Knowledge Graph tool callables
    """
    return [
        kg_get_entity_info,
        kg_get_related_entities,
        kg_get_all_issues,
        kg_find_path,
        kg_get_summary,
        kg_analyze_issues,
        kg_print_graph
    ]

def get_kubernetes_tools() -> List[Any]:
    """
    Get Kubernetes related tools (core + CSI Baremetal)
    
    Returns:
        List[Any]: List of Kubernetes tool callables
    """
    return [
        # Core Kubernetes tools
        kubectl_get,
        kubectl_describe,
        kubectl_apply,
        kubectl_delete,
        kubectl_exec,
        kubectl_logs,
        
        # CSI Baremetal specific tools
        kubectl_get_drive,
        kubectl_get_csibmnode,
        kubectl_get_availablecapacity,
        kubectl_get_logicalvolumegroup,
        kubectl_get_storageclass,
        kubectl_get_csidrivers
    ]

def get_diagnostic_tools() -> List[Any]:
    """
    Get diagnostic tools (hardware + system)
    
    Returns:
        List[Any]: List of diagnostic tool callables
    """
    return [
        # Hardware diagnostic tools
        smartctl_check,
        fio_performance_test,
        fsck_check,
        ssh_execute,
        
        # System diagnostic tools
        df_command,
        lsblk_command,
        mount_command,
        dmesg_command,
        journalctl_command
    ]

def get_remediation_tools() -> List[Any]:
    """
    Get tools needed for remediation and analysis phases
    This is the main function used by the troubleshooting system
    
    Returns:
        List[Any]: List of tool callables for investigation and remediation
    """
    return get_all_tools()

# Maintain backward compatibility
define_remediation_tools = get_remediation_tools
