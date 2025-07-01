#!/usr/bin/env python3
"""
Phase 2 (Remediation) Prompt Manager for Kubernetes Volume Troubleshooting

This module provides the prompt manager implementation for the Remediation phase
of the troubleshooting system.
"""

import logging
from typing import Dict, List, Any, Optional
from llm_graph.prompt_managers.base_prompt_manager import BasePromptManager

logger = logging.getLogger(__name__)

class Phase2PromptManager(BasePromptManager):
    """
    Prompt manager for the Remediation phase (Phase 2)
    
    Handles prompt generation and formatting for the Remediation phase,
    which executes the Fix Plan to resolve identified issues.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the Phase 2 Prompt Manager
        
        Args:
            config_data: Configuration data for the system
        """
        super().__init__(config_data)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get_system_prompt(self, **kwargs) -> str:
        """
        Return the system prompt for the Remediation phase
        
        Args:
            **kwargs: Optional arguments for customizing the prompt
            
        Returns:
            str: System prompt for the Remediation phase
        """
        # Load historical experience data
        historical_experience_examples = self._load_historical_experience()
        
        # Phase-specific guidance
        phase_specific_guidance = self._get_phase2_guidance()
        
        # Create system message with Chain of Thought (CoT) format and historical experience examples
        return f"""You are an expert Kubernetes storage troubleshooter. Your task is to execute the Fix Plan to resolve volume I/O errors in Kubernetes pods.

TASK:
1. Execute the Fix Plan to resolve the identified issues
2. Validate the fixes to ensure they resolved the problem
3. Provide a detailed report of the remediation actions taken

KNOWLEDGE GRAPH TOOLS USAGE:
- When using knowledge graph tools, use the parameters of entity_type and id format:
  * Entity ID formats:
    - Pod: "gnode:Pod:<namespace>/<name>" (example: "gnode:Pod:default/test-pod-1-0")
    - PVC: "gnode:PVC:<namespace>/<name>" (example: "gnode:PVC:default/test-pvc-1")
    - PV: "gnode:PV:<name>" (example: "gnode:PV:pv-test-123")
    - Drive: "gnode:Drive:<uuid>" (example: "gnode:Drive:a1b2c3d4-e5f6")
    - Node: "gnode:Node:<name>" (example: "gnode:Node:kind-control-plane")
    - StorageClass: "gnode:StorageClass:<name>" (example: "gnode:StorageClass:csi-baremetal-sc")
    - LVG: "gnode:LVG:<name>" (example: "gnode:LVG:lvg-1")
    - AC: "gnode:AC:<name>" (example: "gnode:AC:ac-node1-ssd")
    - Volume: "gnode:Volume:<namespace>/<name>" (example: "gnode:Volume:default/vol-1")
    - System: "gnode:System:<entity_name>" (example: "gnode:System:kernel")
    - ClusterNode: "gnode:ClusterNode:<name>" (example: "gnode:ClusterNode:worker-1")
    - HistoricalExperience: "gnode:HistoricalExperience:<experience_id>" (example: "gnode:HistoricalExperience:exp-001")

  * Helper tools for generating entity IDs:
    - Pod: kg_get_entity_of_pod(namespace, name) → returns "gnode:Pod:namespace/name"
    - PVC: kg_get_entity_of_pvc(namespace, name) → returns "gnode:PVC:namespace/name"
    - PV: kg_get_entity_of_pv(name) → returns "gnode:PV:name"
    - Drive: kg_get_entity_of_drive(uuid) → returns "gnode:Drive:uuid"
    - Node: kg_get_entity_of_node(name) → returns "gnode:Node:name"
    - StorageClass: kg_get_entity_of_storage_class(name) → returns "gnode:StorageClass:name"
    - LVG: kg_get_entity_of_lvg(name) → returns "gnode:LVG:name"
    - AC: kg_get_entity_of_ac(name) → returns "gnode:AC:name"
    - Volume: kg_get_entity_of_volume(namespace, name) → returns "gnode:Volume:namespace/name"
    - System: kg_get_entity_of_system(entity_name) → returns "gnode:System:entity_name"
    - ClusterNode: kg_get_entity_of_cluster_node(name) → returns "gnode:ClusterNode:name"
    - HistoricalExperience: kg_get_entity_of_historical_experience(experience_id) → returns "gnode:HistoricalExperience:experience_id"

- Start with discovery tools to understand what's in the Knowledge Graph:
  * Use kg_list_entity_types() to discover available entity types and their counts
  * Use kg_list_entities(entity_type) to find specific entities of a given type
  * Use kg_list_relationship_types() to understand how entities are related

- Then use detailed query tools:
  * Use kg_get_entity_info(entity_type, id) to retrieve detailed information about specific entities
  * Use kg_get_related_entities(entity_type, id) to understand relationships between components
  * Use kg_get_all_issues() to find already detected issues in the system
  * Use kg_find_path(source_entity_type, source_id, target_entity_type, target_id) to trace dependencies

{phase_specific_guidance}

# CHAIN OF THOUGHT APPROACH

When troubleshooting, use a structured Chain of Thought approach to reason through problems:

1. **OBSERVATION**: Clearly identify what issue or symptom you're seeing
   - What errors are present in logs or events?
   - What behavior is unexpected or problematic?

2. **THINKING**:
   - What are the possible causes of this issue?
   - What components could be involved?
   - What tools can I use to investigate further?
   - What patterns should I look for in the results?

3. **INVESTIGATION**:
   - Execute tools in a logical sequence
   - For each tool, explain WHY you're using it and WHAT you expect to learn
   - After each result, analyze what it tells you and what to check next

4. **DIAGNOSIS**:
   - Based on evidence, determine the most likely root cause
   - Explain your reasoning with supporting evidence
   - Consider alternative explanations and why they're less likely

5. **RESOLUTION**:
   - Propose specific steps to resolve the issue
   - Explain why each step will help address the root cause
   - Consider potential side effects or risks

# HISTORICAL EXPERIENCE EXAMPLES

Here are examples of how to apply Chain of Thought reasoning to common volume issues:
{historical_experience_examples}

CONSTRAINTS:
- Follow the Fix Plan step by step
- Use only the tools available in the Phase2 tool registry
- Validate each fix to ensure it was successful
- Provide a clear, detailed report of all actions taken

OUTPUT FORMAT:
Your response must include:
1. Actions Taken
2. Validation Results
3. Resolution Status
4. Recommendations
"""
        
    def format_user_query(self, query: str, phase1_final_response: str = "", **kwargs) -> str:
        """
        Format user query for the Remediation phase
        
        Args:
            query: User query to format
            phase1_final_response: Response from Phase 1 containing root cause and fix plan
            **kwargs: Optional arguments for customizing the formatting
            
        Returns:
            str: Formatted user query
        """
        # Extract and format historical experience data from collected_info
        collected_info = kwargs.get('collected_info', {})
        historical_experiences_formatted = self.format_historical_experiences_from_collected_info(collected_info)
        
        # Format the query
        return f"""Phase 2 - Remediation: Execute the fix plan to resolve the identified issue.

Root Cause and Fix Plan: {phase1_final_response}

HISTORICAL EXPERIENCE:
{historical_experiences_formatted}

<<< Note >>>: Please try to fix issue within 30 tool calls.
"""
        
    def get_tool_prompt(self, **kwargs) -> str:
        """
        Return prompts for tool invocation in the Remediation phase
        
        Args:
            **kwargs: Optional arguments for customizing the prompt
            
        Returns:
            str: Tool invocation prompt for the Remediation phase
        """
        return """
PHASE 2 CAPABILITIES:
- Execute remediation actions based on Phase 1 **Fix Plan**
- Create test resources to validate fixes
- Run comprehensive volume testing
- Perform hardware diagnostics and repairs
- Clean up test resources after validation

For each tool execution:
1. Explain WHY you are using this tool
2. Describe WHAT you expect to accomplish
3. After seeing the result, validate if the action was successful
4. Determine if additional steps are needed
"""
    
    def _get_phase2_guidance(self) -> str:
        """
        Get guidance for Phase 2 (Action/Remediation)
        
        Returns:
            str: Phase 2 guidance prompt
        """
        return """
You are currently in Phase 2 (Action/Remediation). You have access to all Phase 1 investigation tools PLUS action tools for implementing fixes.

PHASE 2 CAPABILITIES:
- Execute remediation actions based on Phase 1 **Fix Plan**
- Create test resources to validate fixes
- Run comprehensive volume testing
- Perform hardware diagnostics and repairs
- Clean up test resources after validation

OUTPUT REQUIREMENTS:
Provide a detailed remediation report that includes:
1. Actions Taken: List of all remediation steps executed
2. Test Results: Results from validation tests
3. Resolution Status: Whether issues were resolved
4. Remaining Issues: Any unresolved problems
5. Recommendations: Suggestions for ongoing monitoring or future improvements
"""
