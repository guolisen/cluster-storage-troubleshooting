#!/usr/bin/env python3
"""
Graph Utility for LangGraph Workflows

This module provides utility functions for LangGraph workflows
used in the Kubernetes volume troubleshooting system.
"""

import logging
import json
import yaml
import os
from typing import Dict, List, Any, Callable, Set, Tuple, Optional
from rich.console import Console
from rich.panel import Panel

from langgraph.graph import StateGraph
from langchain_core.messages import ToolMessage, BaseMessage
from troubleshooting.execute_tool_node import ExecuteToolNode
from troubleshooting.hook_manager import HookManager

logger = logging.getLogger(__name__)

class GraphUtility:
    """
    Utility class for common LangGraph operations
    
    Provides common functionality for LangGraph workflows, including
    node and edge management, tool execution, and state updates.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the GraphUtility
        
        Args:
            config_data: Configuration data for the system
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.console = Console()
        self.file_console = Console(file=open('troubleshoot.log', 'a'))
        
    def add_node_and_edge(self, graph: StateGraph, node_name: str, 
                         node_func: Callable, source_node: Optional[str] = None):
        """
        Add a node and its edge to the graph
        
        Args:
            graph: StateGraph to modify
            node_name: Name of the node to add
            node_func: Function to execute for this node
            source_node: Source node for the edge (optional)
        """
        self.logger.info(f"Adding node: {node_name}")
        graph.add_node(node_name, node_func)
        
        if source_node:
            self.logger.info(f"Adding edge: {source_node} -> {node_name}")
            graph.add_edge(source_node, node_name)
            
    def execute_tool(self, tool_call: Dict[str, Any]) -> ToolMessage:
        """
        Execute a single tool and return a ToolMessage
        
        Args:
            tool_call: Tool call information
            
        Returns:
            ToolMessage: Result of the tool execution
        """
        try:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            
            # Log the tool execution
            self.logger.info(f"Executing tool: {tool_name}")
            self.logger.info(f"Arguments: {json.dumps(tool_args, indent=2)}")
            
            # Execute the tool (placeholder - actual implementation would call the tool)
            result = f"Tool {tool_name} executed with args {tool_args}"
            
            # Return the result as a ToolMessage
            return ToolMessage(content=result, tool_call_id=tool_call.get("id", ""))
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_call.get('name', '')}: {str(e)}")
            return ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_call.get("id", ""))
            
    def update_state(self, state: Dict[str, Any], results: Any) -> Dict[str, Any]:
        """
        Update graph state with results
        
        Args:
            state: Current state
            results: Results to add to the state
            
        Returns:
            Dict[str, Any]: Updated state
        """
        # Increment iteration count if present
        if "iteration_count" in state:
            state["iteration_count"] += 1
            
        # Add results to messages if present
        if "messages" in state and hasattr(results, "content"):
            state["messages"].append(results)
            
        return state
        
    def load_tool_config(self) -> Tuple[Set[str], Set[str]]:
        """
        Load tool configuration to determine parallel and serial tools
        
        Returns:
            Tuple[Set[str], Set[str]]: Sets of parallel and serial tool names
        """
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.yaml')
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
                
            tool_config = config_data.get("tools", {})
            parallel_tools = set(tool_config.get("parallel", []))
            serial_tools = set(tool_config.get("serial", []))
            
            # Log the configuration
            self.logger.info(f"Loaded tool configuration: {len(parallel_tools)} parallel tools, {len(serial_tools)} serial tools")
            
            return parallel_tools, serial_tools
        except Exception as e:
            self.logger.error(f"Error loading tool configuration: {e}")
            # Return empty sets as fallback (all tools will be treated as serial)
            return set(), set()
        
    def create_execute_tool_node(self, tools: List[Any], parallel_tools: Optional[Set[str]] = None, 
                               serial_tools: Optional[Set[str]] = None) -> ExecuteToolNode:
        """
        Create and configure the ExecuteToolNode
        
        Args:
            tools: List of tools
            parallel_tools: Set of tool names to execute in parallel (optional)
            serial_tools: Set of tool names to execute serially (optional)
            
        Returns:
            ExecuteToolNode: Configured ExecuteToolNode
        """
        # If parallel_tools and serial_tools are not provided, load from config
        if parallel_tools is None or serial_tools is None:
            parallel_tools_config, serial_tools_config = self.load_tool_config()
            parallel_tools = parallel_tools or parallel_tools_config
            serial_tools = serial_tools or serial_tools_config
        
        # If a tool is not explicitly categorized, default to serial
        all_tool_names = {tool.name for tool in tools}
        uncategorized_tools = all_tool_names - (parallel_tools or set()) - (serial_tools or set())
        if uncategorized_tools:
            self.logger.info(f"Found {len(uncategorized_tools)} uncategorized tools, defaulting to serial")
            if serial_tools is None:
                serial_tools = set()
            serial_tools.update(uncategorized_tools)
        
        # Create a hook manager for console output
        hook_manager = HookManager(console=self.console, file_console=self.file_console)
        
        # Register hook functions with the hook manager
        hook_manager.register_before_call_hook(self._before_call_tools_hook)
        hook_manager.register_after_call_hook(self._after_call_tools_hook)
        
        # Create ExecuteToolNode with the configured tools
        self.logger.info(f"Creating ExecuteToolNode for execution of {len(parallel_tools or set())} parallel and {len(serial_tools or set())} serial tools")
        execute_tool_node = ExecuteToolNode(tools, parallel_tools or set(), serial_tools or set(), name="execute_tools")
        
        # Register hook manager with the ExecuteToolNode
        execute_tool_node.register_before_call_hook(hook_manager.run_before_hook)
        execute_tool_node.register_after_call_hook(hook_manager.run_after_hook)
        
        return execute_tool_node
    
    def extract_final_message(self, response: Dict[str, Any]) -> str:
        """
        Extract the final message from a graph response
        
        Args:
            response: Response from the graph
            
        Returns:
            str: Final message content
        """
        if not response.get("messages"):
            return "Failed to generate results"
            
        if isinstance(response["messages"], list):
            return response["messages"][-1].content
        else:
            return response["messages"].content
    
    def _before_call_tools_hook(self, tool_name: str, args: Dict[str, Any], call_type: str = "Serial") -> None:
        """
        Hook function called before a tool is executed
        
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
                # Print to console
                tool_panel = Panel(
                    f"[bold yellow]Tool:[/bold yellow] [green]{tool_name}[/green] [bold cyan]({call_type})[/bold cyan]\n\n"
                    f"[bold yellow]Arguments:[/bold yellow]\n[blue]{formatted_args}[/blue]",
                    title="[bold magenta]Start to Call Tools",
                    border_style="magenta",
                    safe_box=True
                )
                self.console.print(tool_panel)
            else:
                # Simple version for tools without arguments
                tool_panel = Panel(
                    f"[bold yellow]Tool:[/bold yellow] [green]{tool_name}[/green] [bold cyan]({call_type})[/bold cyan]\n\n"
                    f"[bold yellow]Arguments:[/bold yellow] None",
                    title="[bold magenta]Start to Call Tools",
                    border_style="magenta",
                    safe_box=True
                )
                self.console.print(tool_panel)

            # Also log to file console
            self.file_console.print(f"Executing tool: {tool_name} ({call_type})")
            self.file_console.print(f"Parameters: {formatted_args}")
            
            # Log to standard logger
            self.logger.info(f"Executing tool: {tool_name} ({call_type})")
            self.logger.info(f"Parameters: {formatted_args}")
        except Exception as e:
            self.logger.error(f"Error in before_call_tools_hook: {e}")

    def _after_call_tools_hook(self, tool_name: str, args: Dict[str, Any], result: Any, call_type: str = "Serial") -> None:
        """
        Hook function called after a tool is executed
        
        Args:
            tool_name: Name of the tool that was called
            args: Arguments that were passed to the tool
            result: Result returned by the tool
            call_type: Type of call execution ("Parallel" or "Serial")
        """
        try:
            # Format result for better readability
            if isinstance(result, ToolMessage):
                result_content = result.content
                result_status = result.status if hasattr(result, 'status') else 'success'
                formatted_result = f"Status: {result_status}\nContent: {result_content[:1000]}"
            else:
                formatted_result = str(result)[:1000]
            
            # Print tool result to console
            tool_panel = Panel(
                f"[bold cyan]Tool completed:[/bold cyan] [green]{tool_name}[/green] [bold cyan]({call_type})[/bold cyan]\n"
                f"[bold cyan]Result:[/bold cyan]\n[yellow]{formatted_result}[/yellow]",
                title="[bold magenta]Call tools Result",
                border_style="magenta",
                safe_box=True
            )
            self.console.print(tool_panel)

            # Also log to file console
            self.file_console.print(f"Tool completed: {tool_name} ({call_type})")
            self.file_console.print(f"Result: {formatted_result}")
            
            # Log to standard logger
            self.logger.info(f"Tool completed: {tool_name} ({call_type})")
            self.logger.info(f"Result: {formatted_result}")
        except Exception as e:
            self.logger.error(f"Error in after_call_tools_hook: {e}")
