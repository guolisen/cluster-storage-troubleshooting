#!/usr/bin/env python3
"""
Phase 2: Remediation for Kubernetes Volume Troubleshooting

This module contains the implementation of Phase 2 (Remediation)
which executes fix plans based on analysis from Phase 1.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from langgraph.graph import StateGraph

from troubleshooting.graph import create_troubleshooting_graph_with_context
from tools.diagnostics.hardware import xfs_repair_check  # Importing the xfs_repair_check tool

logger = logging.getLogger(__name__)

class RemediationPhase:
    """
    Implementation of Phase 2: Remediation
    
    This class handles the implementation of fix plans to resolve
    the identified issues with volume I/O.
    """
    
    def __init__(self, collected_info: Dict[str, Any], config_data: Dict[str, Any]):
        """
        Initialize the Remediation Phase
        
        Args:
            collected_info: Pre-collected diagnostic information from Phase 0
            config_data: Configuration data for the system
        """
        self.collected_info = collected_info
        self.config_data = config_data
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.console = Console()
        self.interactive_mode = config_data.get('troubleshoot', {}).get('interactive_mode', False)
    
    def _format_historical_experiences(self, collected_info: Dict[str, Any]) -> str:
        """
        Format historical experience data from collected information
        
        Args:
            collected_info: Pre-collected diagnostic information from Phase 0
            
        Returns:
            str: Formatted historical experience data for LLM consumption
        """
        try:
            # Extract historical experiences from knowledge graph in collected_info
            kg = collected_info.get('knowledge_graph', None)
            if not kg or not hasattr(kg, 'graph'):
                return "No historical experience data available."
            
            # Find historical experience nodes
            historical_experience_nodes = []
            for node_id, attrs in kg.graph.nodes(data=True):
                if attrs.get('gnode_subtype') == 'HistoricalExperience':
                    historical_experience_nodes.append((node_id, attrs))
            
            if not historical_experience_nodes:
                return "No historical experience data available."
            
            # Format historical experiences in a clear, structured way
            formatted_entries = []
            
            for idx, (node_id, attrs) in enumerate(historical_experience_nodes, 1):
                # Get attributes from the experience
                phenomenon = attrs.get('phenomenon', 'Unknown phenomenon')
                root_cause = attrs.get('root_cause', 'Unknown root cause')
                localization_method = attrs.get('localization_method', 'No localization method provided')
                resolution_method = attrs.get('resolution_method', 'No resolution method provided')
                
                # Format the entry
                entry = f"""HISTORICAL EXPERIENCE #{idx}:
Phenomenon: {phenomenon}
Root Cause: {root_cause}
Localization Method: {localization_method}
Resolution Method: {resolution_method}
"""
                formatted_entries.append(entry)
            
            return "\n".join(formatted_entries)
            
        except Exception as e:
            self.logger.warning(f"Error formatting historical experiences: {str(e)}")
            return "Error formatting historical experience data."
    
    async def run_remediation_with_graph(self, query: str, graph: StateGraph, timeout_seconds: int = 60) -> str:
        """
        Run remediation using the provided LangGraph StateGraph
        
        Args:
            query: The initial query to send to the graph
            graph: LangGraph StateGraph to use
            timeout_seconds: Maximum execution time in seconds
            
        Returns:
            str: Remediation result
        """
        try:
            formatted_query = {"messages": [{"role": "user", "content": query}]}
            
            # Show the remediation panel
            self.console.print("\n")
            self.console.print(Panel(
                "[yellow]Starting remediation with LangGraph...\nThis may take a few minutes to complete.", 
                title="[bold green]Remediation Phase",
                border_style="green"
            ))
            
            # Run graph with timeout
            try:
                response = await asyncio.wait_for(
                    graph.ainvoke(formatted_query, config={"recursion_limit": 100}),
                    timeout=timeout_seconds
                )
                self.console.print("[green]Remediation complete![/green]")
            except asyncio.TimeoutError:
                self.console.print("[red]Remediation timed out![/red]")
                return "Remediation phase timed out - manual intervention may be required"
            except Exception as e:
                self.console.print(f"[red]Remediation failed: {str(e)}[/red]")
                return f"Remediation failed: {str(e)}"
            
            # Extract remediation results
            if response["messages"]:
                if isinstance(response["messages"], list):
                    final_message = response["messages"][-1].content
                else:
                    final_message = response["messages"].content
            else:
                final_message = "Failed to generate remediation results"
            
            return final_message
        except Exception as e:
            self.logger.error(f"Error in run_remediation_with_graph: {str(e)}")
            return f"Error in remediation: {str(e)}"
    
    async def execute_fix_plan(self, phase1_final_response: str) -> str:
        """
        Execute the fix plan from Phase 1 analysis
        
        Args:
            phase1_final_response: Response from Phase 1 containing root cause and fix plan
            
        Returns:
            str: Remediation result
        """
        try:
            # Create troubleshooting graph for remediation
            graph = create_troubleshooting_graph_with_context(
                self.collected_info, phase="phase2", config_data=self.config_data
            )
            
            # Extract and format historical experience data from collected_info
            historical_experiences_formatted = self._format_historical_experiences(self.collected_info)
            
            # Updated query message with dynamic data for LangGraph workflow
            query = f"""Phase 2 - Remediation: Execute the fix plan to resolve the identified issue.

Root Cause and Fix Plan: {phase1_final_response}

HISTORICAL EXPERIENCE:
{historical_experiences_formatted}

<<< Note >>>: Please try to fix issue within 30 tool calls.
"""
            
            # Set timeout
            timeout_seconds = self.config_data['troubleshoot']['timeout_seconds']
            
            # Run remediation with graph
            remediation_result = await self.run_remediation_with_graph(
                query=query,
                graph=graph,
                timeout_seconds=timeout_seconds
            )
            
            return remediation_result

        except Exception as e:
            error_msg = f"Error during remediation: {str(e)}"
            self.logger.error(error_msg)
            return error_msg


async def run_remediation_phase(phase1_final_response: str, collected_info: Dict[str, Any], 
                              config_data: Dict[str, Any]) -> str:
    """
    Run Phase 2: Remediation based on analysis results
    
    Args:
        phase1_final_response: Response from Phase 1 containing root cause and fix plan
        collected_info: Pre-collected diagnostic information from Phase 0
        config_data: Configuration data
        
    Returns:
        str: Remediation result
    """
    logging.info("Starting Phase 2: Remediation")
    
    console = Console()
    console.print("\n")
    console.print(Panel(
        "[bold white]Executing fix plan to resolve identified issues...",
        title="[bold green]PHASE 2: REMEDIATION",
        border_style="green",
        padding=(1, 2)
    ))
    
    try:
        # Initialize the remediation phase
        phase = RemediationPhase(collected_info, config_data)
        
        # Execute the fix plan
        result = await phase.execute_fix_plan(phase1_final_response)
        
        return result
        
    except Exception as e:
        error_msg = f"Error during remediation phase: {str(e)}"
        logging.error(error_msg)
        return error_msg
