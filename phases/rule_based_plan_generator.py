#!/usr/bin/env python3
"""
Rule-based Plan Generator for Investigation Planning

This module contains utilities for generating investigation plans using rule-based approaches.
"""

import logging
from typing import Dict, List, Any, Set
from knowledge_graph import KnowledgeGraph
from phases.utils import validate_knowledge_graph, handle_exception

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
        validate_knowledge_graph(self.kg, self.__class__.__name__)
    
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
            error_msg = handle_exception("generate_preliminary_steps", e, self.logger)
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

        # Add priorities from critical issues on target entities
        priorities.extend(self._get_priorities_from_critical_issues(issues_analysis, target_entities))

        # Add priorities from historical experience
        priorities.extend(self._get_priorities_from_historical_experience(historical_experience))

        # Add priorities from high severity issues
        priorities.extend(self._get_priorities_from_high_issues(issues_analysis, target_entities))
        
        # Add lower priority issues
        priorities.extend(self._get_priorities_from_medium_issues(issues_analysis))
        
        # Always include basic investigation and hardware verification as fallback
        if "basic_investigation" not in priorities:
            priorities.append("basic_investigation")
            
        if "hardware_verification" not in priorities:
            priorities.append("hardware_verification")
        
        return priorities
    
    def _get_priorities_from_historical_experience(self, historical_experience: List[Dict[str, Any]]) -> List[str]:
        """
        Extract investigation priorities from historical experience data
        
        Args:
            historical_experience: Historical experience data
            
        Returns:
            List[str]: Priorities derived from historical experience
        """
        priorities = []
        
        if not historical_experience:
            return priorities
            
        for experience in historical_experience:
            attributes = experience.get('attributes', {})
            root_cause = attributes.get('root_cause', '').lower()
            
            if not root_cause:
                continue
                
            if 'hardware failure' in root_cause:
                priorities.append("hardware_verification")
            elif 'network' in root_cause:
                priorities.append("network_verification")
            elif 'configuration' in root_cause:
                priorities.append("config_verification")
        
        return priorities
    
    def _get_priorities_from_critical_issues(self, issues_analysis: Dict[str, Any], 
                                           target_entities: Dict[str, str]) -> List[str]:
        """
        Extract investigation priorities from critical issues
        
        Args:
            issues_analysis: Analysis of existing issues
            target_entities: Dictionary of target entity IDs
            
        Returns:
            List[str]: Priorities derived from critical issues
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
            
        return priorities
    
    def _get_priorities_from_high_issues(self, issues_analysis: Dict[str, Any], 
                                       target_entities: Dict[str, str]) -> List[str]:
        """
        Extract investigation priorities from high severity issues
        
        Args:
            issues_analysis: Analysis of existing issues
            target_entities: Dictionary of target entity IDs
            
        Returns:
            List[str]: Priorities derived from high severity issues
        """
        priorities = []
        
        # Medium priority: High severity issues on target entities
        target_entity_ids = set(target_entities.values())
        high_issues_on_targets = [
            issue for issue in issues_analysis["by_severity"]["high"]
            if issue.get('node_id') in target_entity_ids
        ]
        
        if high_issues_on_targets:
            priorities.append("high_target_issues")
        
        # Lower priority: High severity issues on any entities
        if issues_analysis["by_severity"]["high"]:
            priorities.append("high_system_issues")
            
        return priorities
    
    def _get_priorities_from_medium_issues(self, issues_analysis: Dict[str, Any]) -> List[str]:
        """
        Extract investigation priorities from medium severity issues
        
        Args:
            issues_analysis: Analysis of existing issues
            
        Returns:
            List[str]: Priorities derived from medium severity issues
        """
        priorities = []
        
        if issues_analysis["by_severity"]["medium"]:
            priorities.append("medium_issues")
            
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
        all_potential_steps = []
        
        # Add steps for each priority category
        self._add_critical_issue_steps(all_potential_steps, priorities, target_entities)
        self._add_hardware_verification_steps(all_potential_steps, priorities, target_entities)
        self._add_drive_investigation_steps(all_potential_steps, target_entities)
        self._add_volume_investigation_steps(all_potential_steps, target_entities, volume_path)
        self._add_pod_investigation_steps(all_potential_steps, target_entities)
        self._add_network_verification_steps(all_potential_steps, priorities)
        
        # Sort steps by priority score and limit to max_steps
        return self._select_and_format_steps(all_potential_steps, max_steps)
    
    def _add_critical_issue_steps(self, steps_list: List[Dict[str, Any]], 
                                priorities: List[str], target_entities: Dict[str, str]) -> None:
        """
        Add steps for critical issues analysis
        
        Args:
            steps_list: List to add steps to
            priorities: List of investigation priorities
            target_entities: Dictionary of target entity IDs
        """
        if "critical_target_issues" in priorities or "critical_system_issues" in priorities:
            steps_list.append({
                "step": None,  # Will be set later
                "description": "Get all critical issues that may be causing volume I/O errors",
                "tool": "kg_get_all_issues",
                "arguments": {"severity": "critical"},
                "expected": "List of critical issues affecting the system",
                "priority": "critical",
                "category": "issue_analysis",
                "priority_score": 100  # Highest priority
            })
    
    def _add_hardware_verification_steps(self, steps_list: List[Dict[str, Any]], 
                                       priorities: List[str], target_entities: Dict[str, str]) -> None:
        """
        Add steps for hardware verification
        
        Args:
            steps_list: List to add steps to
            priorities: List of investigation priorities
            target_entities: Dictionary of target entity IDs
        """
        if "hardware_verification" in priorities:
            node = target_entities.get("node", "").split(":")[-1] if "node" in target_entities else "all"
            
            # Add comprehensive disk health check
            steps_list.append({
                "step": None,
                "description": "Check disk health status using SMART data on the affected node",
                "tool": "check_disk_health",
                "arguments": {"node_name": node, "device_path": "/dev/sda"},
                "expected": "Disk health assessment with key metrics and status",
                "priority": "high",
                "category": "hardware_investigation",
                "priority_score": 95
            })
            
            # Add disk error log scanning
            steps_list.append({
                "step": None,
                "description": "Scan system logs for disk-related errors on the affected node",
                "tool": "scan_disk_error_logs",
                "arguments": {"node_name": node, "hours_back": 24},
                "expected": "Summary of disk-related errors with actionable insights",
                "priority": "high",
                "category": "hardware_investigation",
                "priority_score": 85
            })
    
    def _add_pod_investigation_steps(self, steps_list: List[Dict[str, Any]], 
                                   target_entities: Dict[str, str]) -> None:
        """
        Add steps for pod-specific investigation
        
        Args:
            steps_list: List to add steps to
            target_entities: Dictionary of target entity IDs
        """
        if "pod" in target_entities:
            pod_id = target_entities["pod"].split(":")[-1]
            steps_list.append({
                "step": None,
                "description": f"Get detailed information about the problem pod and its current state",
                "tool": "kg_get_entity_info",
                "arguments": {"entity_type": "Pod", "entity_id": pod_id},
                "expected": "Pod configuration, status, and any detected issues",
                "priority": "critical",
                "category": "entity_investigation",
                "priority_score": 85
            })
    
    def _add_drive_investigation_steps(self, steps_list: List[Dict[str, Any]], 
                                     target_entities: Dict[str, str]) -> None:
        """
        Add steps for drive-specific investigation
        
        Args:
            steps_list: List to add steps to
            target_entities: Dictionary of target entity IDs
        """
        if "drive" in target_entities:
            drive_id = target_entities["drive"].split(":")[-1]
            node = target_entities.get("node", "").split(":")[-1] if "node" in target_entities else None
            
            # Get drive entity information from knowledge graph
            steps_list.append({
                "step": None,
                "description": "Get detailed Drive information including health status and metrics",
                "tool": "kg_get_entity_info",
                "arguments": {"entity_type": "Drive", "entity_id": drive_id},
                "expected": "Drive health status, SMART data, and any hardware issues",
                "priority": "high",
                "category": "hardware_investigation",
                "priority_score": 88
            })
            
            # If we have the node, add disk performance testing
            if node:
                # Add disk read-only test
                steps_list.append({
                    "step": None,
                    "description": "Perform read-only test on the disk to verify readability",
                    "tool": "run_disk_readonly_test",
                    "arguments": {
                        "node_name": node,
                        "device_path": f"/dev/{drive_id}",
                        "duration_minutes": 5
                    },
                    "expected": "Disk read performance metrics and error detection",
                    "priority": "high",
                    "category": "hardware_investigation",
                    "priority_score": 85
                })
                
                # Add disk IO performance test
                steps_list.append({
                    "step": None,
                    "description": "Measure disk I/O performance under different workloads",
                    "tool": "test_disk_io_performance",
                    "arguments": {
                        "node_name": node,
                        "device_path": f"/dev/{drive_id}",
                        "test_types": ["read", "randread"],
                        "duration_seconds": 30
                    },
                    "expected": "Disk I/O performance metrics including IOPS and throughput",
                    "priority": "medium",
                    "category": "hardware_investigation",
                    "priority_score": 75
                })
                
                # Add disk jitter detection
                steps_list.append({
                    "step": None,
                    "description": "Detect intermittent online/offline jitter in disk status",
                    "tool": "detect_disk_jitter",
                    "arguments": {
                        "duration_minutes": 5,
                        "node_name": node,
                        "drive_uuid": drive_id
                    },
                    "expected": "Report on disk status stability and any detected jitter",
                    "priority": "medium",
                    "category": "hardware_investigation",
                    "priority_score": 70
                })
    
    def _add_volume_investigation_steps(self, steps_list: List[Dict[str, Any]],
                                       target_entities: Dict[str, str],
                                       volume_path: str) -> None:
        """
        Add steps for volume-specific investigation
        
        Args:
            steps_list: List to add steps to
            target_entities: Dictionary of target entity IDs
            volume_path: Path of the volume with I/O error
        """
        if "pod" in target_entities:
            pod_id = target_entities["pod"].split(":")[-1]
            namespace = "default"  # Default namespace, could be extracted from pod_id if available
            
            # Add volume mount validation
            steps_list.append({
                "step": None,
                "description": "Verify that the pod volume is correctly mounted and accessible",
                "tool": "verify_volume_mount",
                "arguments": {
                    "pod_name": pod_id,
                    "namespace": namespace,
                    "mount_path": volume_path
                },
                "expected": "Volume mount verification with accessibility and filesystem details",
                "priority": "critical",
                "category": "volume_investigation",
                "priority_score": 92
            })
            
            # Add volume I/O test
            steps_list.append({
                "step": None,
                "description": "Run I/O tests on the volume to check for read/write errors",
                "tool": "run_volume_io_test",
                "arguments": {
                    "pod_name": pod_id,
                    "namespace": namespace,
                    "mount_path": volume_path
                },
                "expected": "Results of read/write tests on the volume",
                "priority": "high", 
                "category": "volume_investigation",
                "priority_score": 86
            })
            
            # Add volume performance test
            steps_list.append({
                "step": None,
                "description": "Test I/O performance of the pod volume including speeds and latency",
                "tool": "test_volume_io_performance",
                "arguments": {
                    "pod_name": pod_id,
                    "namespace": namespace,
                    "mount_path": volume_path,
                    "test_duration": 30
                },
                "expected": "Volume I/O performance metrics for read/write operations",
                "priority": "medium",
                "category": "volume_investigation",
                "priority_score": 80
            })
            
            # Add filesystem check
            steps_list.append({
                "step": None,
                "description": "Perform a non-destructive filesystem check on the pod volume",
                "tool": "check_pod_volume_filesystem",
                "arguments": {
                    "pod_name": pod_id,
                    "namespace": namespace,
                    "mount_path": volume_path
                },
                "expected": "Filesystem health check results and any detected issues",
                "priority": "medium",
                "category": "volume_investigation",
                "priority_score": 78
            })
            
            # Add volume space usage analysis
            steps_list.append({
                "step": None,
                "description": "Analyze volume space usage to identify potential space issues",
                "tool": "analyze_volume_space_usage",
                "arguments": {
                    "pod_name": pod_id,
                    "namespace": namespace,
                    "mount_path": volume_path
                },
                "expected": "Volume space usage analysis with directories and file patterns",
                "priority": "medium",
                "category": "volume_investigation",
                "priority_score": 75
            })
            
    def _add_network_verification_steps(self, steps_list: List[Dict[str, Any]], 
                                      priorities: List[str]) -> None:
        """
        Add steps for network verification
        
        Args:
            steps_list: List to add steps to
            priorities: List of investigation priorities
        """
        if "network_verification" in priorities:
            steps_list.append({
                "step": None,
                "description": "Check network connectivity between pod and storage",
                "tool": "kg_query_relationships",
                "arguments": {"source": "pod", "target": "network"},
                "expected": "Network connectivity and health status",
                "priority": "high",
                "category": "network_investigation",
                "priority_score": 75
            })
    
    def _select_and_format_steps(self, all_potential_steps: List[Dict[str, Any]], 
                               max_steps: int) -> List[Dict[str, Any]]:
        """
        Select and format steps based on priority score
        
        Args:
            all_potential_steps: List of all potential steps
            max_steps: Maximum number of steps to select
            
        Returns:
            List[Dict[str, Any]]: Selected and formatted steps
        """
        # Sort steps by priority score
        all_potential_steps.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        
        # Take only the top max_steps steps
        selected_steps = all_potential_steps[:max_steps]
        
        # Format steps with step numbers
        formatted_steps = []
        for i, step in enumerate(selected_steps, 1):
            step["step"] = i
            step.pop("priority_score", None)  # Remove the priority score used for sorting
            formatted_steps.append(step)
        
        return formatted_steps
    
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
