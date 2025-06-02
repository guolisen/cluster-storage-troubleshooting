#!/usr/bin/env python3
"""
LLM-based Plan Generator for Investigation Planning

This module contains utilities for generating investigation plans using LLMs.
"""

import logging
import json
import inspect
from typing import Dict, List, Any, Optional, Tuple
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

class LLMPlanGenerator:
    """
    Refines Investigation Plans using Large Language Models
    
    Uses LLMs to refine draft investigation plans by analyzing Knowledge Graph data,
    historical experience, and available Phase1 tools, ensuring a comprehensive
    and actionable final plan without directly invoking the tools.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the LLM Plan Generator
        
        Args:
            config_data: Configuration data for the LLM
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.llm = self._initialize_llm()
    
    def _initialize_llm(self) -> Optional[ChatOpenAI]:
        """
        Initialize the LLM for plan generation
        
        Returns:
            ChatOpenAI: Initialized LLM instance or None if initialization fails
        """
        try:
            # Initialize LLM with configuration
            return ChatOpenAI(
                model=self.config_data.get('llm', {}).get('model', 'gpt-4'),
                api_key=self.config_data.get('llm', {}).get('api_key', None),
                base_url=self.config_data.get('llm', {}).get('api_endpoint', None),
                temperature=self.config_data.get('llm', {}).get('temperature', 0.1),
                max_tokens=self.config_data.get('llm', {}).get('max_tokens', 4000)
            )
        except Exception as e:
            self.logger.error(f"Error initializing LLM: {str(e)}")
            return None
    
    def refine_plan(self, draft_plan: List[Dict[str, Any]], pod_name: str, namespace: str, 
                   volume_path: str, kg_context: Dict[str, Any], phase1_tools: List[Dict[str, Any]],
                   message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
        """
        Refine a draft investigation plan using LLM
        
        Args:
            draft_plan: Draft plan from rule-based generator and static steps
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            kg_context: Knowledge Graph context with historical experience
            phase1_tools: Complete Phase1 tool registry with names, descriptions, parameters, and invocation methods
            message_list: Optional message list for chat mode
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Refined Investigation Plan, Updated message list)
        """
        try:
            # Step 1: Generate system prompt for refinement
            system_prompt = self._generate_refinement_system_prompt()
            
            # Step 2: Format input data for LLM context
            def json_serializer(obj):
                """Custom JSON serializer to handle non-serializable objects"""
                try:
                    # Try to convert to a simple dict first
                    if hasattr(obj, "__dict__"):
                        return obj.__dict__
                    # Handle sets
                    elif isinstance(obj, set):
                        return list(obj)
                    # Handle other non-serializable types
                    else:
                        return str(obj)
                except:
                    return str(obj)
            
            try:
                kg_context_str = json.dumps(kg_context, indent=2, default=json_serializer)
            except Exception as e:
                self.logger.warning(f"Error serializing Knowledge Graph context: {str(e)}")
                # Fallback to a simpler representation
                kg_context_str = str(kg_context)

            # Format draft plan for LLM input
            try:
                draft_plan_str = json.dumps(draft_plan, indent=2, default=json_serializer)
            except Exception as e:
                self.logger.warning(f"Error serializing draft plan: {str(e)}")
                draft_plan_str = str(draft_plan)
                
            # Extract and format historical experience data from kg_context
            historical_experiences_formatted = self._format_historical_experiences(kg_context)
            
            # Format phase1_tools for LLM input
            try:
                phase1_tools_str = json.dumps(phase1_tools, indent=2, default=json_serializer)
            except Exception as e:
                self.logger.warning(f"Error serializing Phase1 tools: {str(e)}")
                phase1_tools_str = str(phase1_tools)
            
            # Step 3: Prepare user message for refinement task
            user_message = f"""Refine the draft Investigation Plan for volume read/write errors in pod {pod_name} in namespace {namespace} at volume path {volume_path}.
