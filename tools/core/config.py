#!/usr/bin/env python3
"""
Core configuration and utility functions for the troubleshooting tools.

This module contains global configuration management, command validation,
and execution utilities used across all tool categories.
"""

import logging
import subprocess
from typing import Dict, List, Any, Optional, Tuple

# Global variables
INTERACTIVE_MODE = False  # To be set by the caller
CONFIG_DATA = None  # To be set by the caller with configuration

def validate_command(command_list: List[str], config_data: Dict[str, Any], interactive_mode: bool) -> Tuple[bool, str]:
    """
    Validate command against allowed/disallowed patterns in configuration
    
    Args:
        command_list: Command to validate as list of strings
        config_data: Configuration data containing command restrictions
        interactive_mode: Whether the system is in interactive mode
        
    Returns:
        Tuple[bool, str]: (is_allowed, reason)
    """
    if not command_list:
        return False, "Empty command list"
    
    # config_data is now mandatory
    if config_data is None: # This check might be redundant if type hinting is enforced, but good for safety
        return False, "Configuration data not provided"
    
    command_str = ' '.join(command_list)
    commands_config = config_data.get('commands', {})
    
    # Check disallowed commands first (higher priority)
    disallowed = commands_config.get('disallowed', [])
    for pattern in disallowed:
        if _matches_pattern(command_str, pattern):
            return False, f"Command matches disallowed pattern: {pattern}"
    
    # Check allowed commands
    allowed = commands_config.get('allowed', [])
    if allowed:  # If allowed list exists, command must match one of them
        for pattern in allowed:
            if _matches_pattern(command_str, pattern):
                return True, f"Command matches allowed pattern: {pattern}"
        return False, "Command does not match any allowed pattern"
    
    # If no allowed list, allow by default (only disallowed list matters)
    return True, "No allowed list specified - command permitted"

# Note: interactive_mode parameter is added to validate_command as requested,
# but not currently used in its internal logic. It's available for future use.

def _matches_pattern(command: str, pattern: str) -> bool:
    """
    Check if command matches a pattern (supports wildcards)
    
    Args:
        command: Full command string
        pattern: Pattern to match against (supports * wildcard)
        
    Returns:
        bool: True if command matches pattern
    """
    import fnmatch
    return fnmatch.fnmatch(command, pattern)

def execute_command(command_list: List[str], config_data: Dict[str, Any], interactive_mode: bool, purpose: str, requires_approval: bool = True) -> str:
    """
    Execute a command and return its output
    
    Args:
        command_list: Command to execute as a list of strings
        config_data: Configuration data (currently unused but added for future consistency)
        interactive_mode: Whether the system is in interactive mode
        purpose: Purpose of the command
        requires_approval: Whether this command requires user approval in interactive mode
        
    Returns:
        str: Command output
    """
    # global INTERACTIVE_MODE # Removed
    
    if not command_list:
        logging.error("execute_command received an empty command_list")
        return "Error: Empty command list provided"

    executable = command_list[0]
    command_display_str = ' '.join(command_list)

    # Approval logic
    if interactive_mode and requires_approval:
        # Ensure prompt goes to stderr if stdout is being captured by a parent process or for other reasons.
        # Or use a dedicated prompting mechanism if available. For now, print to console.
        print(f"\nCommand requires approval: {command_display_str}")
        print(f"Purpose: {purpose}")
        try:
            user_input = input("Proceed? (yes/no): ").strip().lower()
            if user_input != 'yes':
                logging.warning(f"Command execution cancelled by user for: {command_display_str}")
                return "Error: Command execution cancelled by user."
        except EOFError: # Handling cases where input stream is not available (e.g. non-interactive script)
            logging.error("Attempted to request approval in a non-interactive environment (EOFError). Denying execution.")
            return "Error: Command approval required but could not obtain user input (EOFError)."

    # Execute command
    try:
        logging.info(f"Executing command for purpose '{purpose}': {command_display_str}")
        result = subprocess.run(command_list, shell=False, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True)
        output = result.stdout
        logging.debug(f"Command output: {output}")
        return output
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed with exit code {e.returncode}: {e.stderr}"
        logging.error(error_msg)
        return f"Error: {error_msg}"
    except FileNotFoundError:
        error_msg = f"Command not found: {executable}"
        logging.error(error_msg)
        return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Failed to execute command {command_display_str}: {str(e)}"
        logging.error(error_msg)
        return f"Error: {error_msg}"
