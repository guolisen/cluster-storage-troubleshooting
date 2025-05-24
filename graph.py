#!/usr/bin/env python3
"""
LangGraph Graph Building Components for Kubernetes Volume I/O Error Troubleshooting

This module contains functions for creating and configuring LangGraph state graphs
used in the analysis and remediation phases of Kubernetes volume troubleshooting.
"""

import json
import logging
from typing import Dict, List, Any

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.chat_models import init_chat_model


def create_troubleshooting_graph_with_context(collected_info: Dict[str, Any], phase: str = "analysis", config_data: Dict[str, Any] = None):
    """
    Create a LangGraph ReAct graph for troubleshooting with pre-collected context
    
    Args:
        collected_info: Pre-collected diagnostic information from Phase 0
        phase: Current troubleshooting phase ("analysis" or "remediation")
        config_data: Configuration data
        
    Returns:
        StateGraph: LangGraph StateGraph
    """
    if config_data is None:
        raise ValueError("Configuration data is required")
    
    # Initialize language model
    model = init_chat_model(
        config_data['llm']['model'],
        api_key=config_data['llm']['api_key'],
        base_url=config_data['llm']['api_endpoint'],
        temperature=config_data['llm']['temperature'],
        max_tokens=config_data['llm']['max_tokens']
    )
    
    # Define function to call the model with pre-collected context
    def call_model(state: MessagesState):
        # Add comprehensive system prompt with pre-collected context
        phase_specific_guidance = ""
        if phase == "analysis":
            phase_specific_guidance = """
You are currently in Phase 1 (Analysis). All diagnostic information has been pre-collected in Phase 0.
Your task is to:
1. Analyze the pre-collected diagnostic data provided in the context
2. Use the Knowledge Graph summary to understand relationships between entities
3. Identify patterns and root causes based on the collected information
4. Present your findings as a JSON object with "root_cause" and "fix_plan" keys
5. DO NOT attempt to execute any commands - all data is already provided

Focus on comprehensive analysis of the pre-collected data and Knowledge Graph relationships.
"""
        elif phase == "remediation":
            phase_specific_guidance = """
You are currently in Phase 2 (Remediation). Your task is to:
1. Execute the fix plan from Phase 1 using available tools
2. Respect command validation and interactive mode settings
3. Verify that issues are resolved after implementing fixes
4. Report final resolution status

Implement the fix plan safely and effectively while following security constraints.
"""
        
        # Prepare context from collected information
        context_summary = f"""
=== PRE-COLLECTED DIAGNOSTIC CONTEXT ===

Knowledge Graph Summary:
{json.dumps(collected_info.get('knowledge_graph_summary', {}), indent=2)}

Pod Information:
{collected_info.get('pod_info', {}).get('description', 'No pod information available')[:2000]}

PVC Information:
{str(collected_info.get('pvc_info', {}))[:2000]}

PV Information:
{str(collected_info.get('pv_info', {}))[:2000]}

Node Information Summary:
{str(collected_info.get('node_info', {}))[:2000]}

CSI Driver Information:
{str(collected_info.get('csi_driver_info', {}))[:2000]}

System Information:
{str(collected_info.get('system_info', {}))[:2000]}

=== END PRE-COLLECTED CONTEXT ===
"""
        
        system_message = {
            "role": "system", 
            "content": f"""You are an AI assistant powering an enhanced Kubernetes volume troubleshooting system. Your role is to analyze volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver (csi-baremetal.dell.com).

{phase_specific_guidance}

All diagnostic information has been pre-collected and is provided in the context below. Use this information to perform your analysis without needing to execute additional diagnostic commands.

{context_summary}

Follow these guidelines for analysis:

1. **Analysis Process**:
   - Review all pre-collected diagnostic information
   - Analyze the Knowledge Graph relationships to identify patterns
   - Look for common failure indicators: I/O errors, mount failures, permission issues, disk health problems
   - Correlate information across different components (Pod -> PVC -> PV -> Drive -> Node)

2. **Output Requirements**:
   - In Phase 1: Provide comprehensive analysis with JSON format containing "root_cause" and "fix_plan"
   - In Phase 2: Report remediation results and resolution status
   - Include performance benchmarks (HDD: 100-200 IOPS, SSD: thousands, NVMe: tens of thousands)
   - Always provide actionable recommendations

You must adhere to these guidelines to ensure effective troubleshooting of local disk issues in Kubernetes with the CSI Baremetal driver.
"""
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
        
        # Call the model (no tools needed for analysis phase since all data is pre-collected)
        if phase == "analysis":
            response = model.invoke(state["messages"])
        else:
            # For remediation phase, we might need tools
            from tools import define_remediation_tools
            tools = define_remediation_tools()
            response = model.bind_tools(tools).invoke(state["messages"])
        
        return {"messages": state["messages"] + [response]}
    
    # Build state graph
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    
    if phase == "remediation":
        # Add tools for remediation phase
        from tools import define_remediation_tools
        tools = define_remediation_tools()
        builder.add_node("tools", ToolNode(tools))
        builder.add_conditional_edges(
            "call_model",
            tools_condition,
            {
                "tools": "tools",
                "none": END
            }
        )
        builder.add_edge("tools", "call_model")
    
    builder.add_edge(START, "call_model")
    if phase == "analysis":
        builder.add_edge("call_model", END)
    
    graph = builder.compile()
    return graph
