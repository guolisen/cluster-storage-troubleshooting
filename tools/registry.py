#!/usr/bin/env python3
"""
Tool registry for Kubernetes volume troubleshooting.

This module provides centralized tool registration and discovery,
making it easy to access all available tools from different categories.
Supports phase-based tool selection for investigation (Phase 1) and 
action (Phase 2) workflows.
"""

import functools # Added functools
from typing import List, Any, Callable, Dict # Added Callable, Dict

# Assuming KnowledgeGraph class is available via this path
# This might need adjustment based on actual project structure.
try:
    from tools.knowledge_graph import KnowledgeGraph
except ImportError:
    # Fallback if tools.knowledge_graph is not the right path,
    # perhaps it's directly accessible or in tools.core
    try:
        from knowledge_graph import KnowledgeGraph
    except ImportError:
        # If KnowledgeGraph class cannot be imported, tools requiring it will fail.
        # For type hinting purposes, we can define a placeholder if needed,
        # but runtime will be affected.
        KnowledgeGraph = Any # Placeholder if import fails


# Import all tool modules
from tools.core.knowledge_graph import (
    kg_get_entity_info,
    kg_get_related_entities,
    kg_get_all_issues,
    kg_find_path,
    kg_get_summary,
    kg_analyze_issues,
    kg_print_graph
    # initialize_knowledge_graph, get_knowledge_graph REMOVED
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

# Helper function to apply partials for config_data and interactive_mode
def _partial_config_tools(tools: List[Callable[..., Any]], config_data: Dict[str, Any], interactive_mode: bool) -> List[Callable[..., Any]]:
    return [functools.partial(tool, config_data=config_data, interactive_mode=interactive_mode) for tool in tools]

def get_knowledge_graph_tools(kg_instance: KnowledgeGraph) -> List[Callable[..., Any]]:
    """
    Get Knowledge Graph specific tools, with kg_instance partially applied.
    
    Args:
        kg_instance: The KnowledgeGraph instance to use.

    Returns:
        List[Callable[..., Any]]: List of Knowledge Graph tool callables.
    """
    kg_tools_list = [
        kg_get_entity_info,
        kg_get_related_entities,
        kg_get_all_issues,
        kg_find_path,
        kg_get_summary,
        kg_analyze_issues,
        kg_print_graph
    ]
    # The first argument for KG tools is kg_instance
    return [functools.partial(tool, kg_instance) for tool in kg_tools_list]

def get_kubernetes_tools(config_data: Dict[str, Any], interactive_mode: bool) -> List[Callable[..., Any]]:
    """
    Get Kubernetes related tools (core + CSI Baremetal), with context partially applied.
    
    Args:
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.

    Returns:
        List[Callable[..., Any]]: List of Kubernetes tool callables.
    """
    k8s_tools_list = [
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
    return _partial_config_tools(k8s_tools_list, config_data, interactive_mode)

def get_diagnostic_tools(config_data: Dict[str, Any], interactive_mode: bool) -> List[Callable[..., Any]]:
    """
    Get diagnostic tools (hardware + system), with context partially applied.

    Args:
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.

    Returns:
        List[Callable[..., Any]]: List of diagnostic tool callables.
    """
    diag_tools_list = [
        # Hardware diagnostic tools
        smartctl_check,
        fio_performance_test,
        fsck_check,
        xfs_repair_check,
        ssh_execute,
        
        # System diagnostic tools
        df_command,
        lsblk_command,
        mount_command,
        dmesg_command,
        journalctl_command
    ]
    return _partial_config_tools(diag_tools_list, config_data, interactive_mode)

def get_testing_tools() -> List[Callable[..., Any]]:
    """Get testing and validation tools. These tools do not require context arguments.
    
    Returns:
        List[Callable[..., Any]]: List of testing tool callables.
    """
    return [
        create_test_pod, create_test_pvc, create_test_storage_class,
        run_volume_io_test, validate_volume_mount, test_volume_permissions, run_volume_stress_test,
        cleanup_test_resources, list_test_resources, cleanup_specific_test_pod,
        cleanup_orphaned_pvs, force_cleanup_stuck_resources
    ]

def get_all_tools(kg_instance: KnowledgeGraph, config_data: Dict[str, Any], interactive_mode: bool) -> List[Callable[..., Any]]:
    """
    Get all available tools for troubleshooting, with context partially applied.
    
    Args:
        kg_instance: The KnowledgeGraph instance.
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.

    Returns:
        List[Callable[..., Any]]: List of all tool callables.
    """
    all_tools = []
    all_tools.extend(get_knowledge_graph_tools(kg_instance))
    all_tools.extend(get_kubernetes_tools(config_data, interactive_mode))
    all_tools.extend(get_diagnostic_tools(config_data, interactive_mode))
    all_tools.extend(get_testing_tools()) # Testing tools don't need context args
    return all_tools

def get_phase1_tools(kg_instance: KnowledgeGraph, config_data: Dict[str, Any], interactive_mode: bool) -> List[Callable[..., Any]]:
    """
    Get Phase 1 investigation tools (read-only, information gathering), with context partially applied.
    
    Args:
        kg_instance: The KnowledgeGraph instance.
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.

    Returns:
        List[Callable[..., Any]]: List of Phase 1 tool callables.
    """
    phase1_kg_tools = get_knowledge_graph_tools(kg_instance)

    # Define read-only Kubernetes tools
    readonly_k8s_core_tools_list = [kubectl_get, kubectl_describe, kubectl_logs, kubectl_exec]
    readonly_csi_tools_list = [
        kubectl_get_drive, kubectl_get_csibmnode, kubectl_get_availablecapacity,
        kubectl_get_logicalvolumegroup, kubectl_get_storageclass, kubectl_get_csidrivers
    ]

    phase1_k8s_tools = _partial_config_tools(
        readonly_k8s_core_tools_list + readonly_csi_tools_list,
        config_data, interactive_mode
    )

    # Define read-only diagnostic tools
    system_info_tools_list = [df_command, lsblk_command, mount_command, dmesg_command, journalctl_command]
    hardware_info_tools_list = [smartctl_check, xfs_repair_check, ssh_execute] # ssh_execute itself can be read-only based on command

    phase1_diag_tools = _partial_config_tools(
        system_info_tools_list + hardware_info_tools_list,
        config_data, interactive_mode
    )

    return phase1_kg_tools + phase1_k8s_tools + phase1_diag_tools

def get_phase2_tools(kg_instance: KnowledgeGraph, config_data: Dict[str, Any], interactive_mode: bool) -> List[Callable[..., Any]]:
    """
    Get Phase 2 tools (Phase 1 + Action tools), with context partially applied.

    Args:
        kg_instance: The KnowledgeGraph instance.
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.

    Returns:
        List[Callable[..., Any]]: List of Phase 2 tool callables.
    """
    phase1_tools = get_phase1_tools(kg_instance, config_data, interactive_mode)

    action_k8s_tools_list = [kubectl_apply, kubectl_delete]
    action_hardware_tools_list = [fio_performance_test, fsck_check] # fsck can be an action if not check_only
                                                                   # fio is definitely an action.

    action_tools = _partial_config_tools(
        action_k8s_tools_list + action_hardware_tools_list,
        config_data, interactive_mode
    )

    # Testing tools don't need context args applied this way
    testing_tools_list = get_testing_tools()

    return phase1_tools + action_tools + testing_tools_list


def get_remediation_tools(kg_instance: KnowledgeGraph, config_data: Dict[str, Any], interactive_mode: bool) -> List[Callable[..., Any]]:
    """Get tools needed for remediation and analysis phases, with context partially applied.

    This is the main function used by the troubleshooting system.

    Args:
        kg_instance: The KnowledgeGraph instance.
        config_data: Configuration data for command execution.
        interactive_mode: Flag for interactive mode.

    Returns:
        List[Callable[..., Any]]: List of tool callables for investigation and remediation.
    """
    # Currently, remediation tools are considered all tools.
    # This could be refined later if a more specific subset for "remediation" is needed.
    return get_all_tools(kg_instance, config_data, interactive_mode)

# Maintain backward compatibility for the alias, but update its effective signature
define_remediation_tools = get_remediation_tools
