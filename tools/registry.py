#!/usr/bin/env python3
"""
Tool registry for Kubernetes volume troubleshooting.

This module provides centralized tool registration and discovery,
making it easy to access all available tools from different categories.
Supports phase-based tool selection for investigation (Phase 1) and 
action (Phase 2) workflows.
"""

from typing import List, Dict, Any
from tools.core.mcp_adapter import get_mcp_adapter

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
    kubectl_logs,
    kubectl_ls_pod_volume
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
    xfs_repair_check,
    #ssh_execute
)

from tools.diagnostics.system import (
    df_command,
    lsblk_command,
    mount_command,
    dmesg_command,
    journalctl_command,
    get_system_hardware_info
)

# Import new disk check tools
from tools.diagnostics.disk_monitoring import (
    detect_disk_jitter
)

from tools.diagnostics.disk_performance import (
    run_disk_readonly_test,
    test_disk_io_performance
)

from tools.diagnostics.disk_analysis import (
    check_disk_health,
    analyze_disk_space_usage,
    scan_disk_error_logs
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
    run_volume_stress_test,
    verify_volume_mount,
    test_volume_io_performance,
    monitor_volume_latency,
    check_pod_volume_filesystem,
    analyze_volume_space_usage,
    check_volume_data_integrity
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
        kubectl_ls_pod_volume,
        
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
        xfs_repair_check,
        #ssh_execute,
        
        # System diagnostic tools
        df_command,
        lsblk_command,
        mount_command,
        dmesg_command,
        journalctl_command,
        get_system_hardware_info,
        
        # New disk check tools
        detect_disk_jitter,
        run_disk_readonly_test,
        test_disk_io_performance,
        check_disk_health,
        analyze_disk_space_usage,
        scan_disk_error_logs,
        
        # Volume testing tools
        run_volume_io_test,
        validate_volume_mount,
        test_volume_permissions,
        run_volume_stress_test,
        verify_volume_mount,
        test_volume_io_performance,
        monitor_volume_latency,
        check_pod_volume_filesystem,
        analyze_volume_space_usage,
        check_volume_data_integrity
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
        kubectl_ls_pod_volume,
        
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
        xfs_repair_check,
        #ssh_execute,
        
        # System diagnostic tools
        df_command,
        lsblk_command,
        mount_command,
        dmesg_command,
        journalctl_command,
        get_system_hardware_info,
        
        # New disk check tools
        detect_disk_jitter,
        run_disk_readonly_test,
        test_disk_io_performance,
        check_disk_health,
        analyze_disk_space_usage,
        scan_disk_error_logs
    ]

def get_phase1_tools() -> List[Any]:
    """
    Get Phase 1 investigation tools (read-only, information gathering)
    
    Phase 1 focuses on comprehensive investigation, root cause analysis,
    and evidence collection without any destructive operations.
    
    Returns:
        List[Any]: List of Phase 1 tool callables
    """
    return [
        # Knowledge Graph tools - Full analysis capabilities
        kg_get_entity_info,
        kg_get_related_entities,
        kg_get_all_issues,
        kg_find_path,
        kg_get_summary,
        kg_analyze_issues,
        kg_print_graph,
        
        # Read-only Kubernetes tools
        kubectl_get,
        kubectl_describe,
        kubectl_logs,
        kubectl_exec,  # Limited to read-only commands
        kubectl_ls_pod_volume,  # New tool for listing pod volume contents
        
        # CSI Baremetal information tools
        kubectl_get_drive,
        kubectl_get_csibmnode,
        kubectl_get_availablecapacity,
        kubectl_get_logicalvolumegroup,
        kubectl_get_storageclass,
        kubectl_get_csidrivers,
        
        # System information tools
        df_command,
        lsblk_command,
        mount_command,
        dmesg_command,
        journalctl_command,
        get_system_hardware_info,
        
        # Hardware information tools
        smartctl_check,  # Read-only disk health check
        xfs_repair_check,  # Read-only file system check
        #ssh_execute,     # Limited to read-only operations
        
        # New read-only disk check tools
        detect_disk_jitter,  # Monitoring tool
        check_disk_health,   # Disk health assessment
        analyze_disk_space_usage,  # Space usage analysis
        scan_disk_error_logs,  # Log scanning
        run_disk_readonly_test,
        test_disk_io_performance,  # Read-only I/O performance test

        # Volume testing tools - Read-only checks
        run_volume_io_test,
        verify_volume_mount,
        test_volume_io_performance,
        test_volume_permissions,
        run_volume_stress_test,  # Non-destructive stress test
        monitor_volume_latency,
        check_pod_volume_filesystem,
        analyze_volume_space_usage,
        check_volume_data_integrity,
    ]

def get_phase2_tools() -> List[Any]:
    """
    Get Phase 2 tools (Phase 1 + Action tools)
    
    Phase 2 includes all Phase 1 investigation tools PLUS action tools
    for remediation, testing, and resource management.
    
    Returns:
        List[Any]: List of Phase 2 tool callables
    """
    return get_phase1_tools() + [
        # Additional Kubernetes action tools
        kubectl_apply,
        kubectl_delete,
        
        # Hardware action tools
        fio_performance_test,
        fsck_check,
        
        # New disk performance testing tools
        run_disk_readonly_test,   # Read-only test
        test_disk_io_performance, # I/O performance test
        
        # Testing tools - Pod/Resource creation
        #create_test_pod,
        #create_test_pvc,
        #create_test_storage_class,
        
        # Testing tools - Volume testing
        run_volume_io_test,
        validate_volume_mount,
        test_volume_permissions,
        run_volume_stress_test,
        verify_volume_mount,
        test_volume_io_performance,
        monitor_volume_latency,
        check_pod_volume_filesystem,
        analyze_volume_space_usage,
        check_volume_data_integrity,
        
        # Testing tools - Resource cleanup
        #cleanup_test_resources,
        #list_test_resources,
        #cleanup_specific_test_pod,
        #cleanup_orphaned_pvs,
        #force_cleanup_stuck_resources
    ]

def get_testing_tools() -> List[Any]:
    """
    Get testing and validation tools for Phase 2
    
    Returns:
        List[Any]: List of testing tool callables
    """
    return [
        # Pod/Resource creation tools
        #create_test_pod,
        #create_test_pvc,
        #create_test_storage_class,
        
        # Volume testing tools
        run_volume_io_test,
        validate_volume_mount,
        test_volume_permissions,
        run_volume_stress_test,
        
        # Resource cleanup tools
        #cleanup_test_resources,
        #list_test_resources,
        #cleanup_specific_test_pod,
        #cleanup_orphaned_pvs,
        #force_cleanup_stuck_resources,
        
        # New disk performance testing tools
        run_disk_readonly_test,
        test_disk_io_performance,
        verify_volume_mount,
        test_volume_io_performance,
        monitor_volume_latency,
        check_pod_volume_filesystem,
        analyze_volume_space_usage,
        check_volume_data_integrity
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
