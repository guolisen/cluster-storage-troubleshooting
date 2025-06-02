#!/usr/bin/env python3
"""
Plan Phase for Kubernetes Volume Troubleshooting

This module contains the PlanPhase class that orchestrates the planning phase
of the troubleshooting process, generating an Investigation Plan for Phase 1.
"""

import logging
import os
import json
from typing import Dict, List, Any, Optional
from knowledge_graph import KnowledgeGraph
from phases.investigation_planner import InvestigationPlanner
from rich.logging import RichHandler
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich import print as rprint

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
               volume_path: str) -> Dict[str, Any]:
        """
        Execute the Plan Phase
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            Dict[str, Any]: Results of the Plan Phase, including the Investigation Plan
        """
        self.logger.info(f"Executing Plan Phase for {namespace}/{pod_name} volume {volume_path}")
        
        try:
            # Initialize Investigation Planner
            self.investigation_planner = InvestigationPlanner(knowledge_graph, self.config_data)
            
            # Generate Investigation Plan
            investigation_plan = self.investigation_planner.generate_investigation_plan(
                pod_name, namespace, volume_path
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
                "volume_path": volume_path
            }
            
        except Exception as e:
            self.logger.error(f"Error executing Plan Phase: {str(e)}")
            return {
                "status": "error",
                "error_message": str(e),
                "investigation_plan": self._generate_basic_fallback_plan(pod_name, namespace, volume_path),
                "pod_name": pod_name,
                "namespace": namespace,
                "volume_path": volume_path
            }
    
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
                if not line or line.startswith("Investigation Plan:") or line.startswith("Target:") or line.startswith("Generated Steps:"):
                    continue
                
                # Check if we're in the fallback section
                if line == "Fallback Steps (if main steps fail):":
                    in_fallback_section = True
                    continue
                
                # Parse step
                if line.startswith("Step "):
                    step_parts = line.split(" | ")
                    
                    if len(step_parts) >= 3:
                        # Extract step number and description
                        step_info = step_parts[0].split(": ", 1)
                        step_number = step_info[0].replace("Step ", "")
                        description = step_info[1] if len(step_info) > 1 else ""
                        
                        # Extract tool and arguments
                        tool_info = step_parts[1].replace("Tool: ", "")
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
                                        # Convert string representations to actual values
                                        if value.lower() == "true":
                                            value = True
                                        elif value.lower() == "false":
                                            value = False
                                        elif value.isdigit():
                                            value = int(value)
                                        elif value.startswith("'") and value.endswith("'"):
                                            value = value[1:-1]
                                        elif value.startswith('"') and value.endswith('"'):
                                            value = value[1:-1]
                                        arguments[key] = value
                        
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
                        
                        # Add to appropriate list
                        if in_fallback_section:
                            structured_plan["fallback_steps"].append(step)
                        else:
                            structured_plan["steps"].append(step)
            
            return structured_plan
            
        except Exception as e:
            self.logger.error(f"Error parsing investigation plan: {str(e)}")
            return {"steps": [], "fallback_steps": []}
    
    def _generate_basic_fallback_plan(self, pod_name: str, namespace: str, volume_path: str) -> str:
        """
        Generate a basic fallback plan when all else fails
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: Basic fallback Investigation Plan
        """
        basic_plan = f"""Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}
Generated Steps: 4 basic steps (fallback mode)

Step 1: Get all critical issues from Knowledge Graph | Tool: kg_get_all_issues(severity='critical') | Expected: List of critical issues affecting the system
Step 2: Analyze existing issues and patterns | Tool: kg_analyze_issues() | Expected: Root cause analysis and issue relationships  
Step 3: Get system overview | Tool: kg_get_summary() | Expected: Overall system health and entity statistics
Step 4: Print complete Knowledge Graph for manual analysis | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Full system visualization for troubleshooting

Fallback Steps (if main steps fail):
Step F1: Search for any Pod entities | Tool: kg_get_related_entities(entity_type='Pod', entity_id='any', max_depth=1) | Expected: List of all Pods | Trigger: entity_not_found
Step F2: Search for any Drive entities | Tool: kg_get_related_entities(entity_type='Drive', entity_id='any', max_depth=1) | Expected: List of all Drives | Trigger: no_target_found
"""
        return basic_plan


async def run_plan_phase(pod_name, namespace, volume_path, collected_info, config_data=None):
    """
    Run the Plan Phase
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Dictionary containing collected information from Phase 0, including knowledge_graph
        config_data: Configuration data for the system (optional)
        
    Returns:
        str: Investigation Plan as a formatted string
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Running Plan Phase for {namespace}/{pod_name} volume {volume_path}")
    
    # Extract knowledge_graph from collected_info
    knowledge_graph = collected_info.get('knowledge_graph')
    
    # Validate knowledge_graph is a KnowledgeGraph instance
    if knowledge_graph is None:
        logger.error("Knowledge Graph not found in collected_info")
        return "Error: Knowledge Graph not found in collected information"
    
    if not isinstance(knowledge_graph, KnowledgeGraph):
        logger.error(f"Invalid Knowledge Graph type: {type(knowledge_graph)}")
        return f"Error: Invalid Knowledge Graph type: {type(knowledge_graph)}"
    
    # Initialize and execute Plan Phase
    plan_phase = PlanPhase(config_data)
    results = plan_phase.execute(knowledge_graph, pod_name, namespace, volume_path)
    
    # Log the results
    logger.info(f"Plan Phase completed with status: {results['status']}")
    
    # Save the investigation plan to a file if configured
    if config_data and config_data.get('plan_phase', {}).get('save_plan', False):
        output_dir = config_data.get('output_dir', 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        plan_file = os.path.join(output_dir, f"investigation_plan_{namespace}_{pod_name}.txt")
        with open(plan_file, 'w') as f:
            f.write(results['investigation_plan'])
        
        logger.info(f"Investigation Plan saved to {plan_file}")
    
    # Check if chat mode is enabled
    chat_mode_enabled = config_data and config_data.get('chat_mode', {}).get('enabled', False)
    if chat_mode_enabled:
        from phases.chat_mode import handle_plan_phase_chat
        
        # Create a context for the LLM plan generator
        llm_context = {
            'pod_name': pod_name,
            'namespace': namespace,
            'volume_path': volume_path,
            'knowledge_graph': knowledge_graph
        }
        
        # Enter chat mode for user approval or refinement
        chat_result = handle_plan_phase_chat(llm_context)
        
        # If user provided instructions to refine the plan, regenerate it
        while chat_result.get('action') == 'regenerate':
            logger.info("Regenerating Investigation Plan based on user instructions")
            
            # Update the context with user instructions
            updated_context = chat_result.get('updated_context', {})
            
            # Regenerate the plan with updated context
            plan_phase = PlanPhase(config_data)
            results = plan_phase.execute(knowledge_graph, pod_name, namespace, volume_path)
            
            # Update the investigation plan
            investigation_plan = results['investigation_plan']

            # output the updated plan
            console = Console()
            console.print(Panel(
                f"[bold white]Updated Investigation Plan:\n{investigation_plan}",
                title="[bold green]UPDATED INVESTIGATION PLAN",
                border_style="green",
                padding=(1, 2)
            ))
            
            # Enter chat mode again for user approval or further refinement
            chat_result = handle_plan_phase_chat(updated_context)
    
    # Return the investigation plan as a string
    return results['investigation_plan']
