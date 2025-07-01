#!/usr/bin/env python3
"""
Plan Phase for Kubernetes Volume Troubleshooting

This module contains the PlanPhase class that orchestrates the planning phase
of the troubleshooting process, generating an Investigation Plan for Phase 1.
"""

import logging
import os
import json
from typing import Dict, List, Any, Optional, Tuple
from knowledge_graph import KnowledgeGraph
from phases.investigation_planner import InvestigationPlanner
from phases.utils import validate_knowledge_graph, generate_basic_fallback_plan, handle_exception
from llm_graph.graphs.plan_llm_graph import PlanLLMGraph

logger = logging.getLogger(__name__)

class PlanPhase:
    """
    Orchestrates the Plan Phase of the troubleshooting process
    
    The Plan Phase can use one of two approaches to generate an Investigation Plan:
    1. Traditional approach (default):
       - Rule-based preliminary steps - Generate critical initial investigation steps
       - Static plan steps integration - Add mandatory steps from static_plan_step.json
       - LLM refinement - Refine and supplement the plan using LLM without tool invocation
    
    2. ReAct graph approach (when use_react=True):
       - Implements a ReAct (Reasoning and Acting) graph using LangGraph
       - Uses the Strategy Pattern with PlanLLMGraph implementing LangGraphInterface
       - Exclusively uses MCP tools for function calling to gather information
       - Follows the standard ReAct pattern: reasoning, acting, observing in a loop
    
    This phase uses the Knowledge Graph from Phase 0, historical experience data, and
    the complete Phase1 tool registry to produce a comprehensive Investigation Plan.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the Plan Phase
        
        Args:
            config_data: Configuration data for the system (optional)
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.investigation_planner = None
        
        # Check if ReAct graph should be used
        self.use_react = self.config_data.get('plan_phase', {}).get('use_react', False)
        self.logger.info(f"Plan Phase initialized with {'ReAct' if self.use_react else 'traditional'} approach")
    
    async def execute(self, knowledge_graph: KnowledgeGraph, pod_name: str, namespace: str, 
                    volume_path: str, message_list: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Execute the Plan Phase
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            
        Returns:
            Dict[str, Any]: Results of the Plan Phase, including the Investigation Plan and updated message list
        """
        self.logger.info(f"Executing Plan Phase for {namespace}/{pod_name} volume {volume_path} using {'React' if self.use_react else 'Legacy'} mode")
        
        try:
            if self.use_react:
                # Use the new PlanLLMGraph implementation for React mode
                return await self._generate_investigation_plan_with_graph(
                    knowledge_graph, pod_name, namespace, volume_path, message_list
                )
            else:
                # Use the traditional approach for Legacy mode
                return await self._generate_investigation_plan(
                    knowledge_graph, pod_name, namespace, volume_path, message_list, False
                )
            
        except Exception as e:
            error_msg = handle_exception("execute", e, self.logger)
            return self._handle_plan_generation_error(
                error_msg, pod_name, namespace, volume_path, message_list
            )
    
    async def _generate_investigation_plan(self, knowledge_graph: KnowledgeGraph, pod_name: str, namespace: str, 
                                        volume_path: str, message_list: List[Dict[str, str]] = None,
                                        use_react: bool = False) -> Dict[str, Any]:
        """
        Generate an investigation plan using the Investigation Planner (Legacy mode)
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            use_react: Whether to use React mode (default: False)
            
        Returns:
            Dict[str, Any]: Results of the plan generation
        """
        # Initialize Investigation Planner
        self.investigation_planner = InvestigationPlanner(knowledge_graph, self.config_data)
        
        # Generate Investigation Plan with use_react flag
        investigation_plan, message_list = await self.investigation_planner.generate_investigation_plan(
            pod_name, namespace, volume_path, message_list, use_react
        )
        
        # Parse the plan into a structured format for Phase 1
        structured_plan = self._parse_investigation_plan(investigation_plan)
        
        # Return results
        return {
            "status": "success",
            "investigation_plan": investigation_plan,
            "structured_plan": structured_plan,
            "pod_name": pod_name,
            "namespace": namespace,
            "volume_path": volume_path,
            "message_list": message_list
        }
        
    async def _generate_investigation_plan_with_graph(self, knowledge_graph: KnowledgeGraph, pod_name: str, namespace: str, 
                                                   volume_path: str, message_list: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Generate an investigation plan using the PlanLLMGraph (React mode)
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            
        Returns:
            Dict[str, Any]: Results of the plan generation
        """
        self.logger.info("Generating investigation plan using PlanLLMGraph")
        
        try:
            # Initialize PlanLLMGraph
            plan_graph = PlanLLMGraph(self.config_data)
            
            # Prepare initial state
            initial_state = {
                "messages": message_list or [],
                "pod_name": pod_name,
                "namespace": namespace,
                "volume_path": volume_path,
                "knowledge_graph": knowledge_graph
            }
            
            # Execute the graph
            final_state = await plan_graph.execute(initial_state)
            
            # Extract the investigation plan
            investigation_plan = final_state.get("investigation_plan", "")
            
            # Parse the plan into a structured format for Phase 1
            structured_plan = self._parse_investigation_plan(investigation_plan)
            
            # Return results
            return {
                "status": "success",
                "investigation_plan": investigation_plan,
                "structured_plan": structured_plan,
                "pod_name": pod_name,
                "namespace": namespace,
                "volume_path": volume_path,
                "message_list": final_state.get("messages", message_list)
            }
        except Exception as e:
            error_msg = handle_exception("_generate_investigation_plan_with_graph", e, self.logger)
            return self._handle_plan_generation_error(
                error_msg, pod_name, namespace, volume_path, message_list
            )
    
    # React mode is now handled by the PlanLLMGraph class in llm_graph/graphs/plan_llm_graph.py
    
    def _handle_plan_generation_error(self, error_msg: str, pod_name: str, namespace: str, 
                                    volume_path: str, message_list: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Handle errors during plan generation
        
        Args:
            error_msg: Error message
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            
        Returns:
            Dict[str, Any]: Error results with fallback plan
        """
        # Generate fallback plan
        fallback_plan = generate_basic_fallback_plan(pod_name, namespace, volume_path)
        
        # Add fallback plan to message list if provided
        updated_message_list = self._update_message_list(message_list, fallback_plan)
        
        return {
            "status": "error",
            "error_message": error_msg,
            "investigation_plan": fallback_plan,
            "pod_name": pod_name,
            "namespace": namespace,
            "volume_path": volume_path,
            "message_list": updated_message_list
        }
    
    def _update_message_list(self, message_list: List[Dict[str, str]], content: str) -> List[Dict[str, str]]:
        """
        Update message list with new content
        
        Args:
            message_list: Message list to update
            content: Content to add to the message list
            
        Returns:
            List[Dict[str, str]]: Updated message list
        """
        if message_list is None:
            return None
            
        # If the last message is from the user, append the assistant response
        if message_list[-1]["role"] == "user":
            message_list.append({"role": "assistant", "content": content})
        else:
            # Replace the last message if it's from the assistant
            message_list[-1] = {"role": "assistant", "content": content}
        
        return message_list
    
    def _parse_investigation_plan(self, investigation_plan: str) -> Dict[str, Any]:
        """
        Parse the Investigation Plan into a structured format for Phase 1
        
        Args:
            investigation_plan: Formatted Investigation Plan
            
        Returns:
            Dict[str, Any]: Structured Investigation Plan
        """
        try:
            # Initialize structured plan
            structured_plan = {
                "steps": [],
                "fallback_steps": []
            }
            
            # Parse the plan
            lines = investigation_plan.strip().split('\n')
            in_fallback_section = False
            
            for line in lines:
                line = line.strip()
                
                # Skip empty lines and headers
                if self._is_header_line(line):
                    continue
                
                # Check if we're in the fallback section
                if line == "Fallback Steps (if main steps fail):":
                    in_fallback_section = True
                    continue
                
                # Parse step
                if line.startswith("Step "):
                    step = self._parse_step_line(line, in_fallback_section)
                    if step:
                        # Add to appropriate list
                        if in_fallback_section:
                            structured_plan["fallback_steps"].append(step)
                        else:
                            structured_plan["steps"].append(step)
            
            return structured_plan
            
        except Exception as e:
            error_msg = handle_exception("_parse_investigation_plan", e, self.logger)
            return {"steps": [], "fallback_steps": []}
    
    def _is_header_line(self, line: str) -> bool:
        """
        Check if a line is a header line that should be skipped
        
        Args:
            line: Line to check
            
        Returns:
            bool: True if the line is a header, False otherwise
        """
        return (not line or 
                line.startswith("Investigation Plan:") or 
                line.startswith("Target:") or 
                line.startswith("Generated Steps:"))
    
    def _parse_step_line(self, line: str, in_fallback_section: bool) -> Dict[str, Any]:
        """
        Parse a step line into a structured step
        
        Args:
            line: Step line to parse
            in_fallback_section: Whether we're in the fallback section
            
        Returns:
            Dict[str, Any]: Parsed step, or None if parsing failed
        """
        step_parts = line.split(" | ")
        
        if len(step_parts) < 3:
            return None
        
        # Extract step number and description
        step_info = step_parts[0].split(": ", 1)
        step_number = step_info[0].replace("Step ", "")
        description = step_info[1] if len(step_info) > 1 else ""
        
        # Extract tool and arguments
        tool_info = step_parts[1].replace("Tool: ", "")
        tool_name = tool_info.split("(")[0] if "(" in tool_info else tool_info
        
        # Extract arguments
        arguments = self._parse_tool_arguments(tool_info)
        
        # Extract expected outcome
        expected = step_parts[2].replace("Expected: ", "") if len(step_parts) > 2 else ""
        
        # Extract trigger for fallback steps
        trigger = step_parts[3].replace("Trigger: ", "") if len(step_parts) > 3 and in_fallback_section else None
        
        # Create step dictionary
        step = {
            "step": step_number,
            "description": description,
            "tool": tool_name,
            "arguments": arguments,
            "expected": expected
        }
        
        if trigger:
            step["trigger"] = trigger
        
        return step
    
    def _parse_tool_arguments(self, tool_info: str) -> Dict[str, Any]:
        """
        Parse tool arguments from tool info string
        
        Args:
            tool_info: Tool info string
            
        Returns:
            Dict[str, Any]: Parsed arguments
        """
        arguments = {}
        if "(" in tool_info and ")" in tool_info:
            args_str = tool_info.split("(", 1)[1].rsplit(")", 1)[0]
            if args_str:
                # Parse arguments
                for arg in args_str.split(", "):
                    if "=" in arg:
                        key, value = arg.split("=", 1)
                        # Convert string representations to actual values
                        arguments[key] = self._convert_argument_value(value)
        
        return arguments
    
    def _convert_argument_value(self, value: str) -> Any:
        """
        Convert a string argument value to its appropriate type
        
        Args:
            value: String value to convert
            
        Returns:
            Any: Converted value
        """
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
        elif value.isdigit():
            return int(value)
        elif value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        elif value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value
    


async def run_plan_phase(pod_name, namespace, volume_path, collected_info, config_data=None, message_list=None):
    """
    Run the Plan Phase
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Dictionary containing collected information from Phase 0, including knowledge_graph
        config_data: Configuration data for the system (optional)
        message_list: Optional message list for chat mode
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: (Investigation Plan as a formatted string, Updated message list)
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Running Plan Phase for {namespace}/{pod_name} volume {volume_path}")
    
    try:
        # Extract and validate knowledge_graph
        knowledge_graph = _extract_and_validate_knowledge_graph(collected_info, logger)
        
        # Initialize and execute Plan Phase
        plan_phase = PlanPhase(config_data)
        
        # Execute the plan phase
        # The React/Legacy mode distinction is handled in the PlanPhase.execute method
        use_react = config_data.get('plan_phase', {}).get('use_react', False)
        logger.info(f"Using {'React' if use_react else 'traditional'} approach for plan generation")
        results = await plan_phase.execute(knowledge_graph, pod_name, namespace, volume_path, message_list)
        
        # Log the results
        logger.info(f"Plan Phase completed with status: {results['status']}")
        
        # Save the investigation plan to a file if configured
        _save_plan_to_file_if_configured(
            results['investigation_plan'], namespace, pod_name, config_data, logger
        )
        
        # Return the investigation plan as a string and the updated message list
        return results['investigation_plan'], results['message_list']
        
    except Exception as e:
        error_msg = handle_exception("run_plan_phase", e, logger)
        return error_msg, message_list


def _extract_and_validate_knowledge_graph(collected_info: Dict[str, Any], logger: logging.Logger) -> KnowledgeGraph:
    """
    Extract and validate the knowledge graph from collected information
    
    Args:
        collected_info: Dictionary containing collected information from Phase 0
        logger: Logger instance
        
    Returns:
        KnowledgeGraph: Validated knowledge graph
        
    Raises:
        ValueError: If the knowledge graph is invalid
    """
    # Extract knowledge_graph from collected_info
    knowledge_graph = collected_info.get('knowledge_graph')
    
    # Validate knowledge_graph is present
    if knowledge_graph is None:
        error_msg = "Knowledge Graph not found in collected_info"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate knowledge_graph is a KnowledgeGraph instance
    if not isinstance(knowledge_graph, KnowledgeGraph):
        error_msg = f"Invalid Knowledge Graph type: {type(knowledge_graph)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return knowledge_graph


def _save_plan_to_file_if_configured(investigation_plan: str, namespace: str, pod_name: str, 
                                   config_data: Dict[str, Any], logger: logging.Logger) -> None:
    """
    Save the investigation plan to a file if configured
    
    Args:
        investigation_plan: Investigation plan to save
        namespace: Namespace of the pod
        pod_name: Name of the pod
        config_data: Configuration data
        logger: Logger instance
    """
    if not config_data or not config_data.get('plan_phase', {}).get('save_plan', False):
        return
        
    try:
        output_dir = config_data.get('output_dir', 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        plan_file = os.path.join(output_dir, f"investigation_plan_{namespace}_{pod_name}.txt")
        with open(plan_file, 'w') as f:
            f.write(investigation_plan)
        
        logger.info(f"Investigation Plan saved to {plan_file}")
    except Exception as e:
        logger.warning(f"Failed to save investigation plan to file: {str(e)}")
