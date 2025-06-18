#!/usr/bin/env python3
"""
LLM-based Plan Generator for Investigation Planning

This module contains utilities for generating investigation plans using LLMs.
"""

import logging
import json
import inspect
from typing import Dict, List, Any, Optional, Tuple
from phases.llm_factory import LLMFactory
from phases.utils import handle_exception, format_json_safely
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from tools.core.mcp_adapter import get_mcp_adapter

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
        
        # Get MCP adapter and tools
        self.mcp_adapter = get_mcp_adapter()
        self.mcp_tools = []
        
        # Get MCP tools for plan phase if available
        if self.mcp_adapter:
            self.mcp_tools = self.mcp_adapter.get_tools_for_phase('plan_phase')
            if self.mcp_tools:
                self.logger.info(f"Loaded {len(self.mcp_tools)} MCP tools for Plan Phase")
    
    def _initialize_llm(self) -> Optional[BaseChatModel]:
        """
        Initialize the LLM for plan generation using the LLMFactory
        
        Returns:
            BaseChatModel: Initialized LLM instance or None if initialization fails
        """
        try:
            # Create LLM using the factory
            llm_factory = LLMFactory(self.config_data)
            return llm_factory.create_llm()
        except Exception as e:
            error_msg = handle_exception("_initialize_llm", e, self.logger)
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
            # Prepare data for LLM
            system_prompt = self._generate_refinement_system_prompt()
            user_message = self._prepare_user_message(
                draft_plan, pod_name, namespace, volume_path, kg_context, phase1_tools
            )
            
            # Prepare message list for LLM
            messages = self._prepare_messages(system_prompt, user_message, message_list)
            
            # Call LLM and process response
            return self._call_llm_and_process_response(
                messages, pod_name, namespace, volume_path, message_list, user_message
            )
            
        except Exception as e:
            error_msg = handle_exception("refine_plan", e, self.logger)
            return self._handle_plan_generation_error(
                error_msg, pod_name, namespace, volume_path, message_list, user_message
            )
    
    def _prepare_user_message(self, draft_plan: List[Dict[str, Any]], pod_name: str, 
                            namespace: str, volume_path: str, kg_context: Dict[str, Any], 
                            phase1_tools: List[Dict[str, Any]]) -> str:
        """
        Prepare user message for LLM with formatted data
        
        Args:
            draft_plan: Draft plan from rule-based generator and static steps
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            kg_context: Knowledge Graph context with historical experience
            phase1_tools: Complete Phase1 tool registry
            
        Returns:
            str: Formatted user message
        """
        # Format input data for LLM context
        kg_context_str = format_json_safely(kg_context, fallback_message="Knowledge Graph context (simplified format)")
        draft_plan_str = format_json_safely(draft_plan, fallback_message="Draft plan (simplified format)")
        phase1_tools_str = format_json_safely(phase1_tools, fallback_message="Phase1 tools (simplified format)")
        
        # Format MCP tools if available
        mcp_tools_str = ""
        if self.mcp_tools:
            mcp_tools_str = format_json_safely(self.mcp_tools, fallback_message="MCP tools (simplified format)")
        
        # Extract and format historical experience data from kg_context
        historical_experiences_formatted = self._format_historical_experiences(kg_context)
        
        # Extract tools already used in draft plan
        used_tools = set()
        for step in draft_plan:
            tool = step.get('tool', '')
            if '(' in tool:
                tool = tool.split('(')[0]
            used_tools.add(tool)
        
        used_tools_str = ", ".join(used_tools)
        
        # Prepare user message for refinement task
        return f"""# INVESTIGATION PLAN GENERATION
## TARGET: Volume read/write errors in pod {pod_name} (namespace: {namespace}, volume path: {volume_path})

This plan will guide troubleshooting in subsequent phases. Each step will execute specific tools according to this plan.

## BACKGROUND INFORMATION

### 1. KNOWLEDGE GRAPH CONTEXT
Current base knowledge and hardware information. Issues identified in the Knowledge Graph are critical:
{kg_context_str}

### 2. HISTORICAL EXPERIENCE
Learn from previous similar cases to improve your plan:
{historical_experiences_formatted}

### 3. DRAFT PLAN
Static plan steps and preliminary steps from rule-based generator:
{draft_plan_str}

### 4. TOOLS ALREADY USED IN DRAFT PLAN
{used_tools_str}

### 5. AVAILABLE TOOLS FOR PHASE1
These tools will be used in next phases (reference only, do not invoke):
{phase1_tools_str}

### 6. AVAILABLE MCP TOOLS
These MCP tools can be used for cloud-specific diagnostics:
{mcp_tools_str}

## PLANNING INSTRUCTIONS

### PRIMARY OBJECTIVE
Create a comprehensive investigation plan that identifies potential problems and provides specific steps to diagnose and resolve volume read/write errors.

### SPECIFIC TASKS
1. **Task 1:** Analyze the Knowledge Graph context and historical experience to infer and list all possible problems
2. **Task 2:** For each possible problem, create detailed investigation steps using appropriate tools

### PLANNING GUIDELINES
1. Respect existing steps from the draft plan (both rule-based and static steps)
2. Infer potential volume read/write error phenomena and root causes based on Knowledge Graph and historical experience
3. Formulate detailed investigation steps, prioritizing verification steps most likely to identify the issue
4. Add additional steps as needed using available Phase1 tools
5. Reorder steps if necessary for logical flow
6. Ensure all steps reference only tools from the Phase1 tool registry

## IMPORTANT CONSTRAINTS
1. Do NOT invoke any tools - only reference them in your plan
2. Include static steps from the draft plan without modification
3. Use historical experience data to inform additional steps and refinements
4. Ensure all tool references follow the format shown in the AVAILABLE TOOLS
5. IMPORTANT: Do not add steps that use tools already present in the draft plan. Each tool should be used at most once in the entire plan

## REQUIRED OUTPUT FORMAT

Investigation Plan:
PossibleProblem 1: [Problem description, e.g., PVC configuration errors, access mode is incorrect]
Step 1: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]
Step 2: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]
...
PossibleProblem 2: [Problem description, e.g., Drive status is OFFLINE]
Step 1: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]
Step 2: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]
...
"""
    
    def _prepare_messages(self, system_prompt: str, user_message: str, 
                        message_list: List[Dict[str, str]] = None) -> List[Dict[str, str]]:
        """
        Prepare message list for LLM
        
        Args:
            system_prompt: System prompt for LLM
            user_message: User message for LLM
            message_list: Optional existing message list
            
        Returns:
            List[Dict[str, str]]: Prepared message list
        """
        if message_list is None:
            # Create new message list
            return [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ]
        
        # Use existing message list
        # If the last message is from the user, we need to regenerate the plan
        if isinstance(message_list[-1], HumanMessage):
            # Keep the system prompt and add the new user message
            return message_list
        else:
            # This is the first call, initialize with system prompt and user message
            return [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ]
    
    def _call_llm_and_process_response(self, messages: List[Dict[str, str]], 
                                     pod_name: str, namespace: str, volume_path: str,
                                     message_list: List[Dict[str, str]] = None,
                                     user_message: str = "") -> Tuple[str, List[Dict[str, str]]]:
        """
        Call LLM and process the response
        
        Args:
            messages: Messages for LLM
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            user_message: User message for fallback
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Refined Investigation Plan, Updated message list)
        """
        self.logger.info("Calling LLM to generate investigation plan")
        response = self.llm.invoke(messages)
        
        # Extract and format the plan
        plan_text = response.content
        
        # Ensure the plan has the required format
        if "Investigation Plan:" not in plan_text:
            plan_text = self._format_raw_plan(plan_text, pod_name, namespace, volume_path)
        
        # Update message list
        updated_message_list = self._update_message_list(messages, message_list, plan_text)
        
        self.logger.info("Successfully generated LLM-based investigation plan")
        return plan_text, updated_message_list
    
    def _update_message_list(self, messages: List[Dict[str, str]], 
                           message_list: List[Dict[str, str]], 
                           plan_text: str) -> List[Dict[str, str]]:
        """
        Update message list with LLM response
        
        Args:
            messages: Messages used for LLM
            message_list: Optional existing message list
            plan_text: Generated plan text
            
        Returns:
            List[Dict[str, str]]: Updated message list
        """
        if message_list is None:
            return messages + [{"role": "assistant", "content": plan_text}]
        
        # If the last message is from the user, append the assistant response
        if message_list[-1]["role"] == "user":
            message_list.append({"role": "assistant", "content": plan_text})
        else:
            # Replace the last message if it's from the assistant
            message_list[-1] = {"role": "assistant", "content": plan_text}
        
        return message_list
    
    def _handle_plan_generation_error(self, error_msg: str, pod_name: str, namespace: str, 
                                    volume_path: str, message_list: List[Dict[str, str]] = None,
                                    user_message: str = "") -> Tuple[str, List[Dict[str, str]]]:
        """
        Handle errors during plan generation
        
        Args:
            error_msg: Error message
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            user_message: User message for fallback
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Fallback plan, Updated message list)
        """
        # Generate fallback plan
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
- You must only reference tools available in the Phase1 tool registry
- All tool references must match the exact name and parameter format shown in the tools registry
- Include at least one disk-related check step and one volume-related check step.
- Max Steps: 10
- IMPORTANT: Each tool should be used at most once in the entire plan. Do not include duplicate tool calls. If a tool is already used in a step, do not use it again in another step.

