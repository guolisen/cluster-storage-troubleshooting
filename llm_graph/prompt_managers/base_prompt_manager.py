#!/usr/bin/env python3
"""
Base Prompt Manager for Kubernetes Volume Troubleshooting

This module provides the base implementation of the PromptManagerInterface
with common functionality for all prompt managers.
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional
from llm_graph.prompt_manager_interface import PromptManagerInterface
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

class BasePromptManager(PromptManagerInterface):
    """
    Base implementation of PromptManagerInterface
    
    Provides common functionality for all prompt managers, including
    loading historical experience data and formatting messages.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the Base Prompt Manager
        
        Args:
            config_data: Configuration data for the system
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get_system_prompt(self, **kwargs) -> str:
        """
        Return the phase-specific system prompt
        
        This is a base implementation that should be overridden by subclasses.
        
        Args:
            **kwargs: Optional arguments for customizing the prompt
            
        Returns:
            str: System prompt for the current phase
        """
        return "You are an AI assistant helping with Kubernetes volume troubleshooting."
        
    def format_user_query(self, query: str, **kwargs) -> str:
        """
        Format user query messages for the phase
        
        This is a base implementation that should be overridden by subclasses.
        
        Args:
            query: User query to format
            **kwargs: Optional arguments for customizing the formatting
            
        Returns:
            str: Formatted user query
        """
        return query
        
    def get_tool_prompt(self, **kwargs) -> str:
        """
        Return prompts for tool invocation
        
        This is a base implementation that should be overridden by subclasses.
        
        Args:
            **kwargs: Optional arguments for customizing the prompt
            
        Returns:
            str: Tool invocation prompt for the current phase
        """
        return "Use the available tools to help with troubleshooting."
    
    def prepare_messages(self, system_prompt: str, user_message: str, 
                       message_list: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
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
        if message_list[-1]["role"] == "user":
            # Keep the system prompt and add the new user message
            return message_list
        else:
            # This is the first call, initialize with system prompt and user message
            return [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message)
            ]
    
    def get_context_summary(self, collected_info: Dict[str, Any]) -> str:
        """
        Get context summary from collected information
        
        Args:
            collected_info: Pre-collected diagnostic information
            
        Returns:
            str: Formatted context summary
        """
        return f"""
=== PRE-COLLECTED DIAGNOSTIC CONTEXT ===
Instructions:
    You can use the pre-collected diagnostic information to understand the current state of the Kubernetes cluster and the volume I/O issues being faced. Use this information to guide your troubleshooting process.

Knowledge Graph Summary:
{json.dumps(collected_info.get('knowledge_graph_summary', {}), indent=2)}

Pod Information:
{str(collected_info.get('pod_info', {}))}

PVC Information:
{str(collected_info.get('pvc_info', {}))}

PV Information:
{str(collected_info.get('pv_info', {}))}

Node Information Summary:
{str(collected_info.get('node_info', {}))}

CSI Driver Information:
{str(collected_info.get('csi_driver_info', {}))}

System Information:
{str(collected_info.get('system_info', {}))}

<<< Current Issues >>>
Issues Summary:
{str(collected_info.get('issues', {}))}

=== END PRE-COLLECTED CONTEXT ===
"""
    
    def _load_historical_experience(self) -> str:
        """
        Load historical experience data from JSON file
        
        Returns:
            str: Formatted historical experience examples
        """
        historical_experience_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
            'data', 
            'historical_experience.json'
        )
        historical_experience_examples = ""
        
        try:
            with open(historical_experience_path, 'r') as f:
                historical_experience = json.load(f)
                
            # Format historical experience data into CoT examples
            for i, experience in enumerate(historical_experience):
                # Create example header
                example_num = i + 1
                example_title = experience.get('observation', f"Example {example_num}")
                historical_experience_examples += f"\n## Example {example_num}: {example_title}\n\n"
                
                # Add OBSERVATION section
                historical_experience_examples += f"**OBSERVATION**: {experience.get('observation', '')}\n\n"
                
                # Add THINKING section
                historical_experience_examples += "**THINKING**:\n"
                thinking_points = experience.get('thinking', [])
                for j, point in enumerate(thinking_points):
                    historical_experience_examples += f"{j+1}. {point}\n"
                historical_experience_examples += "\n"
                
                # Add INVESTIGATION section
                historical_experience_examples += "**INVESTIGATION**:\n"
                investigation_steps = experience.get('investigation', [])
                for j, step_info in enumerate(investigation_steps):
                    if isinstance(step_info, dict):
                        step = step_info.get('step', '')
                        reasoning = step_info.get('reasoning', '')
                        historical_experience_examples += f"{j+1}. {step}\n   - {reasoning}\n"
                    else:
                        historical_experience_examples += f"{j+1}. {step_info}\n"
                historical_experience_examples += "\n"
                
                # Add DIAGNOSIS section
                historical_experience_examples += f"**DIAGNOSIS**: {experience.get('diagnosis', '')}\n\n"
                
                # Add RESOLUTION section
                historical_experience_examples += "**RESOLUTION**:\n"
                resolution_steps = experience.get('resolution', [])
                if isinstance(resolution_steps, list):
                    for j, step in enumerate(resolution_steps):
                        historical_experience_examples += f"{j+1}. {step}\n"
                else:
                    historical_experience_examples += f"{resolution_steps}\n"
                historical_experience_examples += "\n"
                
                # Limit to 2 examples to keep the prompt size manageable
                if example_num >= 2:
                    break
                    
        except Exception as e:
            logging.error(f"Error loading historical experience data: {e}")
            # Provide a fallback example in case the file can't be loaded
            historical_experience_examples = """
## Example 1: Volume Read Errors

**OBSERVATION**: Volume read errors appearing in pod logs

**THINKING**:
1. Read errors often indicate hardware issues with the underlying disk
2. Could be bad sectors, disk degradation, or controller problems
3. Need to check both logical (filesystem) and physical (hardware) health
4. Should examine error logs first, then check disk health metrics
5. Will use knowledge graph to find affected components, then check disk health

**INVESTIGATION**:
1. First, query error logs with `kg_query_nodes(type='log', time_range='24h', filters={{'message': 'I/O error'}})` to identify affected pods
   - This will show which pods are experiencing I/O errors and their frequency
2. Check disk health with `check_disk_health(node='node-1', disk_id='disk1')`
   - This will reveal SMART data and physical health indicators
3. Use 'xfs_repair -n *' to check volume health without modifying it
   - This will identify filesystem-level corruption or inconsistencies

**DIAGNOSIS**: Hardware failure in the underlying disk, specifically bad sectors causing read operations to fail

**RESOLUTION**:
1. Replace the faulty disk identified in `check_disk_health`
2. Restart the affected service with `systemctl restart db-service`
3. Verify pod status with `kubectl get pods` to ensure normal operation
"""
        
        return historical_experience_examples
        
    def format_historical_experiences_from_collected_info(self, collected_info: Dict[str, Any]) -> str:
        """
        Format historical experience data from collected information
        
        Args:
            collected_info: Pre-collected diagnostic information
            
        Returns:
            str: Formatted historical experience data
        """
        try:
            # Extract historical experiences from collected_info
            historical_experiences = collected_info.get('historical_experiences', [])
            
            if not historical_experiences:
                return "No historical experience data available."
            
            # Format historical experiences in a clear, structured way
            formatted_experiences = []
            
            for i, experience in enumerate(historical_experiences):
                # Get attributes
                attributes = experience.get('attributes', {})
                
                # Extract key fields
                observation = attributes.get('observation', attributes.get('phenomenon', 'Unknown issue'))
                diagnosis = attributes.get('diagnosis', attributes.get('root_cause', 'Unknown cause'))
                resolution = attributes.get('resolution', attributes.get('resolution_method', 'No resolution method'))
                
                # Format the experience
                formatted_exp = f"Experience #{i+1}:\n"
                formatted_exp += f"- Observation: {observation}\n"
                formatted_exp += f"- Diagnosis: {diagnosis}\n"
                formatted_exp += f"- Resolution: {resolution}\n"
                
                formatted_experiences.append(formatted_exp)
            
            return "\n".join(formatted_experiences)
            
        except Exception as e:
            logging.error(f"Error formatting historical experiences: {e}")
            return "Error formatting historical experience data."
