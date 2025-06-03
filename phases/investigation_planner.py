#!/usr/bin/env python3
"""
Investigation Planner for Kubernetes Volume Troubleshooting

This module contains the InvestigationPlanner class that generates structured
Investigation Plans based on Knowledge Graph data and issue context.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from knowledge_graph import KnowledgeGraph

# Import modules for plan generation
from phases.kg_context_builder import KGContextBuilder
from phases.tool_registry_builder import ToolRegistryBuilder
from phases.llm_plan_generator import LLMPlanGenerator
from phases.rule_based_plan_generator import RuleBasedPlanGenerator
from phases.static_plan_step_reader import StaticPlanStepReader
from troubleshooting.utils import (
    FallbackPlanGenerator,
    ErrorHandler,
    MessageListManager
)

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
        
        # Validate knowledge graph
        self._validate_knowledge_graph()
        
        # Initialize components
        self._initialize_components()
    
    def _validate_knowledge_graph(self) -> None:
        """
        Validate that the knowledge graph has the required attributes and methods
        
        Raises:
            ValueError: If the knowledge graph is invalid
        """
        # Check for required attributes
        if not hasattr(self.kg, 'graph'):
            error_msg = "Invalid Knowledge Graph: missing 'graph' attribute"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Check for required methods
        required_methods = ['get_all_issues', 'get_entity_info', 'get_related_entities']
        for method in required_methods:
            if not hasattr(self.kg, method):
                error_msg = f"Invalid Knowledge Graph: missing '{method}' method"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
    
    def _initialize_components(self) -> None:
        """
        Initialize the components used by the Investigation Planner
        """
        self.kg_context_builder = KGContextBuilder(self.kg)
        self.tool_registry_builder = ToolRegistryBuilder()
        self.llm_plan_generator = LLMPlanGenerator(self.config_data)
        self.rule_based_plan_generator = RuleBasedPlanGenerator(self.kg)
        self.static_plan_step_reader = StaticPlanStepReader(self.config_data)
    
    def generate_investigation_plan(self, pod_name: str, namespace: str, volume_path: str, 
                                  message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
        """
        Generate a comprehensive Investigation Plan using the three-step process
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod  
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Formatted Investigation Plan with step-by-step actions, Updated message list)
        """
        self.logger.info(f"Generating investigation plan for {namespace}/{pod_name} volume {volume_path}")
        
        try:
            # Step 1: Prepare Knowledge Graph context
            kg_context = self._prepare_knowledge_graph_context(pod_name, namespace, volume_path)
            
            # Step 2: Generate draft plan (rule-based + static steps)
            draft_plan = self._generate_draft_plan(pod_name, namespace, volume_path, kg_context)
            
            # Step 3: Refine plan using LLM if enabled
            return self._refine_plan_with_llm(
                draft_plan, pod_name, namespace, volume_path, kg_context, message_list
            )
            
        except Exception as exception:
            return self._handle_plan_generation_error(
                exception, pod_name, namespace, volume_path, message_list
            )
    
    def _prepare_knowledge_graph_context(self, pod_name: str, namespace: str, volume_path: str) -> Dict[str, Any]:
        """
        Prepare Knowledge Graph context and extract necessary data
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            Dict[str, Any]: Knowledge Graph context with issues analysis and target entities
        """
        self.logger.info("Preparing Knowledge Graph context")
        
        try:
            # Get basic context from KG context builder
            kg_context = self.kg_context_builder.prepare_kg_context(pod_name, namespace, volume_path)
            
            # Add additional analysis data
            kg_context['issues_analysis'] = self.kg_context_builder.analyze_existing_issues()
            kg_context['target_entities'] = self.kg_context_builder.identify_target_entities(pod_name, namespace)
            
            return kg_context
            
        except Exception as exception:
            self.logger.error(f"Error preparing Knowledge Graph context: {str(exception)}")
            # Return minimal context to allow fallback plan generation
            return {
                'issues_analysis': {},
                'target_entities': {},
                'historical_experiences': []
            }
    
    def _generate_draft_plan(self, pod_name: str, namespace: str, volume_path: str, 
                           kg_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate a draft plan using rule-based approach and static steps
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            kg_context: Knowledge Graph context with issues analysis and target entities
            
        Returns:
            List[Dict[str, Any]]: Draft plan with preliminary and static steps
        """
        # Extract necessary data from kg_context
        issues_analysis = kg_context.get('issues_analysis', {})
        target_entities = kg_context.get('target_entities', {})
        historical_experience = kg_context.get('historical_experiences', [])
        
        # Step 1: Generate preliminary steps using rule-based approach
        self.logger.info("Step 1: Generating rule-based preliminary steps")
        preliminary_steps = self.rule_based_plan_generator.generate_preliminary_steps(
            pod_name, namespace, volume_path, target_entities, issues_analysis, historical_experience
        )
        
        # Step 2: Add static plan steps
        self.logger.info("Step 2: Adding static plan steps")
        draft_plan = self.static_plan_step_reader.add_static_steps(preliminary_steps)
        
        return draft_plan
    
    def _refine_plan_with_llm(self, draft_plan: List[Dict[str, Any]], pod_name: str, 
                            namespace: str, volume_path: str, kg_context: Dict[str, Any],
                            message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
        """
        Refine the draft plan using LLM if enabled
        
        Args:
            draft_plan: Draft plan from rule-based generator and static steps
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            kg_context: Knowledge Graph context with issues analysis and target entities
            message_list: Optional message list for chat mode
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Formatted Investigation Plan, Updated message list)
        """
        # Check if LLM refinement is enabled
        use_llm = self.config_data.get('plan_phase', {}).get('use_llm', True)
        
        if use_llm and self.llm_plan_generator.llm is not None:
            self.logger.info("Step 3: Refining plan using LLM")
            
            # Prepare Phase1 tool registry
            phase1_tools = self.tool_registry_builder.prepare_tool_registry()
            
            # Generate final plan using LLM refinement
            return self.llm_plan_generator.refine_plan(
                draft_plan, pod_name, namespace, volume_path, kg_context, phase1_tools, message_list
            )
        else:
            # If LLM is not available, format the draft plan directly
            self.logger.info("LLM refinement disabled or unavailable, using draft plan")
            formatted_plan = self._format_draft_plan(draft_plan, pod_name, namespace, volume_path)
            
            # Add formatted plan to message list if provided
            if message_list is not None:
                message_list = MessageListManager.add_to_message_list(message_list, formatted_plan)
            
            return formatted_plan, message_list
    
    def _format_draft_plan(self, draft_plan: List[Dict[str, Any]], pod_name: str, 
                         namespace: str, volume_path: str) -> str:
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
            # Format arguments as string
            formatted_args = self._format_step_arguments(step.get('arguments', {}))
            
            step_line = (
                f"Step {step['step']}: {step['description']} | "
                f"Tool: {step['tool']}({formatted_args}) | "
                f"Expected: {step['expected']}"
            )
            plan_lines.append(step_line)
        
        return "\n".join(plan_lines)
    
    def _format_step_arguments(self, arguments: Dict[str, Any]) -> str:
        """
        Format step arguments as a string
        
        Args:
            arguments: Step arguments dictionary
            
        Returns:
            str: Formatted arguments string
        """
        # Format each argument as key=value
        formatted_args = []
        for key, value in arguments.items():
            if isinstance(value, str):
                # Add quotes for string values
                formatted_args.append(f"{key}='{value}'")
            else:
                # Use repr for non-string values
                formatted_args.append(f"{key}={repr(value)}")
        
        return ", ".join(formatted_args)
    
    def _handle_plan_generation_error(self, exception: Exception, pod_name: str, 
                                    namespace: str, volume_path: str,
                                    message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
        """
        Handle errors during plan generation
        
        Args:
            exception: Exception that occurred
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Fallback Investigation Plan, Updated message list)
        """
        error_msg = f"Error generating investigation plan: {str(exception)}"
        self.logger.error(error_msg)
        
        # Generate comprehensive fallback plan with error context
        fallback_plan = FallbackPlanGenerator.generate_comprehensive_fallback_plan(
            pod_name, namespace, volume_path, error_msg
        )
        
        # Add fallback plan to message list if provided
        if message_list is not None:
            message_list = MessageListManager.add_to_message_list(message_list, fallback_plan)
        
        return fallback_plan, message_list