OUTPUT FORMAT:
Your response must be a refined Investigation Plan with steps in this format:
Step X: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]

You may include fallback steps for error handling in this format:
Fallback Steps (if main steps fail):
Step FX: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected] | Trigger: [failure_condition]

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
            return self._format_historical_experience_entries(historical_experiences)
            
        except Exception as e:
            error_msg = handle_exception("_format_historical_experiences", e, self.logger)
            return "Error formatting historical experience data."
    
    def _format_historical_experience_entries(self, experiences: List[Dict[str, Any]]) -> str:
        """
        Format historical experience entries using Chain of Thought (CoT) structure
        
        Args:
            experiences: List of historical experience entries
            
        Returns:
            str: Formatted entries with CoT structure
        """
        formatted_entries = []
        
        for idx, exp in enumerate(experiences, 1):
            # Get attributes from the experience
            attributes = exp.get('attributes', {})
            
            # Check for new CoT format fields first
            observation = attributes.get('observation', attributes.get('phenomenon', 'Unknown observation'))
            thinking = attributes.get('thinking', [])
            investigation = attributes.get('investigation', [])
            diagnosis = attributes.get('diagnosis', attributes.get('root_cause', 'Unknown diagnosis'))
            resolution = attributes.get('resolution', attributes.get('resolution_method', 'No resolution method provided'))
            
            # Format thinking points
            thinking_formatted = ""
            if thinking:
                thinking_formatted = "Thinking:\n"
                for i, point in enumerate(thinking, 1):
                    thinking_formatted += f"{i}. {point}\n"
            
            # Format investigation steps
            investigation_formatted = ""
            if investigation:
                investigation_formatted = "Investigation:\n"
                for i, step in enumerate(investigation, 1):
                    if isinstance(step, dict):
                        step_text = step.get('step', '')
                        reasoning = step.get('reasoning', '')
                        investigation_formatted += f"{i}. {step_text}\n   - {reasoning}\n"
                    else:
                        investigation_formatted += f"{i}. {step}\n"
            else:
                # Fall back to legacy format
                localization_method = attributes.get('localization_method', '')
                if localization_method:
                    investigation_formatted = f"Investigation:\n{localization_method}\n"
            
            # Format resolution steps
            resolution_formatted = ""
            if isinstance(resolution, list):
                resolution_formatted = "Resolution:\n"
                for i, step in enumerate(resolution, 1):
                    resolution_formatted += f"{i}. {step}\n"
            else:
                resolution_formatted = f"Resolution:\n{resolution}\n"
            
            # Format the entry using CoT structure
            entry = f"""## HISTORICAL EXPERIENCE #{idx}: {observation}

**OBSERVATION**: {observation}

**THINKING**:
{thinking_formatted}

**INVESTIGATION**:
{investigation_formatted}

**DIAGNOSIS**: {diagnosis}

**RESOLUTION**:
{resolution_formatted}
"""
            formatted_entries.append(entry)
        
        return "\n".join(formatted_entries)
    
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
                step_line = self._format_step_line(step)
                plan_lines.append(step_line)
            
            return "\n".join(plan_lines)
            
        except Exception as e:
            error_msg = handle_exception("_format_draft_plan_as_fallback", e, self.logger)
            return "Investigation Plan:\nError occurred during plan generation."
    
    def _format_step_line(self, step: Dict[str, Any]) -> str:
        """
        Format a step into a string line
        
        Args:
            step: Step data
            
        Returns:
            str: Formatted step line
        """
        # Format arguments
        args_str = ', '.join(f'{k}={repr(v)}' for k, v in step.get('arguments', {}).items())
        
        # Format the step line
        return (
            f"Step {step['step']}: {step['description']} | "
            f"Tool: {step['tool']}({args_str}) | "
            f"Expected: {step['expected']}"
        )
    
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
        from phases.utils import generate_basic_fallback_plan
        return generate_basic_fallback_plan(pod_name, namespace, volume_path)
