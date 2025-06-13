#!/usr/bin/env python3
"""
Test script to demonstrate adding a system hardware entity to Knowledge Graph in phase0.

This script shows how to collect system hardware information and add it to the
Knowledge Graph, including calling tools like get_system_hardware_info() and other
system diagnostic tools.
"""

import asyncio
import logging
from knowledge_graph.knowledge_graph import KnowledgeGraph
from information_collector.knowledge_builder import KnowledgeBuilder
from information_collector.base import InformationCollectorBase
import json

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestCollector(InformationCollectorBase, KnowledgeBuilder):
    """Test implementation of the Information Collector with Knowledge Builder capabilities"""
    
    def __init__(self, config=None):
        """Initialize the test collector with minimal configuration"""
        self.knowledge_graph = KnowledgeGraph()
        self.collected_data = {
            'node_names': ['localhost'],  # Use localhost for testing
            'errors': []
        }
        self.config = config or {}

async def main():
    """Main test function to demonstrate adding a system hardware entity to the Knowledge Graph"""
    logger.info("Starting test for adding system hardware entity to Knowledge Graph...")
    
    # Create test collector
    collector = TestCollector()
    
    # Build the knowledge graph
    # This will call _add_system_entities() which now includes _add_hardware_system_entity()
    kg = await collector._build_knowledge_graph_from_tools()
    
    # Print summary of the knowledge graph
    summary = kg.get_summary()
    logger.info(f"Knowledge Graph built: {summary['total_nodes']} nodes, "
               f"{summary['total_edges']} edges, {summary['total_issues']} issues")
    
    # Check if hardware system entity exists
    system_nodes = kg.find_nodes_by_type('System')
    hardware_nodes = [node for node in system_nodes 
                     if kg.graph.nodes[node].get('name') == 'hardware']
    
    if hardware_nodes:
        logger.info("Hardware system entity successfully added to Knowledge Graph!")
        
        # Print hardware entity details
        hardware_id = hardware_nodes[0]
        hardware_data = kg.graph.nodes[hardware_id]
        
        logger.info(f"Hardware system entity ID: {hardware_id}")
        logger.info(f"Hardware system entity description: {hardware_data.get('description')}")
        
        # Get issues related to hardware
        issues = [issue for issue in kg.issues if issue['node_id'] == hardware_id]
        logger.info(f"Found {len(issues)} hardware-related issues")
        
        # Print issues
        for i, issue in enumerate(issues):
            logger.info(f"Issue {i+1}: {issue['severity']} - {issue['description']}")
        
        # Print connections to nodes
        connected_nodes = kg.find_connected_nodes(hardware_id)
        logger.info(f"Hardware entity is connected to {len(connected_nodes)} other nodes")
    else:
        logger.error("Hardware system entity was not added to Knowledge Graph!")
    
    # Print the formatted knowledge graph
    print(kg.print_graph())
    
    return kg

if __name__ == "__main__":
    # Run the test
    kg = asyncio.run(main())
    
    # Save knowledge graph
    kg_summary = {
        "entities": {entity_type: len(kg.find_nodes_by_type(entity_type))
                   for entity_type in ['System', 'Node', 'Drive', 'Pod', 'PVC', 'PV']},
        "relationships": kg.graph.number_of_edges(),
        "issues": len(kg.issues)
    }
    
    # Save summary as JSON
    with open('hardware_entity_test_results.json', 'w') as f:
        json.dump(kg_summary, f, indent=2)
    
    print("Test completed. Results saved to hardware_entity_test_results.json")
