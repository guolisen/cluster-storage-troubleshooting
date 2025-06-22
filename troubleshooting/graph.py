#!/usr/bin/env python3
"""
LangGraph Graph Building Components for Kubernetes Volume I/O Error Troubleshooting

This module contains functions for creating and configuring LangGraph state graphs
used in the analysis and remediation phases of Kubernetes volume troubleshooting.
Enhanced with specific end conditions for better control over graph termination.
Refactored to support parallel and serial tool execution for improved performance.
"""

import json
import logging
import os
import yaml
from typing import Dict, Any, List, TypedDict, Optional, Union, Set, Tuple
from tools.core.mcp_adapter import get_mcp_adapter

# Configure logging (file only, no console output)
logger = logging.getLogger('langgraph')
logger.setLevel(logging.INFO)
# Don't propagate to root logger to avoid console output
logger.propagate = False

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import tools_condition
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, SystemMessage
from phases.llm_factory import LLMFactory
from troubleshooting.execute_tool_node import ExecuteToolNode
from troubleshooting.hook_manager import HookManager
from troubleshooting.end_conditions import EndConditionFactory
from rich.console import Console
from rich.panel import Panel

# Enhanced state class to track additional information
class EnhancedMessagesState(TypedDict):
    """Enhanced state class that extends MessagesState with additional tracking"""
    messages: List[BaseMessage]
    iteration_count: int
    tool_call_count: int
    goals_achieved: List[str]
    root_cause_identified: bool
    fix_plan_provided: bool


# Create console for rich output
console = Console()
file_console = Console(file=open('troubleshoot.log', 'a'))

def load_tool_config() -> Tuple[Set[str], Set[str]]:
    """
    Load tool configuration from config.yaml to determine which tools
    should be executed in parallel and which should be executed serially.
    
    Returns:
        Tuple[Set[str], Set[str]]: Sets of parallel and serial tool names
    """
    try:
        with open('config.yaml', 'r') as f:
            config_data = yaml.safe_load(f)
            
        tool_config = config_data.get("tools", {})
        parallel_tools = set(tool_config.get("parallel", []))
        serial_tools = set(tool_config.get("serial", []))
        
        # Log the configuration
        logger.info(f"Loaded tool configuration: {len(parallel_tools)} parallel tools, {len(serial_tools)} serial tools")
        
        return parallel_tools, serial_tools
    except Exception as e:
        logger.error(f"Error loading tool configuration: {e}")
        # Return empty sets as fallback (all tools will be treated as serial)
        return set(), set()

# Define hook functions for SerialToolNode
def before_call_tools_hook(tool_name: str, args: Dict[str, Any], call_type: str = "Serial") -> None:
    """Hook function called before a tool is executed.
    
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
                title="[bold magenta]Start to Call Tools",
                border_style="magenta",
                safe_box=True
            )
            console.print(tool_panel)
        else:
            # Simple version for tools without arguments
            tool_panel = Panel(
                f"[bold yellow]Tool:[/bold yellow] [green]{tool_name}[/green] [bold cyan]({call_type})[/bold cyan]\n\n"
                f"[bold yellow]Arguments:[/bold yellow] None",
                title="[bold magenta]Start to Call Tools",
                border_style="magenta",
                safe_box=True
            )
            console.print(tool_panel)

        # Also log to file console
        file_console.print(f"Executing tool: {tool_name} ({call_type})")
        file_console.print(f"Parameters: {formatted_args}")
        
        # Log to standard logger
        logger.info(f"Executing tool: {tool_name} ({call_type})")
        logger.info(f"Parameters: {formatted_args}")
    except Exception as e:
        logger.error(f"Error in before_call_tools_hook: {e}")

def after_call_tools_hook(tool_name: str, args: Dict[str, Any], result: Any, call_type: str = "Serial") -> None:
    """Hook function called after a tool is executed.
    
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
        console.print(tool_panel)

        # Also log to file console
        file_console.print(f"Tool completed: {tool_name} ({call_type})")
        file_console.print(f"Result: {formatted_result}")
        
        # Log to standard logger
        logger.info(f"Tool completed: {tool_name} ({call_type})")
        logger.info(f"Result: {formatted_result}")
    except Exception as e:
        logger.error(f"Error in after_call_tools_hook: {e}")

