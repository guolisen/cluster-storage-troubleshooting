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

logger = logging.getLogger(__name__)

class InvestigationPlanner:
    """
    Generates Investigation Plans based on Knowledge Graph analysis
    
    The Investigation Planner analyzes the Knowledge Graph to create a structured
    step-by-step investigation plan that Phase 1 can follow to efficiently
    diagnose volume I/O issues.
    """
    
    def __init__(self, knowledge_graph: KnowledgeGraph):
        """
        Initialize the Investigation Planner
        
        Args:
            knowledge_graph: KnowledgeGraph instance from Phase 0
        """
        self.kg = knowledge_graph
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
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
            # Step 1: Analyze current issues in the Knowledge Graph
            issues_analysis = self._analyze_existing_issues()
            
            # Step 2: Identify target entities (Pod, PVC, PV, Drive chain)
            target_entities = self._identify_target_entities(pod_name, namespace)
            
            # Step 3: Determine investigation priority based on issue severity
            investigation_priority = self._determine_investigation_priority(issues_analysis, target_entities)
            
            # Step 4: Generate step-by-step plan
            plan_steps = self._generate_investigation_steps(
                target_entities, investigation_priority, issues_analysis, volume_path
            )
            
            # Step 5: Add fallback steps for incomplete data
            fallback_steps = self._generate_fallback_steps(target_entities)
            
            # Step 6: Format the final plan
            formatted_plan = self._format_investigation_plan(
                pod_name, namespace, volume_path, plan_steps, fallback_steps
            )
            
            return formatted_plan
            
        except Exception as e:
            self.logger.error(f"Error generating investigation plan: {str(e)}")
            return self._generate_basic_fallback_plan(pod_name, namespace, volume_path)
    
    def _analyze_existing_issues(self) -> Dict[str, Any]:
        """
        Analyze existing issues in the Knowledge Graph
        
        Returns:
            Dict[str, Any]: Analysis of current issues by severity and type
        """
        try:
            all_issues = self.kg.get_all_issues()
            
            # Categorize issues by severity and type
            issue_analysis = {
                "by_severity": {"critical": [], "high": [], "medium": [], "low": []},
                "by_type": {},
                "total_count": len(all_issues),
                "entities_with_issues": set()
            }
            
            for issue in all_issues:
                severity = issue.get('severity', 'unknown')
                issue_type = issue.get('type', 'unknown')
                node_id = issue.get('node_id', '')
                
                # Group by severity
                if severity in issue_analysis["by_severity"]:
                    issue_analysis["by_severity"][severity].append(issue)
                
                # Group by type
                if issue_type not in issue_analysis["by_type"]:
                    issue_analysis["by_type"][issue_type] = []
                issue_analysis["by_type"][issue_type].append(issue)
                
                # Track entities with issues
                if node_id:
                    issue_analysis["entities_with_issues"].add(node_id)
            
            return issue_analysis
            
        except Exception as e:
            self.logger.warning(f"Error analyzing existing issues: {str(e)}")
            return {"by_severity": {"critical": [], "high": [], "medium": [], "low": []}, 
                   "by_type": {}, "total_count": 0, "entities_with_issues": set()}
    
    def _identify_target_entities(self, pod_name: str, namespace: str) -> Dict[str, str]:
        """
        Identify target entities in the Knowledge Graph for the given pod
        
        Args:
            pod_name: Name of the pod
            namespace: Namespace of the pod
            
        Returns:
            Dict[str, str]: Dictionary mapping entity types to their IDs
        """
        target_entities = {"pod": f"Pod:{namespace}/{pod_name}"}
        
        try:
            # Look for the pod in the knowledge graph
            pod_node_id = f"Pod:{namespace}/{pod_name}"
            if not self.kg.graph.has_node(pod_node_id):
                # Try alternative formats
                pod_node_id = f"Pod:{pod_name}"
                if not self.kg.graph.has_node(pod_node_id):
                    # Search by name attribute
                    for node_id, attrs in self.kg.graph.nodes(data=True):
                        if (attrs.get('entity_type') == 'Pod' and 
                            attrs.get('name') == pod_name and
                            attrs.get('namespace') == namespace):
                            pod_node_id = node_id
                            break
            
            target_entities["pod"] = pod_node_id
            
            # Trace the volume chain: Pod -> PVC -> PV -> Drive
            if self.kg.graph.has_node(pod_node_id):
                # Find connected PVCs
                for _, target, edge_data in self.kg.graph.out_edges(pod_node_id, data=True):
                    target_attrs = self.kg.graph.nodes[target]
                    if target_attrs.get('entity_type') == 'PVC':
                        target_entities["pvc"] = target
                        
                        # Find connected PV
                        for _, pv_target, _ in self.kg.graph.out_edges(target, data=True):
                            pv_attrs = self.kg.graph.nodes[pv_target]
                            if pv_attrs.get('entity_type') == 'PV':
                                target_entities["pv"] = pv_target
                                
                                # Find connected Drive
                                for _, drive_target, _ in self.kg.graph.out_edges(pv_target, data=True):
                                    drive_attrs = self.kg.graph.nodes[drive_target]
                                    if drive_attrs.get('entity_type') == 'Drive':
                                        target_entities["drive"] = drive_target
                                        
                                        # Find the Node hosting the drive
                                        for _, node_target, _ in self.kg.graph.out_edges(drive_target, data=True):
                                            node_attrs = self.kg.graph.nodes[node_target]
                                            if node_attrs.get('entity_type') == 'Node':
                                                target_entities["node"] = node_target
                                        break
                                break
                        break
            
        except Exception as e:
            self.logger.warning(f"Error identifying target entities: {str(e)}")
        
        return target_entities
    
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
