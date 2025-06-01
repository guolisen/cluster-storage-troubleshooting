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
from phases.static_plan_step_reader import StaticPlanStepReader

logger = logging.getLogger(__name__)

class InvestigationPlanner:
    """
    Generates Investigation Plans based on Knowledge Graph analysis
    
    The Investigation Planner follows a three-step process to create a structured
    step-by-step investigation plan that Phase 1 can follow to efficiently
    diagnose volume I/O issues:
    1. Rule-based preliminary steps - Generate critical initial investigation steps
    2. Static plan steps integration - Add mandatory steps from static_plan_step.json
    3. LLM refinement - Refine and supplement the plan using LLM without tool invocation
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
        self.static_plan_step_reader = StaticPlanStepReader(config_data)
    
    def generate_investigation_plan(self, pod_name: str, namespace: str, volume_path: str) -> str:
        """
        Generate a comprehensive Investigation Plan using the three-step process
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod  
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: Formatted Investigation Plan with step-by-step actions
        """
        self.logger.info(f"Generating investigation plan for {namespace}/{pod_name} volume {volume_path}")
        
        try:
            # Prepare Knowledge Graph context and extract necessary data
            kg_context = self.kg_context_builder.prepare_kg_context(pod_name, namespace, volume_path)
            issues_analysis = self.kg_context_builder.analyze_existing_issues()
            target_entities = self.kg_context_builder.identify_target_entities(pod_name, namespace)
            historical_experience = kg_context.get('historical_experiences', [])
            
            # Step 1: Generate preliminary steps using rule-based approach
            self.logger.info("Step 1: Generating rule-based preliminary steps")
            preliminary_steps = self.rule_based_plan_generator.generate_preliminary_steps(
                pod_name, namespace, volume_path, target_entities, issues_analysis, historical_experience
            )
            
            # Step 2: Add static plan steps
            self.logger.info("Step 2: Adding static plan steps")
            draft_plan = self.static_plan_step_reader.add_static_steps(preliminary_steps)
            
            # Step 3: Refine plan using LLM if enabled
            use_llm = self.config_data.get('plan_phase', {}).get('use_llm', True)
            
            if use_llm and self.llm_plan_generator.llm is not None:
                self.logger.info("Step 3: Refining plan using LLM")
                
                # Prepare Phase1 tool registry
                phase1_tools = self.tool_registry_builder.prepare_tool_registry()
                
                # Generate final plan using LLM refinement
                return self.llm_plan_generator.refine_plan(
                    draft_plan, pod_name, namespace, volume_path, kg_context, phase1_tools
                )
            else:
                # If LLM is not available, format the draft plan directly
                self.logger.info("LLM refinement disabled or unavailable, using draft plan")
                return self._format_draft_plan(draft_plan, pod_name, namespace, volume_path)
            
        except Exception as e:
            self.logger.error(f"Error generating investigation plan: {str(e)}")
            return self._generate_basic_fallback_plan(pod_name, namespace, volume_path)
    
    def _format_draft_plan(self, draft_plan: List[Dict[str, Any]], pod_name: str, namespace: str, volume_path: str) -> str:
        """
        Format the draft plan into a structured Investigation Plan string
        
        Args:
            draft_plan: Draft plan from rule-based generator and static steps
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            str: Formatted Investigation Plan
        """
        plan_lines = []
        plan_lines.append("Investigation Plan:")
        plan_lines.append(f"Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}")
        plan_lines.append(f"Generated Steps: {len(draft_plan)} main steps, 0 fallback steps")
        plan_lines.append("")
        
        # Format main investigation steps
        for step in draft_plan:
            step_line = (
                f"Step {step['step']}: {step['description']} | "
                f"Tool: {step['tool']}({', '.join(f'{k}={repr(v)}' for k, v in step.get('arguments', {}).items())}) | "
                f"Expected: {step['expected_outcome']}"
            )
            plan_lines.append(step_line)
        
        return "\n".join(plan_lines)
    
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
