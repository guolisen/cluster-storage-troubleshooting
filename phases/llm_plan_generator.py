#!/usr/bin/env python3
"""
LLM-based Plan Generator for Investigation Planning

This module contains utilities for generating investigation plans using LLMs.
"""

import logging
import json
import inspect
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from phases.llm_factory import LLMFactory
from phases.utils import handle_exception, format_json_safely
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from tools.core.mcp_adapter import get_mcp_adapter
from phases.plan_phase_react import PlanPhaseReActGraph, run_plan_phase_react

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
                
        # Initialize ReAct graph if needed
        self.react_graph = None
        if self.config_data.get('plan_phase', {}).get('use_react', False):
            self.logger.info("Initializing Plan Phase ReAct Graph")
            self.react_graph = PlanPhaseReActGraph(self.config_data)
    
    def _initialize_llm(self) -> Optional[BaseChatModel]:
        """
        Initialize the LLM for plan generation using the LLMFactory
        
        Returns:
            BaseChatModel: Initialized LLM instance or None if initialization fails
        """
        try:
            # Create LLM using the factory
            llm_factory = LLMFactory(self.config_data)
            
            # Check if streaming is enabled in config
            streaming_enabled = self.config_data.get('llm', {}).get('streaming', False)
            
            # Check if React mode is enabled
            use_react = self.config_data.get('plan_phase', {}).get('use_react', False)
            
            # Create LLM with streaming if enabled
            llm = llm_factory.create_llm(
                streaming=streaming_enabled,
                phase_name="plan_phase"
            )
            
            return llm
        except Exception as e:
            error_msg = handle_exception("_initialize_llm", e, self.logger)
            return None
    
    async def refine_plan(self, draft_plan: List[Dict[str, Any]], pod_name: str, namespace: str, 
                   volume_path: str, kg_context: Dict[str, Any], phase1_tools: List[Dict[str, Any]],
                   message_list: List[Dict[str, str]] = None, use_react: bool = True) -> Tuple[str, List[Dict[str, str]]]:
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
            use_react: Whether to use React mode (default: True)
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Refined Investigation Plan, Updated message list)
        """
        try:
            # Prepare data for LLM
            system_prompt = self._generate_refinement_system_prompt(use_react)
            user_message = self._prepare_user_message(
                draft_plan, pod_name, namespace, volume_path, kg_context, phase1_tools, use_react
            )
            
            # Prepare message list for LLM
            messages = self._prepare_messages(system_prompt, user_message, message_list)
            
            # Call LLM and process response
            return await self._call_llm_and_process_response(
                messages, pod_name, namespace, volume_path, message_list, user_message, use_react
            )
            
        except Exception as e:
            error_msg = handle_exception("refine_plan", e, self.logger)
            return self._handle_plan_generation_error(
                error_msg, pod_name, namespace, volume_path, message_list, user_message
            )
    
    def _prepare_user_message(self, draft_plan: List[Dict[str, Any]], pod_name: str, 
                            namespace: str, volume_path: str, kg_context: Dict[str, Any], 
                            phase1_tools: List[Dict[str, Any]], use_react: bool = True) -> str:
        """
        Prepare user message for LLM with formatted data
        
        Args:
            draft_plan: Draft plan from rule-based generator and static steps
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            kg_context: Knowledge Graph context with historical experience
            phase1_tools: Complete Phase1 tool registry
            use_react: Whether to use React mode (default: True)
            
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
        
        # Base user message content for both modes
        base_message = f"""# INVESTIGATION PLAN GENERATION
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

When you identify a knowledge gap, use the appropriate MCP tool to gather the information you need. Don't guess or make assumptions when you can use a tool to get accurate information.

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
1. Search related information by MCP tools as referenced in the AVAILABLE TOOLS section at first
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
        
        # Add mode-specific instructions
        if use_react:
            # React mode instructions
            react_additions = """
## TASK
1. Analyze the available information to understand the context
2. Identify any knowledge gaps that need to be filled
3. Use MCP tools to gather additional information as needed
4. Create a comprehensive Investigation Plan with specific steps to diagnose and resolve the volume I/O error

