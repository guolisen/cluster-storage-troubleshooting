#!/usr/bin/env python3
"""
Phase 2: Remediation for Kubernetes Volume Troubleshooting

This module contains the implementation of Phase 2 (Remediation)
which executes fix plans based on analysis from Phase 1.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from langgraph.graph import StateGraph

from troubleshooting.graph import create_troubleshooting_graph_with_context
from troubleshooting.utils import (
    HistoricalExperienceFormatter,
    GraphExecutor,
    ErrorHandler,
    MessageListManager,
    OutputFormatter
)

logger = logging.getLogger(__name__)


class RemediationPhase:
    """
    Implementation of Phase 2: Remediation
    
    This class handles the implementation of fix plans to resolve
    the identified issues with volume I/O. It creates a LangGraph ReAct
    workflow that executes the fix plan from Phase 1 and validates the
    results to ensure the issues are resolved.
    """
    
    def __init__(self, collected_info: Dict[str, Any], config_data: Dict[str, Any]):
        """
        Initialize the Remediation Phase
        
        Args:
            collected_info: Pre-collected diagnostic information from Phase 0
            config_data: Configuration data for the system
        """
        self.collected_info = collected_info
        self.config_data = config_data
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.console = Console()
        self.interactive_mode = config_data.get('troubleshoot', {}).get('interactive_mode', False)
    
    async def execute_fix_plan(self, phase1_final_response: str, message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
        """
        Execute the fix plan from Phase 1 analysis
        
        Args:
            phase1_final_response: Response from Phase 1 containing root cause and fix plan
            message_list: Optional message list for chat mode
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Remediation result, Updated message list)
        """
        try:
            # Initialize message list if not provided
            message_list = self._initialize_message_list(message_list, phase1_final_response)
            
            # Create troubleshooting graph for remediation
            graph = self._create_troubleshooting_graph()
            
            # Prepare query for the graph
            query = self._prepare_remediation_query(phase1_final_response)
            
            # Execute graph and get final response
            remediation_result, message_list = await self._execute_graph_and_get_response(
                graph, message_list
            )
            
            return remediation_result, message_list

        except Exception as exception:
            return self._handle_remediation_error(exception, message_list)
    
    def _initialize_message_list(self, message_list: Optional[List[Dict[str, str]]], 
                               phase1_final_response: str) -> List[Dict[str, str]]:
        """
        Initialize message list with system prompt if not provided
        
        Args:
            message_list: Optional existing message list
            phase1_final_response: Response from Phase 1 containing root cause and fix plan
            
        Returns:
            List[Dict[str, str]]: Initialized message list
        """
        if message_list is None:
            system_prompt = self._create_system_prompt()
            
            # Create initial message list with system prompt and fix plan
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Fix Plan:\n" + phase1_final_response}
            ]
        
        return message_list
    
    def _create_system_prompt(self) -> str:
        """
        Create the system prompt for Phase 2
        
        Returns:
            str: System prompt for Phase 2
        """
        return """You are an expert Kubernetes storage troubleshooter. Your task is to execute the Fix Plan to resolve volume I/O errors in Kubernetes pods.

TASK:
1. Execute the Fix Plan to resolve the identified issues
2. Validate the fixes to ensure they resolved the problem
3. Provide a detailed report of the remediation actions taken

CONSTRAINTS:
- Follow the Fix Plan step by step
- Use only the tools available in the Phase2 tool registry
- Validate each fix to ensure it was successful
- Provide a clear, detailed report of all actions taken

OUTPUT FORMAT:
Your response must include:
1. Actions Taken
2. Validation Results
3. Resolution Status
4. Recommendations
"""
    
    def _create_troubleshooting_graph(self) -> StateGraph:
        """
        Create the troubleshooting graph for remediation
        
        Returns:
            StateGraph: LangGraph StateGraph for remediation
        """
        return create_troubleshooting_graph_with_context(
            self.collected_info, phase="phase2", config_data=self.config_data
        )
    
    def _prepare_remediation_query(self, phase1_final_response: str) -> str:
        """
        Prepare the remediation query for the graph
        
        Args:
            phase1_final_response: Response from Phase 1 containing root cause and fix plan
            
        Returns:
            str: Formatted remediation query
        """
        # Extract and format historical experience data
        historical_experiences_formatted = self._format_historical_experiences()
        
        # Create execution guidelines
        execution_guidelines = self._create_execution_guidelines()
        
        # Create query with dynamic data for LangGraph workflow
        return f"""Phase 2 - Remediation: Execute the fix plan to resolve the identified issue.

Root Cause and Fix Plan: {phase1_final_response}

HISTORICAL EXPERIENCE:
{historical_experiences_formatted}

