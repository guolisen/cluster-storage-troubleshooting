#!/usr/bin/env python3
"""
Phase 0: Information Collection for Kubernetes Volume Troubleshooting

This module contains the implementation of Phase 0 (Information Collection)
which gathers all necessary diagnostic data upfront.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from rich.console import Console
from rich.panel import Panel

from information_collector import ComprehensiveInformationCollector
from phases.utils import handle_exception

logger = logging.getLogger(__name__)

class InformationCollectionPhase:
    """
    Implementation of Phase 0: Information Collection
    
    This class handles the collection of all necessary diagnostic information
    before starting the troubleshooting process.
    """
    
    def __init__(self, config_data: Dict[str, Any]):
        """
        Initialize the Information Collection Phase
        
        Args:
            config_data: Configuration data for the system
        """
        self.config_data = config_data
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.console = Console()
        self.file_console = Console(file=open('troubleshoot.log', 'w'))
        
    async def collect_information(self, pod_name: str, namespace: str, volume_path: str) -> Dict[str, Any]:
        """
        Collect all necessary diagnostic information
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            Dict[str, Any]: Pre-collected diagnostic information
        """
        self.logger.info(f"Collecting information for pod {namespace}/{pod_name}")
        
        try:
            # Initialize information collector
            info_collector = ComprehensiveInformationCollector(self.config_data)
            
            # Run comprehensive collection
            collection_result = await info_collector.comprehensive_collect(
                target_pod=pod_name,
                target_namespace=namespace,
                target_volume_path=volume_path
            )
            
            # Get the knowledge graph from collection result
            knowledge_graph = collection_result.get('knowledge_graph')
            
            # Format collected data into expected structure
            collected_info = self._format_collected_data(collection_result, knowledge_graph)
            
            self._print_knowledge_graph_summary(knowledge_graph)
            
            return collected_info
            
        except Exception as e:
            error_msg = handle_exception("collect_information", e, self.logger)
            return self._create_empty_collected_info(error_msg)
    
    def _format_collected_data(self, collection_result: Dict[str, Any], knowledge_graph: Any) -> Dict[str, Any]:
        """
        Format collected data into expected structure
        
        Args:
            collection_result: Result from comprehensive collection
            knowledge_graph: Knowledge Graph instance
            
        Returns:
            Dict[str, Any]: Formatted collected data
        """
        return {
            "pod_info": collection_result.get('collected_data', {}).get('kubernetes', {}).get('pods', {}),
            "pvc_info": collection_result.get('collected_data', {}).get('kubernetes', {}).get('pvcs', {}),
            "pv_info": collection_result.get('collected_data', {}).get('kubernetes', {}).get('pvs', {}),
            "node_info": collection_result.get('collected_data', {}).get('kubernetes', {}).get('nodes', {}),
            "csi_driver_info": collection_result.get('collected_data', {}).get('csi_baremetal', {}),
            "storage_class_info": {},  # Will be included in kubernetes data
            "system_info": collection_result.get('collected_data', {}).get('system', {}),
            "knowledge_graph_summary": collection_result.get('context_summary', {}),
            "issues": knowledge_graph.issues if knowledge_graph else [],
            "knowledge_graph": knowledge_graph
        }
    
    def _create_empty_collected_info(self, error_msg: str) -> Dict[str, Any]:
        """
        Create empty collected info structure with error message
        
        Args:
            error_msg: Error message
            
        Returns:
            Dict[str, Any]: Empty collected info structure
        """
        return {
            "collection_error": error_msg,
            "pod_info": {},
            "pvc_info": {},
            "pv_info": {},
            "node_info": {},
            "csi_driver_info": {},
            "storage_class_info": {},
            "system_info": {},
            "knowledge_graph_summary": {},
            "issues": [],
            "knowledge_graph": None
        }
    
    def _print_knowledge_graph_summary(self, knowledge_graph: Any) -> None:
        """
        Print Knowledge Graph summary with rich formatting
        
        Args:
            knowledge_graph: Knowledge Graph instance
        """
        self.console.print("\n")
        self.console.print(Panel(
            "[bold white]Building and analyzing knowledge graph...",
            title="[bold cyan]PHASE 0: INFORMATION COLLECTION - KNOWLEDGE GRAPH",
            border_style="cyan",
            padding=(1, 2)
        ))
        
        try:
            # Try to use rich formatting with proper error handling
            formatted_output = knowledge_graph.print_graph(use_rich=True)
            
            # Handle different output types
            if formatted_output is None:
                # If there was a silent success (no return value)
                self.console.print("[green]Knowledge graph built successfully[/green]")
            elif isinstance(formatted_output, str):
                # Regular string output - print as is
                print(formatted_output)
            else:
                # For any other type of output
                self.console.print("[green]Knowledge graph analysis complete[/green]")
        except Exception as e:
            # Fall back to plain text if rich formatting fails
            error_msg = handle_exception("_print_knowledge_graph_summary", e, self.logger)
            try:
                # Try plain text formatting
                formatted_output = knowledge_graph.print_graph(use_rich=False)
                print(formatted_output)
            except Exception as e2:
                # Last resort fallback
                error_msg = handle_exception("_print_knowledge_graph_summary (plain text fallback)", e2, self.logger)
                print("=" * 80)
                print("KNOWLEDGE GRAPH SUMMARY (FALLBACK FORMAT)")
                print("=" * 80)
                print(f"Total nodes: {knowledge_graph.graph.number_of_nodes()}")
                print(f"Total edges: {knowledge_graph.graph.number_of_edges()}")
                print(f"Total issues: {len(knowledge_graph.issues)}")
        
        self.console.print("\n")


async def run_information_collection_phase(pod_name: str, namespace: str, volume_path: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run Phase 0: Information Collection - Gather all necessary data upfront
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        config_data: Configuration data
        
    Returns:
        Dict[str, Any]: Pre-collected diagnostic information
    """
    logging.info("Starting Phase 0: Information Collection")
    
    try:
        # Initialize the phase
        phase = InformationCollectionPhase(config_data)
        
        # Run the collection
        collected_info = await phase.collect_information(pod_name, namespace, volume_path)
        
        return collected_info
        
    except Exception as e:
        error_msg = handle_exception("run_information_collection_phase", e, logger)
        return {
            "collection_error": error_msg,
            "pod_info": {},
            "pvc_info": {},
            "pv_info": {},
            "node_info": {},
            "csi_driver_info": {},
            "storage_class_info": {},
            "system_info": {},
            "knowledge_graph_summary": {}
        }
