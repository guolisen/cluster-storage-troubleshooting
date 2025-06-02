#!/usr/bin/env python3
"""
Chat Mode for Kubernetes Volume Troubleshooting

This module implements the chat mode functionality that allows users to interact
with the troubleshooting system at specific points during execution.
"""

import logging
import signal
import sys
from typing import Dict, List, Any, Optional, Tuple, Callable
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

logger = logging.getLogger(__name__)

class ChatMode:
    """
    Chat Mode for Kubernetes Volume Troubleshooting
    
    Implements interactive chat mode that allows users to approve plans,
    provide instructions to refine plans or guide workflows, or exit the program.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the Chat Mode
        
        Args:
            config_data: Configuration data for the system
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.console = Console()
        self.original_sigint_handler = None
        self.shortcut_key = self.config_data.get('shortcut_key', 'Ctrl+C')
        
    def setup_shortcut_handler(self, callback: Callable):
        """
        Setup handler for shortcut key (e.g., Ctrl+C)
        
        Args:
            callback: Function to call when shortcut key is pressed
        """
        try:
            # Store the original SIGINT handler
            self.original_sigint_handler = signal.getsignal(signal.SIGINT)
            
            # Define a new handler that calls our callback
            def sigint_handler(sig, frame):
                callback()
            
            # Register the new handler
            signal.signal(signal.SIGINT, sigint_handler)
            self.logger.info(f"Registered shortcut key handler for {self.shortcut_key}")
            
        except Exception as e:
            self.logger.error(f"Failed to setup shortcut key handler: {str(e)}")
    
    def restore_shortcut_handler(self):
        """
        Restore the original shortcut key handler
        """
        if self.original_sigint_handler:
            try:
                signal.signal(signal.SIGINT, self.original_sigint_handler)
                self.logger.info("Restored original shortcut key handler")
            except Exception as e:
                self.logger.error(f"Failed to restore shortcut key handler: {str(e)}")
    
    def enter_chat_mode(self, prompt_message: str) -> Tuple[str, str]:
        """
        Enter chat mode with a specified prompt message
        
        Args:
            prompt_message: Rich-formatted prompt message to display
            
        Returns:
            Tuple[str, str]: (action, instructions)
                action: 'approve', 'refine', 'exit', 'continue', or 'instruct'
                instructions: User instructions if action is 'refine' or 'instruct', empty string otherwise
        """
        try:
            # Display the prompt
            self.console.print(prompt_message)
            
            # Get user input
            user_input = input("Your input: ").strip()
            
            # Process user input
            if user_input.lower() == 'approve':
                self.logger.info("User approved the plan")
                return 'approve', ''
            elif user_input.lower() == 'exit':
                self.logger.info("User requested to exit")
                return 'exit', ''
            elif not user_input and prompt_message.startswith("[bold yellow]"):  # Shortcut mode with empty input
                self.logger.info("User provided no instructions, continuing workflow")
                return 'continue', ''
            else:
                self.logger.info(f"User provided instructions: {user_input}")
                return 'refine', user_input
                
        except Exception as e:
            self.logger.error(f"Error in chat mode: {str(e)}")
            return 'error', str(e)
    
    def handle_chat_mode_result(self, result: Tuple[str, str]) -> Dict[str, Any]:
        """
        Handle the result of a chat mode interaction
        
        Args:
            result: Tuple containing (action, instructions)
            
        Returns:
            Dict[str, Any]: Result dictionary with action, instructions, and status
        """
        action, instructions = result
        
        if action == 'error':
            return {
                'status': 'error',
                'error_message': instructions,
                'action': 'exit'
            }
        
        return {
            'status': 'success',
            'action': action,
            'instructions': instructions
        }
    
    def format_user_instructions(self, instructions: str) -> str:
        """
        Format user instructions for inclusion in LLM context
        
        Args:
            instructions: Raw user instructions
            
        Returns:
            str: Formatted user instructions
        """
        return f"User Instruction: {instructions}"
    
    def exit_program(self, exit_code: int = 0):
        """
        Exit the program gracefully
        
        Args:
            exit_code: Exit code to use
        """
        self.logger.info(f"Exiting program with code {exit_code}")
        self.console.print("[bold red]Exiting program as requested.[/bold red]")
        sys.exit(exit_code)


# Singleton instance for global access
_chat_mode_instance = None

def get_chat_mode(config_data: Dict[str, Any] = None) -> ChatMode:
    """
    Get the singleton ChatMode instance
    
    Args:
        config_data: Configuration data for the system
        
    Returns:
        ChatMode: Singleton instance
    """
    global _chat_mode_instance
    
    if _chat_mode_instance is None:
        _chat_mode_instance = ChatMode(config_data)
    
    return _chat_mode_instance


def handle_plan_phase_chat(llm_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Handle chat mode after Plan Phase (Entry Point 1)
    
    Args:
        llm_context: Current LLM context for plan generation
        
    Returns:
        Dict[str, Any]: Result with action, instructions, and updated context
    """
    chat_mode = get_chat_mode()
    prompt = "[bold cyan]Please review the Investigation Plan. Enter '[green]approve[/green]' to proceed to Phase1, provide new instructions to refine the plan, or enter '[red]exit[/red]' to terminate the program.[/bold cyan]"
    
    # Enter chat mode loop until approve or exit
    while True:
        result = chat_mode.enter_chat_mode(prompt)
        processed_result = chat_mode.handle_chat_mode_result(result)
        
        if processed_result['action'] == 'exit':
            chat_mode.exit_program()
            
        if processed_result['action'] == 'approve':
            return processed_result
            
        # If we get here, user provided instructions to refine the plan
        if llm_context is None:
            llm_context = {}
            
        # Append user instructions to LLM context
        formatted_instructions = chat_mode.format_user_instructions(processed_result['instructions'])
        if 'user_instructions' not in llm_context:
            llm_context['user_instructions'] = [formatted_instructions]
        else:
            if isinstance(llm_context['user_instructions'], list):
                llm_context['user_instructions'].append(formatted_instructions)
            else:
                llm_context['user_instructions'] = [llm_context['user_instructions'], formatted_instructions]
        
        # Return with 'regenerate' action to signal that the plan should be regenerated
        processed_result['action'] = 'regenerate'
        processed_result['updated_context'] = llm_context
        return processed_result


