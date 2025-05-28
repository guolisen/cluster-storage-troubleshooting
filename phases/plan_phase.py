#!/usr/bin/env python3
"""
Plan Phase for Kubernetes Volume Troubleshooting

This module implements the Plan Phase that generates Investigation Plans
based on Knowledge Graph analysis. The Plan Phase is inserted between
Phase 0 (Information Collection) and Phase 1 (ReAct Investigation).
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from rich.console import Console
from rich.panel import Panel

from knowledge_graph import KnowledgeGraph
from .investigation_planner import InvestigationPlanner

logger = logging.getLogger(__name__)

class PlanPhase:
    """
    Plan Phase implementation for generating Investigation Plans
    
    The Plan Phase analyzes the Knowledge Graph from Phase 0 and generates
    a structured Investigation Plan for Phase 1 to follow.
    """
    
    def __init__(self, knowledge_graph: KnowledgeGraph, config_data: Dict[str, Any]):
        """
        Initialize the Plan Phase
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
            config_data: Configuration data for the system
        """
        self.kg = knowledge_graph
        self.config_data = config_data
        self.planner = InvestigationPlanner(knowledge_graph)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Rich console for output
        self.console = Console()
        
    def generate_plan(self, pod_name: str, namespace: str, volume_path: str) -> str:
        """
        Generate an Investigation Plan for the given pod and volume error
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: Formatted Investigation Plan
        """
        self.logger.info(f"Plan Phase: Generating investigation plan for {namespace}/{pod_name}")
        
        try:
            # Use the Investigation Planner to generate the plan
            investigation_plan = self.planner.generate_investigation_plan(
                pod_name, namespace, volume_path
            )
            
            self.logger.info(f"Plan Phase: Successfully generated plan with {len(investigation_plan.split('Step'))-1} steps")
            return investigation_plan
            
        except Exception as e:
            self.logger.error(f"Plan Phase: Error generating investigation plan: {str(e)}")
            # Return a basic fallback plan
            return self._generate_emergency_fallback_plan(pod_name, namespace, volume_path)
    
    def _generate_emergency_fallback_plan(self, pod_name: str, namespace: str, volume_path: str) -> str:
        """
        Generate an emergency fallback plan when all else fails
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: Emergency fallback Investigation Plan
        """
        emergency_plan = f"""Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}
Generated Steps: 3 emergency steps (minimal fallback)

Step 1: Get Knowledge Graph summary | Tool: kg_get_summary() | Expected: Basic system overview and entity counts
Step 2: Get all issues from Knowledge Graph | Tool: kg_get_all_issues() | Expected: Complete list of detected issues
Step 3: Print Knowledge Graph for manual analysis | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Full graph visualization

Fallback Steps (if main steps fail):
Step F1: Emergency analysis fallback | Tool: kg_analyze_issues() | Expected: Any available issue analysis | Trigger: all_steps_failed
"""
        return emergency_plan


def create_plan_phase_graph(collected_info: Dict[str, Any], config_data: Dict[str, Any]) -> StateGraph:
    """
    Create a LangGraph StateGraph for the Plan Phase
    
    The Plan Phase graph only uses Knowledge Graph tools and generates
    Investigation Plans based on the Knowledge Graph from Phase 0.
    
    Args:
        collected_info: Pre-collected diagnostic information from Phase 0
        config_data: Configuration data
        
    Returns:
        StateGraph: LangGraph StateGraph for Plan Phase
    """
    if config_data is None:
        raise ValueError("Configuration data is required")
    
    # Initialize language model
    model = ChatOpenAI(
        model=config_data['llm']['model'],
        api_key=config_data['llm']['api_key'],
        base_url=config_data['llm']['api_endpoint'],
        temperature=config_data['llm']['temperature'],
        max_tokens=config_data['llm']['max_tokens']
    )
    
    def call_model(state: MessagesState):
        """
        Call the model with Plan Phase specific instructions
        """
        logging.info(f"Plan Phase: Processing state with {len(state['messages'])} messages")
        
        # Plan Phase specific system prompt
        plan_phase_guidance = """
