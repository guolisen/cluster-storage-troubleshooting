#!/usr/bin/env python3
"""
Chat Mode for Kubernetes Volume Troubleshooting

This module implements the chat mode functionality for the troubleshooting system,
allowing users to approve plans, provide instructions, or exit at two entry points:
1. After Plan Phase: Review and refine the Investigation Plan
2. After Phase1: Review and refine the Fix Plan
"""

import sys
import logging
from typing import Dict, List, Any, Tuple
from rich.console import Console

logger = logging.getLogger(__name__)

class ChatMode:
    """
    Implements chat mode functionality for the troubleshooting system
    
    This class provides methods for entering chat mode at two entry points:
    1. After Plan Phase: Review and refine the Investigation Plan
    2. After Phase1: Review and refine the Fix Plan
    
    The chat mode allows users to:
    - Approve plans to proceed to the next phase
    - Provide instructions to refine the plans
    - Exit the program
    """
    
    def __init__(self):
        """Initialize the Chat Mode"""
        self.console = Console()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def chat_after_plan_phase(self, message_list: List[Dict[str, str]], investigation_plan: str) -> Tuple[List[Dict[str, str]], bool]:
        """
        Enter chat mode after Plan Phase to review and refine the Investigation Plan
        
        Args:
            message_list: Message list for the Plan Phase
            investigation_plan: Generated Investigation Plan
            
        Returns:
            Tuple[List[Dict[str, str]], bool]: (Updated message list, Exit flag)
        """
        self.logger.info("Entering chat mode after Plan Phase")
        
        # Display prompt
        self.console.print("[bold cyan]Please review the Investigation Plan. Enter '[green]approve[/green]' to proceed to Phase1, provide new instructions to refine the plan, or enter '[red]exit[/red]' to terminate the program.[/bold cyan]")
        
        # Get user input
        user_input = input("User Input: ").strip()
        
        # Process user input
        if user_input.lower() == "approve":
            self.logger.info("User approved the Investigation Plan")
            return message_list, False
        elif user_input.lower() == "exit":
            self.logger.info("User requested to exit the program")
            return message_list, True
        else:
            self.logger.info(f"User provided instructions: {user_input}")
            
            # Add user input to message list
            if message_list is None:
                # Initialize message list with system prompt and user input
                system_prompt = """You are an expert Kubernetes storage troubleshooter. Your task is to refine a draft Investigation Plan for troubleshooting volume read/write errors in Kubernetes.

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
                message_list = [
                    {"role": "system", "content": system_prompt},
                    {"role": "assistant", "content": investigation_plan},
                    {"role": "user", "content": f"User Input: {user_input}"}
                ]
            else:
                # Add user input to existing message list
                message_list.append({"role": "user", "content": f"User Input: {user_input}"})
            
            return message_list, False
    
    def chat_after_phase1(self, message_list: List[Dict[str, str]], fix_plan: str) -> Tuple[List[Dict[str, str]], bool]:
        """
        Enter chat mode after Phase1 to review and refine the Fix Plan
        
        Args:
            message_list: Message list for Phase1
            fix_plan: Generated Fix Plan
            
        Returns:
            Tuple[List[Dict[str, str]], bool]: (Updated message list, Exit flag)
        """
        self.logger.info("Entering chat mode after Phase1")
        
        # Display prompt
        self.console.print("[bold cyan]Need user approval for the Fix Plan. Enter '[green]approve[/green]' to proceed to Phase2, provide new instructions to refine the plan, or enter '[red]exit[/red]' to terminate the program.[/bold cyan]")
        
        # Get user input
        user_input = input("User Input: ").strip()
        
        # Process user input
        if user_input.lower() == "approve":
            self.logger.info("User approved the Fix Plan")
            return message_list, False
        elif user_input.lower() == "exit":
            self.logger.info("User requested to exit the program")
            return message_list, True
        else:
            self.logger.info(f"User provided instructions: {user_input}")
            
            # Add user input to message list
            if message_list is None:
                # Initialize message list with system prompt and user input
                system_prompt = """You are an expert Kubernetes storage troubleshooter. Your task is to execute the Investigation Plan to actively investigate volume I/O errors in Kubernetes pods and generate a comprehensive Fix Plan.

TASK:
1. Execute the Investigation Plan to identify the root cause of volume I/O errors
2. Analyze the results of the investigation
3. Generate a comprehensive Fix Plan to resolve the identified issues

CONSTRAINTS:
- Follow the Investigation Plan step by step
- Use only the tools available in the Phase1 tool registry
- Provide a detailed root cause analysis
- Generate a clear, actionable Fix Plan

OUTPUT FORMAT:
Your response must include:
1. Summary of Findings
2. Detailed Analysis
3. Root Cause
4. Fix Plan
"""
                message_list = [
                    {"role": "system", "content": system_prompt},
                    {"role": "assistant", "content": fix_plan},
                    {"role": "user", "content": f"User Input: {user_input}"}
                ]
            else:
                # Add user input to existing message list
                message_list.append({"role": "user", "content": f"User Input: {user_input}"})
            
            return message_list, False
