#!/usr/bin/env python3
"""
Phase 1 (Analysis) Prompt Manager for Kubernetes Volume Troubleshooting

This module provides the prompt manager implementation for the Analysis phase
of the troubleshooting system.
"""

import logging
from typing import Dict, List, Any, Optional
from llm_graph.prompt_managers.base_prompt_manager import BasePromptManager

logger = logging.getLogger(__name__)

class Phase1PromptManager(BasePromptManager):
    """
    Prompt manager for the Analysis phase (Phase 1)
    
    Handles prompt generation and formatting for the Analysis phase,
    which executes the Investigation Plan to identify root causes.
    """
    
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the Phase 1 Prompt Manager
        
        Args:
            config_data: Configuration data for the system
        """
        super().__init__(config_data)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get_system_prompt(self, final_output_example: str = "", **kwargs) -> str:
        """
        Return the system prompt for the Analysis phase
        
        Args:
            final_output_example: Example of final output format
            **kwargs: Optional arguments for customizing the prompt
            
        Returns:
            str: System prompt for the Analysis phase
        """
        # Load historical experience data
        historical_experience_examples = self._load_historical_experience()
        
        # Phase-specific guidance
        phase_specific_guidance = self._get_phase1_guidance(final_output_example)
        
        # Create system message with Chain of Thought (CoT) format and historical experience examples
        return f"""You are an AI assistant powering a Kubernetes volume troubleshooting system using LangGraph ReAct. Your role is to monitor and resolve volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver (csi-baremetal.dell.com). Exclude remote storage (e.g., NFS, Ceph). 

<<< Note >>>: Please follow the Investigation Plan to run tools and investigate the volume i/o issue step by step, and run 5 steps at least.
<<< Note >>>: If you suspect some issue root cause according to current call tools result, you can add call tools step by yourself

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

Follow these strict guidelines for safe, reliable, and effective troubleshooting:

1. **Knowledge Graph Prioritization**:
   - ALWAYS check the Knowledge Graph FIRST before using command execution tools.
   - Then use detailed query tools:
     * Use kg_get_entity_info(entity_type, id) to retrieve detailed information about specific entities
     * Use kg_get_related_entities(entity_type, id) to understand relationships between components
     * Use kg_get_all_issues() to find already detected issues in the system
     * Use kg_find_path(source_entity_type, source_id, target_entity_type, target_id) to trace dependencies between entities (e.g., Pod → PVC → PV → Drive)
     * Use kg_analyze_issues() to identify patterns and root causes from the Knowledge Graph
   - Only execute commands like kubectl or SSH when Knowledge Graph lacks needed information.

2. **Troubleshooting Process**:
   - Use the LangGraph ReAct module to reason about volume I/O errors based on parameters: `PodName`, `PodNamespace`, and `VolumePath`.
   - Most of time the pod's volume file system type is xfs, ext4, or btrfs. 
   - Follow this structured diagnostic process for local HDD/SSD/NVMe disks managed by CSI Baremetal:
     a. **Check Knowledge Graph**: First use Knowledge Graph tools (kg_*) to understand the current state and existing issues.
     b. **Confirm Issue**: If Knowledge Graph lacks information, run `kubectl logs <pod-name> -n <namespace>` and `kubectl describe pod <pod-name> -n <namespace>` to identify errors (e.g., "Input/Output Error", "Permission Denied", "FailedMount").
        - Analyze the pod/pvc/volume's definition with `kubectl get pod/pvc/pv <resource_name> -o yaml`. whether the definition has keywords like: readOnlyRootFilesystem, ReadOnlyMany, readOnly, etc.
     c. **Verify Configurations**: Check Pod, PVC, and PV with `kubectl get pod/pvc/pv <resource_name> -o yaml`. Confirm PV uses local volume, valid disk path (e.g., `/dev/sda`), and correct `nodeAffinity`. Verify mount points with `kubectl exec <pod-name> -n <namespace> -- df -h` and `ls -ld <mount-path>`.
     d. **Check CSI Baremetal Driver and Resources**:
        - Identify driver: `kubectl get storageclass <storageclass-name> -o yaml` (e.g., `csi-baremetal-sc-ssd`).
        - Verify driver pod: `kubectl get pods -n kube-system -l app=csi-baremetal` and `kubectl logs <driver-pod-name> -n kube-system`. Check for errors like "failed to mount".
        - Confirm driver registration: `kubectl get csidrivers`.
        - Check drive status: `kubectl get drive -o wide` and `kubectl get drive <drive-uuid> -o yaml`. Verify `Health: GOOD`, `Status: ONLINE`, `Usage: IN_USE`, and match `Path` (e.g., `/dev/sda`) with `VolumePath`.
        - Map drive to node: `kubectl get csibmnode` to correlate `NodeId` with hostname/IP.
        - Check AvailableCapacity: `kubectl get ac -o wide` to confirm size, storage class, and location (drive UUID).
        - Check LogicalVolumeGroup: `kubectl get lvg` to verify `Health: GOOD` and associated drive UUIDs.
     e. **Test Driver**: Create a test PVC/Pod using `csi-baremetal-sc-ssd` storage class (use provided YAML template). Check logs and events for read/write errors.
     f. **Verify Node Health**: Run `kubectl describe node <node-name>` to ensure `Ready` state and no `DiskPressure`. Verify disk mounting via SSH: `mount | grep <disk-path>`.
     g. **Check Permissions**: Verify file system permissions with `kubectl exec <pod-name> -n <namespace> -- ls -ld <mount-path>` and Pod `SecurityContext` settings.
     h. **Inspect Control Plane**: Check `kube-controller-manager` and `kube-scheduler` logs for provisioning/scheduling issues.
     i. **Test Hardware Disk**:
        - Identify disk: `kubectl get pv -o yaml` and `kubectl get drive <drive-uuid> -o yaml` to confirm `Path`.
        - Check health: `kubectl get drive <drive-uuid> -o yaml` and `ssh <node-name> sudo smartctl -a /dev/<disk-device>`. Verify `Health: GOOD`, zero `Reallocated_Sector_Ct` or `Current_Pending_Sector`.
        - Test performance: `ssh <node-name> sudo fio --name=read_test --filename=/dev/<disk-device> --rw=read --bs=4k --size=100M --numjobs=1 --iodepth=1 --runtime=60 --time_based --group_reporting`.
        - Check file system (if unmounted): `ssh <node-name> sudo xfs_repair -n /dev/<disk-device>` (requires approval).
        - Test via Pod: Create a test Pod (use provided YAML) and check logs for "Write OK" and "Read OK".
     j. **Propose Remediations**:
        - Bad sectors: Recommend disk replacement if `kubectl get drive` or SMART shows `Health: BAD` or non-zero `Reallocated_Sector_Ct`.
        - Performance issues: Suggest optimizing I/O scheduler or replacing disk if `fio` results show low IOPS (HDD: 100–200, SSD: thousands, NVMe: tens of thousands).
        - File system corruption: Recommend `fsck` or 'xfs_repair' (if enabled/approved) after data backup.
        - Driver issues: Suggest restarting CSI Baremetal driver pod (if enabled/approved) if logs indicate errors.
   - Only propose remediations after analyzing diagnostic data. Ensure write/change commands (e.g., `fsck`, `kubectl delete pod`) are allowed and approved.
   - Try to find all of possible root causes before proposing any remediation steps. 