def handle_phase1_chat(langgraph_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Handle chat mode after Phase1 or after LLM response in Phase1 (Entry Points 2 and 3)
    
    Args:
        langgraph_context: Current LangGraph context
        
    Returns:
        Dict[str, Any]: Result with action, instructions, and updated context
    """
    chat_mode = get_chat_mode()
    prompt = "[bold cyan]Need user approval for the Fix Plan. Enter '[green]approve[/green]' to proceed to Phase2, provide new instructions to guide the workflow, or enter '[red]exit[/red]' to terminate the program.[/bold cyan]"
    
    # Enter chat mode loop until approve or exit
    while True:
        result = chat_mode.enter_chat_mode(prompt)
        processed_result = chat_mode.handle_chat_mode_result(result)
        
        if processed_result['action'] == 'exit':
            chat_mode.exit_program()
            
        if processed_result['action'] == 'approve':
            return processed_result
            
        # If we get here, user provided instructions to guide the workflow
        if langgraph_context is None:
            langgraph_context = {}
            
        # Append user instructions to LangGraph context
        updated_context = append_user_instructions_to_context(
            langgraph_context, 
            processed_result['instructions']
        )
        
        # Return with 'continue' action to signal that the workflow should continue
        processed_result['action'] = 'continue'
        processed_result['updated_context'] = updated_context
        return processed_result


def handle_shortcut_key(langgraph_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Handle shortcut key press during Phase1 or Phase2 (Entry Point 4)
    
    Args:
        langgraph_context: Current LangGraph context
        
    Returns:
        Dict[str, Any]: Result with action, instructions, and updated context
    """
    chat_mode = get_chat_mode()
    prompt = "[bold yellow]Chat mode activated. Provide instructions to guide the workflow, or enter '[red]exit[/red]' to terminate the program.[/bold yellow]"
    
    result = chat_mode.enter_chat_mode(prompt)
    processed_result = chat_mode.handle_chat_mode_result(result)
    
    if processed_result['action'] == 'exit':
        chat_mode.exit_program()
        
    if processed_result['action'] == 'continue':
        return processed_result
        
    # If we get here, user provided instructions to guide the workflow
    if langgraph_context is None:
        langgraph_context = {}
        
    # Append user instructions to LangGraph context
    if processed_result['action'] == 'refine' and processed_result['instructions']:
        updated_context = append_user_instructions_to_context(
            langgraph_context, 
            processed_result['instructions']
        )
        
        # Return with 'continue' action to signal that the workflow should continue
        processed_result['action'] = 'continue'
        processed_result['updated_context'] = updated_context
    
    return processed_result


def append_user_instructions_to_context(context: Dict[str, Any], instructions: str) -> Dict[str, Any]:
    """
    Append user instructions to LangGraph context
    
    Args:
        context: LangGraph context
        instructions: User instructions
        
    Returns:
        Dict[str, Any]: Updated context
    """
    chat_mode = get_chat_mode()
    formatted_instructions = chat_mode.format_user_instructions(instructions)
    
    # Create a copy of the context to avoid modifying the original
    updated_context = context.copy()
    
    # Append instructions to user_instructions field
    if 'user_instructions' not in updated_context:
        updated_context['user_instructions'] = [formatted_instructions]
    else:
        if isinstance(updated_context['user_instructions'], list):
            updated_context['user_instructions'].append(formatted_instructions)
        else:
            updated_context['user_instructions'] = [updated_context['user_instructions'], formatted_instructions]
    
    return updated_context


def update_llm_plan_generator_context(llm_generator, user_instructions: List[str]) -> None:
    """
    Update the LLM Plan Generator context with user instructions
    
    Args:
        llm_generator: LLMPlanGenerator instance
        user_instructions: List of user instructions
    """
    if not hasattr(llm_generator, 'user_instructions'):
        llm_generator.user_instructions = user_instructions
    else:
        if isinstance(llm_generator.user_instructions, list):
            llm_generator.user_instructions.extend(user_instructions)
        else:
            llm_generator.user_instructions = [llm_generator.user_instructions] + user_instructions


def update_langgraph_context(state: Dict[str, Any], user_instructions: List[str]) -> Dict[str, Any]:
    """
    Update LangGraph state with user instructions
    
    Args:
        state: Current LangGraph state
        user_instructions: List of user instructions
        
    Returns:
        Dict[str, Any]: Updated state
    """
    # Create a copy of the state to avoid modifying the original
    updated_state = state.copy()
    
    # Add user instructions to the messages
    if 'messages' in updated_state:
        # Format user instructions as a single string
        instructions_text = "\n".join([f"- {instr}" for instr in user_instructions])
        user_message = {
            "role": "user", 
            "content": f"User Instructions:\n{instructions_text}\n\nPlease incorporate these instructions into your workflow."
        }
        
        if isinstance(updated_state['messages'], list):
            updated_state['messages'].append(user_message)
        else:
            updated_state['messages'] = [updated_state['messages'], user_message]
    
    # Also add to user_instructions field for direct access
    if 'user_instructions' not in updated_state:
        updated_state['user_instructions'] = user_instructions
    else:
        if isinstance(updated_state['user_instructions'], list):
            updated_state['user_instructions'].extend(user_instructions)
        else:
            updated_state['user_instructions'] = [updated_state['user_instructions']] + user_instructions
    
    return updated_state