Please start by analyzing the available information and identifying any knowledge gaps.
"""
            return base_message + react_additions
        else:
            return base_message
    
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
    
    async def _call_llm_and_process_response(self, messages: List[Dict[str, str]], 
                                     pod_name: str, namespace: str, volume_path: str,
                                     message_list: List[Dict[str, str]] = None,
                                     user_message: str = "", 
                                     use_react: bool = True) -> Tuple[str, List[Dict[str, str]]]:
        """
        Call LLM and process the response
        
        Args:
            messages: Messages for LLM
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            user_message: User message for fallback
            use_react: Whether to use React mode (default: True)
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Refined Investigation Plan, Updated message list)
        """
        self.logger.info(f"Calling LLM to generate investigation plan using {'React' if use_react else 'Legacy'} mode")
        self.logger.info("This may take a few moments...")
        
        # Call model with appropriate approach based on mode
        if use_react and self.mcp_tools and self.react_graph:
            # React mode with PlanPhaseReActGraph
            self.logger.info(f"Using PlanPhaseReActGraph with {len(self.mcp_tools)} MCP tools")
            
            try:
                # Run the Plan Phase ReAct graph
                plan_text, updated_messages = await run_plan_phase_react(
                    pod_name=pod_name,
                    namespace=namespace,
                    volume_path=volume_path,
                    messages=messages,  # Pass the messages directly
                    config_data=self.config_data
                )
                
                # Update message list with the result
                updated_message_list = self._update_message_list_from_react(message_list, updated_messages)
                
                # Ensure the plan has the required format
                if "Investigation Plan:" not in plan_text:
                    plan_text = self._format_raw_plan(plan_text, pod_name, namespace, volume_path)
                
                self.logger.info("Successfully generated LLM-based investigation plan using PlanPhaseReActGraph")
                return plan_text, updated_message_list
                
            except Exception as e:
                error_msg = handle_exception("_call_llm_and_process_response (PlanPhaseReActGraph)", e, self.logger)
                self.logger.warning(f"Failed to use PlanPhaseReActGraph: {error_msg}, falling back to legacy mode")
                # Fall back to legacy mode if React graph fails
                use_react = False
        
        # Legacy mode (either by choice or as fallback)
        if use_react and self.mcp_tools:
            # Simple React mode with bound tools
            self.logger.info(f"Using simple React mode with {len(self.mcp_tools)} MCP tools")
            response = self.llm.bind_tools(self.mcp_tools).invoke(messages)
        else:
            # Legacy mode or React mode without MCP tools
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
    
    def _generate_refinement_system_prompt(self, use_react: bool = False) -> str:
        """
        Generate system prompt for LLM focused on plan refinement with static guiding principles
        
        Args:
            use_react: Whether to use React mode (default: False)
            
        Returns:
            str: System prompt for LLM
        """
        # Base system prompt for both modes
        base_prompt = """You are an expert Kubernetes storage troubleshooter. Your task is to refine a draft Investigation Plan for troubleshooting volume read/write errors in Kubernetes.

TASK:
1. Review the draft plan containing preliminary steps from rule-based analysis and mandatory static steps
2. Analyze the Knowledge Graph and historical experience data
3. Refine the plan by:
   - Respecting existing steps (do not remove or modify static steps as much as possible)
   - Adding necessary additional steps using only the provided Phase1 tools
   - Reordering steps if needed for logical flow
   - Adding fallback steps for error handling

CONSTRAINTS:
- When you identify a knowledge gap, use the appropriate MCP tool to gather the information you need. Don't guess or make assumptions when you can use a tool to get accurate information.
- You must only reference tools available in the Phase1 tool registry
- All tool references must match the exact name and parameter format shown in the tools registry
- Include at least one disk-related check step and one volume-related check step.
- Max Steps: 15
- IMPORTANT: Each tool should be used at most once in the entire plan. Do not include duplicate tool calls. If a tool is already used in a step, do not use it again in another step.

OUTPUT FORMAT:
Your response must be a refined Investigation Plan with steps in this format:
Step X: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]

