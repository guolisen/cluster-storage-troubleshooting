#!/usr/bin/env python3
"""
Test script for the refactored Plan Phase

This script tests the refactored Plan Phase with the three-step process:
1. Rule-based preliminary steps
2. Static plan steps integration
3. LLM refinement
"""

import logging
import json
import os
import sys
import yaml
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from knowledge_graph.knowledge_graph import KnowledgeGraph
from phases.rule_based_plan_generator import RuleBasedPlanGenerator
from phases.static_plan_step_reader import StaticPlanStepReader
from phases.llm_plan_generator import LLMPlanGenerator
from phases.investigation_planner import InvestigationPlanner
from phases.tool_registry_builder import ToolRegistryBuilder

def load_config() -> Dict[str, Any]:
    """Load configuration from config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        return {}

def load_historical_experience() -> List[Dict[str, Any]]:
    """Load historical experience data"""
    try:
        with open('historical_experience.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading historical experience: {str(e)}")
        return []

def create_mock_knowledge_graph() -> KnowledgeGraph:
    """Create a mock Knowledge Graph for testing"""
    # Create a basic KnowledgeGraph instance
    kg = KnowledgeGraph()
    
    # Add some nodes
    kg.add_node(
        node_id="pod:app-1",
        node_type="pod",
        attributes={
            "name": "app-1",
            "namespace": "default",
            "status": "Running",
            "volume_mounts": ["/data"]
        }
    )
    
    kg.add_node(
        node_id="pvc:data-pvc",
        node_type="pvc",
        attributes={
            "name": "data-pvc",
            "namespace": "default",
            "status": "Bound"
        }
    )
    
    kg.add_node(
        node_id="node:node-1",
        node_type="node",
        attributes={
            "name": "node-1",
            "status": "Ready"
        }
    )
    
    kg.add_node(
        node_id="drive:disk1",
        node_type="drive",
        attributes={
            "name": "disk1",
            "node": "node-1",
            "health": "warning"
        }
    )
    
    kg.add_node(
        node_id="log:log1",
        node_type="log",
        attributes={
            "timestamp": "2025-05-31T20:55:00",
            "message": "I/O error on volume for pod 'app-1'"
        }
    )
    
    # Add relationships
    kg.add_relationship(
        source_id="pod:app-1",
        target_id="pvc:data-pvc",
        relationship_type="uses"
    )
    
    kg.add_relationship(
        source_id="pvc:data-pvc",
        target_id="drive:disk1",
        relationship_type="stored_on"
    )
    
    kg.add_relationship(
        source_id="drive:disk1",
        target_id="node:node-1",
        relationship_type="attached_to"
    )
    
    kg.add_relationship(
        source_id="log:log1",
        target_id="pod:app-1",
        relationship_type="affects"
    )
    
    # Add some issues
    kg.add_issue(
        node_id="drive:disk1",
        issue_type="disk_health",
        severity="critical",
        description="Disk showing SMART errors",
        timestamp="2025-05-31T20:50:00"
    )
    
    kg.add_issue(
        node_id="pod:app-1",
        issue_type="volume_io",
        severity="high",
        description="Volume I/O errors detected",
        timestamp="2025-05-31T20:55:00"
    )
    
    return kg

def test_rule_based_generator(config_data: Dict[str, Any], kg: KnowledgeGraph, historical_experience: List[Dict[str, Any]]):
    """Test the rule-based preliminary steps generation"""
    logger.info("\n==== Testing Rule-Based Plan Generator ====")
    
    # Create rule-based plan generator
    rule_generator = RuleBasedPlanGenerator(kg)
    
    # Mock data for generation
    pod_name = "app-1"
    namespace = "default"
    volume_path = "/data"
    target_entities = {
        "pod": "pod:app-1",
        "drive": "drive:disk1",
        "node": "node:node-1"
    }
    
    # Mock issues analysis
    issues_analysis = {
        "by_severity": {
            "critical": [
                {
                    "node_id": "drive:disk1",
                    "issue_type": "disk_health",
                    "severity": "critical",
                    "description": "Disk showing SMART errors"
                }
            ],
            "high": [
                {
                    "node_id": "pod:app-1",
                    "issue_type": "volume_io",
                    "severity": "high",
                    "description": "Volume I/O errors detected"
                }
            ],
            "medium": [],
            "low": []
        }
    }
    
    # Generate preliminary steps
    preliminary_steps = rule_generator.generate_preliminary_steps(
        pod_name, namespace, volume_path, target_entities, issues_analysis, historical_experience
    )
    
    # Print the result
    logger.info(f"Generated {len(preliminary_steps)} preliminary steps:")
    for step in preliminary_steps:
        logger.info(f"  Step {step['step']}: {step['description']}")
    
    return preliminary_steps

def test_static_plan_step_reader(config_data: Dict[str, Any], preliminary_steps: List[Dict[str, Any]]):
    """Test the static plan step reader and integration"""
    logger.info("\n==== Testing Static Plan Step Reader ====")
    
    # Create static plan step reader
    static_reader = StaticPlanStepReader(config_data)
    
    # Read static steps and add to preliminary steps
    draft_plan = static_reader.add_static_steps(preliminary_steps)
    
    # Print the result
    logger.info(f"Added static steps, draft plan now has {len(draft_plan)} steps:")
    for step in draft_plan:
        source = "rule-based" if step.get('source') != 'static' else "static"
        logger.info(f"  Step {step['step']}: {step['description']} (Source: {source})")
    
    return draft_plan

def test_llm_refinement(config_data: Dict[str, Any], draft_plan: List[Dict[str, Any]], kg: KnowledgeGraph, historical_experience: List[Dict[str, Any]]):
    """Test the LLM refinement process"""
    logger.info("\n==== Testing LLM Refinement ====")
    
    # Skip if LLM is disabled
    if not config_data.get('plan_phase', {}).get('use_llm', True):
        logger.info("LLM refinement is disabled in config, skipping test")
        return None
    
    # Create LLM plan generator
    llm_generator = LLMPlanGenerator(config_data)
    
    # Skip if LLM initialization failed
    if not llm_generator.llm:
        logger.info("LLM initialization failed, skipping test")
        return None
    
    # Prepare tool registry
    tool_registry_builder = ToolRegistryBuilder()
    phase1_tools = tool_registry_builder.prepare_tool_registry()
    
    # Prepare KG context
    kg_context = {
        "nodes": kg.graph.nodes(data=True),
        "edges": list(kg.graph.edges(data=True)),
        "issues": kg.get_all_issues(),
        "historical_experiences": historical_experience
    }
    
    # Mock data
    pod_name = "app-1"
    namespace = "default"
    volume_path = "/data"
    
    # Refine plan using LLM
    refined_plan = llm_generator.refine_plan(
        draft_plan, pod_name, namespace, volume_path, kg_context, phase1_tools
    )
    
    # Print the result
    logger.info("LLM refined plan:")
    logger.info(refined_plan)
    
    return refined_plan

def test_investigation_planner(config_data: Dict[str, Any], kg: KnowledgeGraph):
    """Test the full Investigation Planner with the three-step process"""
    logger.info("\n==== Testing Complete Investigation Planner ====")
    
    # Create Investigation Planner
    planner = InvestigationPlanner(kg, config_data)
    
    # Generate plan
    pod_name = "app-1"
    namespace = "default"
    volume_path = "/data"
    
    investigation_plan = planner.generate_investigation_plan(pod_name, namespace, volume_path)
    
    # Print the result
    logger.info("Final Investigation Plan:")
    logger.info(investigation_plan)
    
    return investigation_plan

def main():
    """Main test function"""
    logger.info("Starting Plan Phase tests")
    
    # Load configuration
    config_data = load_config()
    
    # Load historical experience
    historical_experience = load_historical_experience()
    
    # Create mock Knowledge Graph
    kg = create_mock_knowledge_graph()
    
    # Test rule-based generator
    preliminary_steps = test_rule_based_generator(config_data, kg, historical_experience)
    
    # Test static plan step reader
    draft_plan = test_static_plan_step_reader(config_data, preliminary_steps)
    
    # Test LLM refinement
    refined_plan = test_llm_refinement(config_data, draft_plan, kg, historical_experience)
    
    # Test full investigation planner
    final_plan = test_investigation_planner(config_data, kg)
    
    logger.info("Plan Phase tests completed")

if __name__ == "__main__":
    main()
