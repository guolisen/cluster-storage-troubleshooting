#!/usr/bin/env python3
"""
Phase 1 (Analysis) LangGraph Implementation for Kubernetes Volume Troubleshooting

This module implements the LangGraph workflow for the Analysis phase
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
from llm_graph.prompt_managers.phase1_prompt_manager import Phase1PromptManager
from phases.llm_factory import LLMFactory
from phases.utils import handle_exception
from tools.core.mcp_adapter import get_mcp_adapter

logger = logging.getLogger(__name__)

class Phase1State(TypedDict):
    """State for the Analysis Phase ReAct graph"""
    messages: List[BaseMessage]  # Conversation history
    iteration_count: int  # Track iterations
    tool_call_count: int  # Track tool calls
    goals_achieved: List[str]  # Track achieved goals
    root_cause_identified: bool  # Whether root cause was identified
    investigation_plan: str  # Investigation plan to follow

class Phase1LLMGraph(LangGraphInterface):
    """
    LangGraph implementation for the Analysis phase (Phase 1)
    
    Implements the LangGraphInterface for the Analysis phase,
    which executes the Investigation Plan to identify root causes.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the Phase 1 LLM Graph
        
        Args:
            config_data: Configuration data for the system
        """
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.graph_utility = GraphUtility(config_data)
        self.prompt_manager = Phase1PromptManager(config_data)
        
        # Initialize LLM
        self.llm = self._initialize_llm()
        
        # Get MCP tools
        self.mcp_tools = self._get_mcp_tools_for_phase1()
        
        # Load tool configuration
        self.parallel_tools, self.serial_tools = self._load_tool_config()
        
        # Maximum iterations to prevent infinite loops
        self.max_iterations = self.config_data.get("max_iterations", 30)
    
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
                phase_name="phase1"
            )
        except Exception as e:
            error_msg = handle_exception("_initialize_llm", e, self.logger)
            raise ValueError(f"Failed to initialize LLM: {error_msg}")
    
    def _get_mcp_tools_for_phase1(self) -> List[BaseTool]:
        """
        Get MCP tools for Phase 1
        
        Returns:
            List[BaseTool]: List of MCP tools for Phase 1
        """
        # Get MCP adapter
        mcp_adapter = get_mcp_adapter()
        
        if not mcp_adapter:
            self.logger.warning("MCP adapter not initialized, no MCP tools will be available")
            return []
        
        if not mcp_adapter.mcp_enabled:
            self.logger.warning("MCP integration is disabled, no MCP tools will be available")
            return []
        
        # Get MCP tools for phase1
        mcp_tools = mcp_adapter.get_tools_for_phase('phase1')
        
        if not mcp_tools:
            self.logger.warning("No MCP tools available for Phase 1")
            return []
        
        self.logger.info(f"Loaded {len(mcp_tools)} MCP tools for Phase 1")
        return mcp_tools
    
    def _load_tool_config(self) -> Tuple[Set[str], Set[str]]:
        """
        Load tool configuration to determine which tools
        should be executed in parallel and which should be executed serially.
        
        Returns:
            Tuple[Set[str], Set[str]]: Sets of parallel and serial tool names
        """
        try:
            import yaml
            
            with open('config.yaml', 'r') as f:
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
    
    def initialize_graph(self) -> StateGraph:
        """
        Initialize and return the LangGraph StateGraph
        
        Returns:
            StateGraph: Compiled LangGraph StateGraph
        """
        # Build state graph
        self.logger.info("Building Phase 1 ReAct graph")
        builder = StateGraph(Phase1State)
        
        # Add nodes
        self.logger.info("Adding node: call_model")
        builder.add_node("call_model", self.call_model)
        
        # Initialize ExecuteToolNode with parallel/serial tool configuration
        execute_tools_node = self.graph_utility.create_execute_tool_node(
            self.mcp_tools, self.parallel_tools, self.serial_tools
        )
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
    
    def call_model(self, state: Phase1State) -> Phase1State:
        """
        LLM reasoning node that analyzes current state and decides next action
        
        Args:
            state: Current state of the graph
            
        Returns:
            Phase1State: Updated state after LLM reasoning
        """
        # Increment iteration count
        state["iteration_count"] += 1
        
        # Check if we've reached max iterations
        if state["iteration_count"] > self.max_iterations:
            self.logger.info(f"Reached max iterations ({self.max_iterations}), marking analysis as complete")
            
            # Add a final message indicating max iterations reached
            final_message = AIMessage(content=f"[MAX_ITERATIONS_REACHED] Completed {self.max_iterations} iterations. Finalizing analysis with current information.")
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
            
            return state
    
    def check_end_conditions(self, state: Phase1State) -> Dict[str, str]:
        """
        Check if analysis is complete
        
        Args:
            state: Current state of the graph
            
        Returns:
            Dict[str, str]: Result indicating whether to end or continue
        """
        self.logger.info("Checking end conditions for Phase 1 ReAct graph")
        
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
        end_markers = ["[END_GRAPH]", "[END]", "End of graph", "GRAPH END", "CONCLUSION:", "SUMMARY OF FINDINGS:"]
        if any(marker in content for marker in end_markers):
            self.logger.info(f"Detected end marker in content, ending graph")
            return {"result": "end"}
        
        # Check for completion indicators
        if "Summary of Findings:" in content and "Root Cause:" in content:
            self.logger.info("Detected completion indicators in content, ending graph")
            state["root_cause_identified"] = True
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
                    return {"result": "end"}
        
        # Default: continue execution
        return {"result": "continue"}
    
    def extract_analysis_from_state(self, state: Phase1State) -> str:
        """
        Extract the analysis results from the final state
        
        Args:
            state: Final state of the graph
            
        Returns:
            str: Analysis results as a formatted string
        """
        # Get the last AI message
        ai_messages = [m for m in state["messages"] if getattr(m, "type", "") == "ai"]
        
        if not ai_messages:
            self.logger.warning("No AI messages found in final state")
            return "Failed to generate analysis results."
        
        # Get the content of the last AI message
        last_ai_message = ai_messages[-1]
        content = getattr(last_ai_message, "content", "")
        
        # Remove end markers
        for marker in ["[END_GRAPH]", "[END]", "End of graph", "GRAPH END"]:
            content = content.replace(marker, "")
            
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
                "goals_achieved": [],
                "root_cause_identified": False,
                "investigation_plan": state.get("investigation_plan", "")
            }
            
            # Run the graph
            self.logger.info("Running Phase 1 ReAct graph")
            final_state = graph.invoke(initial_state)
            
            # Extract the analysis results
            analysis_results = self.extract_analysis_from_state(final_state)
            
            # Add the analysis results to the final state
            final_state["analysis_results"] = analysis_results
            
            return final_state
            
        except Exception as e:
            error_msg = handle_exception("execute", e, self.logger)
            
            return {
                "status": "error",
                "error_message": error_msg,
                "analysis_results": "Failed to complete analysis due to an error.",
                "messages": state.get("messages", [])
            }
    
    def get_prompt_manager(self):
        """
        Return the prompt manager for this graph
        
        Returns:
            Phase1PromptManager: Prompt manager for the Analysis phase
        """
        return self.prompt_manager
