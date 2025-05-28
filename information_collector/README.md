# Information Collector Package

This package implements the Phase 0 information-collection phase that executes diagnostic LangGraph tools according to parameter's volume path and pod, to collect data and construct a Knowledge Graph before analysis.

## Package Structure

```
information_collector/
├── __init__.py                 # Package initialization and exports
├── README.md                   # This documentation file
├── base.py                     # Base functionality and initialization
├── volume_discovery.py         # Volume dependency chain discovery
├── tool_executors.py           # Tool execution methods
├── metadata_parsers.py         # Metadata parsing from tool outputs
├── knowledge_builder.py        # Knowledge Graph construction
└── collector.py                # Main collector class
```

## Components Overview

### Base Module (`base.py`)
- **InformationCollectorBase**: Base class with core functionality
- Kubernetes client initialization
- Tool execution with validation and approval
- Interactive mode support
- Error handling and logging
- Enhanced context summary creation

### Volume Discovery (`volume_discovery.py`)
- **VolumeDiscovery**: Volume dependency chain discovery functionality
- Discovers volume chains starting from target pods
- Maps pod → PVCs → PVs → drives → nodes relationships
- Extracts storage classes and node affinity information

### Tool Executors (`tool_executors.py`)
- **ToolExecutors**: Tool execution methods for different diagnostic categories
- Pod discovery tools (kubectl get, describe, logs)
- Volume chain discovery tools (PVCs, PVs, StorageClasses)
- CSI Baremetal discovery tools (drives, nodes, capacity, LVGs)
- **Enhanced system log collection** with comprehensive storage keywords:
  - Enhanced dmesg collection with storage-specific filtering
  - Systemd journal logs for storage services and kubelet
  - Boot-time hardware detection logs
  - Filtered by keywords: disk, drive, nvme, ssd, hdd, xfs, slot, etc.

### Metadata Parsers (`metadata_parsers.py`)
- **MetadataParsers**: Metadata parsing methods for different entity types
- Pod metadata extraction (restart count, phase, security context)
- PVC metadata extraction (access modes, storage size, volume mode)
- PV metadata extraction (phase, reclaim policy, capacity, disk path)
- Drive metadata extraction (health, status, type, size, usage)
- Node metadata extraction (ready status, pressure conditions, versions)
- **Advanced log parsing capabilities**:
  - `_parse_dmesg_issues()`: Detects hardware errors, filesystem issues, I/O timeouts
  - `_parse_journal_issues()`: Analyzes systemd logs for storage services and kubelet errors
  - Issue categorization by severity and type

### Knowledge Builder (`knowledge_builder.py`)
- **KnowledgeBuilder**: Knowledge Graph construction from tool outputs
- Builds enhanced Knowledge Graph with rich CSI metadata
- Processes volume chain entities with comprehensive metadata
- Adds CSI Baremetal specific entities (LVGs, Available Capacity)
- Identifies and adds issues for unhealthy components
- **Log-based issue integration**: Automatically adds log-detected issues to knowledge graph
- Links log issues to specific system entities (kernel, kubelet, storage services)

### Main Collector (`collector.py`)
- **ComprehensiveInformationCollector**: Main class combining all components
- Inherits from all other classes using multiple inheritance
- Provides the main `comprehensive_collect()` method
- Orchestrates the complete Phase 0 information collection process

## Usage

```python
from information_collector import ComprehensiveInformationCollector

# Initialize with configuration
config_data = {
    'troubleshoot': {
        'interactive_mode': False
    }
}

collector = ComprehensiveInformationCollector(config_data)

# Perform comprehensive collection
result = await collector.comprehensive_collect(
    target_pod="my-pod",
    target_namespace="default",
    target_volume_path="/data"
)

# Access results
collected_data = result['collected_data']
knowledge_graph = result['knowledge_graph']
context_summary = result['context_summary']
volume_chain = result['volume_chain']
metadata = result['collection_metadata']

# Access log analysis results
log_analysis = collected_data['log_analysis']
dmesg_issues = log_analysis['dmesg_issues']
journal_issues = log_analysis['journal_issues']
```

