#!/usr/bin/env python3
"""
Prompt Manager for Kubernetes Volume I/O Error Troubleshooting

This module provides backward compatibility with the original PromptManager class
by importing and using the new LegacyPromptManager from the llm_graph package.
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional
from llm_graph.prompt_managers.legacy_prompt_manager import LegacyPromptManager

logger = logging.getLogger(__name__)

# For backward compatibility, provide the original PromptManager class
# that delegates to the new LegacyPromptManager
class PromptManager:
    """
    Manages all prompts used in the troubleshooting system
    
    Centralizes prompt generation and management to improve maintainability
    and make it easier to update prompts across the system.
    
    This class is maintained for backward compatibility and delegates
    to the new LegacyPromptManager class.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the Prompt Manager
        
        Args:
            config_data: Configuration data for the system
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Create an instance of the new LegacyPromptManager
        self.legacy_prompt_manager = LegacyPromptManager(config_data)
    
    def get_phase_specific_guidance(self, phase: str, final_output_example: str = "") -> str:
        """
        Get phase-specific guidance prompt
        
        Args:
            phase: Current troubleshooting phase ("phase1" for investigation, "phase2" for action)
            final_output_example: Example of final output format
            
        Returns:
            str: Phase-specific guidance prompt
        """
        return self.legacy_prompt_manager.get_phase_specific_guidance(phase, final_output_example)
    
    def get_system_prompt(self, phase: str, final_output_example: str = "") -> str:
        """
        Get the system prompt for a specific phase
        
        Args:
            phase: Current troubleshooting phase
            final_output_example: Example of final output format
            
        Returns:
            str: System prompt for the specified phase
        """
        return self.legacy_prompt_manager.get_system_prompt(phase, final_output_example)
    
    def get_context_summary(self, collected_info: Dict[str, Any]) -> str:
        """
        Get context summary from collected information
        
        Args:
            collected_info: Pre-collected diagnostic information
            
        Returns:
            str: Formatted context summary
        """
        return self.legacy_prompt_manager.get_context_summary(collected_info)
