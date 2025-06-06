#!/usr/bin/env python3
"""
Tool registry for Kubernetes volume troubleshooting.

This module provides centralized tool registration and discovery,
making it easy to access all available tools from different categories.
Supports phase-based tool selection for investigation (Phase 1) and 
action (Phase 2) workflows.
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
    xfs_repair_check,  # Added xfs_repair_check for XFS file system checks
    ssh_execute
)

from tools.diagnostics.system import (
    df_command,
    lsblk_command,
    mount_command,
    dmesg_command,
    journalctl_command
)

# Import testing tools
from tools.testing.pod_creation import (
    create_test_pod,
    create_test_pvc,
    create_test_storage_class
)

from tools.testing.volume_testing import (
    run_volume_io_test,
    validate_volume_mount,
    test_volume_permissions,
    run_volume_stress_test
)

from tools.testing.resource_cleanup import (
    cleanup_test_resources,
    list_test_resources,
    cleanup_specific_test_pod,
    cleanup_orphaned_pvs,
    force_cleanup_stuck_resources
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
        xfs_repair_check,  # Added XFS file system check
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
        xfs_repair_check,  # Added XFS file system check
        ssh_execute,
        
        # System diagnostic tools
        df_command,
        lsblk_command,
        mount_command,
        dmesg_command,
        journalctl_command
    ]

def get_phase1_tools() -> List[Any]:
    """
    Get Phase 1 investigation tools (read-only, information gathering)
    
    Phase 1 focuses on comprehensive investigation, root cause analysis,
    and evidence collection without any destructive operations.
    
    Returns:
        List[Any]: List of Phase 1 tool callables (24 tools)
    """
    return [
        # Knowledge Graph tools (7 tools) - Full analysis capabilities
        kg_get_entity_info,
        kg_get_related_entities,
        kg_get_all_issues,
        kg_find_path,
        kg_get_summary,
        kg_analyze_issues,
        kg_print_graph,
        
        # Read-only Kubernetes tools (4 tools)
        kubectl_get,
        kubectl_describe,
        kubectl_logs,
        kubectl_exec,  # Limited to read-only commands
        
        # CSI Baremetal information tools (6 tools)
        kubectl_get_drive,
        kubectl_get_csibmnode,
        kubectl_get_availablecapacity,
        kubectl_get_logicalvolumegroup,
        kubectl_get_storageclass,
        kubectl_get_csidrivers,
        
        # System information tools (5 tools)
        df_command,
        lsblk_command,
        mount_command,
        dmesg_command,
        journalctl_command,
        
        # Hardware information tools (2 tools)
        smartctl_check,  # Read-only disk health check
        xfs_repair_check,  # Read-only XFS file system check
        ssh_execute     # Limited to read-only operations
    ]

def get_phase2_tools() -> List[Any]:
    """
    Get Phase 2 tools (Phase 1 + Action tools)
    
    Phase 2 includes all Phase 1 investigation tools PLUS action tools
    for remediation, testing, and resource management.
    
    Returns:
        List[Any]: List of Phase 2 tool callables (34+ tools)
    """
    return get_phase1_tools() + [
        # Additional Kubernetes action tools
        kubectl_apply,
        kubectl_delete,
        
        # Hardware action tools
        fio_performance_test,
        fsck_check,
        
        # Testing tools - Pod/Resource creation
        create_test_pod,
        create_test_pvc,
        create_test_storage_class,
        
        # Testing tools - Volume testing
        run_volume_io_test,
        validate_volume_mount,
        test_volume_permissions,
        run_volume_stress_test,
        
        # Testing tools - Resource cleanup
        cleanup_test_resources,
        list_test_resources,
        cleanup_specific_test_pod,
        cleanup_orphaned_pvs,
        force_cleanup_stuck_resources
    ]

def get_testing_tools() -> List[Any]:
    """
    Get testing and validation tools for Phase 2
    
    Returns:
        List[Any]: List of testing tool callables
    """
    return [
        # Pod/Resource creation tools
        create_test_pod,
        create_test_pvc,
        create_test_storage_class,
        
        # Volume testing tools
        run_volume_io_test,
        validate_volume_mount,
        test_volume_permissions,
        run_volume_stress_test,
        
        # Resource cleanup tools
        cleanup_test_resources,
        list_test_resources,
        cleanup_specific_test_pod,
        cleanup_orphaned_pvs,
        force_cleanup_stuck_resources
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
