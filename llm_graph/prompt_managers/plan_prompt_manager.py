#!/usr/bin/env python3
"""
Plan Phase Prompt Manager for Kubernetes Volume Troubleshooting

This module provides the prompt manager implementation for the Plan phase
of the troubleshooting system.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from llm_graph.prompt_managers.base_prompt_manager import BasePromptManager

logger = logging.getLogger(__name__)

class PlanPromptManager(BasePromptManager):
    """
    Prompt manager for the Plan phase
    
    Handles prompt generation and formatting for the Plan phase,
    which generates an Investigation Plan for Phase 1.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the Plan Prompt Manager
        
        Args:
            config_data: Configuration data for the system
        """
        super().__init__(config_data)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get_system_prompt(self, use_react: bool = False, **kwargs) -> str:
        """
        Return the system prompt for the Plan phase
        
        Args:
            use_react: Whether to use React mode (default: False)
            **kwargs: Optional arguments for customizing the prompt
            
        Returns:
            str: System prompt for the Plan phase
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
            mcp_tools_info = kwargs.get('mcp_tools_info', "")

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
        
    def format_user_query(self, query: str, draft_plan: List[Dict[str, Any]] = None, 
                        pod_name: str = "", namespace: str = "", volume_path: str = "",
                        kg_context: Dict[str, Any] = None, phase1_tools: List[Dict[str, Any]] = None,
                        use_react: bool = True, **kwargs) -> str:
        """
        Format user query for the Plan phase
        
        Args:
            query: User query to format
            draft_plan: Draft plan from rule-based generator and static steps
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            kg_context: Knowledge Graph context with historical experience
            phase1_tools: Complete Phase1 tool registry
            use_react: Whether to use React mode (default: True)
            **kwargs: Optional arguments for customizing the formatting
            
        Returns:
            str: Formatted user query
        """
        # Format input data for LLM context
        kg_context_str = self._format_json_safely(kg_context, fallback_message="Knowledge Graph context (simplified format)")
        draft_plan_str = self._format_json_safely(draft_plan, fallback_message="Draft plan (simplified format)")
        phase1_tools_str = self._format_json_safely(phase1_tools, fallback_message="Phase1 tools (simplified format)")
        
        # Format MCP tools if available
        mcp_tools = kwargs.get('mcp_tools', [])
        mcp_tools_str = ""
        if mcp_tools:
            mcp_tools_str = self._format_json_safely(mcp_tools, fallback_message="MCP tools (simplified format)")
        
        # Extract and format historical experience data from kg_context
        historical_experiences_formatted = self._format_historical_experiences(kg_context)
        
        # Extract tools already used in draft plan
        used_tools = set()
        if draft_plan:
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
        
    def get_tool_prompt(self, **kwargs) -> str:
        """
        Return prompts for tool invocation in the Plan phase
        
        Args:
            **kwargs: Optional arguments for customizing the prompt
            
        Returns:
            str: Tool invocation prompt for the Plan phase
        """
        return """
When you identify a knowledge gap, use the appropriate MCP tool to gather the information you need.
Don't guess or make assumptions when you can use a tool to get accurate information.
"""
    
    def _format_json_safely(self, data: Any, fallback_message: str = "Data could not be formatted") -> str:
        """
        Format data as JSON with fallback for complex objects
        
        Args:
            data: Data to format as JSON
            fallback_message: Message to use if formatting fails
            
        Returns:
            str: Formatted JSON string or fallback message
        """
        try:
            if data is None:
                return fallback_message
                
            return json.dumps(data, indent=2)
        except Exception as e:
            self.logger.error(f"Error formatting JSON: {e}")
            return f"{fallback_message} (Error: {str(e)})"
    
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
            self.logger.error(f"Error formatting historical experiences: {e}")
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
