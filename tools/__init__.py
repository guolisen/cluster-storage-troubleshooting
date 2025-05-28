#!/usr/bin/env python3
"""
Tools package for Kubernetes volume troubleshooting.

This package provides a comprehensive set of tools organized by category:
- core: Configuration, utilities, and Knowledge Graph tools
- kubernetes: Kubernetes operations (core and CSI Baremetal specific)
- diagnostics: Hardware and system diagnostic tools
- registry: Centralized tool registration and discovery
"""

# Import main registry functions for easy access
from tools.registry import (
    get_all_tools,
    get_knowledge_graph_tools,
    get_kubernetes_tools,
    get_diagnostic_tools,
    get_phase1_tools,
    get_phase2_tools,
    get_testing_tools,
    get_remediation_tools,
    define_remediation_tools
)

# Import core utilities
from tools.core.config import (
    INTERACTIVE_MODE,
    CONFIG_DATA,
    validate_command,
    execute_command
)

from tools.core.knowledge_graph import (
    initialize_knowledge_graph,
    get_knowledge_graph,
    kg_get_entity_info,
    kg_get_related_entities,
    kg_get_all_issues,
    kg_find_path,
    kg_get_summary,
    kg_analyze_issues,
    kg_print_graph
)

# Import all individual tools for backward compatibility
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

__all__ = [
    # Registry functions
    'get_all_tools',
    'get_knowledge_graph_tools',
    'get_kubernetes_tools',
    'get_diagnostic_tools',
    'get_phase1_tools',
    'get_phase2_tools',
    'get_testing_tools',
    'get_remediation_tools',
    'define_remediation_tools',
    
    # Core utilities
    'INTERACTIVE_MODE',
    'CONFIG_DATA',
    'validate_command',
    'execute_command',
    'initialize_knowledge_graph',
    'get_knowledge_graph',
    
    # Knowledge Graph tools
    'kg_get_entity_info',
    'kg_get_related_entities',
    'kg_get_all_issues',
    'kg_find_path',
    'kg_get_summary',
    'kg_analyze_issues',
    'kg_print_graph',
    
    # Kubernetes core tools
    'kubectl_get',
    'kubectl_describe',
    'kubectl_apply',
    'kubectl_delete',
    'kubectl_exec',
    'kubectl_logs',
    
    # CSI Baremetal tools
    'kubectl_get_drive',
    'kubectl_get_csibmnode',
    'kubectl_get_availablecapacity',
    'kubectl_get_logicalvolumegroup',
    'kubectl_get_storageclass',
    'kubectl_get_csidrivers',
    
    # Hardware diagnostic tools
    'smartctl_check',
    'fio_performance_test',
    'fsck_check',
    'ssh_execute',
    
    # System diagnostic tools
    'df_command',
    'lsblk_command',
    'mount_command',
    'dmesg_command',
    'journalctl_command'
]