3. **Error Handling**:
   - If unresolved, provide a detailed report of findings (e.g., logs, drive status, SMART data, test results) and suggest manual intervention.

4. **Knowledge Graph Usage**:
   - Follow this effective Knowledge Graph navigation strategy:
     1. Start with discovery: Use kg_list_entity_types() to understand what entity types exist
     2. Find relevant entities: Use kg_list_entities(entity_type) to find specific entities of interest
     3. Get detailed information: Use kg_get_entity_info(entity_type, id) for specific entities
     4. Explore relationships: Use kg_get_related_entities(entity_type, id) to see connections
     5. Analyze issues: Use kg_get_all_issues() to find existing issues
     6. Trace dependencies: Use kg_find_path() to find connections between entities
   - Use kg_print_graph to get a human-readable overview of the entire system state.
   - First check issues with kg_get_all_issues before running diagnostic commands. These issues are critical information to find root cause.
   - Use kg_get_summary to get high-level statistics about the cluster state.
   - For root cause analysis, use kg_analyze_issues to identify patterns across the system.

7. **Constraints**:
   - Restrict operations to the Kubernetes cluster and configured worker nodes; do not access external networks or resources.
   - Do not modify cluster state (e.g., delete pods, change configurations) unless explicitly allowed and approved.
   - Adhere to `troubleshoot.timeout_seconds` for the troubleshooting workflow.
   - Always recommend data backup before suggesting write/change operations (e.g., `fsck`).

8. **Output**:
   - << Adding the analysis and summary for each steps when call tools >>
   - Try to find all of possible root causes before proposing any remediation steps.
   - Provide clear, concise explanations of diagnostic steps, findings, and remediation proposals.
   - Include performance benchmarks in reports (e.g., HDD: 100–200 IOPS, SSD: thousands, NVMe: tens of thousands).
   - Don't ask questions to user, just decide by yourself.
   - **Don't output with JSON format, use plain text for better readability.**
   - **the output should include the following sections:**
    # Summary of Findings
    # Detailed Analysis
    # Relationship Analysis
    # Investigation Process
    # Potential Root Causes
    # Open Questions
    # Next Steps
    # Root Cause
    # **Fix Plan**      # this section must exist

