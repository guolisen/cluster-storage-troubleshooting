#!/usr/bin/env python3
"""
Plan Phase LangGraph Implementation for Kubernetes Volume Troubleshooting

This module implements the LangGraph workflow for the Plan phase
of the troubleshooting system using the Strategy Pattern.
"""

import logging
import asyncio
from typing import Dict, List, Any, TypedDict, Optional, Union, Tuple, Set
from enum import Enum

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import BaseTool

from llm_graph.langgraph_interface import LangGraphInterface
from llm_graph.graph_utility import GraphUtility
from llm_graph.prompt_managers.plan_prompt_manager import PlanPromptManager
from phases.llm_factory import LLMFactory
from phases.utils import handle_exception, generate_basic_fallback_plan

logger = logging.getLogger(__name__)

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
    knowledge_graph: Optional[Any]  # Knowledge graph for context

class ReActStage(Enum):
    """Stages in the ReAct process"""
    REASONING = "reasoning"  # LLM analyzing and reasoning about the problem
    ACTING = "acting"  # Calling tools to gather information
    OBSERVING = "observing"  # Processing tool outputs
    PLANNING = "planning"  # Generating the final plan

class PlanLLMGraph(LangGraphInterface):
    """
    LangGraph implementation for the Plan phase
    
    Implements the LangGraphInterface for the Plan phase,
    which generates an Investigation Plan for Phase 1.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the Plan LLM Graph
        
        Args:
            config_data: Configuration data for the system
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.graph_utility = GraphUtility(config_data)
        self.prompt_manager = PlanPromptManager(config_data)
        
        # Initialize LLM
        self.llm = self._initialize_llm()
        
        # Get MCP tools
        self.mcp_tools = self._get_mcp_tools_for_plan_phase()
        
        # Maximum iterations to prevent infinite loops
        self.max_iterations = self.config_data.get("max_iterations", 15)
    
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
        """
        from tools.core.mcp_adapter import get_mcp_adapter
        
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
    
    def initialize_graph(self) -> StateGraph:
        """
        Initialize and return the LangGraph StateGraph
        
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
            
            return state
        except Exception as e:
            error_msg = handle_exception("call_model", e, self.logger)
            
            # Add error message to state
            error_message = SystemMessage(content=f"Error calling model: {error_msg}")
            state["messages"].append(error_message)
            
            # Mark plan as complete to exit the loop
            state["plan_complete"] = True
            
            return state
    
    def _initialize_execute_tool_node(self):
        """
        Initialize ExecuteToolNode with all MCP tools set to parallel execution
        
        Returns:
            ExecuteToolNode: Configured ExecuteToolNode instance
        """
        if not self.mcp_tools:
            self.logger.warning("No MCP tools available for ExecuteToolNode")
            return None
        
        # Get all tool names
        tool_names = {tool.name for tool in self.mcp_tools}
        
        # Configure all MCP tools to run in parallel by default
        parallel_tools = tool_names
        serial_tools = set()
        
        self.logger.info(f"Configuring ExecuteToolNode with {len(parallel_tools)} parallel tools")
        
        # Create and return ExecuteToolNode with all tools set to parallel execution
        return self.graph_utility.create_execute_tool_node(self.mcp_tools, parallel_tools, serial_tools)
    
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
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the graph with the provided state
        
        Args:
            state: Initial state for the graph execution
            
        Returns:
            Dict[str, Any]: Final state after graph execution
        """
        try:
            # Initialize the graph
            graph = self.initialize_graph()
            
            # Prepare initial state
            initial_state = {
                "messages": state.get("messages", []),
                "iteration_count": 0,
                "tool_call_count": 0,
                "knowledge_gathered": {},
                "plan_complete": False,
                "pod_name": state.get("pod_name", ""),
                "namespace": state.get("namespace", ""),
                "volume_path": state.get("volume_path", ""),
                "knowledge_graph": state.get("knowledge_graph", None)
            }
            
            # Run the graph
            self.logger.info("Running Plan Phase ReAct graph")
            final_state = graph.invoke(initial_state)
            
            # Extract the investigation plan
            investigation_plan = self.extract_plan_from_state(final_state)
            
            # Add the investigation plan to the final state
            final_state["investigation_plan"] = investigation_plan
            
            return final_state
            
        except Exception as e:
            error_msg = handle_exception("execute", e, self.logger)
            fallback_plan = generate_basic_fallback_plan(
                state.get("pod_name", ""), 
                state.get("namespace", ""), 
                state.get("volume_path", "")
            )
            
            return {
                "status": "error",
                "error_message": error_msg,
                "investigation_plan": fallback_plan,
                "messages": state.get("messages", [])
            }
    
    def get_prompt_manager(self):
        """
        Return the prompt manager for this graph
        
        Returns:
            PlanPromptManager: Prompt manager for the Plan phase
        """
        return self.prompt_manager
