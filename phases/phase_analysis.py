#!/usr/bin/env python3
"""
Phase 1: ReAct Investigation for Kubernetes Volume Troubleshooting

This module contains the implementation of Phase 1 (ReAct Investigation)
which actively investigates using tools with pre-collected data as base knowledge.
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

class AnalysisPhase:
    """
    Implementation of Phase 1: ReAct Investigation
    
    This class handles the active investigation of volume I/O errors
    using the Investigation Plan and pre-collected data.
    """
    
    def __init__(self, collected_info: Dict[str, Any], config_data: Dict[str, Any]):
        """
        Initialize the Analysis Phase
        
        Args:
            collected_info: Pre-collected diagnostic information from Phase 0
            config_data: Configuration data for the system
        """
        self.collected_info = collected_info
        self.config_data = config_data
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.console = Console()
    
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
    
    async def run_analysis_with_graph(self, query: str, graph: StateGraph, timeout_seconds: int = 60) -> str:
        """
        Run an analysis using the provided LangGraph StateGraph with enhanced progress tracking
        
        Args:
            query: The initial query to send to the graph
            graph: LangGraph StateGraph to use
            timeout_seconds: Maximum execution time in seconds
            
        Returns:
            str: Analysis result
        """
        try:
            formatted_query = {"messages": [{"role": "user", "content": query}]}
            
            # First show the analysis panel
            self.console.print(Panel(
                "[yellow]Starting analysis with LangGraph...\nThis may take a few minutes to complete.", 
                title="[bold blue]Analysis Phase",
                border_style="blue"
            ))
            
            # Run graph with timeout
            try:
                response = await asyncio.wait_for(
                    graph.ainvoke(formatted_query, config={"recursion_limit": 100}),
                    timeout=timeout_seconds
                )
                self.console.print("[green]Analysis complete![/green]")
            except asyncio.TimeoutError:
                self.console.print("[red]Analysis timed out![/red]")
                raise
            except Exception as e:
                self.console.print(f"[red]Analysis failed: {str(e)}[/red]")
                raise
            
            # Extract analysis results
            if response["messages"]:
                if isinstance(response["messages"], list):
                    final_message = response["messages"][-1].content
                else:
                    final_message = response["messages"].content
            else:
                final_message = "Failed to generate analysis results"
            
            return final_message
        except Exception as e:
            self.logger.error(f"Error in run_analysis_with_graph: {str(e)}")
            return f"Error in analysis: {str(e)}"
    
    async def run_investigation(self, pod_name: str, namespace: str, volume_path: str, 
                               investigation_plan: str) -> str:
        """
        Run the investigation based on the Investigation Plan
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            investigation_plan: Investigation Plan generated by the Plan Phase
            
        Returns:
            str: Analysis result
        """
        try:
            # Create troubleshooting graph with pre-collected context
            graph = create_troubleshooting_graph_with_context(
                self.collected_info, phase="phase1", config_data=self.config_data
            )
            
            # Extract and format historical experience data from collected_info
            historical_experiences_formatted = self._format_historical_experiences(self.collected_info)
            
            # Updated query message with dynamic data for LangGraph workflow
            query = f"""Phase 1 - ReAct Investigation: Execute the Investigation Plan to actively investigate the volume I/O error in pod {pod_name} in namespace {namespace} at volume path {volume_path}.

INVESTIGATION PLAN TO FOLLOW:
{investigation_plan}

HISTORICAL EXPERIENCE:
{historical_experiences_formatted}

SPECIAL CASE DETECTION:
After executing the Investigation Plan, you must determine if one of these special cases applies:

CASE 1 - NO ISSUES DETECTED:
If the Knowledge Graph and Investigation Plan execution confirm the system has no issues:
- Output a structured summary in the following format:
  ```
  Summary Finding: No issues detected in the system.
  Evidence: [Details from Knowledge Graph queries, e.g., no error logs found, all services operational]
  Advice: [Recommendations, e.g., continue monitoring the system]
  SKIP_PHASE2: YES
  ```

CASE 2 - MANUAL INTERVENTION REQUIRED:
If the Knowledge Graph and Investigation Plan execution confirm the issue cannot be fixed automatically:
- Output a structured summary in the following format:
  ```
  Summary Finding: Issue detected, but requires manual intervention.
  Evidence: [Details from Knowledge Graph queries, e.g., specific error or configuration requiring human action]
  Advice: [Detailed step-by-step instructions for manual resolution, e.g., specific commands or actions for the user]
  SKIP_PHASE2: YES
  ```

