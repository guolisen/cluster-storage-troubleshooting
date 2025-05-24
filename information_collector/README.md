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
- Node and system discovery tools (nodes, disk usage, block devices, kernel logs)

### Metadata Parsers (`metadata_parsers.py`)
- **MetadataParsers**: Metadata parsing methods for different entity types
- Pod metadata extraction (restart count, phase, security context)
- PVC metadata extraction (access modes, storage size, volume mode)
- PV metadata extraction (phase, reclaim policy, capacity, disk path)
- Drive metadata extraction (health, status, type, size, usage)
- Node metadata extraction (ready status, pressure conditions, versions)

### Knowledge Builder (`knowledge_builder.py`)
- **KnowledgeBuilder**: Knowledge Graph construction from tool outputs
- Builds enhanced Knowledge Graph with rich CSI metadata
- Processes volume chain entities with comprehensive metadata
- Adds CSI Baremetal specific entities (LVGs, Available Capacity)
- Identifies and adds issues for unhealthy components

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
```

## Key Features

- **Volume-focused tool selection and execution**: Targets diagnostic tools based on discovered volume dependencies
- **LangGraph tools integration**: Integrates with existing LangGraph tool ecosystem
- **Interactive mode support**: Optional user approval for tool execution
- **Enhanced Knowledge Graph construction**: Rich metadata extraction and issue identification
- **Structured tool output processing**: Organized storage and processing of tool outputs
- **Error handling and logging**: Comprehensive error tracking and logging
- **CSI Baremetal metadata extraction**: Specialized extraction for CSI Baremetal components

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