EXECUTION GUIDELINES:
{execution_guidelines}

<<< Note >>>: Please try to fix issue within 30 tool calls.
"""
    
    def _format_historical_experiences(self) -> str:
        """
        Format historical experience data from collected_info
        
        Returns:
            str: Formatted historical experience data
        """
        return HistoricalExperienceFormatter.format_historical_experiences(
            self.collected_info
        )
    
    def _create_execution_guidelines(self) -> str:
        """
        Create execution guidelines for remediation
        
        Returns:
            str: Execution guidelines
        """
        return """1. Follow the Fix Plan step by step
2. For each step, use the appropriate tool from the Phase 2 tool registry
3. After each action, validate that it was successful
4. If an action fails, try alternative approaches or provide detailed manual instructions
5. Clean up any test resources created during remediation
6. Provide a comprehensive report of all actions taken and their results"""
    
    async def _execute_graph_and_get_response(self, graph: StateGraph, 
                                            message_list: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
        """
        Execute the graph and get the final response
        
        Args:
            graph: LangGraph StateGraph to execute
            message_list: Message list for the graph
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Final response, Updated message list)
        """
        # Set timeout from config
        timeout_seconds = self.config_data.get('troubleshoot', {}).get('timeout_seconds', 600)
        
        # Create initial state with messages
        initial_state = {"messages": message_list}
        
        # Execute graph
        final_state = await GraphExecutor.execute_graph(
            graph, initial_state, timeout_seconds
        )
        
        # Extract final response
        remediation_result = GraphExecutor.extract_final_response(final_state)
        
        # Add remediation result to message list
        message_list = MessageListManager.add_to_message_list(message_list, remediation_result)
        
        return remediation_result, message_list
    
    def _handle_remediation_error(self, exception: Exception, 
                                message_list: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
        """
        Handle errors during remediation
        
        Args:
            exception: Exception that occurred
            message_list: Message list to update
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Error message, Updated message list)
        """
        error_msg = ErrorHandler.create_error_response(
            exception, "Error during remediation phase"
        )
        
        # Add error message to message list
        if message_list is not None:
            message_list = MessageListManager.add_to_message_list(message_list, error_msg)
        
        self.logger.error(f"Error in remediation phase: {str(exception)}")
        return error_msg, message_list


async def run_remediation_phase(phase1_final_response: str, collected_info: Dict[str, Any], 
                              config_data: Dict[str, Any], message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
    """
    Run Phase 2: Remediation based on analysis results
    
    Args:
        phase1_final_response: Response from Phase 1 containing root cause and fix plan
        collected_info: Pre-collected diagnostic information from Phase 0
        config_data: Configuration data
        message_list: Optional message list for chat mode
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: (Remediation result, Updated message list)
    """
    logging.info("Starting Phase 2: Remediation")
    
    # Display phase header
    _display_phase_header()
    
    try:
        # Initialize the remediation phase
        phase = RemediationPhase(collected_info, config_data)
        
        # Execute the fix plan
        result, message_list = await phase.execute_fix_plan(phase1_final_response, message_list)
        
        return result, message_list
        
    except Exception as exception:
        return _handle_phase_error(exception, message_list)


def _display_phase_header() -> None:
    """
    Display the phase header in the console
    """
    console = Console()
    console.print("\n")
    console.print(Panel(
        "[bold white]Executing fix plan to resolve identified issues...",
        title="[bold green]PHASE 2: REMEDIATION",
        border_style="green",
        padding=(1, 2)
    ))


def _handle_phase_error(exception: Exception, message_list: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    """
    Handle errors during the remediation phase
    
    Args:
        exception: Exception that occurred
        message_list: Message list to update
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: (Error message, Updated message list)
    """
    error_msg = ErrorHandler.create_error_response(
        exception, "Error during remediation phase"
    )
    
    # Add error message to message list
    if message_list is not None:
        message_list = MessageListManager.add_to_message_list(message_list, error_msg)
    
    logging.error(f"Error in remediation phase: {str(exception)}")
    return error_msg, message_list


def extract_fix_plan_from_analysis(analysis_result: str) -> str:
    """
    Extract the fix plan section from the analysis result
    
    Args:
        analysis_result: Analysis result from Phase 1
        
    Returns:
            str: Extracted fix plan, or the entire analysis if no fix plan section is found
    """
    # Try to extract the Fix Plan section
    fix_plan = OutputFormatter.extract_section_from_text(analysis_result, "Fix Plan")
    
    # If no Fix Plan section found, return the entire analysis
    if not fix_plan:
        return analysis_result
    
    return f"Fix Plan:\n{fix_plan}"