CASE 3 - AUTOMATIC FIX POSSIBLE:
If the issue can be resolved automatically:
- Generate a fix plan based on the Investigation Plan's results
- Output a comprehensive root cause analysis and fix plan
- Do NOT include the SKIP_PHASE2 marker

<<< Note >>>: Please provide the root cause and fix plan analysis within 30 tool calls.
"""
            # Set timeout
            timeout_seconds = self.config_data['troubleshoot']['timeout_seconds']
            
            # Run analysis using the tools module
            phase1_response = await self.run_analysis_with_graph(
                query=query,
                graph=graph,
                timeout_seconds=timeout_seconds
            )
            
            return phase1_response

        except Exception as e:
            error_msg = f"Error during analysis phase: {str(e)}"
            self.logger.error(error_msg)
            return error_msg


async def run_analysis_phase_with_plan(pod_name: str, namespace: str, volume_path: str, 
                                     collected_info: Dict[str, Any], investigation_plan: str,
                                     config_data: Dict[str, Any]) -> Tuple[str, bool]:
    """
    Run Phase 1: ReAct Investigation with pre-collected information as base knowledge
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        investigation_plan: Investigation Plan generated by the Plan Phase
        config_data: Configuration data
        
    Returns:
        Tuple[str, bool]: (Analysis result, Skip Phase2 flag)
    """
    logging.info("Starting Phase 1: ReAct Investigation with Plan")
    
    console = Console()
    console.print("\n")
    console.print(Panel(
        "[bold white]Executing Investigation Plan to actively investigate volume I/O issue...",
        title="[bold magenta]PHASE 1: REACT INVESTIGATION WITH PLAN",
        border_style="magenta",
        padding=(1, 2)
    ))
    
    try:
        # Initialize the analysis phase
        phase = AnalysisPhase(collected_info, config_data)
        
        # Setup shortcut key handler if chat mode is enabled
        chat_mode_enabled = config_data and config_data.get('chat_mode', {}).get('enabled', False)
        if chat_mode_enabled:
            from phases.chat_mode import get_chat_mode, handle_shortcut_key
            
            # Create a context for the LangGraph workflow
            langgraph_context = {
                'pod_name': pod_name,
                'namespace': namespace,
                'volume_path': volume_path,
                'investigation_plan': investigation_plan
            }
            
            # Setup shortcut key handler
            chat_mode = get_chat_mode(config_data)
            chat_mode.setup_shortcut_handler(lambda: handle_shortcut_key(langgraph_context))
        
        # Run the investigation
        result = await phase.run_investigation(pod_name, namespace, volume_path, investigation_plan)
        
        # Restore shortcut key handler if chat mode is enabled
        if chat_mode_enabled:
            chat_mode.restore_shortcut_handler()
        
        # Check if the result contains the SKIP_PHASE2 marker
        skip_phase2 = "SKIP_PHASE2: YES" in result
        
        # Remove the SKIP_PHASE2 marker from the output if present
        if skip_phase2:
            result = result.replace("SKIP_PHASE2: YES", "").strip()
            logging.info("Phase 1 indicated Phase 2 should be skipped")
        
        # Enter chat mode after Phase1 if enabled
        if chat_mode_enabled:
            from phases.chat_mode import handle_phase1_chat
            
            # Create a context for the LangGraph workflow
            langgraph_context = {
                'pod_name': pod_name,
                'namespace': namespace,
                'volume_path': volume_path,
                'investigation_plan': investigation_plan,
                'phase1_result': result
            }
            
            # Enter chat mode for user approval or refinement
            chat_result = handle_phase1_chat(langgraph_context)
            
            # If user provided instructions to guide the workflow, update the result
            if chat_result.get('action') == 'continue':
                # In a real implementation, we would continue the LangGraph workflow
                # with the updated context, but for this implementation, we'll just
                # append the user instructions to the result
                updated_context = chat_result.get('updated_context', {})
                user_instructions = updated_context.get('user_instructions', [])
                if user_instructions:
                    result += f"\n\nUser Instructions:\n"
                    for instruction in user_instructions:
                        result += f"- {instruction}\n"
        
        return result, skip_phase2
    
    except Exception as e:
        error_msg = f"Error during analysis phase: {str(e)}"
        logging.error(error_msg)
        return error_msg, False
