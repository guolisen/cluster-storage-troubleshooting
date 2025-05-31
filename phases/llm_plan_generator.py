#!/usr/bin/env python3
"""
LLM-based Plan Generator for Investigation Planning

This module contains utilities for generating investigation plans using LLMs.
"""

import logging
import json
import inspect
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

class LLMPlanGenerator:
    """
    Generates Investigation Plans using Large Language Models
    
    Uses LLMs to analyze Knowledge Graph data, hypothesize causes of volume
    read/write errors, prioritize them, and generate step-by-step plans.
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
    
    def generate_plan(self, pod_name: str, namespace: str, volume_path: str, 
                     kg_context: Dict[str, Any], tool_registry: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Generate Investigation Plan using LLM
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            kg_context: Knowledge Graph context
            tool_registry: Registry of available tools
            
        Returns:
            str: Formatted Investigation Plan
        """
        try:
            # Step 1: Generate system prompt
            system_prompt = self._generate_system_prompt(pod_name, namespace, volume_path)
            
            # Step 2: Format contexts as strings with custom serialization
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
            
            try:
                tool_registry_str = json.dumps(tool_registry, indent=2, default=json_serializer)
            except Exception as e:
                self.logger.warning(f"Error serializing tool registry: {str(e)}")
                # Fallback to a simpler representation
                tool_registry_str = str(tool_registry)
            
            # Step 3: Prepare user message with explicit historical experience section
            
            # Extract and format historical experience data from kg_context
            historical_experiences_formatted = self._format_historical_experiences(kg_context)
            
            user_message = f"""Generate an Investigation Plan for volume read/write errors in pod {pod_name} in namespace {namespace} at volume path {volume_path}.

KNOWLEDGE GRAPH CONTEXT:
{kg_context_str}

HISTORICAL EXPERIENCE:
{historical_experiences_formatted}

AVAILABLE TOOLS FOR PHASE1:
{tool_registry_str}

Analyze the Knowledge Graph, generate hypotheses for the volume read/write errors, prioritize them, and create a step-by-step Investigation Plan using the available tools.

IMPORTANT: Pay special attention to the historical experience data above. Use this data to:
1. Identify patterns where current symptoms match previously observed phenomena
2. Consider known root causes from similar past incidents when forming hypotheses
3. Incorporate proven localization methods into your Investigation Plan
4. Reference relevant historical experiences when prioritizing hypotheses (high, medium, low)
"""
            
            # Step 4: Call LLM
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
            
            self.logger.info("Successfully generated LLM-based investigation plan")
            return plan_text
            
        except Exception as e:
            self.logger.error(f"Error in LLM-based plan generation: {str(e)}")
            return self._generate_basic_fallback_plan(pod_name, namespace, volume_path)
    
    def _generate_system_prompt(self, pod_name: str, namespace: str, volume_path: str) -> str:
        """
        Generate system prompt for LLM with only static guiding principles
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: System prompt for LLM
        """
        return f"""You are an expert Kubernetes storage troubleshooter. Your task is to analyze the Knowledge Graph from Phase0, hypothesize the most likely causes of volume read/write errors, prioritize them by likelihood, and create a step-by-step Investigation Plan for Phase1.

TASK:
1. Analyze the Knowledge Graph to identify patterns or indicators of volume read/write errors in pod {pod_name} in namespace {namespace} at volume path {volume_path}.
2. Generate hypotheses for the top potential causes of the volume read/write errors.
3. Prioritize these hypotheses by likelihood (high, medium, low) based on evidence in the Knowledge Graph and historical experience data.
4. Create a step-by-step Investigation Plan for Phase1 to execute, using the available tools.

USING HISTORICAL EXPERIENCE:
Use the historical experience data provided in the query message to:
- Identify patterns similar to the current issue
- Inform your hypotheses about what might be causing the current issue
- Guide which tools to use and in what order during your investigation
- Understand potential solutions once the root cause is confirmed

OUTPUT FORMAT:
Your response must include:

1. HYPOTHESES ANALYSIS:
List the top potential causes, each with:
- Description of the potential cause
- Evidence from the Knowledge Graph
- Reference to relevant historical experience (if applicable)
- Likelihood ranking (high, medium, low)

2. INVESTIGATION PLAN:
A step-by-step plan with:
- Step number
- Description of the action
- Tool to use with parameters
- Expected outcome
- Reference to historical experience (if this step was informed by past incidents)

Format each step as:
Step X: [Description] | Tool: [tool_name(parameters)] | Expected: [expected_outcome]

Include fallback steps for error handling:
Fallback Steps (if main steps fail):
Step FX: [Description] | Tool: [tool_name(parameters)] | Expected: [expected_outcome] | Trigger: [failure_condition]
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
