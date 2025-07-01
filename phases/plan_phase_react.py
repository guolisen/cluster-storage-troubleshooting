#!/usr/bin/env python3
"""
ReAct Graph Implementation for Plan Phase in Kubernetes Volume Troubleshooting

This module implements a standalone ReAct (Reasoning and Acting) graph using LangGraph
for the plan phase of Kubernetes volume troubleshooting. The graph exclusively uses
MCP (Multi-Component Platform) tools for function calling to gather information
when the plan phase encounters knowledge gaps.
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, TypedDict, Optional, Union, Tuple, Set
from enum import Enum
from rich.console import Console
from rich.panel import Panel

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition, ToolNode
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from phases.llm_factory import LLMFactory
from phases.utils import handle_exception, format_json_safely, generate_basic_fallback_plan
from tools.core.mcp_adapter import get_mcp_adapter
from knowledge_graph import KnowledgeGraph
from troubleshooting.execute_tool_node import ExecuteToolNode
from troubleshooting.strategies import ExecutionType

# Configure logging
logger = logging.getLogger(__name__)

# Define hook functions for PlanPhaseReActGraph
def before_call_tools_hook(tool_name: str, args: Dict[str, Any], call_type: str = "Parallel") -> None:
    """Hook function called before a tool is executed in Plan Phase ReAct.
    
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
                title="[bold magenta]Plan Phase ReAct Tool",
                border_style="magenta",
                safe_box=True
            )
            console = Console()
            console.print(tool_panel)
        else:
            # Simple version for tools without arguments
            tool_panel = Panel(
                f"[bold yellow]Tool:[/bold yellow] [green]{tool_name}[/green] [bold cyan]({call_type})[/bold cyan]\n\n"
                f"[bold yellow]Arguments:[/bold yellow] None",
                title="[bold magenta]Plan Phase ReAct Tool",
                border_style="magenta",
                safe_box=True
            )
            console = Console()
            console.print(tool_panel)

        # Log to standard logger
        logger.info(f"Plan Phase ReAct executing tool: {tool_name} ({call_type})")
        logger.info(f"Parameters: {formatted_args}")
    except Exception as e:
        logger.error(f"Error in before_call_tools_hook: {e}")

