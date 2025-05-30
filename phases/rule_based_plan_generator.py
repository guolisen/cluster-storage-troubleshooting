#!/usr/bin/env python3
"""
Rule-based Plan Generator for Investigation Planning

This module contains utilities for generating investigation plans using rule-based approaches.
"""

import logging
from typing import Dict, List, Any, Set
from knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

class RuleBasedPlanGenerator:
    """
    Generates Investigation Plans using rule-based approaches
    
    Uses predefined rules to analyze Knowledge Graph data and generate
    step-by-step investigation plans.
    """
    
    def __init__(self, knowledge_graph):
        """
        Initialize the Rule-based Plan Generator
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
        """
        self.kg = knowledge_graph
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Validate knowledge_graph is a KnowledgeGraph instance
        if not hasattr(self.kg, 'graph'):
            self.logger.error(f"Invalid Knowledge Graph: missing 'graph' attribute")
            raise ValueError(f"Invalid Knowledge Graph: missing 'graph' attribute")
        
        if not hasattr(self.kg, 'get_all_issues'):
            self.logger.error(f"Invalid Knowledge Graph: missing 'get_all_issues' method")
            raise ValueError(f"Invalid Knowledge Graph: missing 'get_all_issues' method")
    
    def generate_plan(self, pod_name: str, namespace: str, volume_path: str,
                     target_entities: Dict[str, str], issues_analysis: Dict[str, Any]) -> str:
        """
        Generate Investigation Plan using rule-based approach
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            target_entities: Dictionary of target entity IDs
            issues_analysis: Analysis of existing issues
            
        Returns:
            str: Formatted Investigation Plan
        """
        try:
            # Step 1: Determine investigation priority based on issue severity
            investigation_priority = self._determine_investigation_priority(issues_analysis, target_entities)
            
            # Step 2: Generate step-by-step plan
            plan_steps = self._generate_investigation_steps(
                target_entities, investigation_priority, issues_analysis, volume_path
            )
            
            # Step 3: Add fallback steps for incomplete data
            fallback_steps = self._generate_fallback_steps(target_entities)
            
            # Step 4: Format the final plan
            formatted_plan = self._format_investigation_plan(
                pod_name, namespace, volume_path, plan_steps, fallback_steps
            )
            
            return formatted_plan
            
        except Exception as e:
            self.logger.error(f"Error generating rule-based investigation plan: {str(e)}")
            return self._generate_basic_fallback_plan(pod_name, namespace, volume_path)
    
    def _determine_investigation_priority(self, issues_analysis: Dict[str, Any], 
                                        target_entities: Dict[str, str]) -> List[str]:
        """
        Determine investigation priority based on issue severity and target entities
        
        Args:
            issues_analysis: Analysis of existing issues
            target_entities: Dictionary of target entity IDs
            
        Returns:
            List[str]: Ordered list of investigation priorities
        """
        priorities = []
        
        # High priority: Critical issues affecting target entities
        target_entity_ids = set(target_entities.values())
        critical_issues_on_targets = [
            issue for issue in issues_analysis["by_severity"]["critical"]
            if issue.get('node_id') in target_entity_ids
        ]
        
        if critical_issues_on_targets:
            priorities.append("critical_target_issues")
        
        # Medium-high priority: Critical issues on any entities  
        if issues_analysis["by_severity"]["critical"]:
            priorities.append("critical_system_issues")
        
        # Medium priority: High severity issues on target entities
        high_issues_on_targets = [
            issue for issue in issues_analysis["by_severity"]["high"]
            if issue.get('node_id') in target_entity_ids
        ]
        
        if high_issues_on_targets:
            priorities.append("high_target_issues")
        
        # Lower priorities
        if issues_analysis["by_severity"]["high"]:
            priorities.append("high_system_issues")
        
        if issues_analysis["by_severity"]["medium"]:
            priorities.append("medium_issues")
        
        # Always include basic investigation
        priorities.append("basic_investigation")
        priorities.append("hardware_verification")
        
        return priorities
    
    def _generate_investigation_steps(self, target_entities: Dict[str, str], 
                                    priorities: List[str], issues_analysis: Dict[str, Any],
                                    volume_path: str) -> List[Dict[str, Any]]:
        """
        Generate detailed investigation steps based on priorities and entities
        
        Args:
            target_entities: Dictionary of target entity IDs
            priorities: List of investigation priorities  
            issues_analysis: Analysis of existing issues
            volume_path: Volume path with I/O error
            
        Returns:
            List[Dict[str, Any]]: List of investigation steps
        """
        steps = []
        step_number = 1
        
        # Step 1: Always start with comprehensive issue analysis
        steps.append({
            "step": step_number,
            "description": "Get all critical and high severity issues from Knowledge Graph",
            "tool": "kg_get_all_issues",
            "arguments": {"severity": "critical"},
            "expected_outcome": "List of critical issues that may be causing volume I/O errors",
            "priority": "critical",
            "category": "issue_analysis"
        })
        step_number += 1
        
        steps.append({
            "step": step_number,
            "description": "Analyze issue patterns and relationships to identify root causes",
            "tool": "kg_analyze_issues", 
            "arguments": {},
            "expected_outcome": "Root cause analysis with probability scores and relationship patterns",
            "priority": "critical",
            "category": "issue_analysis"
        })
        step_number += 1
        
        # Step 2-N: Priority-based investigation
        if "critical_target_issues" in priorities or "critical_system_issues" in priorities:
            steps.append({
                "step": step_number,
                "description": "Get high severity issues that may be related to the volume problem",
                "tool": "kg_get_all_issues",
                "arguments": {"severity": "high"},
                "expected_outcome": "High severity issues for comprehensive analysis",
                "priority": "high", 
                "category": "issue_analysis"
            })
            step_number += 1
        
        # Entity-specific investigation based on what we found
        if "pod" in target_entities:
            steps.append({
                "step": step_number,
                "description": f"Get detailed information about the problem pod and its current state",
                "tool": "kg_get_entity_info",
                "arguments": {"entity_type": "Pod", "entity_id": target_entities["pod"].split(":")[-1]},
                "expected_outcome": "Pod configuration, status, and any detected issues",
                "priority": "critical",
                "category": "entity_investigation"
            })
            step_number += 1
            
            steps.append({
                "step": step_number,
                "description": "Find all entities related to the problem pod (PVC, PV, Node, etc.)",
                "tool": "kg_get_related_entities",
                "arguments": {"entity_type": "Pod", "entity_id": target_entities["pod"].split(":")[-1], "max_depth": 2},
                "expected_outcome": "Complete dependency chain from Pod to underlying storage",
                "priority": "critical", 
                "category": "relationship_analysis"
            })
            step_number += 1
        
        # Drive and hardware investigation
        if "drive" in target_entities:
            steps.append({
                "step": step_number,
                "description": "Get detailed Drive information including health status and metrics",
                "tool": "kg_get_entity_info",
                "arguments": {"entity_type": "Drive", "entity_id": target_entities["drive"].split(":")[-1]},
                "expected_outcome": "Drive health status, SMART data, and any hardware issues",
                "priority": "high",
                "category": "hardware_investigation"
            })
            step_number += 1
        elif "hardware_verification" in priorities:
            # If no specific drive found, look for any drive issues
            steps.append({
                "step": step_number,
                "description": "Search for any Drive entities with health issues in the system",
                "tool": "kg_get_all_issues", 
                "arguments": {"issue_type": "disk_health"},
                "expected_outcome": "Any disk health issues that could affect volume I/O",
                "priority": "high",
                "category": "hardware_investigation"
            })
            step_number += 1
        
        # Node investigation
        if "node" in target_entities:
            steps.append({
                "step": step_number,
                "description": "Get Node information to check for node-level issues affecting storage",
                "tool": "kg_get_entity_info",
                "arguments": {"entity_type": "Node", "entity_id": target_entities["node"].split(":")[-1]},
                "expected_outcome": "Node health, resource usage, and any node-level storage issues",
                "priority": "high",
                "category": "infrastructure_investigation"
            })
            step_number += 1
        
        # Path analysis for dependency tracking
        if "pod" in target_entities and "drive" in target_entities:
            steps.append({
                "step": step_number,
                "description": "Trace the complete path from Pod to Drive to understand dependencies",
                "tool": "kg_find_path",
                "arguments": {
                    "source_entity_type": "Pod", 
                    "source_entity_id": target_entities["pod"].split(":")[-1],
                    "target_entity_type": "Drive",
                    "target_entity_id": target_entities["drive"].split(":")[-1]
                },
                "expected_outcome": "Complete dependency chain with relationship details",
                "priority": "medium",
                "category": "relationship_analysis"
            })
            step_number += 1
        
        # System overview
        steps.append({
            "step": step_number,
            "description": "Get overall Knowledge Graph summary for system health context",
            "tool": "kg_get_summary",
            "arguments": {},
            "expected_outcome": "System overview with entity counts and issue statistics",
            "priority": "low",
            "category": "system_overview"
        })
        step_number += 1
        
        return steps
    
    def _generate_fallback_steps(self, target_entities: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Generate fallback steps for cases where primary investigation fails
        
        Args:
            target_entities: Dictionary of target entity IDs
            
        Returns:
            List[Dict[str, Any]]: List of fallback investigation steps
        """
        fallback_steps = []
        
        # Fallback 1: If specific entity lookup fails, search broadly
        fallback_steps.append({
            "step": "F1",
            "description": "If specific entity lookup fails, get all medium severity issues",
            "tool": "kg_get_all_issues",
            "arguments": {"severity": "medium"},
            "expected_outcome": "Medium severity issues for broader analysis",
            "trigger": "entity_not_found",
            "category": "fallback"
        })
        
        # Fallback 2: If no issues found, search by entity type
        fallback_steps.append({
            "step": "F2", 
            "description": "If no specific issues found, search for all Drive entities",
            "tool": "kg_get_related_entities",
            "arguments": {"entity_type": "Drive", "entity_id": "any", "max_depth": 1},
            "expected_outcome": "List of all Drive entities for manual inspection",
            "trigger": "no_issues_found",
            "category": "fallback"
        })
        
        # Fallback 3: Comprehensive graph overview
        fallback_steps.append({
            "step": "F3",
            "description": "If investigation data is incomplete, print full Knowledge Graph",
            "tool": "kg_print_graph",
            "arguments": {"include_details": True, "include_issues": True},
            "expected_outcome": "Complete Knowledge Graph visualization for manual analysis",
            "trigger": "insufficient_data",
            "category": "fallback"
        })
        
        return fallback_steps
    
    def _format_investigation_plan(self, pod_name: str, namespace: str, volume_path: str,
                                 plan_steps: List[Dict[str, Any]], 
                                 fallback_steps: List[Dict[str, Any]]) -> str:
        """
        Format the Investigation Plan into the required string format
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error  
            plan_steps: List of main investigation steps
            fallback_steps: List of fallback steps
            
        Returns:
            str: Formatted Investigation Plan
        """
        plan_lines = []
        plan_lines.append("Investigation Plan:")
        plan_lines.append(f"Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}")
        plan_lines.append(f"Generated Steps: {len(plan_steps)} main steps, {len(fallback_steps)} fallback steps")
        plan_lines.append("")
        
        # Main investigation steps
        for step in plan_steps:
            step_line = (
                f"Step {step['step']}: {step['description']} | "
                f"Tool: {step['tool']}({', '.join(f'{k}={repr(v)}' for k, v in step['arguments'].items())}) | "
                f"Expected: {step['expected_outcome']}"
            )
            plan_lines.append(step_line)
        
        # Fallback steps
        if fallback_steps:
            plan_lines.append("")
            plan_lines.append("Fallback Steps (if main steps fail):")
            for step in fallback_steps:
                fallback_line = (
                    f"Step {step['step']}: {step['description']} | "
                    f"Tool: {step['tool']}({', '.join(f'{k}={repr(v)}' for k, v in step['arguments'].items())}) | "
                    f"Expected: {step['expected_outcome']} | "
                    f"Trigger: {step['trigger']}"
                )
                plan_lines.append(fallback_line)
        
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
