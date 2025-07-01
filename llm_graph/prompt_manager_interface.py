#!/usr/bin/env python3
"""
Abstract Interface for Prompt Management

This module defines the abstract base class for prompt management
used in the Kubernetes volume troubleshooting system.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class PromptManagerInterface(ABC):
    """
    Abstract base class for prompt management
    
    Defines the interface that all PromptManager implementations must follow,
    ensuring consistency across different phases of the troubleshooting system.
    """
    
    @abstractmethod
    def get_system_prompt(self, **kwargs) -> str:
        """
        Return the phase-specific system prompt
        
        This method should return the appropriate system prompt for the current phase,
        optionally customized based on the provided kwargs.
        
        Args:
            **kwargs: Optional arguments for customizing the prompt
            
        Returns:
            str: System prompt for the current phase
        """
        pass
        
    @abstractmethod
    def format_user_query(self, query: str, **kwargs) -> str:
        """
        Format user query messages for the phase
        
        This method should format the user query according to the requirements
        of the current phase, optionally customized based on the provided kwargs.
        
        Args:
            query: User query to format
            **kwargs: Optional arguments for customizing the formatting
            
        Returns:
            str: Formatted user query
        """
        pass
        
    @abstractmethod
    def get_tool_prompt(self, **kwargs) -> str:
        """
        Return prompts for tool invocation
        
        This method should return the appropriate prompts for tool invocation
        in the current phase, optionally customized based on the provided kwargs.
        
        Args:
            **kwargs: Optional arguments for customizing the prompt
            
        Returns:
            str: Tool invocation prompt for the current phase
        """
        pass
        
    @abstractmethod
    def prepare_messages(self, system_prompt: str, user_message: str, 
                       message_list: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        """
        Prepare message list for LLM
        
        This method should prepare the message list for the LLM based on the
        provided system prompt, user message, and optional existing message list.
        
        Args:
            system_prompt: System prompt for LLM
            user_message: User message for LLM
            message_list: Optional existing message list
            
        Returns:
            List[Dict[str, str]]: Prepared message list
        """
        pass
