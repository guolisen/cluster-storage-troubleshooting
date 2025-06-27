#!/usr/bin/env python3
"""
Test script for the Plan Phase ReAct graph implementation.

This script demonstrates how to use the ReAct graph implementation for the plan phase
of the Kubernetes volume troubleshooting system.
"""

import asyncio
import logging
import yaml
import json
import sys
import os
from langchain_core.messages import SystemMessage, HumanMessage

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_graph import KnowledgeGraph
from phases.plan_phase_react import run_plan_phase_react, PlanPhaseReActGraph
from tests.mock_knowledge_graph import create_mock_knowledge_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_plan_phase_react.log')
    ]
)

logger = logging.getLogger(__name__)

async def test_plan_phase_react():
    """Test the Plan Phase ReAct graph implementation."""
    logger.info("Starting Plan Phase ReAct test")
    
    # Load configuration
    try:
        with open('config.yaml', 'r') as f:
            config_data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        config_data = {}
    
    # Ensure ReAct is enabled
    if 'plan_phase' not in config_data:
        config_data['plan_phase'] = {}
    config_data['plan_phase']['use_react'] = True
    
    # Create mock knowledge graph
    logger.info("Creating mock knowledge graph")
    knowledge_graph = create_mock_knowledge_graph()
    
    # Set test parameters
    pod_name = "test-pod"
    namespace = "default"
    volume_path = "/dev/sda"
    
    # Prepare messages for the ReAct graph
    logger.info("Preparing messages for the ReAct graph")
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
    
    # Run the ReAct graph
    logger.info(f"Running Plan Phase ReAct for {namespace}/{pod_name} volume {volume_path}")
    try:
        investigation_plan, message_list = await run_plan_phase_react(
            pod_name, namespace, volume_path, messages, config_data
        )
        
        # Log the results
        logger.info("Plan Phase ReAct completed successfully")
        logger.info(f"Investigation Plan:\n{investigation_plan}")
        
        # Save the investigation plan to a file
        with open('test_plan_phase_react_output.txt', 'w') as f:
            f.write(investigation_plan)
        
        # Save the message list to a file
        with open('test_plan_phase_react_messages.json', 'w') as f:
            json.dump(message_list, f, indent=2)
        
        logger.info("Test completed successfully")
        return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False

def print_usage():
    """Print usage information."""
    print("Usage: python test_plan_phase_react.py")
    print("This script tests the Plan Phase ReAct graph implementation.")

if __name__ == "__main__":
    print("Testing Plan Phase ReAct graph implementation")
    asyncio.run(test_plan_phase_react())
