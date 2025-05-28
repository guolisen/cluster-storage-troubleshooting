# Phase-Based LangGraph Tools Enhancement Summary

## Overview
Enhanced the LangGraph troubleshooting system with phase-based tool selection to support a two-phase workflow:
- **Phase 1**: Investigation and root cause analysis (read-only tools)
- **Phase 2**: Action and remediation (investigation tools + action tools)

## Key Enhancements

### 1. New Testing Tools Package (`tools/testing/`)

#### Pod Creation Tools (`tools/testing/pod_creation.py`)
- `create_test_pod()`: Create test pods with volume mounts for validation
- `create_test_pvc()`: Create test PVCs with specified storage classes
- `create_test_storage_class()`: Create test storage classes for CSI Baremetal

#### Volume Testing Tools (`tools/testing/volume_testing.py`)
- `run_volume_io_test()`: Comprehensive I/O testing (read/write/random operations)
- `validate_volume_mount()`: Verify volume mount status and accessibility
- `test_volume_permissions()`: Test read/write/execute permissions
- `run_volume_stress_test()`: Stress test volumes under concurrent load

#### Resource Cleanup Tools (`tools/testing/resource_cleanup.py`)
- `cleanup_test_resources()`: Clean up test resources by label selector
- `list_test_resources()`: List all test resources for monitoring
- `cleanup_specific_test_pod()`: Clean up specific pods and their PVCs
- `cleanup_orphaned_pvs()`: Remove orphaned PVs no longer bound to PVCs
- `force_cleanup_stuck_resources()`: Force cleanup using finalizer removal

### 2. Enhanced Tool Registry (`tools/registry.py`)

#### Phase-Based Tool Functions
- `get_phase1_tools()`: Returns 24 investigation tools (read-only)
  - Knowledge Graph Analysis (7 tools)
  - Read-only Kubernetes (4 tools)
  - CSI Baremetal Info (6 tools)
  - System Information (5 tools)
  - Hardware Information (2 tools)

- `get_phase2_tools()`: Returns 34+ tools (Phase 1 + action tools)
  - All Phase 1 tools (24 tools)
  - Kubernetes Action Tools (2 tools)
  - Hardware Action Tools (2 tools)
  - Testing Tools (10+ tools)

- `get_testing_tools()`: Returns testing and validation tools specifically

### 3. Enhanced Graph Configuration (`graph.py`)

#### Phase-Specific Tool Selection
- Automatically selects appropriate tool set based on phase parameter
- Phase 1: Uses `get_phase1_tools()` for investigation only
- Phase 2: Uses `get_phase2_tools()` for investigation + action

#### Phase-Specific Guidance
- **Phase 1 Guidance**: Comprehensive investigation requirements
  - Root cause analysis methodology
  - Evidence collection standards
  - Issue classification criteria
  - Diagnostic process workflow
  - Output requirements for investigation reports

- **Phase 2 Guidance**: Action and remediation requirements
  - Remediation process workflow
  - Safety requirements for destructive operations
  - Test validation procedures
  - Resource cleanup protocols
  - Output requirements for remediation reports

### 4. Updated Package Exports (`tools/__init__.py`)
- Added exports for new phase-based functions
- Maintained backward compatibility with existing functions
- Updated `__all__` list to include new testing tools

## Tool Categories and Counts

### Phase 1 Tools (24 investigation tools)
1. **Knowledge Graph Analysis (7 tools)**:
   - `kg_get_entity_info`, `kg_get_related_entities`, `kg_get_all_issues`
   - `kg_find_path`, `kg_get_summary`, `kg_analyze_issues`, `kg_print_graph`

2. **Read-only Kubernetes (4 tools)**:
   - `kubectl_get`, `kubectl_describe`, `kubectl_logs`, `kubectl_exec`

3. **CSI Baremetal Info (6 tools)**:
   - `kubectl_get_drive`, `kubectl_get_csibmnode`, `kubectl_get_availablecapacity`
   - `kubectl_get_logicalvolumegroup`, `kubectl_get_storageclass`, `kubectl_get_csidrivers`

4. **System Information (5 tools)**:
   - `df_command`, `lsblk_command`, `mount_command`, `dmesg_command`, `journalctl_command`

5. **Hardware Information (2 tools)**:
   - `smartctl_check`, `ssh_execute` (read-only operations)

### Phase 2 Additional Tools (10+ action tools)
1. **Kubernetes Action Tools (2)**:
   - `kubectl_apply`, `kubectl_delete`

2. **Hardware Action Tools (2)**:
   - `fio_performance_test`, `fsck_check`

3. **Pod/Resource Creation (3)**:
   - `create_test_pod`, `create_test_pvc`, `create_test_storage_class`

4. **Volume Testing (4)**:
   - `run_volume_io_test`, `validate_volume_mount`, `test_volume_permissions`, `run_volume_stress_test`

5. **Resource Cleanup (5)**:
   - `cleanup_test_resources`, `list_test_resources`, `cleanup_specific_test_pod`
   - `cleanup_orphaned_pvs`, `force_cleanup_stuck_resources`

## Workflow Benefits

### Phase 1 (Investigation)
- **Focused Investigation**: Limited to read-only tools prevents accidental changes
- **Comprehensive Analysis**: All necessary tools for root cause analysis
- **Evidence Collection**: Systematic gathering of diagnostic information
- **Risk Mitigation**: No destructive operations during investigation

### Phase 2 (Action/Remediation)
- **Complete Toolkit**: Access to all investigation tools plus action tools
- **Test Validation**: Create test resources to validate fixes safely
- **Controlled Remediation**: Implement fixes with proper testing and cleanup
- **Resource Management**: Comprehensive cleanup capabilities

## Safety Features

### Phase 1 Restrictions
- No destructive operations (`kubectl_apply`, `kubectl_delete`, `fsck_check`)
- No test resource creation
- No hardware modifications
- Focus on comprehensive investigation and root cause analysis

### Phase 2 Safety Requirements
- Always backup data before destructive operations
- Use test resources for validation before affecting production
- Follow proper cleanup procedures
- Verify each step before proceeding to the next
- Document all changes and their outcomes

## Usage Examples

### Phase 1 Investigation
```python
from tools import get_phase1_tools
from graph import create_troubleshooting_graph_with_context

# Create Phase 1 graph for investigation
graph = create_troubleshooting_graph_with_context(
    collected_info=diagnostic_data,
    phase="phase1",
    config_data=config
)

# Run investigation
result = graph.invoke({"messages": [{"role": "user", "content": "Investigate volume I/O errors"}]})
```

### Phase 2 Remediation
```python
from tools import get_phase2_tools
from graph import create_troubleshooting_graph_with_context

# Create Phase 2 graph for action/remediation
graph = create_troubleshooting_graph_with_context(
    collected_info=diagnostic_data,
    phase="phase2",
    config_data=config
)

# Run remediation
result = graph.invoke({"messages": [{"role": "user", "content": "Implement fixes from Phase 1 analysis"}]})
```

## Backward Compatibility
- All existing functions remain available
- Legacy `get_remediation_tools()` still works
- Existing workflows continue to function
- New phase-based approach is opt-in

## Future Enhancements
- Phase 3: Monitoring and validation
- Enhanced test templates for different storage scenarios
- Automated rollback capabilities
- Integration with monitoring systems
- Performance benchmarking tools

This enhancement provides a structured, safe, and comprehensive approach to Kubernetes volume troubleshooting with clear separation between investigation and action phases.
