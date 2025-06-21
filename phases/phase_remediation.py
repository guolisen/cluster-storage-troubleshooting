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
from tools.core.mcp_adapter import get_mcp_adapter
from phases.llm_factory import LLMFactory
from tools.diagnostics.hardware import xfs_repair_check  # Importing the xfs_repair_check tool
from phases.utils import format_historical_experiences_from_collected_info, handle_exception

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
        
        # Get MCP adapter and tools
        self.mcp_adapter = get_mcp_adapter()
        self.mcp_tools = []
        
        # Get MCP tools for phase2 if available
        if self.mcp_adapter:
            self.mcp_tools = self.mcp_adapter.get_tools_for_phase('phase2')
            if self.mcp_tools:
                self.logger.info(f"Loaded {len(self.mcp_tools)} MCP tools for Phase2")
                
        # Initialize LLM factory
        self.llm_factory = LLMFactory(self.config_data)
    
    async def run_remediation_with_graph(self, query: str, graph: StateGraph, timeout_seconds: int = 1800) -> str:
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
                self.console.print(f"[red]run_remediation_with_graph Remediation failed: {str(e)}[/red]")
                return f"run_remediation_with_graph Remediation failed: {str(e)}"
            
            # Extract remediation results
            return self._extract_final_message(response)
            
        except Exception as e:
            error_msg = handle_exception("run_remediation_with_graph", e, self.logger)
            return f"Error in remediation: {str(e)}"
    
    def _extract_final_message(self, response: Dict[str, Any]) -> str:
        """
        Extract the final message from a graph response
        
        Args:
            response: Response from the graph
            
        Returns:
            str: Final message content
        """
        if not response.get("messages"):
            return "Failed to generate remediation results"
            
        if isinstance(response["messages"], list):
            return response["messages"][-1].content
        else:
            return response["messages"].content
    
    async def execute_fix_plan(self, phase1_final_response: str, message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
        """
        Execute the fix plan from Phase 1 analysis
        
        Args:
            phase1_final_response: Response from Phase 1 containing root cause and fix plan
            message_list: Optional message list for chat mode
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Remediation result, Updated message list)
        """
        try:
            # Initialize message list if not provided
            if message_list is None:
                # System prompt for Phase2
                system_prompt = """You are an expert Kubernetes storage troubleshooter. Your task is to execute the Fix Plan to resolve volume I/O errors in Kubernetes pods.

TASK:
1. Execute the Fix Plan to resolve the identified issues
2. Validate the fixes to ensure they resolved the problem
3. Provide a detailed report of the remediation actions taken

KNOWLEDGE GRAPH TOOLS USAGE:
- When using knowledge graph tools, use the parameters of entity_type and id format:
  * Entity ID formats:
    - Pod: "gnode:Pod:<namespace>/<name>" (example: "gnode:Pod:default/test-pod-1-0")
    - PVC: "gnode:PVC:<namespace>/<name>" (example: "gnode:PVC:default/test-pvc-1")
    - PV: "gnode:PV:<name>" (example: "gnode:PV:pv-test-123")
    - Drive: "gnode:Drive:<uuid>" (example: "gnode:Drive:a1b2c3d4-e5f6")
    - Node: "gnode:Node:<name>" (example: "gnode:Node:kind-control-plane")
    - StorageClass: "gnode:StorageClass:<name>" (example: "gnode:StorageClass:csi-baremetal-sc")
    - LVG: "gnode:LVG:<name>" (example: "gnode:LVG:lvg-1")
    - AC: "gnode:AC:<name>" (example: "gnode:AC:ac-node1-ssd")
    - Volume: "gnode:Volume:<namespace>/<name>" (example: "gnode:Volume:default/vol-1")
    - System: "gnode:System:<entity_name>" (example: "gnode:System:kernel")
    - ClusterNode: "gnode:ClusterNode:<name>" (example: "gnode:ClusterNode:worker-1")
    - HistoricalExperience: "gnode:HistoricalExperience:<experience_id>" (example: "gnode:HistoricalExperience:exp-001")

  * Helper tools for generating entity IDs:
    - Pod: kg_get_entity_of_pod(namespace, name) → returns "gnode:Pod:namespace/name"
    - PVC: kg_get_entity_of_pvc(namespace, name) → returns "gnode:PVC:namespace/name"
    - PV: kg_get_entity_of_pv(name) → returns "gnode:PV:name"
    - Drive: kg_get_entity_of_drive(uuid) → returns "gnode:Drive:uuid"
    - Node: kg_get_entity_of_node(name) → returns "gnode:Node:name"
    - StorageClass: kg_get_entity_of_storage_class(name) → returns "gnode:StorageClass:name"
    - LVG: kg_get_entity_of_lvg(name) → returns "gnode:LVG:name"
    - AC: kg_get_entity_of_ac(name) → returns "gnode:AC:name"
    - Volume: kg_get_entity_of_volume(namespace, name) → returns "gnode:Volume:namespace/name"
    - System: kg_get_entity_of_system(entity_name) → returns "gnode:System:entity_name"
    - ClusterNode: kg_get_entity_of_cluster_node(name) → returns "gnode:ClusterNode:name"
    - HistoricalExperience: kg_get_entity_of_historical_experience(experience_id) → returns "gnode:HistoricalExperience:experience_id"

- Start with discovery tools to understand what's in the Knowledge Graph:
  * Use kg_list_entity_types() to discover available entity types and their counts
  * Use kg_list_entities(entity_type) to find specific entities of a given type
  * Use kg_list_relationship_types() to understand how entities are related

- Then use detailed query tools:
  * Use kg_get_entity_info(entity_type, id) to retrieve detailed information about specific entities
  * Use kg_get_related_entities(entity_type, id) to understand relationships between components
  * Use kg_get_all_issues() to find already detected issues in the system
  * Use kg_find_path(source_entity_type, source_id, target_entity_type, target_id) to trace dependencies

CONSTRAINTS:
- Follow the Fix Plan step by step
- Use only the tools available in the Phase2 tool registry
- Validate each fix to ensure it was successful
- Provide a clear, detailed report of all actions taken

OUTPUT FORMAT:
Your response must include:
1. Actions Taken
2. Validation Results
3. Resolution Status
4. Recommendations
"""
                message_list = [
                    {"role": "system", "content": system_prompt},
                    {"role": "assistant", "content": "Fix Plan:\n" + phase1_final_response}
                ]
            
            # Check if streaming is enabled in config
            streaming_enabled = self.config_data.get('llm', {}).get('streaming', False)
            
            # Create troubleshooting graph for remediation
            # Import here to avoid circular imports
            from troubleshooting.graph import create_troubleshooting_graph_with_context
            graph = create_troubleshooting_graph_with_context(
                self.collected_info, phase="phase2", config_data=self.config_data,
                streaming=streaming_enabled
            )
            
            # Extract and format historical experience data from collected_info
            historical_experiences_formatted = format_historical_experiences_from_collected_info(self.collected_info)
            
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
                remediation_result = "Remediation phase timed out - manual intervention may be required"
                
                # Add timeout message to message list
                message_list.append({"role": "assistant", "content": remediation_result})
                return remediation_result, message_list
            except Exception as e:
                self.console.print(f"[red]execute_fix_plan Remediation failed: {str(e)}[/red]")
                remediation_result = f"execute_fix_plan Remediation failed: {str(e)}"
                
                # Add error message to message list
                message_list.append({"role": "assistant", "content": remediation_result})
                return remediation_result, message_list
            
            # Extract remediation results
            remediation_result = self._extract_final_message(response)
            
            # Add remediation result to message list
            message_list.append({"role": "assistant", "content": remediation_result})
            
            return remediation_result, message_list

        except Exception as e:
            error_msg = handle_exception("execute_fix_plan", e, self.logger)
            
            # Add error message to message list if provided
            if message_list is not None:
                message_list.append({"role": "assistant", "content": error_msg})
            
            return error_msg, message_list


async def run_remediation_phase(phase1_final_response: str, collected_info: Dict[str, Any], 
                              config_data: Dict[str, Any], message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
    """
    Run Phase 2: Remediation based on analysis results
    
    Args:
        phase1_final_response: Response from Phase 1 containing root cause and fix plan
        collected_info: Pre-collected diagnostic information from Phase 0
        config_data: Configuration data
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: (Remediation result, Updated message list)
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
        result, message_list = await phase.execute_fix_plan(phase1_final_response, message_list)
        
        return result, message_list
        
    except Exception as e:
        error_msg = handle_exception("run_remediation_phase", e, logger)
        # Add error message to message list if provided
        if message_list is not None:
            message_list.append({"role": "assistant", "content": error_msg})
        
        return error_msg, message_list