def after_call_tools_hook(tool_name: str, args: Dict[str, Any], result: Any, call_type: str = "Parallel") -> None:
    """Hook function called after a tool is executed in Plan Phase ReAct.
    
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
            title="[bold magenta]Plan Phase ReAct Result",
            border_style="magenta",
            safe_box=True
        )
        console = Console()
        console.print(tool_panel)

        # Log to standard logger
        logger.info(f"Plan Phase ReAct tool completed: {tool_name} ({call_type})")
        logger.info(f"Result: {formatted_result}")
    except Exception as e:
        logger.error(f"Error in after_call_tools_hook: {e}")

class PlanPhaseState(TypedDict):
    """State for the Plan Phase ReAct graph"""
    messages: List[BaseMessage]  # Conversation history
    iteration_count: int  # Track iterations
    tool_call_count: int  # Track tool calls
    knowledge_gathered: Dict[str, Any]  # Knowledge gathered from tools
    plan_complete: bool  # Whether the plan is complete
    pod_name: str  # Pod name for context
    namespace: str  # Namespace for context
    volume_path: str  # Volume path for context
    knowledge_graph: Optional[KnowledgeGraph]  # Knowledge graph for context

class ReActStage(Enum):
    """Stages in the ReAct process"""
    REASONING = "reasoning"  # LLM analyzing and reasoning about the problem
    ACTING = "acting"  # Calling tools to gather information
    OBSERVING = "observing"  # Processing tool outputs
    PLANNING = "planning"  # Generating the final plan

class PlanPhaseReActGraph:
    """
    ReAct Graph for Plan Phase using LangGraph
    
    Implements a standalone ReAct (Reasoning and Acting) graph that exclusively
    uses MCP tools for function calling when the plan phase encounters knowledge gaps.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None, messages: List[BaseMessage] = None):
        """
        Initialize the Plan Phase ReAct Graph
        
        Args:
            config_data: Configuration data for the system
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize LLM
        self.llm = self._initialize_llm()
        
        # Get MCP tools
        self.mcp_tools = self._get_mcp_tools_for_plan_phase()
        
        # Maximum iterations to prevent infinite loops
        self.max_iterations = self.config_data.get("max_iterations", 15)

        self.init_message = messages
    
    def _initialize_llm(self):
        """
        Initialize the LLM for the ReAct graph
        
        Returns:
            BaseChatModel: Initialized LLM instance
        """
        try:
            # Create LLM using the factory
            llm_factory = LLMFactory(self.config_data)
            
            # Check if streaming is enabled in config
            streaming_enabled = self.config_data.get('llm', {}).get('streaming', False)
            
            # Create LLM with streaming if enabled
            return llm_factory.create_llm(
                streaming=streaming_enabled,
                phase_name="plan_phase"
            )
        except Exception as e:
            error_msg = handle_exception("_initialize_llm", e, self.logger)
            raise ValueError(f"Failed to initialize LLM: {error_msg}")
    
    def _get_mcp_tools_for_plan_phase(self) -> List[BaseTool]:
        """
        Get MCP tools for the plan phase
        
        Returns:
            List[BaseTool]: List of MCP tools for the plan phase
        
        Raises:
            ValueError: If MCP integration is not enabled or no tools are available
        """
        # Get MCP adapter
        mcp_adapter = get_mcp_adapter()
        
        if not mcp_adapter:
            self.logger.warning("MCP adapter not initialized, no MCP tools will be available")
            return []
        
        if not mcp_adapter.mcp_enabled:
            self.logger.warning("MCP integration is disabled, no MCP tools will be available")
            return []
        
        # Get MCP tools for plan phase
        mcp_tools = mcp_adapter.get_tools_for_phase('plan_phase')
        
        if not mcp_tools:
            self.logger.warning("No MCP tools available for plan phase")
            return []
        
        self.logger.info(f"Loaded {len(mcp_tools)} MCP tools for Plan Phase")
        return mcp_tools
    
    def build_graph(self) -> StateGraph:
        """
        Build the Plan Phase ReAct graph
        
        Returns:
            StateGraph: Compiled LangGraph StateGraph
        """
        # Build state graph
        self.logger.info("Building Plan Phase ReAct graph")
        builder = StateGraph(PlanPhaseState)
        
        # Add nodes
        self.logger.info("Adding node: call_model")
        builder.add_node("call_model", self.call_model)
        
        # Initialize ExecuteToolNode with all MCP tools set to parallel execution
        execute_tools_node = self._initialize_execute_tool_node()
        self.logger.info("Adding node: execute_tools")
        builder.add_node("execute_tools", execute_tools_node)
        
        self.logger.info("Adding node: check_end")
        builder.add_node("check_end", self.check_end_conditions)
        
        # Add edges
        self.logger.info("Adding edge: START -> call_model")
        builder.add_edge(START, "call_model")
        
        # Add conditional edges for tools
        self.logger.info("Adding conditional edges for tools")
        builder.add_conditional_edges(
            "call_model",
            tools_condition,
            {
                "tools": "execute_tools",   # Route to execute_tools node
                "none": "check_end",        # If no tools, go to check_end
                "__end__": "check_end"
            }
        )
        
        # Add edge from execute_tools to call_model
        self.logger.info("Adding edge: execute_tools -> call_model")
        builder.add_edge("execute_tools", "call_model")
        
        # Add conditional edges from check_end node
        self.logger.info("Adding conditional edges from check_end node")
        builder.add_conditional_edges(
            "check_end",
            lambda state: self.check_end_conditions(state)["result"],
            {
                "end": END,
                "__end__": END,
                "continue": "call_model"  # Loop back if conditions not met
            }
        )
        
        # Compile graph
        self.logger.info("Compiling graph")
        return builder.compile()
    
    def call_model(self, state: PlanPhaseState) -> PlanPhaseState:
        """
        LLM reasoning node that analyzes current state and decides next action
        
        Args:
            state: Current state of the graph
            
        Returns:
            PlanPhaseState: Updated state after LLM reasoning
        """
        # Increment iteration count
        state["iteration_count"] += 1
        
        # Check if we've reached max iterations
        if state["iteration_count"] > self.max_iterations:
            self.logger.info(f"Reached max iterations ({self.max_iterations}), marking plan as complete")
            state["plan_complete"] = True
            
            # Add a final message indicating max iterations reached
            final_message = AIMessage(content=f"[MAX_ITERATIONS_REACHED] Completed {self.max_iterations} iterations. Finalizing plan with current information.")
            state["messages"].append(final_message)
            
            return state
        
        self.logger.info(f"Calling model (iteration {state['iteration_count']})")
        
        try:
            # Prepare messages if this is the first iteration or if messages need to be initialized
            state = self._prepare_messages(state)
            
            # Call the model with tools
            response = None
            if len(self.mcp_tools) != 0:
                response = self.llm.bind_tools(self.mcp_tools).invoke(state["messages"])
            else:
                response = self.llm.invoke(state["messages"])
            
            # Add response to messages
            state["messages"].append(response)
            
            # Log the response
            self.logger.info(f"Model response: {response.content[:100]}...")
            #print (f"Model response: {response.content[:]}...")
            return state
        except Exception as e:
            error_msg = handle_exception("call_model", e, self.logger)
            
            # Add error message to state
            error_message = SystemMessage(content=f"Error calling model: {error_msg}")
            state["messages"].append(error_message)
            
            # Mark plan as complete to exit the loop
            state["plan_complete"] = True
            
            return state
    
    def _initialize_execute_tool_node(self) -> ExecuteToolNode:
        """
        Initialize ExecuteToolNode with all MCP tools set to parallel execution
        
        Returns:
            ExecuteToolNode: Configured ExecuteToolNode instance
        """
        if not self.mcp_tools:
            self.logger.warning("No MCP tools available for ExecuteToolNode")
            # Return empty ExecuteToolNode if no tools available
            return ExecuteToolNode(
                tools=[],
                parallel_tools=set(),
                serial_tools=set()
            )
        
        # Get all tool names
        tool_names = {tool.name for tool in self.mcp_tools}
        
        # Configure all MCP tools to run in parallel by default
        parallel_tools = tool_names
        serial_tools = set()
        
        self.logger.info(f"Configuring ExecuteToolNode with {len(parallel_tools)} parallel tools")
        
        # Create and return ExecuteToolNode with all tools set to parallel execution
        execute_tool_node = ExecuteToolNode(
            tools=self.mcp_tools,
            parallel_tools=parallel_tools,
            serial_tools=serial_tools,
            handle_tool_errors=True,
            messages_key="messages"
        )
        
        # Create a hook manager for console output
        from troubleshooting.hook_manager import HookManager
        
        console = Console()
        file_console = Console(file=open('plan_phase_react.log', 'a'))
        hook_manager = HookManager(console=console, file_console=file_console)
        
        # Register custom hook functions with the hook manager
        hook_manager.register_before_call_hook(before_call_tools_hook)
        hook_manager.register_after_call_hook(after_call_tools_hook)
        
        # Register hook manager with the ExecuteToolNode
        execute_tool_node.register_before_call_hook(hook_manager.run_before_hook)
        execute_tool_node.register_after_call_hook(hook_manager.run_after_hook)
        
        return execute_tool_node

    def _prepare_messages(self, state: PlanPhaseState) -> PlanPhaseState:
        """
        Prepare messages for the LLM with system prompt and context
        
        Similar to graph.py's _prepare_messages() but using LLMPlanGenerator's approach for
        preparing system prompt and human query.
        
        Args:
            state: Current state with messages
            
        Returns:
            PlanPhaseState: Updated state with prepared messages
        """
        
        user_messages = []
        if state["messages"]:
            if isinstance(state["messages"], list):
                for msg in state["messages"]:
                    if not isinstance(msg, SystemMessage) and not isinstance(msg, HumanMessage):
                        user_messages.append(msg)
                
                # Create new message list with system message, context message, and existing user messages
                state["messages"] = self.init_message + user_messages
            else:
                state["messages"] = [self.init_message, state["messages"]]
        else:
            state["messages"] = self.init_message

        self.logger.info("Prepared initial messages with system prompt and user query")
        return state
        
    def check_end_conditions(self, state: PlanPhaseState) -> Dict[str, str]:
        """
        Check if plan generation is complete
        
        Args:
            state: Current state of the graph
            
        Returns:
            Dict[str, str]: Result indicating whether to end or continue
        """
        self.logger.info("Checking end conditions for Plan Phase ReAct graph")

        # If plan is already marked as complete, end the graph
        if state["plan_complete"]:
            self.logger.info("Plan marked as complete, ending graph")
            return {"result": "end"}
        
        # Check if we've reached max iterations
        if state["iteration_count"] >= self.max_iterations:
            self.logger.info(f"Reached max iterations ({self.max_iterations}), ending graph")
            return {"result": "end"}
        
        # Get the last message
        messages = state["messages"]
        if not messages:
            return {"result": "continue"}
        
        last_message = messages[-1]
        
        # Skip content checks if the last message isn't from the AI
        if getattr(last_message, "type", "") != "ai":
            return {"result": "continue"}
        
        content = getattr(last_message, "content", "")
        if not content:
            return {"result": "continue"}
        
        llm_end_markers = self._check_explicit_end_markers(content)
        if llm_end_markers:
            self.logger.info("Detected end markers from LLM, ending graph")
            state["plan_complete"] = True
            return {"result": "end"}

        # Check for explicit end markers in the content
        end_markers = ["[END_GRAPH]", "[END]", "End of graph", "GRAPH END", "Investigation Plan:", "Fix Plan:", "Step by Step"]
        if any(marker in content for marker in end_markers):
            self.logger.info(f"Detected end marker in content, ending graph")
            state["plan_complete"] = True
            return {"result": "end"}
        
        # Check for completion indicators
        if "Summary of Findings:" in content and "Root Cause:" in content and "Fix Plan:" in content:
            self.logger.info("Detected completion indicators in content, ending graph")
            state["plan_complete"] = True
            return {"result": "end"}
        
        # Check for convergence (model repeating itself)
        ai_messages = [m for m in messages if getattr(m, "type", "") == "ai"]
        if len(ai_messages) > 3:
            # Compare the last message with the third-to-last message
            last_content = content
            third_to_last_content = getattr(ai_messages[-3], "content", "")
            
            # Simple similarity check - if they start with the same paragraph
            if last_content and third_to_last_content:
                # Get first 100 chars of each message
                last_start = last_content[:100] if len(last_content) > 100 else last_content
                third_start = third_to_last_content[:100] if len(third_to_last_content) > 100 else third_to_last_content
                
                if last_start == third_start:
                    self.logger.info("Detected convergence (model repeating itself), ending graph")
                    state["plan_complete"] = True
                    return {"result": "end"}
        
        # Default: continue execution
        return {"result": "continue"}

    def _check_explicit_end_markers(self, content: str) -> bool:
        """Use LLM to check if content contains explicit or implicit end markers.
        
        Args:
            content: The content to check for end markers
            
        Returns:
            bool: True if end markers detected, False otherwise
        """
        # Create a focused prompt for the LLM
        system_prompt = """
        You are an AI assistant tasked with determining if a text contains explicit or implicit markers 
        indicating the end of a process or conversation. Your task is to analyze the given text and 
        determine if it contains phrases or markers that suggest completion or termination.
        
        Examples of explicit end markers include:
        - "[END_GRAPH]", "[END]", "End of graph", "GRAPH END"
        - "This concludes the analysis"
        - "Final report"
        - "Step by Step"
        - "Step XXX: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]"
        - "Investigation complete"
        - " Would you like to"
        - A question from AI that indicates the end of the process, such as " Would you like to proceed with planning the disk replacement or further investigate filesystem integrity?"
        - If just a call tools result, then return 'NO'

        Examples of implicit end markers include:
        - A summary followed by recommendations with no further questions
        - A conclusion paragraph that wraps up all findings
        - A complete analysis with all required sections present
        - A question from AI that indicates the end of the process, such as "Is there anything else I can help you with?" or "Do you have any further questions?"
        
        Respond with "YES" if you detect end markers, or "NO" if you don't.
        """
        
        user_prompt = f"""
        Analyze the following text and determine if it contains explicit or implicit end markers:
        
        {content}  # Limit content length to avoid token limits
        
        Does this text contain markers indicating it's the end of the process? Respond with only YES or NO.
        """
        
        try:
            # Create messages for the LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # Call the LLM
            response = self.llm.invoke(messages)
            
            # Check if the response indicates end markers
            response_text = response.content.strip().upper()
            
            # Log the LLM's response
            logger.info(f"LLM end marker detection response: {response_text}")
            
            # Return True if the LLM detected end markers
            return "YES" in response_text
        except Exception as e:
            # Log any errors and fall back to the original behavior
            logger.error(f"Error in LLM end marker detection: {e}")
            
            # Fall back to simple string matching
            return any(marker in content for marker in ["[END_GRAPH]", "[END]", "End of graph", "GRAPH END", "Fix Plan", "FIX PLAN"])
    
    def extract_plan_from_state(self, state: PlanPhaseState) -> str:
        """
        Extract the investigation plan from the final state
        
        Args:
            state: Final state of the graph
            
        Returns:
            str: Investigation plan as a formatted string
        """
        # Get the last AI message
        ai_messages = [m for m in state["messages"] if getattr(m, "type", "") == "ai"]
        
        if not ai_messages:
            self.logger.warning("No AI messages found in final state")
            return generate_basic_fallback_plan(
                state["pod_name"], state["namespace"], state["volume_path"]
            )
        
        # Get the content of the last AI message
        last_ai_message = ai_messages[-1]
        content = getattr(last_ai_message, "content", "")
        
        # Extract the investigation plan
        if "Investigation Plan:" in content:
            plan_index = content.find("Investigation Plan:")
            plan = content[plan_index:]
            
            # Remove end markers
            for marker in ["[END_GRAPH]", "[END]", "End of graph", "GRAPH END"]:
                plan = plan.replace(marker, "")
                
            return plan.strip()
        
        # If no plan found, return the entire content
        return content.strip()

async def run_plan_phase_react(pod_name: str, namespace: str, volume_path: str, 
                             messages: List[BaseMessage] = None, 
                             config_data: Dict[str, Any] = None) -> Tuple[str, List[Dict[str, str]]]:
    """
    Run the Plan Phase using ReAct graph
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        messages: List of messages (system prompt, user message) to use for the ReAct graph
        config_data: Configuration data for the system (optional)
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: (Investigation Plan as a formatted string, Updated message list)
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Running Plan Phase ReAct for {namespace}/{pod_name} volume {volume_path}")
    
    try:
        # Initialize and build the ReAct graph
        react_graph = PlanPhaseReActGraph(config_data, messages if messages else [])
        graph = react_graph.build_graph() 

        # Prepare initial state with provided messages
        initial_state = {
            "messages": messages if messages else [],
            "iteration_count": 0,
            "tool_call_count": 0,
            "knowledge_gathered": {},
            "plan_complete": False,
            "pod_name": pod_name,
            "namespace": namespace,
            "volume_path": volume_path,
            "knowledge_graph": None  # Knowledge graph information is now in messages
        }
        
        # Run the graph
        logger.info("Running Plan Phase ReAct graph")
        final_state = graph.invoke(initial_state)
        
        # Extract the investigation plan
        investigation_plan = react_graph.extract_plan_from_state(final_state)
        
        # Convert messages to message list format
        message_list = _convert_messages_to_message_list(final_state["messages"])
        
        # Log the results
        logger.info("Plan Phase ReAct completed successfully")
        
        return investigation_plan, message_list
        
    except Exception as e:
        error_msg = handle_exception("run_plan_phase_react", e, logger)
        fallback_plan = generate_basic_fallback_plan(pod_name, namespace, volume_path)
        return fallback_plan, []

def _convert_messages_to_message_list(messages: List[BaseMessage]) -> List[Dict[str, str]]:
    """
    Convert BaseMessage list to message list format
    
    Args:
        messages: List of BaseMessage objects
        
    Returns:
        List[Dict[str, str]]: Message list format
    """
    message_list = []
    
    for message in messages:
        role = "system"
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        elif isinstance(message, ToolMessage):
            role = "tool"
        
        message_list.append({
            "role": role,
            "content": message.content
        })
    
    return message_list
