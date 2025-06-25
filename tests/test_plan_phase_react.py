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
    
    # Prepare collected info with knowledge graph
    collected_info = {'knowledge_graph': knowledge_graph}
    
    # Run the ReAct graph
    logger.info(f"Running Plan Phase ReAct for {namespace}/{pod_name} volume {volume_path}")
    try:
        investigation_plan, message_list = await run_plan_phase_react(
            pod_name, namespace, volume_path, collected_info, config_data
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
