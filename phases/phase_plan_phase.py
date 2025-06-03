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
from troubleshooting.utils import (
    FallbackPlanGenerator,
    ErrorHandler,
    MessageListManager
)

logger = logging.getLogger(__name__)


class PlanPhase:
    """
    Orchestrates the Plan Phase of the troubleshooting process
    
    The Plan Phase follows a three-step process to generate an Investigation Plan:
    1. Rule-based preliminary steps - Generate critical initial investigation steps
    2. Static plan steps integration - Add mandatory steps from static_plan_step.json
    3. LLM refinement - Refine and supplement the plan using LLM without tool invocation
    
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
    
    def execute(self, knowledge_graph: KnowledgeGraph, pod_name: str, namespace: str, 
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
        self.logger.info(f"Executing Plan Phase for {namespace}/{pod_name} volume {volume_path}")
        
        try:
            # Initialize Investigation Planner
            self.investigation_planner = InvestigationPlanner(knowledge_graph, self.config_data)
            
            # Generate Investigation Plan
            investigation_plan, message_list = self.investigation_planner.generate_investigation_plan(
                pod_name, namespace, volume_path, message_list
            )
            
            # Parse the plan into a structured format for Phase 1
            structured_plan = self._parse_investigation_plan(investigation_plan)
            
            # Return results
            return self._create_success_result(
                investigation_plan, structured_plan, pod_name, namespace, volume_path, message_list
            )
            
        except Exception as exception:
            self.logger.error(f"Error executing Plan Phase: {str(exception)}")
            # Generate fallback plan
            fallback_plan = FallbackPlanGenerator.generate_basic_fallback_plan(pod_name, namespace, volume_path)
            
            # Add fallback plan to message list if provided
            if message_list is not None:
                message_list = MessageListManager.add_to_message_list(message_list, fallback_plan)
            
            return self._create_error_result(
                str(exception), fallback_plan, pod_name, namespace, volume_path, message_list
            )
    
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
                if self._should_skip_line(line):
                    continue
                
                # Check if we're in the fallback section
                if line == "Fallback Steps (if main steps fail):":
                    in_fallback_section = True
                    continue
                
                # Parse step
                if line.startswith("Step "):
                    step = self._parse_step_line(line, in_fallback_section)
                    
                    # Add to appropriate list
                    if in_fallback_section:
                        structured_plan["fallback_steps"].append(step)
                    else:
                        structured_plan["steps"].append(step)
            
            return structured_plan
            
        except Exception as e:
            self.logger.error(f"Error parsing investigation plan: {str(e)}")
            return {"steps": [], "fallback_steps": []}
    
    def _should_skip_line(self, line: str) -> bool:
        """
        Determine if a line should be skipped during parsing
        
        Args:
            line: Line to check
            
        Returns:
            bool: True if the line should be skipped, False otherwise
        """
        if not line:
            return True
            
        skip_prefixes = [
            "Investigation Plan:",
            "Target:",
            "Generated Steps:"
        ]
        
        for prefix in skip_prefixes:
            if line.startswith(prefix):
                return True
                
        return False
    
    def _parse_step_line(self, line: str, in_fallback_section: bool) -> Dict[str, Any]:
        """
        Parse a step line into a structured step dictionary
        
        Args:
            line: Step line to parse
            in_fallback_section: Whether the line is in the fallback section
            
        Returns:
            Dict[str, Any]: Structured step dictionary
        """
        step_parts = line.split(" | ")
        
        if len(step_parts) < 3:
            # Handle malformed step line
            return {
                "step": "unknown",
                "description": line,
                "tool": "unknown",
                "arguments": {},
                "expected": "unknown"
            }
        
        # Extract step number and description
        step_info = step_parts[0].split(": ", 1)
        step_number = step_info[0].replace("Step ", "")
        description = step_info[1] if len(step_info) > 1 else ""
        
        # Extract tool and arguments
        tool_info = step_parts[1].replace("Tool: ", "")
        tool_name, arguments = self._parse_tool_and_arguments(tool_info)
        
        # Extract expected outcome
        expected = step_parts[2].replace("Expected: ", "") if len(step_parts) > 2 else ""
        
        # Extract trigger for fallback steps
        trigger = None
        if len(step_parts) > 3 and in_fallback_section:
            trigger = step_parts[3].replace("Trigger: ", "")
        
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
    
    def _parse_tool_and_arguments(self, tool_info: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse tool name and arguments from tool info string
        
        Args:
            tool_info: Tool info string (e.g., "tool_name(arg1='value1', arg2=True)")
            
        Returns:
            Tuple[str, Dict[str, Any]]: (Tool name, Arguments dictionary)
        """
        # Extract tool name
        tool_name = tool_info.split("(")[0] if "(" in tool_info else tool_info
        
        # Extract arguments if present
        arguments = {}
        if "(" in tool_info and ")" in tool_info:
            args_str = tool_info.split("(", 1)[1].rsplit(")", 1)[0]
            if args_str:
                # Parse arguments
                for arg in args_str.split(", "):
                    if "=" in arg:
                        key, value = arg.split("=", 1)
                        arguments[key] = self._convert_argument_value(value)
        
        return tool_name, arguments
    
    def _convert_argument_value(self, value: str) -> Any:
        """
        Convert string argument value to appropriate Python type
        
        Args:
            value: String value to convert
            
        Returns:
            Any: Converted value
        """
        # Convert boolean values
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
        
        # Convert numeric values
        if value.isdigit():
            return int(value)
        
        # Convert string values (remove quotes)
        if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
            return value[1:-1]
        
        # Return as-is for other values
        return value
    
    def _create_success_result(self, investigation_plan: str, structured_plan: Dict[str, Any],
                             pod_name: str, namespace: str, volume_path: str,
                             message_list: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Create a success result dictionary
        
        Args:
            investigation_plan: The generated investigation plan
            structured_plan: Structured version of the investigation plan
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Message list for chat mode
            
        Returns:
            Dict[str, Any]: Success result dictionary
        """
        return {
            "status": "success",
            "investigation_plan": investigation_plan,
            "structured_plan": structured_plan,
            "pod_name": pod_name,
            "namespace": namespace,
            "volume_path": volume_path,
            "message_list": message_list
        }
    
    def _create_error_result(self, error_message: str, fallback_plan: str,
                           pod_name: str, namespace: str, volume_path: str,
                           message_list: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Create an error result dictionary
        
        Args:
            error_message: Error message describing what went wrong
            fallback_plan: Fallback investigation plan
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Message list for chat mode
            
        Returns:
            Dict[str, Any]: Error result dictionary
        """
        return {
            "status": "error",
            "error_message": error_message,
            "investigation_plan": fallback_plan,
            "pod_name": pod_name,
            "namespace": namespace,
            "volume_path": volume_path,
            "message_list": message_list
        }


async def run_plan_phase(pod_name: str, namespace: str, volume_path: str, 
                       collected_info: Dict[str, Any], config_data: Dict[str, Any] = None, 
                       message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
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
        # Extract and validate knowledge_graph from collected_info
        knowledge_graph = _validate_knowledge_graph(collected_info)
        
        # Initialize and execute Plan Phase
        plan_phase = PlanPhase(config_data)
        results = plan_phase.execute(knowledge_graph, pod_name, namespace, volume_path, message_list)
        
        # Log the results
        logger.info(f"Plan Phase completed with status: {results['status']}")
        
        # Save the investigation plan to a file if configured
        _save_investigation_plan_if_configured(
            config_data, results['investigation_plan'], namespace, pod_name
        )
        
        # Return the investigation plan as a string and the updated message list
        return results['investigation_plan'], results['message_list']
    
    except Exception as exception:
        # Create error response
        error_msg = ErrorHandler.create_error_response(
            exception, "Error during plan phase"
        )
        
        # Add error message to message list
        if message_list is not None:
            message_list = MessageListManager.add_to_message_list(message_list, error_msg)
        
        logging.error(f"Error in plan phase: {str(exception)}")
        return error_msg, message_list


def _validate_knowledge_graph(collected_info: Dict[str, Any]) -> KnowledgeGraph:
    """
    Extract and validate the knowledge graph from collected information
    
    Args:
        collected_info: Dictionary containing collected information from Phase 0
        
    Returns:
        KnowledgeGraph: Validated knowledge graph instance
        
    Raises:
        ValueError: If knowledge graph is missing or invalid
    """
    # Extract knowledge_graph from collected_info
    knowledge_graph = collected_info.get('knowledge_graph')
    
    # Validate knowledge_graph is a KnowledgeGraph instance
    if knowledge_graph is None:
        raise ValueError("Knowledge Graph not found in collected information")
    
    if not isinstance(knowledge_graph, KnowledgeGraph):
        raise ValueError(f"Invalid Knowledge Graph type: {type(knowledge_graph)}")
    
    return knowledge_graph


def _save_investigation_plan_if_configured(config_data: Dict[str, Any], investigation_plan: str, 
                                         namespace: str, pod_name: str) -> None:
    """
    Save the investigation plan to a file if configured
    
    Args:
        config_data: Configuration data for the system
        investigation_plan: Investigation plan to save
        namespace: Namespace of the pod
        pod_name: Name of the pod
    """
    logger = logging.getLogger(__name__)
    
    if not config_data or not config_data.get('plan_phase', {}).get('save_plan', False):
        return
    
    try:
        # Create output directory if it doesn't exist
        output_dir = config_data.get('output_dir', 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        # Create plan file path
        plan_file = os.path.join(output_dir, f"investigation_plan_{namespace}_{pod_name}.txt")
        
        # Write plan to file
        with open(plan_file, 'w') as f:
            f.write(investigation_plan)
        
        logger.info(f"Investigation Plan saved to {plan_file}")
    except Exception as e:
        logger.error(f"Error saving investigation plan to file: {str(e)}")