You are in the Plan Phase of a Kubernetes volume troubleshooting system. Your ONLY task is to generate a detailed Investigation Plan based on Knowledge Graph analysis.

PLAN PHASE CONSTRAINTS:
- You can ONLY use Knowledge Graph tools (kg_* functions)
- NO external system access (no kubectl, ssh, etc.)
- NO hardware tools or system commands
- NO modification of any system state
- DETERMINISTIC analysis based solely on Knowledge Graph data

AVAILABLE TOOLS (7 Knowledge Graph tools only):
1. kg_get_entity_info - Get detailed information about specific entities
2. kg_get_related_entities - Find entities related to a target entity
3. kg_get_all_issues - Get all issues, optionally filtered by severity/type
4. kg_find_path - Find shortest path between two entities  
5. kg_get_summary - Get overall Knowledge Graph statistics
6. kg_analyze_issues - Analyze issue patterns and relationships
7. kg_print_graph - Get human-readable graph representation

YOUR TASK:
Generate a comprehensive Investigation Plan that Phase 1 can follow. The plan should:

1. Start with Knowledge Graph analysis to understand current issues
2. Identify the most critical problems affecting the target pod
3. Create a step-by-step sequence for Phase 1 to follow
4. Focus on Knowledge Graph queries that will provide maximum diagnostic value
5. Include fallback steps for incomplete data scenarios

INVESTIGATION PLAN FORMAT:
```
Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}
Generated Steps: {number} main steps, {number} fallback steps

Step 1: [Description] | Tool: [kg_tool(arguments)] | Expected: [expected_outcome]
Step 2: [Description] | Tool: [kg_tool(arguments)] | Expected: [expected_outcome]
...

Fallback Steps (if main steps fail):
Step F1: [Description] | Tool: [kg_tool(arguments)] | Expected: [expected_outcome] | Trigger: [failure_condition]
...
```

STRATEGY:
- Always start with kg_get_all_issues to understand critical problems
- Use kg_analyze_issues to identify patterns and root causes
- Follow the dependency chain: Pod -> PVC -> PV -> Drive -> Node
- Include hardware and infrastructure checks through Knowledge Graph queries
- Provide comprehensive fallback strategies

Remember: You are creating a PLAN, not executing it. Phase 1 will execute your plan using both Knowledge Graph tools and additional diagnostic tools.
"""

        # Prepare context from collected information
        context_summary = f"""
=== KNOWLEDGE GRAPH CONTEXT FOR PLAN GENERATION ===

Knowledge Graph Summary:
{json.dumps(collected_info.get('knowledge_graph_summary', {}), indent=2)}

Current Issues:
{str(collected_info.get('issues', []))[:1000]}

System Overview:
- Total Nodes: {len(collected_info.get('node_info', {}))}
- Total Pods: {len(collected_info.get('pod_info', {}))}
- Total PVCs: {len(collected_info.get('pvc_info', {}))}
- Total PVs: {len(collected_info.get('pv_info', {}))}

=== END CONTEXT ===
"""

        system_message = {
            "role": "system",
            "content": f"""{plan_phase_guidance}

Current System Context:
{context_summary}