def create_troubleshooting_graph_with_context(collected_info: Dict[str, Any], phase: str = "phase1", 
                                            config_data: Dict[str, Any] = None, streaming: bool = False):
    """
    Create a LangGraph ReAct graph for troubleshooting with pre-collected context
    and enhanced end conditions
    
    Args:
        collected_info: Pre-collected diagnostic information from Phase 0
        phase: Current troubleshooting phase ("phase1" for investigation, "phase2" for action)
        config_data: Configuration data
        streaming: Whether to enable streaming for the LLM
        
    Returns:
        StateGraph: LangGraph StateGraph
    """
    if config_data is None:
        raise ValueError("Configuration data is required")
    
    # Initialize components
    model = _initialize_llm(config_data, streaming, phase)
    
    # Define function to call the model with pre-collected context
    def call_model(state: MessagesState):
        logging.info(f"Processing state with {len(state['messages'])} messages")
        
        # Prepare messages for the model
        state = _prepare_messages(state, collected_info, phase, model)
        
        # Get tools for the current phase
        tools = _get_tools_for_phase(phase)
        
        # Call the model with tools
        response = model.bind_tools(tools).invoke(state["messages"])
        
        logging.info(f"Model response: {response.content}...")
        
        # Create console for rich output
        console = Console()
        console.print(f"[bold cyan]LangGraph thinking process:[/bold cyan]")

        if response.content:
            console.print(Panel(
                f"[bold green]{response.content}[/bold green]",
                title="[bold magenta]Thinking step",
                border_style="magenta",
                safe_box=True
            ))

        return {"messages": state["messages"] + [response]}
    
    # Create an end condition checker using the factory
    end_condition_checker = EndConditionFactory.create_checker(
        "llm" if config_data.get("llm_end_condition_check", True) else "simple",
        model=model,
        phase=phase,
        max_iterations=config_data.get("max_iterations", 30)
    )
    
    # Define the end condition check function that delegates to the checker
    def check_end_conditions(state: MessagesState) -> Dict[str, str]:
        """
        Delegate end condition checking to the appropriate strategy
        Returns {"result": "end"} if the graph should end, {"result": "continue"} if it should continue
        """
        return end_condition_checker.check_conditions(state)

    # Load tool configuration
    parallel_tools, serial_tools = load_tool_config()
    
    # Get tools for the current phase
    tools = _get_tools_for_phase(phase)
    
    # Create ExecuteToolNode with the configured tools
    execute_tool_node = _create_execute_tool_node(tools, parallel_tools, serial_tools)
    
    # Build the graph
    graph = _build_graph(call_model, check_end_conditions, execute_tool_node)
    
    logging.info("Graph compilation complete")
    return graph

def _initialize_llm(config_data: Dict[str, Any], streaming: bool, phase: str):
    """
    Initialize the language model using LLMFactory
    
    Args:
        config_data: Configuration data
        streaming: Whether to enable streaming for the LLM
        phase: Current troubleshooting phase
        
    Returns:
        BaseChatModel: Initialized language model
    """
    # Initialize language model using LLMFactory
    llm_factory = LLMFactory(config_data)
    model = llm_factory.create_llm(streaming=streaming, phase_name=phase)
    return model

def _prepare_messages(state: MessagesState, collected_info: Dict[str, Any], phase: str, model) -> MessagesState:
    """
    Prepare messages for the model with pre-collected context
    
    Args:
        state: Current state with messages
        collected_info: Pre-collected diagnostic information
        phase: Current troubleshooting phase
        model: Language model
        
    Returns:
        MessagesState: Updated state with prepared messages
    """
    from troubleshooting.prompt_manager import PromptManager
    
    # Create prompt manager
    prompt_manager = PromptManager(config_data=None)
    
    # Get system prompt and context summary
    system_prompt = prompt_manager.get_system_prompt(phase)
    context_summary = prompt_manager.get_context_summary(collected_info)
    
    # Create system and context messages
    system_message = SystemMessage(content=system_prompt)
    context_message = SystemMessage(content=context_summary)
    
    # Extract existing user messages (skip system message if present)
    user_messages = []
    if state["messages"]:
        if isinstance(state["messages"], list):
            for msg in state["messages"]:
                if not isinstance(msg, SystemMessage):
                    user_messages.append(msg)
            
            # Create new message list with system message, context message, and existing user messages
            state["messages"] = [system_message, context_message] + user_messages
        else:
            state["messages"] = [system_message, context_message, state["messages"]]
    else:
        state["messages"] = [system_message, context_message]
    
    return state

