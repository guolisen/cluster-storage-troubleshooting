#!/usr/bin/env python3
"""
Investigation Planner for Kubernetes Volume Troubleshooting

This module contains the InvestigationPlanner class that generates structured
Investigation Plans based on Knowledge Graph data and issue context.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from knowledge_graph import KnowledgeGraph

# Import modules for plan generation
from phases.kg_context_builder import KGContextBuilder
from phases.tool_registry_builder import ToolRegistryBuilder
from phases.llm_plan_generator import LLMPlanGenerator
from phases.rule_based_plan_generator import RuleBasedPlanGenerator
from phases.static_plan_step_reader import StaticPlanStepReader
from phases.utils import validate_knowledge_graph, generate_basic_fallback_plan, handle_exception

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
        validate_knowledge_graph(self.kg, self.__class__.__name__)
        
        # Initialize components
        self.kg_context_builder = KGContextBuilder(knowledge_graph)
        self.tool_registry_builder = ToolRegistryBuilder()
        self.llm_plan_generator = LLMPlanGenerator(config_data)
        self.rule_based_plan_generator = RuleBasedPlanGenerator(knowledge_graph)
        self.static_plan_step_reader = StaticPlanStepReader(config_data)
    
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
        self.logger.info(f"Generating investigation plan for {namespace} {pod_name} volume {volume_path}")
        
        try:
            # Generate the plan using the three-step process
            formatted_plan, updated_message_list = self._generate_plan_with_three_step_process(
                pod_name, namespace, volume_path, message_list
            )
            return formatted_plan, updated_message_list
            
        except Exception as e:
            error_msg = handle_exception("generate_investigation_plan", e, self.logger)
            fallback_plan = generate_basic_fallback_plan(pod_name, namespace, volume_path)
            
            # Update message list with fallback plan
            updated_message_list = self._update_message_list(message_list, fallback_plan)
            
            return fallback_plan, updated_message_list
    
    def _generate_plan_with_three_step_process(self, pod_name: str, namespace: str, volume_path: str, 
                                             message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
        """
        Generate a plan using the three-step process
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod  
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Formatted Investigation Plan, Updated message list)
        """
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
            # Refine with LLM
            return self._refine_plan_with_llm(draft_plan, pod_name, namespace, volume_path, 
                                            kg_context, message_list)
        else:
            # Format draft plan directly
            return self._format_draft_plan_with_message_list(draft_plan, pod_name, namespace, 
                                                          volume_path, message_list)
    
    def _refine_plan_with_llm(self, draft_plan: List[Dict[str, Any]], pod_name: str, namespace: str, 
                            volume_path: str, kg_context: Dict[str, Any], 
                            message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
        """
        Refine the plan using LLM
        
        Args:
            draft_plan: Draft plan from rule-based generator and static steps
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            kg_context: Knowledge Graph context
            message_list: Optional message list for chat mode
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Refined Investigation Plan, Updated message list)
        """
        self.logger.info("Step 3: Refining plan using LLM")
        
        # Prepare Phase1 tool registry
        phase1_tools = self.tool_registry_builder.prepare_tool_registry()
        
        # Generate final plan using LLM refinement
        return self.llm_plan_generator.refine_plan(
            draft_plan, pod_name, namespace, volume_path, kg_context, phase1_tools, message_list
        )
    
    def _format_draft_plan_with_message_list(self, draft_plan: List[Dict[str, Any]], pod_name: str, 
                                           namespace: str, volume_path: str,
                                           message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
        """
        Format the draft plan and update message list
        
        Args:
            draft_plan: Draft plan from rule-based generator and static steps
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            message_list: Optional message list for chat mode
            
        Returns:
            Tuple[str, List[Dict[str, str]]]: (Formatted Investigation Plan, Updated message list)
        """
        self.logger.info("LLM refinement disabled or unavailable, using draft plan")
        formatted_plan = self._format_draft_plan(draft_plan, pod_name, namespace, volume_path)
        
        # Update message list with formatted plan
        updated_message_list = self._update_message_list(message_list, formatted_plan)
        
        return formatted_plan, updated_message_list
    
    def _update_message_list(self, message_list: List[Dict[str, str]], plan: str) -> List[Dict[str, str]]:
        """
        Update message list with a new plan
        
        Args:
            message_list: Message list to update
            plan: Plan to add to the message list
            
        Returns:
            List[Dict[str, str]]: Updated message list
        """
        if message_list is None:
            return None
            
        # If the last message is from the user, append the assistant response
        if message_list[-1]["role"] == "user":
            message_list.append({"role": "assistant", "content": plan})
        else:
            # Replace the last message if it's from the assistant
            message_list[-1] = {"role": "assistant", "content": plan}
        
        return message_list
    
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
            step_line = self._format_step(step)
            plan_lines.append(step_line)
        
        return "\n".join(plan_lines)
    
    def _format_step(self, step: Dict[str, Any]) -> str:
        """
        Format a single investigation step
        
        Args:
            step: Step data
            
        Returns:
            str: Formatted step string
        """
        # Format arguments
        args_str = ', '.join(f'{k}={repr(v)}' for k, v in step.get('arguments', {}).items())
        
        # Format the step line
        return (
            f"Step {step['step']}: {step['description']} | "
            f"Tool: {step['tool']}({args_str}) | "
            f"Expected: {step['expected']}"
        )