this plan will be used to troubleshoot the issue in next phases. The next phase will execute or run tool according to the steps in this plan.

KNOWLEDGE GRAPH CONTEXT(current base knowledge and some hardware information): 
{kg_context_str}

DRAFT PLAN(static plan steps and preliminary steps from rule-based generator, please do not modify static steps as much as possible):
{draft_plan_str}

HISTORICAL EXPERIENCE(the historical experience data, you can learn from this data to improve the plan):
{historical_experiences_formatted}

AVAILABLE TOOLS FOR PHASE1(this tools will be used in next phases, please do not invoke any tools, just reference them in your plan):
{phase1_tools_str}

Your task is to refine the draft plan by:
1. Respecting the existing steps from the draft plan (both rule-based and static steps)
2. Adding additional steps as needed using the available Phase1 tools
3. Reordering steps if necessary for logical flow
4. Ensuring all steps reference only tools from the Phase1 tool registry

IMPORTANT CONSTRAINTS:
1. Do NOT invoke any tools - only reference them in your plan
2. Include static steps from the draft plan without modification
3. Use historical experience data to inform additional steps and refinements
4. Ensure all tool references follow the format shown in the AVAILABLE TOOLS
5. Output the plan in the required format:

Investigation Plan:
Step 1: [Description] | Tool: [tool_name(parameters)] | Expected: [expected]
Step 2: [Description] | Tool: [tool_name(parameters)] | Expected: [expected]
...
"""
            
            # Step 4: Initialize or update message list
            if message_list is None:
                # Create new message list
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            else:
                # Use existing message list
                # If the last message is from the user, we need to regenerate the plan
                if message_list[-1]["role"] == "user":
                    # Keep the system prompt and add the new user message
                    messages = message_list
                else:
                    # This is the first call, initialize with system prompt and user message
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ]
            
            self.logger.info("Calling LLM to generate investigation plan")
            response = self.llm.invoke(messages)
            
            # Step 5: Extract and format the plan
            plan_text = response.content
            
            # Step 6: Ensure the plan has the required format
            if "Investigation Plan:" not in plan_text:
                plan_text = self._format_raw_plan(plan_text, pod_name, namespace, volume_path)
            
            # Add assistant response to message list
            if message_list is None:
                message_list = messages + [{"role": "assistant", "content": plan_text}]
            else:
                # If the last message is from the user, append the assistant response
                if message_list[-1]["role"] == "user":
                    message_list.append({"role": "assistant", "content": plan_text})
                else:
                    # Replace the last message if it's from the assistant
                    message_list[-1] = {"role": "assistant", "content": plan_text}
            
            self.logger.info("Successfully generated LLM-based investigation plan")
            return plan_text, message_list
            
        except Exception as e:
            self.logger.error(f"Error in LLM-based plan generation: {str(e)}")
            fallback_plan = self._generate_basic_fallback_plan(pod_name, namespace, volume_path)
            
            # Add fallback plan to message list
            if message_list is None:
                message_list = [
                    {"role": "system", "content": self._generate_refinement_system_prompt()},
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": fallback_plan}
                ]
            else:
                # If the last message is from the user, append the assistant response
                if message_list[-1]["role"] == "user":
                    message_list.append({"role": "assistant", "content": fallback_plan})
                else:
                    # Replace the last message if it's from the assistant
                    message_list[-1] = {"role": "assistant", "content": fallback_plan}
            
            return fallback_plan, message_list
    
    def _generate_refinement_system_prompt(self) -> str:
        """
        Generate system prompt for LLM focused on plan refinement with static guiding principles
        
        Returns:
            str: System prompt for LLM
        """
        return """You are an expert Kubernetes storage troubleshooter. Your task is to refine a draft Investigation Plan for troubleshooting volume read/write errors in Kubernetes.