def _get_tools_for_phase(phase: str) -> List[Any]:
    """
    Get tools for the current phase
    
    Args:
        phase: Current troubleshooting phase
        
    Returns:
        List[Any]: List of tools for the current phase
    """
    # Get MCP adapter and tools
    mcp_adapter = get_mcp_adapter()
    mcp_tools = []
    
    # Select tools based on phase
    if phase == "phase1":
        from tools import get_phase1_tools
        tools = get_phase1_tools()
        # Add MCP tools for phase1 if available
        if mcp_adapter:
            mcp_tools = mcp_adapter.get_tools_for_phase('phase1')
            if mcp_tools:
                tools.extend(mcp_tools)
                logging.info(f"Using Phase 1 tools: {len(tools)} investigation tools (including {len(mcp_tools)} MCP tools)")
            else:
                logging.info(f"Using Phase 1 tools: {len(tools)} investigation tools")
        else:
            logging.info(f"Using Phase 1 tools: {len(tools)} investigation tools")
    elif phase == "phase2":
        from tools import get_phase2_tools
        tools = get_phase2_tools()
        
        # Add MCP tools for phase2 if available
        if mcp_adapter:
            mcp_tools = mcp_adapter.get_tools_for_phase('phase2')
            if mcp_tools:
                tools.extend(mcp_tools)
                logging.info(f"Using Phase 2 tools: {len(tools)} investigation + action tools (including {len(mcp_tools)} MCP tools)")
            else:
                logging.info(f"Using Phase 2 tools: {len(tools)} investigation + action tools")
        else:
            logging.info(f"Using Phase 2 tools: {len(tools)} investigation + action tools")
    else:
        # Fallback to all tools for backward compatibility
        from tools import define_remediation_tools
        tools = define_remediation_tools()
        logging.info(f"Using all tools (fallback): {len(tools)} tools")
    
    return tools

def _create_execute_tool_node(tools: List[Any], parallel_tools: Set[str], serial_tools: Set[str]) -> ExecuteToolNode:
    """
    Create and configure the ExecuteToolNode
    
    Args:
        tools: List of tools
        parallel_tools: Set of tool names to execute in parallel
        serial_tools: Set of tool names to execute serially
        
    Returns:
        ExecuteToolNode: Configured ExecuteToolNode
    """
    # If a tool is not explicitly categorized, default to serial
    all_tool_names = {tool.name for tool in tools}
    uncategorized_tools = all_tool_names - parallel_tools - serial_tools
    if uncategorized_tools:
        logging.info(f"Found {len(uncategorized_tools)} uncategorized tools, defaulting to serial")
        serial_tools.update(uncategorized_tools)
    
    # Create a hook manager for console output
    hook_manager = HookManager(console=console, file_console=file_console)
    
    # Register hook functions with the hook manager
    hook_manager.register_before_call_hook(before_call_tools_hook)
    hook_manager.register_after_call_hook(after_call_tools_hook)
    
    # Create ExecuteToolNode with the configured tools
    logging.info(f"Creating ExecuteToolNode for execution of {len(parallel_tools)} parallel and {len(serial_tools)} serial tools")
    execute_tool_node = ExecuteToolNode(tools, parallel_tools, serial_tools, name="execute_tools")
    
    # Register hook manager with the ExecuteToolNode
    execute_tool_node.register_before_call_hook(hook_manager.run_before_hook)
    execute_tool_node.register_after_call_hook(hook_manager.run_after_hook)
    
    return execute_tool_node

def _build_graph(call_model, check_end_conditions: callable, execute_tool_node: ExecuteToolNode) -> StateGraph:
    """
    Build the LangGraph state graph
    
    Args:
        call_model: Function to call the model
        check_end_conditions: Function to check end conditions
        execute_tool_node: ExecuteToolNode for tool execution
        
    Returns:
        StateGraph: Compiled LangGraph StateGraph
    """
    # Build state graph
    logging.info("Building state graph with enhanced end conditions")
    builder = StateGraph(MessagesState)
    
    logging.info("Adding node: call_model")
    builder.add_node("call_model", call_model)
    
    logging.info("Adding node: execute_tools")
    builder.add_node("execute_tools", execute_tool_node)
    
    logging.info("Adding node: check_end")
    builder.add_node("check_end", check_end_conditions)
    
    logging.info("Adding conditional edges for tools")
    builder.add_conditional_edges(
        "call_model",
        tools_condition,
        {
            "tools": "execute_tools",   # Route to execute_tools node
            "none": "check_end",        # If no tools, go to check_end
            "end": "check_end",
            "__end__": "check_end"
        }
    )
    
    logging.info("Adding conditional edges from check_end node")
    builder.add_conditional_edges(
        "check_end",
        lambda state: check_end_conditions(state)["result"],
        {
            "end": END,
            "__end__": END,
            "continue": "call_model"  # Loop back if conditions not met
        }
    )
    
    # Add edge from execute_tools to call_model
    logging.info("Adding edge: execute_tools -> call_model")
    builder.add_edge("execute_tools", "call_model")
    
    logging.info("Adding edge: START -> call_model")
    builder.add_edge(START, "call_model")
    
    logging.info("Compiling graph")
    return builder.compile()
