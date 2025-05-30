#!/usr/bin/env python3
"""
Investigation Planner for Kubernetes Volume Troubleshooting

This module contains the InvestigationPlanner class that generates structured
Investigation Plans based on Knowledge Graph data and issue context.
"""

import logging
from typing import Dict, List, Any, Optional
from knowledge_graph import KnowledgeGraph

# Import modules for plan generation
from phases.kg_context_builder import KGContextBuilder
from phases.tool_registry_builder import ToolRegistryBuilder
from phases.llm_plan_generator import LLMPlanGenerator
from phases.rule_based_plan_generator import RuleBasedPlanGenerator

logger = logging.getLogger(__name__)

class InvestigationPlanner:
    """
    Generates Investigation Plans based on Knowledge Graph analysis
    
    The Investigation Planner analyzes the Knowledge Graph to create a structured
    step-by-step investigation plan that Phase 1 can follow to efficiently
    diagnose volume I/O issues.
    """
    
    def __init__(self, knowledge_graph, config_data: Dict[str, Any] = None):
        """
        Initialize the Investigation Planner
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
            config_data: Configuration data for the system (optional)
        """
        self.kg = knowledge_graph
        self.config_data = config_data or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Validate knowledge_graph is a KnowledgeGraph instance
        if not hasattr(self.kg, 'graph'):
            self.logger.error(f"Invalid Knowledge Graph: missing 'graph' attribute")
            raise ValueError(f"Invalid Knowledge Graph: missing 'graph' attribute")
        
        if not hasattr(self.kg, 'get_all_issues'):
            self.logger.error(f"Invalid Knowledge Graph: missing 'get_all_issues' method")
            raise ValueError(f"Invalid Knowledge Graph: missing 'get_all_issues' method")
        
        # Initialize components
        self.kg_context_builder = KGContextBuilder(knowledge_graph)
        self.tool_registry_builder = ToolRegistryBuilder()
        self.llm_plan_generator = LLMPlanGenerator(config_data)
        self.rule_based_plan_generator = RuleBasedPlanGenerator(knowledge_graph)
    
    def generate_investigation_plan(self, pod_name: str, namespace: str, volume_path: str) -> str:
        """
        Generate a comprehensive Investigation Plan based on Knowledge Graph analysis
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod  
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: Formatted Investigation Plan with step-by-step actions
        """
        self.logger.info(f"Generating investigation plan for {namespace}/{pod_name} volume {volume_path}")
        
        try:
            # Check if LLM-based generation should be used
            use_llm = self.config_data.get('plan_phase', {}).get('use_llm', True)
            
            if use_llm and self.llm_plan_generator.llm is not None:
                self.logger.info("Using LLM-based plan generation")
                
                # Prepare Knowledge Graph context
                kg_context = self.kg_context_builder.prepare_kg_context(pod_name, namespace, volume_path)
                
                # Prepare tool registry
                tool_registry = self.tool_registry_builder.prepare_tool_registry()
                
                # Generate plan using LLM
                return self.llm_plan_generator.generate_plan(
                    pod_name, namespace, volume_path, kg_context, tool_registry
                )
            else:
                self.logger.info("Using rule-based plan generation")
                
                # Analyze existing issues
                issues_analysis = self.kg_context_builder.analyze_existing_issues()
                
                # Identify target entities
                target_entities = self.kg_context_builder.identify_target_entities(pod_name, namespace)
                
                # Generate plan using rule-based approach
                return self.rule_based_plan_generator.generate_plan(
                    pod_name, namespace, volume_path, target_entities, issues_analysis
                )
            
        except Exception as e:
            self.logger.error(f"Error generating investigation plan: {str(e)}")
            return self._generate_basic_fallback_plan(pod_name, namespace, volume_path)
    
    def _generate_basic_fallback_plan(self, pod_name: str, namespace: str, volume_path: str) -> str:
        """
        Generate a basic fallback plan when all else fails
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: Basic fallback Investigation Plan
        """
        basic_plan = f"""Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}
Generated Steps: 4 basic steps (fallback mode)

Step 1: Get all critical issues from Knowledge Graph | Tool: kg_get_all_issues(severity='critical') | Expected: List of critical issues affecting the system
Step 2: Analyze existing issues and patterns | Tool: kg_analyze_issues() | Expected: Root cause analysis and issue relationships  
Step 3: Get system overview | Tool: kg_get_summary() | Expected: Overall system health and entity statistics
Step 4: Print complete Knowledge Graph for manual analysis | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Full system visualization for troubleshooting

Fallback Steps (if main steps fail):
Step F1: Search for any Pod entities | Tool: kg_get_related_entities(entity_type='Pod', entity_id='any', max_depth=1) | Expected: List of all Pods | Trigger: entity_not_found
Step F2: Search for any Drive entities | Tool: kg_get_related_entities(entity_type='Drive', entity_id='any', max_depth=1) | Expected: List of all Drives | Trigger: no_target_found
"""
        return basic_plan