TASK:
1. Review the draft plan containing preliminary steps from rule-based analysis and mandatory static steps
2. Analyze the Knowledge Graph and historical experience data
3. Refine the plan by:
   - Respecting existing steps (do not remove or modify static steps)
   - Adding necessary additional steps using only the provided Phase1 tools
   - Reordering steps if needed for logical flow
   - Adding fallback steps for error handling

CONSTRAINTS:
- You must NOT invoke any tools - only reference them in your plan
- You must include all static steps from the draft plan without modification
- You must only reference tools available in the Phase1 tool registry
- All tool references must match the exact name and parameter format shown in the tools registry

OUTPUT FORMAT:
Your response must be a refined Investigation Plan with steps in this format:
Step X: [Description] | Tool: [tool_name(parameters)] | Expected: [expected]

You may include fallback steps for error handling in this format:
Fallback Steps (if main steps fail):
Step FX: [Description] | Tool: [tool_name(parameters)] | Expected: [expected] | Trigger: [failure_condition]

The plan must be comprehensive, logically structured, and include all necessary steps to investigate the volume I/O errors.
"""
    
    def _format_raw_plan(self, raw_plan: str, pod_name: str, namespace: str, volume_path: str) -> str:
        """
        Format raw LLM output into the required Investigation Plan format
        
        Args:
            raw_plan: Raw LLM output
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: Formatted Investigation Plan
        """
        lines = []
        lines.append(f"Investigation Plan:")
        lines.append(f"Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}")
        
        # Count steps
        main_steps = 0
        fallback_steps = 0
        
        # Extract steps from raw plan
        for line in raw_plan.split('\n'):
            if line.strip().startswith("Step ") and " | Tool: " in line:
                main_steps += 1
            elif line.strip().startswith("Step F") and " | Tool: " in line:
                fallback_steps += 1
        
        lines.append(f"Generated Steps: {main_steps} main steps, {fallback_steps} fallback steps")
        lines.append("")
        
        # Add the raw plan content
        lines.append(raw_plan)
        
        return "\n".join(lines)
    
    def _format_historical_experiences(self, kg_context: Dict[str, Any]) -> str:
        """
        Format historical experience data from Knowledge Graph context
        
        Args:
            kg_context: Knowledge Graph context containing historical experience data
            
        Returns:
            str: Formatted historical experience data for LLM consumption
        """
        try:
            # Extract historical experiences from kg_context
            historical_experiences = kg_context.get('historical_experiences', [])
            
            if not historical_experiences:
                return "No historical experience data available."
            
            # Format historical experiences in a clear, structured way
            formatted_entries = []
            
            for idx, exp in enumerate(historical_experiences, 1):
                # Get attributes from the experience
                attributes = exp.get('attributes', {})
                phenomenon = attributes.get('phenomenon', 'Unknown phenomenon')
                root_cause = attributes.get('root_cause', 'Unknown root cause')
                localization_method = attributes.get('localization_method', 'No localization method provided')
                resolution_method = attributes.get('resolution_method', 'No resolution method provided')
                
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
    
    def _format_draft_plan_as_fallback(self, draft_plan: List[Dict[str, Any]]) -> str:
        """
        Format the draft plan as a fallback when LLM refinement fails
        
        Args:
            draft_plan: Draft plan from rule-based generator and static steps
            
        Returns:
            str: Formatted Investigation Plan
        """
        try:
            plan_lines = ["Investigation Plan:"]
            
            # Add the draft plan steps
            for step in draft_plan:
                step_line = (
                    f"Step {step['step']}: {step['description']} | "
                    f"Tool: {step['tool']}({', '.join(f'{k}={repr(v)}' for k, v in step.get('arguments', {}).items())}) | "
                    f"Expected: {step['expected']}"
                )
                plan_lines.append(step_line)
            
            return "\n".join(plan_lines)
            
        except Exception as e:
            self.logger.error(f"Error formatting draft plan as fallback: {str(e)}")
            return "Investigation Plan:\nError occurred during plan generation."
    
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
