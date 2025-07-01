#!/usr/bin/env python3
"""
Abstract Interface for LangGraph Workflows

This module defines the abstract base class for all LangGraph workflows
used in the Kubernetes volume troubleshooting system.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from langgraph.graph import StateGraph

logger = logging.getLogger(__name__)

class LangGraphInterface(ABC):
    """
    Abstract base class for LangGraph workflows
    
    Defines the interface that all LangGraph implementations must follow,
    ensuring consistency across different phases of the troubleshooting system.
    """
    
    @abstractmethod
    def initialize_graph(self) -> StateGraph:
        """
        Initialize and return the LangGraph StateGraph
        
        This method should set up the graph structure including nodes,
        edges, and conditional logic.
        
        Returns:
            StateGraph: Compiled LangGraph StateGraph
        """
        pass
        
    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the graph with the provided state
        
        This method should run the graph with the given initial state
        and return the final state after execution.
        
        Args:
            state: Initial state for the graph execution
            
        Returns:
            Dict[str, Any]: Final state after graph execution
        """
        pass
        
    @abstractmethod
    def get_prompt_manager(self):
        """
        Return the prompt manager for this graph
        
        This method should return the appropriate PromptManagerInterface
        implementation for the current phase.
        
        Returns:
            PromptManagerInterface: Prompt manager for this graph
        """
        pass
