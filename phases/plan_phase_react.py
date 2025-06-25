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

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from phases.llm_factory import LLMFactory
from phases.utils import handle_exception, format_json_safely, generate_basic_fallback_plan
from tools.core.mcp_adapter import get_mcp_adapter
from knowledge_graph import KnowledgeGraph

# Configure logging
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
    
    def __init__(self, config_data: Dict[str, Any] = None):
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
        
        self.logger.info("Adding node: execute_tools")
        builder.add_node("execute_tools", self.execute_tools)
        
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
    
    def execute_tools(self, state: PlanPhaseState) -> PlanPhaseState:
        """
        Execute MCP tools based on LLM decisions
        
        Args:
            state: Current state of the graph
            
        Returns:
            PlanPhaseState: Updated state after tool execution
        """
        # Get the last message
        last_message = state["messages"][-1]
        
        # Extract tool calls
        tool_calls = last_message.tool_calls
        
        if not tool_calls:
            self.logger.warning("No tool calls found in last message")
            return state
        
        self.logger.info(f"Executing {len(tool_calls)} tool calls")
        
        # Process each tool call
        for tool_call in tool_calls:
            # Increment tool call count
            state["tool_call_count"] += 1
            
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            self.logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
            
            try:
                # Find the tool
                tool = next((t for t in self.mcp_tools if t.name == tool_name), None)
                
                if not tool:
                    error_msg = f"Tool not found: {tool_name}"
                    self.logger.error(error_msg)
                    
                    # Add error message to state
                    tool_message = ToolMessage(
                        content=f"Error: {error_msg}",
                        name=tool_name,
                        tool_call_id=tool_id
                    )
                    state["messages"].append(tool_message)
                    continue
                
                # Execute the tool
                result = tool.invoke(tool_args)
                
                # Add result to state
                tool_message = ToolMessage(
                    content=str(result),
                    name=tool_name,
                    tool_call_id=tool_id
                )
                state["messages"].append(tool_message)
                
                # Store knowledge in state
                state["knowledge_gathered"][tool_name] = {
                    "args": tool_args,
                    "result": result
                }
                
                self.logger.info(f"Tool {tool_name} executed successfully")
            except Exception as e:
                error_msg = handle_exception(f"execute_tool_{tool_name}", e, self.logger)
                
                # Add error message to state
                tool_message = ToolMessage(
                    content=f"Error executing tool {tool_name}: {error_msg}",
                    name=tool_name,
                    tool_call_id=tool_id
                )
                state["messages"].append(tool_message)
        
        return state
    
    def check_end_conditions(self, state: PlanPhaseState) -> Dict[str, str]:
        """
        Check if plan generation is complete
        
        Args:
            state: Current state of the graph
            
        Returns:
            Dict[str, str]: Result indicating whether to end or continue
        """
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
        end_markers = ["[END_GRAPH]", "[END]", "End of graph", "GRAPH END", "Investigation Plan:", "Fix Plan:"]
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
    
    def prepare_initial_messages(self, knowledge_graph: KnowledgeGraph, pod_name: str, 
                               namespace: str, volume_path: str) -> List[BaseMessage]:
        """
        Prepare initial messages for the ReAct graph
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            List[BaseMessage]: Initial messages for the ReAct graph
        """
        # Create system message with instructions
        system_message = SystemMessage(content=self._generate_system_prompt())
        
        # Create user message with context
        user_message = HumanMessage(content=self._generate_user_prompt(
            knowledge_graph, pod_name, namespace, volume_path
        ))
        
        return [system_message, user_message]
    
    def _generate_system_prompt(self) -> str:
        """
        Generate system prompt for the ReAct graph
        
        Returns:
            str: System prompt
        """
        # Get available MCP tools information
        mcp_tools_info = "\n".join([
            f"- {tool.name}: {tool.description}" for tool in self.mcp_tools
        ])
        
        return f"""You are an AI assistant tasked with generating an Investigation Plan for troubleshooting Kubernetes volume I/O errors.
You are operating in a ReAct (Reasoning and Acting) framework where you can:
1. REASON about the problem and identify knowledge gaps
2. ACT by calling external tools to gather information
3. OBSERVE the results and update your understanding
4. Continue this loop until you have enough information to create a comprehensive plan

Your goal is to create a detailed Investigation Plan that identifies potential problems and provides specific steps to diagnose and resolve volume read/write errors.

Available MCP tools:
{mcp_tools_info}

When you identify a knowledge gap, use the appropriate MCP tool to gather the information you need. Don't guess or make assumptions when you can use a tool to get accurate information.

Once you have gathered sufficient information, generate a comprehensive Investigation Plan with this format:

Investigation Plan:
PossibleProblem 1: [Problem description]
Step 1: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]
Step 2: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]
...
PossibleProblem 2: [Problem description]
Step 1: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]
Step 2: [Description and Reason] | Tool: [tool_name(parameters)] | Expected: [expected]
...

When you've completed the Investigation Plan, include the marker [END_GRAPH] at the end of your message.
"""
    
    def _generate_user_prompt(self, knowledge_graph: KnowledgeGraph, pod_name: str,
                            namespace: str, volume_path: str) -> str:
        """
        Generate user prompt with context for the ReAct graph
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: User prompt with context
        """
        # Extract knowledge graph context
        kg_context = self._extract_kg_context(knowledge_graph)
        
        return f"""# INVESTIGATION PLAN GENERATION TASK
## TARGET: Volume read/write errors in pod {pod_name} (namespace: {namespace}, volume path: {volume_path})

I need you to create a comprehensive Investigation Plan for troubleshooting this volume I/O error.

## BACKGROUND INFORMATION

### KNOWLEDGE GRAPH CONTEXT
{kg_context}

## TASK
1. Analyze the available information to understand the context
2. Identify any knowledge gaps that need to be filled
3. Use MCP tools to gather additional information as needed
4. Create a comprehensive Investigation Plan with specific steps to diagnose and resolve the volume I/O error

Please start by analyzing the available information and identifying any knowledge gaps.
"""
    
    def _extract_kg_context(self, knowledge_graph: KnowledgeGraph) -> str:
        """
        Extract context from Knowledge Graph
        
        Args:
            knowledge_graph: KnowledgeGraph instance
            
        Returns:
            str: Formatted knowledge graph context
        """
        if not knowledge_graph:
            return "No Knowledge Graph available."
        
        try:
            # Get summary of knowledge graph
            kg_summary = knowledge_graph.get_summary()
            
            # Get all issues
            issues = knowledge_graph.get_all_issues()
            
            # Format the context
            context = f"""
Knowledge Graph Summary:
{json.dumps(kg_summary, indent=2)}

Issues:
{json.dumps(issues, indent=2)}
"""
            return context
        except Exception as e:
            error_msg = handle_exception("_extract_kg_context", e, self.logger)
            return f"Error extracting Knowledge Graph context: {error_msg}"
    
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
                             collected_info: Dict[str, Any], config_data: Dict[str, Any] = None) -> Tuple[str, List[Dict[str, str]]]:
    """
    Run the Plan Phase using ReAct graph
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Dictionary containing collected information from Phase 0, including knowledge_graph
        config_data: Configuration data for the system (optional)
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: (Investigation Plan as a formatted string, Updated message list)
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Running Plan Phase ReAct for {namespace}/{pod_name} volume {volume_path}")
    
    try:
        # Extract knowledge_graph from collected_info
        knowledge_graph = collected_info.get('knowledge_graph')
        
        # Validate knowledge_graph is present
        if knowledge_graph is None:
            error_msg = "Knowledge Graph not found in collected_info"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Initialize and build the ReAct graph
        react_graph = PlanPhaseReActGraph(config_data)
        graph = react_graph.build_graph()
        
        # Prepare initial state
        initial_state = {
            "messages": react_graph.prepare_initial_messages(knowledge_graph, pod_name, namespace, volume_path),
            "iteration_count": 0,
            "tool_call_count": 0,
            "knowledge_gathered": {},
            "plan_complete": False,
            "pod_name": pod_name,
            "namespace": namespace,
            "volume_path": volume_path,
            "knowledge_graph": knowledge_graph
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