## Enhanced Log Analysis Features

### Storage Keyword Filtering
The system uses comprehensive keyword filtering to capture storage-related log entries:

**Hardware/Device Keywords:**
- `disk`, `drive`, `nvme`, `ssd`, `hdd`, `scsi`, `sata`, `pcie`
- `slot`, `bay`, `controller`, `adapter`, `raid`

**Filesystem/Storage Keywords:**
- `xfs`, `ext4`, `btrfs`, `ntfs`, `fat32`
- `mount`, `umount`, `filesystem`, `fsck`

**Error/Status Keywords:**
- `error`, `fail`, `timeout`, `corrupt`, `bad`, `sector`
- `i/o`, `io`, `read`, `write`, `sync`

**CSI/Kubernetes Storage:**
- `csi`, `kubelet`, `volume`, `pv`, `pvc`, `storageclass`
- `baremetal-csi`, `lvg`, `lvs`, `vg`

### Log Sources Analyzed
1. **Kernel logs (dmesg)**: Hardware errors, driver issues, I/O problems
2. **Systemd journal logs**: Service failures, storage daemon issues
3. **Kubelet service logs**: Volume mount/attach failures, CSI driver errors
4. **Boot logs**: Hardware detection issues, initialization failures

### Issue Detection and Classification
- **Hardware Issues**: Disk errors, bad sectors, controller failures, NVMe/SSD issues
- **Filesystem Issues**: XFS corruption, mount failures, I/O errors
- **Kubernetes Storage Issues**: CSI driver errors, volume attach/detach failures
- **Service Issues**: Storage service failures, kubelet volume plugin errors

## Key Features

- **Volume-focused tool selection and execution**: Targets diagnostic tools based on discovered volume dependencies
- **LangGraph tools integration**: Integrates with existing LangGraph tool ecosystem
- **Interactive mode support**: Optional user approval for tool execution
- **Enhanced Knowledge Graph construction**: Rich metadata extraction and issue identification
- **Structured tool output processing**: Organized storage and processing of tool outputs
- **Error handling and logging**: Comprehensive error tracking and logging
- **CSI Baremetal metadata extraction**: Specialized extraction for CSI Baremetal components
- **Comprehensive log analysis**: Advanced parsing of dmesg and systemd journal logs with storage-specific keyword filtering
- **Automated issue detection**: Pattern matching for common storage infrastructure problems
- **Log-to-knowledge-graph integration**: Automatic correlation of log issues with system entities

## Dependencies

- kubernetes
- knowledge_graph
- tools (LangGraph tools module)
- Standard Python libraries: os, yaml, logging, asyncio, time, subprocess, json, paramiko

## Inheritance Hierarchy

```
InformationCollectorBase
├── VolumeDiscovery
├── ToolExecutors  
├── MetadataParsers
│   └── KnowledgeBuilder
└── ComprehensiveInformationCollector (combines all)
```

The package uses multiple inheritance to combine functionality while maintaining clear separation of concerns. Each module focuses on a specific aspect of the information collection process.

## Log Analysis Data Structure

The enhanced log analysis creates structured data for troubleshooting:

```python
collected_data['log_analysis'] = {
    'dmesg_issues': [
        {
            'type': 'disk_hardware_error',
            'severity': 'critical',
            'description': 'Hardware disk error detected: ...',
            'raw_log': '...',
            'source': 'dmesg'
        }
    ],
    'journal_issues': [
        {
            'type': 'kubelet_volume_error',
            'severity': 'high', 
            'description': 'Kubelet volume error: ...',
            'raw_log': '...',
            'source': 'journal_kubelet'
        }
    ],
    'total_issues': 15
}
```

This enhanced log analysis provides deep insights into storage infrastructure health and helps identify root causes of volume-related issues in Kubernetes environments.
