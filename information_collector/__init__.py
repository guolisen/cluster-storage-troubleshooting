"""
Information Collector Package for Kubernetes Volume Troubleshooting

This package implements the Phase 0 information-collection phase that executes diagnostic
LangGraph tools according to parameter's volume path and pod, to collect data and construct
a Knowledge Graph before analysis.

Components:
- ComprehensiveInformationCollector: Main collector class
- VolumeDiscovery: Volume dependency chain discovery
- ToolExecutors: LangGraph tool execution methods
- KnowledgeBuilder: Knowledge Graph construction from tool outputs
- MetadataParsers: Tool output parsing and metadata extraction
"""

from .collector import ComprehensiveInformationCollector

__all__ = ['ComprehensiveInformationCollector']
__version__ = '1.0.0'
