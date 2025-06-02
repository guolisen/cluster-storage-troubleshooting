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
    Generates preliminary investigation steps using rule-based approaches
    
    Uses predefined rules to analyze Knowledge Graph data and generate
    a limited number of critical initial investigation steps based on 
    issue severity and historical experience.
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
    
    def generate_preliminary_steps(self, pod_name: str, namespace: str, volume_path: str,
                                  target_entities: Dict[str, str], issues_analysis: Dict[str, Any],
                                  historical_experience: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Generate preliminary investigation steps based on rule-based prioritization
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            target_entities: Dictionary of target entity IDs
            issues_analysis: Analysis of existing issues
            historical_experience: Historical experience data (optional)
            
        Returns:
            List[Dict[str, Any]]: List of preliminary investigation steps (1-3 steps)
        """
        try:
            # Step 1: Determine investigation priority based on issue severity and historical experience
            investigation_priority = self._determine_investigation_priority(
                issues_analysis, target_entities, historical_experience
            )
            
            # Step 2: Generate a limited set of preliminary steps (1-3) based on priorities
            preliminary_steps = self._generate_priority_steps(
                target_entities, investigation_priority, issues_analysis, volume_path, 
                max_steps=3  # Limit to 3 preliminary steps
            )
            
            return preliminary_steps
            
        except Exception as e:
            self.logger.error(f"Error generating rule-based preliminary steps: {str(e)}")
            return self._generate_basic_fallback_steps()
    
    def _determine_investigation_priority(self, issues_analysis: Dict[str, Any], 
                                        target_entities: Dict[str, str],
                                        historical_experience: List[Dict[str, Any]] = None) -> List[str]:
        """
        Determine investigation priority based on issue severity, target entities, and historical experience
        
        Args:
            issues_analysis: Analysis of existing issues
            target_entities: Dictionary of target entity IDs
            historical_experience: Historical experience data (optional)
            
        Returns:
            List[str]: Ordered list of investigation priorities
        """
        priorities = []
        
        # Add priorities based on historical experience if available
        if historical_experience:
            for experience in historical_experience:
                attributes = experience.get('attributes', {})
                root_cause = attributes.get('root_cause')
                if root_cause:
                    if 'hardware failure' in root_cause.lower():
                        priorities.append("hardware_verification")
                    elif 'network' in root_cause.lower():
                        priorities.append("network_verification")
                    elif 'configuration' in root_cause.lower():
                        priorities.append("config_verification")
        
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
    
    def _generate_priority_steps(self, target_entities: Dict[str, str], 
                               priorities: List[str], issues_analysis: Dict[str, Any],
                               volume_path: str, max_steps: int = 3) -> List[Dict[str, Any]]:
        """
        Generate a limited number of high-priority investigation steps
        
        Args:
            target_entities: Dictionary of target entity IDs
            priorities: List of investigation priorities  
            issues_analysis: Analysis of existing issues
            volume_path: Volume path with I/O error
            max_steps: Maximum number of steps to generate
            
        Returns:
            List[Dict[str, Any]]: List of preliminary investigation steps
        """
        steps = []
        step_number = 1
        all_potential_steps = []
        
        # Collect potential steps based on priorities
        
        # Critical issues analysis - highest priority
        if "critical_target_issues" in priorities or "critical_system_issues" in priorities:
            all_potential_steps.append({
                "step": None,  # Will be set later
                "description": "Get all critical issues that may be causing volume I/O errors",
                "tool": "kg_get_all_issues",
                "arguments": {"severity": "critical"},
                "expected": "List of critical issues affecting the system",
                "priority": "critical",
                "category": "issue_analysis",
                "priority_score": 100  # Highest priority
            })
        
        # Hardware verification - from historical experience or critical issues
        if "hardware_verification" in priorities:
            all_potential_steps.append({
                "step": None,
                "description": "Check disk health on the affected node",
                "tool": "check_disk_health",
                "arguments": {"node": target_entities.get("node", "").split(":")[-1] if "node" in target_entities else "all"},
                "expected": "Disk status and hardware errors",
                "priority": "high",
                "category": "hardware_investigation",
                "priority_score": 90
            })
        
        # Pod-specific investigation for the problem pod
        if "pod" in target_entities:
            all_potential_steps.append({
                "step": None,
                "description": f"Get detailed information about the problem pod and its current state",
                "tool": "kg_get_entity_info",
                "arguments": {"entity_type": "Pod", "entity_id": target_entities["pod"].split(":")[-1]},
                "expected": "Pod configuration, status, and any detected issues",
                "priority": "critical",
                "category": "entity_investigation",
                "priority_score": 85
            })
        
        # Drive-specific investigation
        if "drive" in target_entities:
            all_potential_steps.append({
                "step": None,
                "description": "Get detailed Drive information including health status and metrics",
                "tool": "kg_get_entity_info",
                "arguments": {"entity_type": "Drive", "entity_id": target_entities["drive"].split(":")[-1]},
                "expected": "Drive health status, SMART data, and any hardware issues",
                "priority": "high",
                "category": "hardware_investigation",
                "priority_score": 80
            })
        
        # Network verification if prioritized from historical experience
        if "network_verification" in priorities:
            all_potential_steps.append({
                "step": None,
                "description": "Check network connectivity between pod and storage",
                "tool": "kg_query_relationships",
                "arguments": {"source": "pod", "target": "network"},
                "expected": "Network connectivity and health status",
                "priority": "high",
                "category": "network_investigation",
                "priority_score": 75
            })
        
        # Sort steps by priority score
        all_potential_steps.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        
        # Take only the top max_steps steps
        selected_steps = all_potential_steps[:max_steps]
        
        # Assign step numbers
        for i, step in enumerate(selected_steps, 1):
            step["step"] = i
            step.pop("priority_score", None)  # Remove the priority score used for sorting
            steps.append(step)
        
        return steps
    
    def _generate_basic_fallback_steps(self) -> List[Dict[str, Any]]:
        """
        Generate basic fallback steps when all else fails
        
        Returns:
            List[Dict[str, Any]]: List of basic fallback steps
        """
        return [{
            "step": 1,
            "description": "Get all critical issues from Knowledge Graph",
            "tool": "kg_get_all_issues",
            "arguments": {"severity": "critical"},
            "expected": "List of critical issues affecting the system",
            "priority": "critical",
            "category": "issue_analysis"
        }]
