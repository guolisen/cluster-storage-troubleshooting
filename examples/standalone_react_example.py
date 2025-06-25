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
    
    # Prepare initial state
    logger.info("Preparing initial state")
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
