# Tools Package for Kubernetes Volume Troubleshooting

This package provides a comprehensive set of tools organized by category for Kubernetes volume I/O error troubleshooting.

## Package Structure

```
tools/
├── __init__.py                    # Main package exports
├── README.md                      # This documentation
├── registry.py                    # Tool registration and discovery
├── core/
│   ├── __init__.py
│   ├── config.py                  # Global config, validation, execution utilities
│   └── knowledge_graph.py         # Knowledge Graph management and tools
├── kubernetes/
│   ├── __init__.py
│   ├── core.py                    # Basic kubectl operations
│   └── csi_baremetal.py          # CSI Baremetal specific tools
└── diagnostics/
    ├── __init__.py
    ├── hardware.py               # Hardware diagnostic tools
    └── system.py                 # System diagnostic tools
```

## Tool Categories

### Core Tools (7 tools)
- **Knowledge Graph Tools**: Entity queries, relationship analysis, issue management
  - `kg_get_entity_info`, `kg_get_related_entities`, `kg_get_all_issues`
  - `kg_find_path`, `kg_get_summary`, `kg_analyze_issues`, `kg_print_graph`

### Kubernetes Tools (12 tools)
- **Core Kubernetes Tools**: Basic kubectl operations
  - `kubectl_get`, `kubectl_describe`, `kubectl_apply`, `kubectl_delete`
  - `kubectl_exec`, `kubectl_logs`
- **CSI Baremetal Tools**: CSI-specific custom resources
  - `kubectl_get_drive`, `kubectl_get_csibmnode`, `kubectl_get_availablecapacity`
  - `kubectl_get_logicalvolumegroup`, `kubectl_get_storageclass`, `kubectl_get_csidrivers`

### Diagnostic Tools (9 tools)
- **Hardware Diagnostics**: Hardware-level checks
  - `smartctl_check`, `fio_performance_test`, `fsck_check`, `ssh_execute`
- **System Diagnostics**: System-level information
  - `df_command`, `lsblk_command`, `mount_command`, `dmesg_command`, `journalctl_command`

## Usage Examples

### Import All Tools
```python
from tools import get_all_tools
tools = get_all_tools()  # Returns all 28 tools
```

### Import by Category
```python
from tools import get_kubernetes_tools, get_diagnostic_tools
k8s_tools = get_kubernetes_tools()
diag_tools = get_diagnostic_tools()
```

### Import Specific Tools
```python
from tools.kubernetes import kubectl_get, kubectl_describe
from tools.diagnostics import smartctl_check, df_command
from tools.core import kg_get_entity_info
```

### Initialize Knowledge Graph
```python
from tools import initialize_knowledge_graph
kg = initialize_knowledge_graph()
```

## Backward Compatibility

The original `tools.py` file has been updated to serve as a compatibility layer. All existing imports will continue to work:

```python
# This still works
from tools import define_remediation_tools
from tools import kubectl_get, kg_get_entity_info
```

## Benefits of the New Structure

1. **Logical Organization**: Tools are grouped by functionality
2. **Better Maintainability**: Each category is in its own module
3. **Cleaner Imports**: Import only what you need
4. **Extensibility**: Easy to add new tool categories
5. **Testing**: Each module can be tested independently
6. **Documentation**: Clear separation of concerns

## Migration Guide

For new code, prefer importing from the specific modules:

```python
# Old way (still works)
from tools import kubectl_get

# New way (recommended)
from tools.kubernetes import kubectl_get
```

This provides better IDE support and makes dependencies clearer.