Generate a comprehensive Investigation Plan that Phase 1 can execute to diagnose volume I/O issues efficiently."""
        }
        
        # Ensure system message is first
        if state["messages"]:
            if isinstance(state["messages"], list):
                if state["messages"][0].type != "system":
                    state["messages"] = [system_message] + state["messages"]
            else:
                state["messages"] = [system_message, state["messages"]]
        else:
            state["messages"] = [system_message]
        
        # Import and get ONLY Knowledge Graph tools for Plan Phase
        from tools.core.knowledge_graph import (
            kg_get_entity_info,
            kg_get_related_entities, 
            kg_get_all_issues,
            kg_find_path,
            kg_get_summary,
            kg_analyze_issues,
            kg_print_graph
        )
        
        plan_phase_tools = [
            kg_get_entity_info,
            kg_get_related_entities,
            kg_get_all_issues, 
            kg_find_path,
            kg_get_summary,
            kg_analyze_issues,
            kg_print_graph
        ]
        
        logging.info(f"Plan Phase: Using {len(plan_phase_tools)} Knowledge Graph tools only")
        
        # Call the model with only Knowledge Graph tools
        response = model.bind_tools(plan_phase_tools).invoke(state["messages"])
        
        logging.info(f"Plan Phase: Model response generated")
        
        # Display thinking process with rich formatting
        console = Console()
        
        if response.content:
            console.print(Panel(
                f"[bold green]{response.content}[/bold green]",
                title="[bold cyan]Plan Phase - Investigation Plan Generation",
                border_style="cyan",
                safe_box=True
            ))
        
        # Log tool usage for Plan Phase
        if hasattr(response, 'additional_kwargs') and 'tool_calls' in response.additional_kwargs:
            try:
                for tool_call in response.additional_kwargs['tool_calls']:
                    tool_name = tool_call['function']['name']
                    
                    if 'arguments' in tool_call['function']:
                        args = tool_call['function']['arguments']
                        try:
                            args_json = json.loads(args)
                            formatted_args = json.dumps(args_json, indent=2)
                        except:
                            formatted_args = args
                        
                        tool_panel = Panel(
                            f"[bold yellow]Tool:[/bold yellow] [green]{tool_name}[/green]\n\n"
                            f"[bold yellow]Arguments:[/bold yellow]\n[blue]{formatted_args}[/blue]",
                            title="[bold cyan]Plan Phase - Knowledge Graph Query",
                            border_style="cyan",
                            safe_box=True
                        )
                        console.print(tool_panel)
                    
                    logging.info(f"Plan Phase: Using tool {tool_name}")
                    
            except Exception as e:
                logging.warning(f"Plan Phase: Error in rich formatting: {e}")
                for tool_call in response.additional_kwargs['tool_calls']:
                    logging.info(f"Plan Phase: Using tool: {tool_call['function']['name']}")
        
        return {"messages": state["messages"] + [response]}
    
    # Build state graph for Plan Phase
    logging.info("Plan Phase: Building state graph")
    builder = StateGraph(MessagesState)
    
    builder.add_node("call_model", call_model)
    
    # Add tools - ONLY Knowledge Graph tools for Plan Phase
    from tools.core.knowledge_graph import (
        kg_get_entity_info,
        kg_get_related_entities,
        kg_get_all_issues,
        kg_find_path, 
        kg_get_summary,
        kg_analyze_issues,
        kg_print_graph
    )
    
    plan_phase_tools = [
        kg_get_entity_info,
        kg_get_related_entities,
        kg_get_all_issues,
        kg_find_path,
        kg_get_summary, 
        kg_analyze_issues,
        kg_print_graph
    ]
    
    builder.add_node("tools", ToolNode(plan_phase_tools))
    
    # Add conditional edges
    builder.add_conditional_edges(
        "call_model",
        tools_condition,
        {
            "tools": "tools",
            "none": END,
            "__end__": END
        }
    )
    
    builder.add_edge("tools", "call_model")
    builder.add_edge(START, "call_model")
    
    graph = builder.compile()
    logging.info("Plan Phase: Graph compilation complete")
    
    return graph


async def run_plan_phase(pod_name: str, namespace: str, volume_path: str, 
                        collected_info: Dict[str, Any], config_data: Dict[str, Any]) -> str:
    """
    Run the Plan Phase to generate an Investigation Plan
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        config_data: Configuration data
        
    Returns:
        str: Generated Investigation Plan
    """
    console = Console()
    
    try:
        console.print("\n")
        console.print(Panel(
            f"[bold white]Generating Investigation Plan based on Knowledge Graph analysis...\n"
            f"Target: [green]{namespace}/{pod_name}[/green]\n"
            f"Volume: [blue]{volume_path}[/blue]",
            title="[bold cyan]PLAN PHASE: INVESTIGATION PLAN GENERATION",
            border_style="cyan",
            padding=(1, 2)
        ))
        
        # Get the Knowledge Graph from collected info
        knowledge_graph = collected_info.get('knowledge_graph')
        if not knowledge_graph:
            logging.warning("Plan Phase: No Knowledge Graph found in collected info")
            # Create a basic plan without KG analysis
            basic_plan = f"""Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}