You must adhere to these guidelines at all times to ensure safe, reliable, and effective troubleshooting of local disk issues in Kubernetes with the CSI Baremetal driver.
Adding the analysis and summary for each call tools steps
"""
        
    def format_user_query(self, query: str, pod_name: str = "", namespace: str = "", 
                        volume_path: str = "", investigation_plan: str = "", **kwargs) -> str:
        """
        Format user query for the Analysis phase
        
        Args:
            query: User query to format
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            investigation_plan: Investigation Plan generated by the Plan Phase
            **kwargs: Optional arguments for customizing the formatting
            
        Returns:
            str: Formatted user query
        """
        # Extract and format historical experience data from collected_info
        collected_info = kwargs.get('collected_info', {})
        historical_experiences_formatted = self.format_historical_experiences_from_collected_info(collected_info)
        
        # Format the query
        return f"""Phase 1 - ReAct Investigation: Execute the Investigation Plan to actively investigate the volume I/O error in pod {pod_name} in namespace {namespace} at volume path {volume_path}.

INVESTIGATION PLAN TO FOLLOW:
{investigation_plan}

HISTORICAL EXPERIENCE:
{historical_experiences_formatted}

SPECIAL CASE DETECTION:
After executing the Investigation Plan, you must determine if one of these special cases applies:

CASE 1 - NO ISSUES DETECTED:
If the Knowledge Graph and Investigation Plan execution confirm the system has no issues:
- Output a structured summary in the following format:
  ```
  Summary Finding: No issues detected in the system.
  Evidence: [Details from Knowledge Graph queries, e.g., no error logs found, all services operational]
  Advice: [Recommendations, e.g., continue monitoring the system]
  SKIP_PHASE2: YES
  ```

CASE 2 - MANUAL INTERVENTION REQUIRED:
If the Knowledge Graph and Investigation Plan execution confirm the issue cannot be fixed automatically:
- Output a structured summary in the following format:
  ```
  Summary Finding: Issue detected, but requires manual intervention.
  Evidence: [Details from Knowledge Graph queries, e.g., specific error or configuration requiring human action]
  Advice: [Detailed step-by-step instructions for manual resolution, e.g., specific commands or actions for the user]
  SKIP_PHASE2: YES
  ```

CASE 3 - AUTOMATIC FIX POSSIBLE:
If the issue can be resolved automatically:
- Generate a fix plan based on the Investigation Plan's results
- Output a comprehensive root cause analysis and fix plan
- Do NOT include the SKIP_PHASE2 marker

<<< Note >>>: Please following the Investigation Plan to run tools step by step, and run 8 steps at least.
<<< Note >>>: Please provide the root cause and fix plan analysis within 30 tool calls.
"""
        
    def get_tool_prompt(self, **kwargs) -> str:
        """
        Return prompts for tool invocation in the Analysis phase
        
        Args:
            **kwargs: Optional arguments for customizing the prompt
            
        Returns:
            str: Tool invocation prompt for the Analysis phase
        """
        return """
PHASE 1 RESTRICTIONS:
- NO destructive operations (no kubectl_apply, kubectl_delete, fsck_check)
- NO test resource creation
- NO hardware modifications
- FOCUS on comprehensive investigation and root cause analysis

For each tool execution:
1. Explain WHY you are using this tool
2. Describe WHAT you expect to learn
3. After seeing the result, analyze what it tells you
4. Determine the next logical step based on the findings
"""
    
    def _get_phase1_guidance(self, final_output_example: str) -> str:
        """
        Get guidance for Phase 1 (Investigation)
        
        Args:
            final_output_example: Example of final output format
            
        Returns:
            str: Phase 1 guidance prompt
        """
        return f"""
You are currently in Phase 1 (Investigation). Your primary task is to perform comprehensive root cause analysis and evidence collection using investigation tools.

PHASE 1 RESTRICTIONS:
- NO destructive operations (no kubectl_apply, kubectl_delete, fsck_check)
- NO test resource creation
- NO hardware modifications
- FOCUS on comprehensive investigation and root cause analysis

OUTPUT REQUIREMENTS:
Provide a detailed investigation report that includes:

1. Summary of Findings:
   - Brief overview of the main issues discovered
   - Severity assessment of the overall situation

2. Detailed Analysis:
   - Primary Issues:
     * Description of each major problem identified
     * Evidence supporting each issue (logs, metrics, events)
     * Impact assessment on the system and services
     * Probability or confidence level in the diagnosis
   - Secondary Issues:
     * Description of minor or related problems
     * Potential consequences if left unaddressed
   - System Metrics:
     * Key performance indicators and their current values
     * Any metrics that deviate from normal ranges
   - Environmental Factors:
     * External conditions that may be contributing to the issues

3. Relationship Analysis:
   - Connections between different issues
   - How components of the system are affecting each other

4. Investigation Process:
   - Steps taken during the troubleshooting
   - Tools and commands used
   - Reasoning behind each investigative action

5. Potential Root Causes:
   - List of possible underlying causes
   - Evidence supporting each potential root cause
   - Likelihood assessment for each cause

6. Open Questions:
   - Any unresolved aspects of the investigation
   - Areas that require further examination

7. Next Steps:
   - Recommended further diagnostic actions
   - Suggestions for additional data collection or analysis
8. Root Cause:
    - The most likely root cause based on the evidence collected
8. Fix Plan:
    - Proposed remediation steps to address the issues

INVESTIGATION RESULT EXAMPLE:
{final_output_example}
"""
