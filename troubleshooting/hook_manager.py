"""
Hook Manager for Tool Execution in Kubernetes Volume I/O Error Troubleshooting

This module defines classes for managing hooks that run before and after tool execution.
It separates hook management from the main execution logic for better modularity.
"""

import logging
import json
from typing import Any, Callable, Dict, Optional
from rich.console import Console
from rich.panel import Panel

# Configure logging
logger = logging.getLogger('hook_manager')
logger.setLevel(logging.INFO)

# Hook type definitions
BeforeCallToolsHook = Callable[[str, Dict[str, Any], str], None]
AfterCallToolsHook = Callable[[str, Dict[str, Any], Any, str], None]

class HookManager:
    """Manager for before and after tool execution hooks."""
    
    def __init__(self, console: Optional[Console] = None, file_console: Optional[Console] = None):
        """Initialize the hook manager.
        
        Args:
            console: Rich console for output. If None, a new console will be created.
            file_console: Rich console for file output. If None, no file output will be generated.
        """
        self.before_call_hook: Optional[BeforeCallToolsHook] = None
        self.after_call_hook: Optional[AfterCallToolsHook] = None
        self.console = console or Console()
        self.file_console = file_console
    
    def register_before_call_hook(self, hook: BeforeCallToolsHook) -> None:
        """Register a hook function to be called before tool execution.
        
        Args:
            hook: A callable that takes tool name and arguments as parameters
        """
        self.before_call_hook = hook
    
    def register_after_call_hook(self, hook: AfterCallToolsHook) -> None:
        """Register a hook function to be called after tool execution.
        
        Args:
            hook: A callable that takes tool name, arguments, and result as parameters
        """
        self.after_call_hook = hook
    
    def run_before_hook(self, tool_name: str, args: Dict[str, Any], call_type: str) -> None:
        """Run the before call hook if registered.
        
        Args:
            tool_name: Name of the tool being called
            args: Arguments passed to the tool
            call_type: Type of call execution ("Parallel" or "Serial")
        """
        if self.before_call_hook:
            try:
                self.before_call_hook(tool_name, args, call_type)
            except Exception as e:
                logger.error(f"Error in before_call_hook: {e}")
        else:
            # Default implementation if no hook is registered
            self._default_before_hook(tool_name, args, call_type)
    
    def run_after_hook(self, tool_name: str, args: Dict[str, Any], result: Any, call_type: str) -> None:
        """Run the after call hook if registered.
        
        Args:
            tool_name: Name of the tool that was called
            args: Arguments that were passed to the tool
            result: Result returned by the tool
            call_type: Type of call execution ("Parallel" or "Serial")
        """
        if self.after_call_hook:
            try:
                self.after_call_hook(tool_name, args, result, call_type)
            except Exception as e:
                logger.error(f"Error in after_call_hook: {e}")
        else:
            # Default implementation if no hook is registered
            self._default_after_hook(tool_name, args, result, call_type)
    
    def _default_before_hook(self, tool_name: str, args: Dict[str, Any], call_type: str) -> None:
        """Default implementation for the before call hook.
        
        Args:
            tool_name: Name of the tool being called
            args: Arguments passed to the tool
            call_type: Type of call execution ("Parallel" or "Serial")
        """
        try:
            # Format arguments for better readability
            formatted_args = json.dumps(args, indent=2) if args else "None"
            
            # Format the tool usage in a nice way
            if formatted_args != "None":
                # Print to console and log file
                tool_panel = Panel(
                    f"[bold yellow]Tool:[/bold yellow] [green]{tool_name}[/green] [bold cyan]({call_type})[/bold cyan]\n\n"
                    f"[bold yellow]Arguments:[/bold yellow]\n[blue]{formatted_args}[/blue]",
                    title="[bold magenta]Thinking Step",
                    border_style="magenta",
                    safe_box=True
                )
                self.console.print(tool_panel)
            else:
                # Simple version for tools without arguments
                tool_panel = Panel(
                    f"[bold yellow]Tool:[/bold yellow] [green]{tool_name}[/green] [bold cyan]({call_type})[/bold cyan]\n\n"
                    f"[bold yellow]Arguments:[/bold yellow] None",
                    title="[bold magenta]Thinking Step",
                    border_style="magenta",
                    safe_box=True
                )
                self.console.print(tool_panel)

            # Also log to file console if available
            if self.file_console:
                self.file_console.print(f"Executing tool: {tool_name} ({call_type})")
                self.file_console.print(f"Parameters: {formatted_args}")
            
            # Log to standard logger
            logger.info(f"Executing tool: {tool_name} ({call_type})")
            logger.info(f"Parameters: {formatted_args}")
        except Exception as e:
            logger.error(f"Error in default_before_hook: {e}")
    
    def _default_after_hook(self, tool_name: str, args: Dict[str, Any], result: Any, call_type: str) -> None:
        """Default implementation for the after call hook.
        
        Args:
            tool_name: Name of the tool that was called
            args: Arguments that were passed to the tool
            result: Result returned by the tool
            call_type: Type of call execution ("Parallel" or "Serial")
        """
        try:
            try:
                # Format result for better readability
                if hasattr(result, 'content'):
                    result_content = result.content
                    result_status = result.status if hasattr(result, 'status') else 'success'
                    formatted_result = f"Status: {result_status}\nContent: {result_content[:1000]}"
                else:
                    formatted_result = str(result)[:1000]
                
                # Print tool result to console
                tool_panel = Panel(
                    f"[bold cyan]Tool completed:[/bold cyan] [green]{tool_name}[/green] [bold cyan]({call_type})[/bold cyan]\n"
                    f"[bold cyan]Result:[/bold cyan]\n[yellow]{formatted_result}[/yellow]",
                    title="[bold magenta]Call tools",
                    border_style="magenta",
                    safe_box=True
                )
                self.console.print(tool_panel)
            except Exception as e:
                logger.error(f"Error formatting result: {e}")
                formatted_result = "Error formatting result"

            # Also log to file console if available
            if self.file_console:
                self.file_console.print(f"Tool completed: {tool_name} ({call_type})")
                self.file_console.print(f"Result: {formatted_result}")
            
            # Log to standard logger
            logger.info(f"Tool completed: {tool_name} ({call_type})")
            logger.info(f"Result: {formatted_result}")
        except Exception as e:
            logger.error(f"Error in default_after_hook: {e}")