You may include fallback steps for error handling in this format:
Fallback Steps (if main steps fail):
Step FX: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected] | Trigger: [failure_condition]

The plan must be comprehensive, logically structured, and include all necessary steps to investigate the volume I/O errors.
"""

        # Add React-specific additions if in React mode
        if use_react:
            # Get available MCP tools information
            mcp_tools_info = ""
            if hasattr(self, 'mcp_tools') and self.mcp_tools:
                mcp_tools_info = "\n".join([
                    f"- {tool.name}: {tool.description}" for tool in self.mcp_tools
                ])


            react_additions = f"""
You are operating in a ReAct (Reasoning and Acting) framework where you can:
1. REASON about the problem and identify knowledge gaps
2. ACT by calling external tools to gather information
3. OBSERVE the results and update your understanding
4. Continue this loop until you have enough information to create a comprehensive plan

Available MCP tools:
{mcp_tools_info}

When you identify a knowledge gap, use the appropriate MCP tool to gather the information you need. Don't guess or make assumptions when you can use a tool to get accurate information.

When you've completed the Investigation Plan, include the marker [END_GRAPH] at the end of your message.
"""
            return base_prompt + react_additions
        
        # Return base prompt for Legacy mode
        return base_prompt
    
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
    
    def _extract_kg_context_from_message(self, message_content: str) -> Dict[str, Any]:
        """
        Extract knowledge graph context from a message
        
        Args:
            message_content: Content of a message containing knowledge graph context
            
        Returns:
            Dict[str, Any]: Extracted knowledge graph context
        """
        try:
            # Find the knowledge graph context section
            start_marker = "KNOWLEDGE GRAPH CONTEXT"
            end_markers = ["HISTORICAL EXPERIENCE", "DRAFT PLAN", "TOOLS ALREADY USED"]
            
            if start_marker not in message_content:
                self.logger.warning("Knowledge Graph Context section not found in message")
                return {}
            
            # Get start position
            start_pos = message_content.find(start_marker)
            start_pos = message_content.find('\n', start_pos) + 1  # Move to next line
            
            # Find the end position using end markers
            end_pos = len(message_content)
            for marker in end_markers:
                marker_pos = message_content.find(marker, start_pos)
                if marker_pos != -1 and marker_pos < end_pos:
                    end_pos = marker_pos
            
            # Extract and parse the knowledge graph context
            kg_context_str = message_content[start_pos:end_pos].strip()
            
            # Try to parse as JSON
            try:
                # Look for JSON-like content
                json_start = kg_context_str.find('{')
                json_end = kg_context_str.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    kg_json_str = kg_context_str[json_start:json_end]
                    return json.loads(kg_json_str)
                
                # Fall back to treating whole content as knowledge graph context
                return {"knowledge_graph_content": kg_context_str}
                
            except json.JSONDecodeError:
                # Not valid JSON, return as raw text
                return {"knowledge_graph_content": kg_context_str}
                
        except Exception as e:
            error_msg = handle_exception("_extract_kg_context_from_message", e, self.logger)
            self.logger.warning(f"Failed to extract Knowledge Graph context: {error_msg}")
            return {}
    
    def _update_message_list_from_react(self, original_message_list: List[Dict[str, str]], 
                                      react_messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Update message list from React graph results
        
        Args:
            original_message_list: Original message list
            react_messages: Messages from React graph
            
        Returns:
            List[Dict[str, str]]: Updated message list
        """
        if not original_message_list:
            # If no original message list, return react messages directly
            return react_messages
        
        # Get the first message from original list (system prompt)
        system_message = original_message_list[0]
        
        # Get the last message from react messages (final plan)
        final_message = react_messages[-1] if react_messages else {"role": "assistant", "content": "No plan generated"}
        
        # Create new message list with system prompt and final plan
        new_message_list = [system_message]
        
        # If there are at least 2 messages in the original list, add the user message
        if len(original_message_list) > 1:
            user_message = original_message_list[1]
            new_message_list.append(user_message)
        
        # Add the final message
        new_message_list.append(final_message)
        
        return new_message_list
