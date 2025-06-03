#!/usr/bin/env python3
"""
Phase 0: Information Collection for Kubernetes Volume Troubleshooting

This module contains the implementation of Phase 0 (Information Collection)
which gathers all necessary diagnostic data upfront.
"""

import logging
import time
import atexit
from typing import Dict, List, Any, Optional, Tuple
from rich.console import Console
from rich.panel import Panel

from information_collector import ComprehensiveInformationCollector

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
        
        # Open log file and register cleanup handler
        self.log_file = open('troubleshoot.log', 'w')
        self.file_console = Console(file=self.log_file)
        atexit.register(self._cleanup_resources)
    
    def _cleanup_resources(self):
        """
        Clean up resources when the object is destroyed
        """
        try:
            if hasattr(self, 'log_file') and self.log_file and not self.log_file.closed:
                self.log_file.close()
                self.logger.info("Log file closed")
        except Exception as e:
            self.logger.error(f"Error closing log file: {e}")
        
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
            # Initialize and run information collector
            collection_result = await self._run_information_collector(
                pod_name, namespace, volume_path
            )
            
            # Format collected data into expected structure
            collected_info = self._format_collection_result(collection_result)
            
            # Get the knowledge graph from collection result
            knowledge_graph = collection_result.get('knowledge_graph')
            collected_info["knowledge_graph"] = knowledge_graph
            
            # Print knowledge graph summary
            self._print_knowledge_graph_summary(knowledge_graph)
            
            return collected_info
            
        except Exception as e:
            error_msg = f"Error during information collection phase: {str(e)}"
            self.logger.error(error_msg)
            return self._create_error_result(error_msg)
    
    async def _run_information_collector(self, pod_name: str, namespace: str, 
                                       volume_path: str) -> Dict[str, Any]:
        """
        Initialize and run the information collector
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            Dict[str, Any]: Collection result
        """
        # Initialize information collector
        info_collector = ComprehensiveInformationCollector(self.config_data)
        
        # Run comprehensive collection
        return await info_collector.comprehensive_collect(
            target_pod=pod_name,
            target_namespace=namespace,
            target_volume_path=volume_path
        )
    
    def _format_collection_result(self, collection_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format the collection result into the expected structure
        
        Args:
            collection_result: Raw collection result from the information collector
            
        Returns:
            Dict[str, Any]: Formatted collection result
        """
        # Extract collected data
        collected_data = collection_result.get('collected_data', {})
        kubernetes_data = collected_data.get('kubernetes', {})
        
        # Get the knowledge graph from collection result
        knowledge_graph = collection_result.get('knowledge_graph')
        
        # Format collected data into expected structure
        return {
            "pod_info": kubernetes_data.get('pods', {}),
            "pvc_info": kubernetes_data.get('pvcs', {}),
            "pv_info": kubernetes_data.get('pvs', {}),
            "node_info": kubernetes_data.get('nodes', {}),
            "csi_driver_info": collected_data.get('csi_baremetal', {}),
            "storage_class_info": kubernetes_data.get('storage_classes', {}),
            "system_info": collected_data.get('system', {}),
            "knowledge_graph_summary": collection_result.get('context_summary', {}),
            "issues": knowledge_graph.issues if knowledge_graph else []
        }
    
    def _create_error_result(self, error_msg: str) -> Dict[str, Any]:
        """
        Create an error result when collection fails
        
        Args:
            error_msg: Error message
            
        Returns:
            Dict[str, Any]: Error result
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
            "knowledge_graph_summary": {}
        }
    
    def _print_knowledge_graph_summary(self, knowledge_graph):
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
            # Try to use rich formatting
            self._print_with_rich_formatting(knowledge_graph)
        except Exception as e:
            # Fall back to plain text if rich formatting fails
            self.logger.error(f"Error in rich formatting, falling back to plain text: {str(e)}")
            self._print_with_fallback_formatting(knowledge_graph)
        
        self.console.print("\n")
    
    def _print_with_rich_formatting(self, knowledge_graph):
        """
        Print knowledge graph with rich formatting
        
        Args:
            knowledge_graph: Knowledge Graph instance
        """
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
    
    def _print_with_fallback_formatting(self, knowledge_graph):
        """
        Print knowledge graph with fallback formatting when rich formatting fails
        
        Args:
            knowledge_graph: Knowledge Graph instance
        """
        try:
            # Try plain text formatting
            formatted_output = knowledge_graph.print_graph(use_rich=False)
            print(formatted_output)
        except Exception as e2:
            # Last resort fallback
            self.logger.error(f"Error in plain text formatting: {str(e2)}")
            self._print_minimal_graph_info(knowledge_graph)
    
    def _print_minimal_graph_info(self, knowledge_graph):
        """
        Print minimal graph information when all other formatting methods fail
        
        Args:
            knowledge_graph: Knowledge Graph instance
        """
        print("=" * 80)
        print("KNOWLEDGE GRAPH SUMMARY (FALLBACK FORMAT)")
        print("=" * 80)
        print(f"Total nodes: {knowledge_graph.graph.number_of_nodes()}")
        print(f"Total edges: {knowledge_graph.graph.number_of_edges()}")
        print(f"Total issues: {len(knowledge_graph.issues)}")


async def run_information_collection_phase(pod_name: str, namespace: str, volume_path: str, 
                                         config_data: Dict[str, Any]) -> Dict[str, Any]:
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
    
    # Display phase header
    _display_phase_header()
    
    try:
        # Initialize the phase
        phase = InformationCollectionPhase(config_data)
        
        # Run the collection
        collected_info = await phase.collect_information(pod_name, namespace, volume_path)
        
        return collected_info
        
    except Exception as e:
        return _handle_phase_error(e)


def _display_phase_header():
    """
    Display the phase header in the console
    """
    console = Console()
    console.print("\n")
    console.print(Panel(
        "[bold white]Collecting diagnostic information...",
        title="[bold cyan]PHASE 0: INFORMATION COLLECTION",
        border_style="cyan",
        padding=(1, 2)
    ))


def _handle_phase_error(exception: Exception) -> Dict[str, Any]:
    """
    Handle errors during the information collection phase
    
    Args:
        exception: Exception that occurred
        
    Returns:
        Dict[str, Any]: Error result
    """
    error_msg = f"Error during information collection phase: {str(exception)}"
    logging.error(error_msg)
    
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
