#!/usr/bin/env python3
"""
LangGraph Tools for Kubernetes Volume I/O Error Troubleshooting

This module serves as a compatibility layer for the reorganized tools package.
All tools have been moved to the tools/ package with better organization.

For new code, import directly from the tools package:
    from tools import get_all_tools, initialize_knowledge_graph
    from tools.kubernetes import kubectl_get
    from tools.diagnostics import smartctl_check
"""

# Import everything from the new tools package for backward compatibility
from tools import *
from tools.registry import define_remediation_tools

# Re-export core utilities with original names for compatibility
from tools.core.config import (
    INTERACTIVE_MODE,
    CONFIG_DATA,
    validate_command,
    execute_command
)

from tools.core.knowledge_graph import (
    initialize_knowledge_graph,
    get_knowledge_graph
)

# Re-export all individual tools for backward compatibility
from tools.core.knowledge_graph import (
    kg_get_entity_info,
    kg_get_related_entities,
    kg_get_all_issues,
    kg_find_path,
    kg_get_summary,
    kg_analyze_issues,
    kg_print_graph,
    # Entity ID helper tools
    kg_get_entity_of_pod,
    kg_get_entity_of_pvc,
    kg_get_entity_of_pv,
    kg_get_entity_of_drive,
    kg_get_entity_of_node,
    kg_get_entity_of_storage_class,
    kg_get_entity_of_lvg,
    kg_get_entity_of_ac,
    kg_get_entity_of_volume,
    kg_get_entity_of_system,
    kg_get_entity_of_cluster_node,
    kg_get_entity_of_historical_experience
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

# Maintain the original function for backward compatibility
def define_remediation_tools():
    """
    Define tools needed for remediation and analysis phases
    
    Returns:
        List[Any]: List of tool callables for investigation and remediation
    """
    return get_all_tools()
