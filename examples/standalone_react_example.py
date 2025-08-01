#!/usr/bin/env python3
"""
Standalone example of using the Plan Phase ReAct graph directly.

This script demonstrates how to use the Plan Phase ReAct graph implementation
in a standalone manner, without going through the full troubleshooting system.
"""

import asyncio
import logging
import yaml
import json
import sys
import os
from typing import Dict, List, Any
from langchain_core.messages import SystemMessage, HumanMessage

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_graph import KnowledgeGraph
from phases.plan_phase_react import PlanPhaseReActGraph
from tests.mock_knowledge_graph import create_mock_knowledge_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('standalone_react_example.log')
    ]
)

logger = logging.getLogger(__name__)

async def run_standalone_react_example():
    """Run a standalone example of the Plan Phase ReAct graph."""
    logger.info("Starting standalone ReAct graph example")
    
    # Load configuration
    try:
        with open('config.yaml', 'r') as f:
            config_data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        config_data = {}
    
    # Create mock knowledge graph
    logger.info("Creating mock knowledge graph")
    knowledge_graph = create_mock_knowledge_graph()
    
    # Set test parameters
    pod_name = "example-pod"
    namespace = "default"
    volume_path = "/dev/sda"
    
    # Initialize the ReAct graph
    logger.info("Initializing ReAct graph")
    react_graph = PlanPhaseReActGraph(config_data)
    
    # Build the graph
    logger.info("Building ReAct graph")
    graph = react_graph.build_graph()
    
    # Prepare initial messages
    logger.info("Preparing initial messages")
    # Create system message with instructions for ReAct
    system_prompt = """You are an AI assistant tasked with generating an Investigation Plan for troubleshooting Kubernetes volume I/O errors.
You are operating in a ReAct (Reasoning and Acting) framework where you can:
1. REASON about the problem and identify knowledge gaps
2. ACT by calling external tools to gather information
3. OBSERVE the results and update your understanding
4. Continue this loop until you have enough information to create a comprehensive plan

Your goal is to create a detailed Investigation Plan that identifies potential problems and provides specific steps to diagnose and resolve volume read/write errors.

When you identify a knowledge gap, use the appropriate MCP tool to gather the information you need. Don't guess or make assumptions when you can use a tool to get accurate information.

When you've completed the Investigation Plan, include the marker [END_GRAPH] at the end of your message.
"""
    
    # Create user message with context
    kg_summary = knowledge_graph.get_summary() if knowledge_graph else {}
    issues = knowledge_graph.get_all_issues() if knowledge_graph else []
    
    kg_context = f"""
Knowledge Graph Summary:
{json.dumps(kg_summary, indent=2)}

Issues:
{json.dumps(issues, indent=2)}
"""
    
    user_prompt = f"""# INVESTIGATION PLAN GENERATION TASK
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
    
    # Create message list
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    # Prepare initial state
    logger.info("Preparing initial state")
    initial_state = {
        "messages": messages,
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
    logger.info("Running ReAct graph")
    try:
        final_state = graph.invoke(initial_state)
        
        # Extract the investigation plan
        investigation_plan = react_graph.extract_plan_from_state(final_state)
        
        # Log the results
        logger.info("ReAct graph execution completed successfully")
        logger.info(f"Investigation Plan:\n{investigation_plan}")
        
        # Print statistics
        logger.info(f"Iterations: {final_state['iteration_count']}")
        logger.info(f"Tool calls: {final_state['tool_call_count']}")
        logger.info(f"Knowledge gathered: {len(final_state['knowledge_gathered'])}")
        
        # Save the investigation plan to a file
        with open('standalone_react_example_output.txt', 'w') as f:
            f.write(investigation_plan)
        
        # Save the final state to a file
        with open('standalone_react_example_state.json', 'w') as f:
            # Convert messages to a serializable format
            serializable_state = final_state.copy()
            serializable_state['messages'] = [
                {
                    'role': msg.type if hasattr(msg, 'type') else 'unknown',
                    'content': msg.content if hasattr(msg, 'content') else str(msg)
                }
                for msg in final_state['messages']
            ]
            serializable_state['knowledge_graph'] = 'KnowledgeGraph instance (not serializable)'
            json.dump(serializable_state, f, indent=2)
        
        logger.info("Example completed successfully")
        return True
    except Exception as e:
        logger.error(f"Example failed: {e}")
        return False

def print_usage():
    """Print usage information."""
    print("Usage: python standalone_react_example.py")
    print("This script demonstrates how to use the Plan Phase ReAct graph in a standalone manner.")

if __name__ == "__main__":
    print("Standalone ReAct Graph Example")
    print("==============================")
    print("This example demonstrates how to use the Plan Phase ReAct graph directly,")
    print("without going through the full troubleshooting system.")
    print()
    
    # Create examples directory if it doesn't exist
    os.makedirs('examples', exist_ok=True)
    
    asyncio.run(run_standalone_react_example())
