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

def validate_command(command_list: List[str], config_data: Dict[str, Any] = None) -> Tuple[bool, str]:
    """
    Validate command against allowed/disallowed patterns in configuration
    
    Args:
        command_list: Command to validate as list of strings
        config_data: Configuration data containing command restrictions
        
    Returns:
        Tuple[bool, str]: (is_allowed, reason)
    """
    if not command_list:
        return False, "Empty command list"
    
    if config_data is None:
        config_data = CONFIG_DATA
    
    if config_data is None:
        return True, "No configuration available - allowing command"
    
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

def execute_command(command_list: List[str], purpose: str = "none", requires_approval: bool = True) -> str:
    """
    Execute a command and return its output
    
    Args:
        command_list: Command to execute as a list of strings
        purpose: Purpose of the command
        requires_approval: Whether this command requires user approval in interactive mode
        
    Returns:
        str: Command output
    """
    global INTERACTIVE_MODE
    
    if not command_list:
        logging.error("execute_command received an empty command_list")
        return "Error: Empty command list provided"

    executable = command_list[0]
    command_display_str = ' '.join(command_list)
    
    # Execute command
    try:
        logging.info(f"Executing command: {command_display_str}")
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