Generated Steps: 3 basic steps (no Knowledge Graph available)

Step 1: Get system overview | Tool: kg_get_summary() | Expected: Basic system statistics if available
Step 2: Get all issues | Tool: kg_get_all_issues() | Expected: Any detected issues in the system
Step 3: Print Knowledge Graph | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Full system visualization

Fallback Steps (if main steps fail):
Step F1: Emergency analysis | Tool: kg_analyze_issues() | Expected: Basic issue analysis | Trigger: kg_unavailable
"""
            return basic_plan
        
        # Initialize Plan Phase with Knowledge Graph
        plan_phase = PlanPhase(knowledge_graph, config_data)
        
        # Option 1: Direct plan generation (simpler, faster)
        if config_data.get('plan_phase', {}).get('use_direct_generation', True):
            investigation_plan = plan_phase.generate_plan(pod_name, namespace, volume_path)
            
            console.print(Panel(
                f"[bold green]Investigation Plan generated successfully![/bold green]\n"
                f"[yellow]Plan contains {len(investigation_plan.split('Step'))-1} main steps[/yellow]",
                title="[bold cyan]Plan Phase Complete",
                border_style="green"
            ))
            
            return investigation_plan
        
        # Option 2: LangGraph-based generation (more sophisticated)
        else:
            # Create and run the Plan Phase graph
            graph = create_plan_phase_graph(collected_info, config_data)
            
            # Initial query for plan generation
            query = f"""Plan Phase: Generate a comprehensive Investigation Plan for troubleshooting volume I/O error in pod {pod_name} in namespace {namespace} at volume path {volume_path}.

Use only Knowledge Graph tools to analyze the current system state and create a step-by-step investigation plan that Phase 1 can follow.

Your task:
1. Analyze the Knowledge Graph to understand current issues
2. Identify critical problems affecting the target pod
3. Create a structured investigation sequence
4. Include fallback steps for incomplete data scenarios
5. Focus on queries that provide maximum diagnostic value

Generate the Investigation Plan in the specified format."""
            
            # Set timeout for plan generation
            timeout_seconds = config_data.get('plan_phase', {}).get('timeout_seconds', 120)
            
            # Run the graph
            formatted_query = {"messages": [{"role": "user", "content": query}]}
            
            try:
                import asyncio
                response = await asyncio.wait_for(
                    graph.ainvoke(formatted_query, config={"recursion_limit": 50}),
                    timeout=timeout_seconds
                )
                
                # Extract the Investigation Plan from the response
                if response["messages"]:
                    if isinstance(response["messages"], list):
                        final_message = response["messages"][-1].content
                    else:
                        final_message = response["messages"].content
                        
                    console.print(Panel(
                        f"[bold green]Investigation Plan generated via LangGraph![/bold green]",
                        title="[bold cyan]Plan Phase Complete",
                        border_style="green"
                    ))
                    
                    return final_message
                else:
                    logging.warning("Plan Phase: No response from LangGraph")
                    return plan_phase.generate_plan(pod_name, namespace, volume_path)
                    
            except Exception as e:
                logging.error(f"Plan Phase: Error in LangGraph execution: {str(e)}")
                # Fallback to direct generation
                return plan_phase.generate_plan(pod_name, namespace, volume_path)
        
    except Exception as e:
        error_msg = f"Plan Phase: Critical error: {str(e)}"
        logging.error(error_msg)
        console.print(Panel(
            f"[bold red]Plan Phase failed: {str(e)}[/bold red]\n"
            f"[yellow]Falling back to emergency plan generation[/yellow]",
            title="[bold red]Plan Phase Error",
            border_style="red"
        ))
        
        # Emergency fallback plan
        emergency_plan = f"""Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}  
Generated Steps: 2 emergency steps (error fallback)

Step 1: Get all available issues | Tool: kg_get_all_issues() | Expected: Any detectable issues in the system
Step 2: Get system summary | Tool: kg_get_summary() | Expected: Basic system health overview

Fallback Steps (if main steps fail):
Step F1: Print full Knowledge Graph | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Complete system visualization | Trigger: plan_phase_error
"""
        return emergency_plan
