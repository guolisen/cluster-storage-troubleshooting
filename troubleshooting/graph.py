#!/usr/bin/env python3
"""
LangGraph Graph Building Components for Kubernetes Volume I/O Error Troubleshooting

This module contains functions for creating and configuring LangGraph state graphs
used in the analysis and remediation phases of Kubernetes volume troubleshooting.
Enhanced with specific end conditions for better control over graph termination.
"""

import json
import logging
import os
import re
from typing import Dict, Any, List, TypedDict, Optional, Union, Callable

# Configure logging (file only, no console output)
logger = logging.getLogger('langgraph')
logger.setLevel(logging.INFO)
# Don't propagate to root logger to avoid console output
logger.propagate = False

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import tools_condition
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, SystemMessage
from phases.llm_factory import LLMFactory
from troubleshooting.serial_tool_node import SerialToolNode, BeforeCallToolsHook, AfterCallToolsHook
from rich.console import Console
from rich.panel import Panel

# Enhanced state class to track additional information
class EnhancedMessagesState(TypedDict):
    """Enhanced state class that extends MessagesState with additional tracking"""
    messages: List[BaseMessage]
    iteration_count: int
    tool_call_count: int
    goals_achieved: List[str]
    root_cause_identified: bool
    fix_plan_provided: bool


# Create console for rich output
console = Console()
file_console = Console(file=open('troubleshoot.log', 'a'))

# Define hook functions for SerialToolNode
def before_call_tools_hook(tool_name: str, args: Dict[str, Any]) -> None:
    """Hook function called before a tool is executed.
    
    Args:
        tool_name: Name of the tool being called
        args: Arguments passed to the tool
    """
    try:
        # Format arguments for better readability
        formatted_args = json.dumps(args, indent=2) if args else "None"
        
        # Format the tool usage in a nice way
        if formatted_args != "None":
            # Print to console and log file
            tool_panel = Panel(
                f"[bold yellow]Tool:[/bold yellow] [green]{tool_name}[/green]\n\n"
                f"[bold yellow]Arguments:[/bold yellow]\n[blue]{formatted_args}[/blue]",
                title="[bold magenta]Thinking Step",
                border_style="magenta",
                safe_box=True
            )
            console.print(tool_panel)
        else:
            # Simple version for tools without arguments
            tool_panel = Panel(
                f"[bold yellow]Tool:[/bold yellow] [green]{tool_name}[/green]\n\n"
                f"[bold yellow]Arguments:[/bold yellow] None",
                title="[bold magenta]Thinking Step",
                border_style="magenta",
                safe_box=True
            )
            console.print(tool_panel)

        # Also log to file console
        file_console.print(f"Executing tool: {tool_name}")
        file_console.print(f"Parameters: {formatted_args}")
        
        # Log to standard logger
        logger.info(f"Executing tool: {tool_name}")
        logger.info(f"Parameters: {formatted_args}")
    except Exception as e:
        logger.error(f"Error in before_call_tools_hook: {e}")

def after_call_tools_hook(tool_name: str, args: Dict[str, Any], result: Any) -> None:
    """Hook function called after a tool is executed.
    
    Args:
        tool_name: Name of the tool that was called
        args: Arguments that were passed to the tool
        result: Result returned by the tool
    """
    try:
        # Format result for better readability
        if isinstance(result, ToolMessage):
            result_content = result.content
            result_status = result.status if hasattr(result, 'status') else 'success'
            formatted_result = f"Status: {result_status}\nContent: {result_content[:1000]}"
        else:
            formatted_result = str(result)[:1000]
        
        # Print tool result to console
        tool_panel = Panel(
            f"[bold cyan]Tool completed:[/bold cyan] [green]{tool_name}[/green]\n"
            f"[bold cyan]Result:[/bold cyan]\n[yellow]{formatted_result}[/yellow]",
            title="[bold magenta]Call tools",
            border_style="magenta",
            safe_box=True
        )
        console.print(tool_panel)

        # Also log to file console
        file_console.print(f"Tool completed: {tool_name}")
        file_console.print(f"Result: {formatted_result}")
        
        # Log to standard logger
        logger.info(f"Tool completed: {tool_name}")
        logger.info(f"Result: {formatted_result}")
    except Exception as e:
        logger.error(f"Error in after_call_tools_hook: {e}")

def create_troubleshooting_graph_with_context(collected_info: Dict[str, Any], phase: str = "phase1", config_data: Dict[str, Any] = None):
    """
    Create a LangGraph ReAct graph for troubleshooting with pre-collected context
    and enhanced end conditions
    
    Args:
        collected_info: Pre-collected diagnostic information from Phase 0
        phase: Current troubleshooting phase ("phase1" for investigation, "phase2" for action)
        config_data: Configuration data
        
    Returns:
        StateGraph: LangGraph StateGraph
    """
    if config_data is None:
        raise ValueError("Configuration data is required")
    
    # Initialize language model using LLMFactory
    llm_factory = LLMFactory(config_data)
    model = llm_factory.create_llm()
    
    # Define function to call the model with pre-collected context
    def call_model(state: MessagesState):
        logging.info(f"Processing state with {len(state['messages'])} messages")
        
        final_output_example = """ 
=== GRAPH END OUTPUT EXAMPLE ===
1. Summary of Findings:
- Issues detected with volume mounts and storage
- Node kernel logs show disk-related errors
- CSI Baremetal driver resources missing

2. Detailed Analysis:
Primary Issues:
- Volume uses local path provisioner instead of CSI Baremetal
- Kernel logs show disk errors (I/O, filesystem, mount issues)

3. Relationship Analysis:
- Pod → PVC → PV → Local disk with errors

4. Investigation Process:
- Checked pod, PVC, PV configurations
- Analyzed kernel logs and disk status

5. Potential Root Causes:
- Hardware disk failure (High likelihood)
- Configuration mismatch (High likelihood)

6. Open Questions:
- Is CSI Baremetal driver intended for this cluster?

7. Next Steps:
- Verify CSI driver installation
- Check disk health with smartctl

Root Cause:
- Disk hardware issues on node's local disk
- Missing proper CSI driver configuration

Fix Plan:
1. Verify CSI Baremetal driver installation
2. Check disk health with diagnostic tools
3. Consider hardware replacement if needed
=== GRAPH END OUTPUT EXAMPLE ===
"""
        # Add phase-specific guidance with optimized content
        phase_specific_guidance = ""
        if phase == "phase1":
            phase_specific_guidance = """
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

INVESTIGATION PLAN EXAMPLE:
{final_output_example}

"""
        elif phase == "phase2":
            phase_specific_guidance = """
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
        else:
            phase_specific_guidance = """
You are in a legacy mode. Please specify either 'phase1' for investigation or 'phase2' for action/remediation.
"""

        # Prepare context from collected information for query message
        context_summary = f"""
=== PRE-COLLECTED DIAGNOSTIC CONTEXT ===
Instructions:
    You can use the pre-collected diagnostic information to understand the current state of the Kubernetes cluster and the volume I/O issues being faced. Use this information to guide your troubleshooting process.

Knowledge Graph Summary:
{json.dumps(collected_info.get('knowledge_graph_summary', {}), indent=2)}

Pod Information:
{str(collected_info.get('pod_info', {}))}

PVC Information:
{str(collected_info.get('pvc_info', {}))}

PV Information:
{str(collected_info.get('pv_info', {}))}

Node Information Summary:
{str(collected_info.get('node_info', {}))}

CSI Driver Information:
{str(collected_info.get('csi_driver_info', {}))}

System Information:
{str(collected_info.get('system_info', {}))}

<<< Current Issues >>>
Issues Summary:
{str(collected_info.get('issues', {}))}

=== END PRE-COLLECTED CONTEXT ===
"""

        # Load historical experience data from JSON file
        historical_experience_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'historical_experience.json')
        historical_experience_examples = ""
        
        try:
            with open(historical_experience_path, 'r') as f:
                historical_experience = json.load(f)
                
            # Format historical experience data into CoT examples
            for i, experience in enumerate(historical_experience):
                # Create example header
                example_num = i + 1
                example_title = experience.get('observation', f"Example {example_num}")
                historical_experience_examples += f"\n## Example {example_num}: {example_title}\n\n"
                
                # Add OBSERVATION section
                historical_experience_examples += f"**OBSERVATION**: {experience.get('observation', '')}\n\n"
                
                # Add THINKING section
                historical_experience_examples += "**THINKING**:\n"
                thinking_points = experience.get('thinking', [])
                for j, point in enumerate(thinking_points):
                    historical_experience_examples += f"{j+1}. {point}\n"
                historical_experience_examples += "\n"
                
                # Add INVESTIGATION section
                historical_experience_examples += "**INVESTIGATION**:\n"
                investigation_steps = experience.get('investigation', [])
                for j, step_info in enumerate(investigation_steps):
                    if isinstance(step_info, dict):
                        step = step_info.get('step', '')
                        reasoning = step_info.get('reasoning', '')
                        historical_experience_examples += f"{j+1}. {step}\n   - {reasoning}\n"
                    else:
                        historical_experience_examples += f"{j+1}. {step_info}\n"
                historical_experience_examples += "\n"
                
                # Add DIAGNOSIS section
                historical_experience_examples += f"**DIAGNOSIS**: {experience.get('diagnosis', '')}\n\n"
                
                # Add RESOLUTION section
                historical_experience_examples += "**RESOLUTION**:\n"
                resolution_steps = experience.get('resolution', [])
                if isinstance(resolution_steps, list):
                    for j, step in enumerate(resolution_steps):
                        historical_experience_examples += f"{j+1}. {step}\n"
                else:
                    historical_experience_examples += f"{resolution_steps}\n"
                historical_experience_examples += "\n"
                
                # Limit to 6 examples to keep the prompt size manageable
                if example_num >= 6:
                    break
                    
        except Exception as e:
            logging.error(f"Error loading historical experience data: {e}")
            # Provide a fallback example in case the file can't be loaded
            historical_experience_examples = """
## Example 1: Volume Read Errors

**OBSERVATION**: Volume read errors appearing in pod logs

**THINKING**:
1. Read errors often indicate hardware issues with the underlying disk
2. Could be bad sectors, disk degradation, or controller problems
3. Need to check both logical (filesystem) and physical (hardware) health
4. Should examine error logs first, then check disk health metrics
5. Will use knowledge graph to find affected components, then check disk health

**INVESTIGATION**:
1. First, query error logs with `kg_query_nodes(type='log', time_range='24h', filters={{'message': 'I/O error'}})` to identify affected pods
   - This will show which pods are experiencing I/O errors and their frequency
2. Check disk health with `check_disk_health(node='node-1', disk_id='disk1')`
   - This will reveal SMART data and physical health indicators
3. Use 'xfs_repair -n *' to check volume health without modifying it
   - This will identify filesystem-level corruption or inconsistencies

**DIAGNOSIS**: Hardware failure in the underlying disk, specifically bad sectors causing read operations to fail

**RESOLUTION**:
1. Replace the faulty disk identified in `check_disk_health`
2. Restart the affected service with `systemctl restart db-service`
3. Verify pod status with `kubectl get pods` to ensure normal operation
"""
        
        # Create system message with Chain of Thought (CoT) format and historical experience examples
        system_message = SystemMessage(
            content = f"""You are an AI assistant powering a Kubernetes volume troubleshooting system using LangGraph ReAct. Your role is to monitor and resolve volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver (csi-baremetal.dell.com). Exclude remote storage (e.g., NFS, Ceph). 

<<< Note >>>: Please follow the Investigation Plan to run tools and investigate the volume i/o issue step by step, and run 8 steps at least.

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
   - Start with discovery tools to understand what's in the Knowledge Graph:
     * Use kg_list_entity_types() to discover available entity types and their counts
     * Use kg_list_entities(entity_type) to find specific entities of a given type
     * Use kg_list_relationship_types() to understand how entities are related
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
"""
        )
        
        # Add pre-collected diagnostic context and output example to user message
        user_messages = []

        context_message = HumanMessage(
            content = f"""Pre-collected diagnostic context:
{context_summary}
"""
        )
        
        # Ensure system message is first, followed by context message, then any existing user messages
        if state["messages"]:
            if isinstance(state["messages"], list):
                # Extract existing user messages (skip system message if present)
                for msg in state["messages"]:
                    if msg.type != "system":
                        user_messages.append(msg)
                
                # Create new message list with system message, context message, and existing user messages
                state["messages"] = [system_message, context_message] + user_messages
            else:
                state["messages"] = [system_message, context_message, state["messages"]]
        else:
            state["messages"] = [system_message, context_message]
        
        # Select tools based on phase
        if phase == "phase1":
            from tools import get_phase1_tools
            tools = get_phase1_tools()
            logging.info(f"Using Phase 1 tools: {len(tools)} investigation tools")
        elif phase == "phase2":
            from tools import get_phase2_tools
            tools = get_phase2_tools()
            logging.info(f"Using Phase 2 tools: {len(tools)} investigation + action tools")
        else:
            # Fallback to all tools for backward compatibility
            from tools import define_remediation_tools
            tools = define_remediation_tools()
            logging.info(f"Using all tools (fallback): {len(tools)} tools")
        
        # Call the model with tools for both phases (Phase 1 now actively investigates)
        response = model.bind_tools(tools).invoke(state["messages"])
        
        logging.info(f"Model response: {response.content}...")
        
        # Create console for rich output
        console = Console()
        console.print(f"[bold cyan]LangGraph thinking process:[/bold cyan]")

        if response.content:
            console.print(Panel(
                f"[bold green]{response.content}[/bold green]",
                title="[bold magenta]Thinking step",
                border_style="magenta",
                safe_box=True
            ))

        return {"messages": state["messages"] + [response]}
    
    def check_explicit_end_markers_with_llm(content: str, model) -> bool:
        """
        Use LLM to check if content contains explicit or implicit end markers.
        
        Args:
            content: The content to check for end markers
            model: The LLM model to use for checking
            
        Returns:
            bool: True if end markers detected, False otherwise
        """
        # Create a focused prompt for the LLM
        system_prompt = """
        You are an AI assistant tasked with determining if a text contains explicit or implicit markers 
        indicating the end of a process or conversation. Your task is to analyze the given text and 
        determine if it contains phrases or markers that suggest completion or termination.
        
        Examples of explicit end markers include:
        - "[END_GRAPH]", "[END]", "End of graph", "GRAPH END"
        - "This concludes the analysis"
        - "Final report"
        - "Investigation complete"
        - "FIX PLAN", "Fix Plan"
        - " Would you like to"
        - A question from AI that indicates the end of the process, such as " Would you like to proceed with planning the disk replacement or further investigate filesystem integrity?"
        
        Examples of implicit end markers include:
        - A summary followed by recommendations with no further questions
        - A conclusion paragraph that wraps up all findings
        - A complete analysis with all required sections present
        - A question from AI that indicates the end of the process, such as "Is there anything else I can help you with?" or "Do you have any further questions?"
        
        Respond with "YES" if you detect end markers, or "NO" if you don't.
        """
        
        user_prompt = f"""
        Analyze the following text and determine if it contains explicit or implicit end markers:
        
        {content}  # Limit content length to avoid token limits
        
        Does this text contain markers indicating it's the end of the process? Respond with only YES or NO.
        """
        
        try:
            # Create messages for the LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # Call the LLM
            response = model.invoke(messages)
            
            # Check if the response indicates end markers
            response_text = response.content.strip().upper()
            
            # Log the LLM's response
            logging.info(f"LLM end marker detection response: {response_text}")
            
            # Return True if the LLM detected end markers
            return "YES" in response_text
        except Exception as e:
            # Log any errors and fall back to the original behavior
            logging.error(f"Error in LLM end marker detection: {e}")
            
            # Fall back to simple string matching
            return any(marker in content for marker in ["[END_GRAPH]", "[END]", "End of graph", "GRAPH END"])

    def check_completion_indicators_with_llm(content: str, phase: str, model) -> bool:
        """
        Use LLM to check if content indicates task completion based on phase requirements.
        
        Args:
            content: The content to check for completion indicators
            phase: The current phase (phase1 or phase2)
            model: The LLM model to use for checking
            
        Returns:
            bool: True if completion indicators detected, False otherwise
        """
        # Define phase-specific required sections
        phase1_sections = [
            "Summary of Findings:",
            "Special Case Detected",
            "Detailed Analysis:",
            "Relationship Analysis:",
            "Investigation Process:",
            "Potential Root Causes:",
            "Root Cause:",
            "Fix Plan:",
            "Summary",
            "Recommendations"
        ]
        
        phase2_sections = [
            "Actions Taken:",
            "Test Results:",
            "Resolution Status:",
            "Remaining Issues:",
            "Recommendations:"
            "Summary of Findings:",
            "Special Case Detected",
            "Detailed Analysis:",
            "Relationship Analysis:",
            "Investigation Process:",
            "Potential Root Causes:",
            "Root Cause:",
            "Fix Plan:",
            "Summary",
            "Recommendations"
        ]
        
        # Select the appropriate sections based on the phase
        required_sections = phase1_sections if phase == "phase1" else phase2_sections
        
        # Create a focused prompt for the LLM
        system_prompt = f"""
        You are an AI assistant tasked with determining if a text contains sufficient information 
        to indicate that a troubleshooting process is complete. Your task is to analyze the given text 
        and determine if it contains the required sections and information for a {phase} report.
        
        For {phase}, the following sections are expected in a complete report:
        {', '.join(required_sections)}
        
        A complete report should have some of these sections and provide comprehensive information 
        in each section. The report should feel complete and not leave major questions unanswered.
        
        Respond with "YES" if you believe the text represents a complete report, or "NO" if it seems incomplete.
        """
        
        user_prompt = f"""
        Analyze the following text and determine if it represents a complete {phase} report:
        
        {content}  # Limit content length to avoid token limits
        
        Does this text contain sufficient information to be considered a complete report? Respond with only YES or NO.
        """
        
        try:
            # Create messages for the LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            # Call the LLM
            response = model.invoke(messages)
            
            # Check if the response indicates completion
            response_text = response.content.strip().upper()
            
            # Log the LLM's response
            logging.info(f"LLM completion detection response for {phase}: {response_text}")
            
            # Return True if the LLM detected completion
            return "YES" in response_text
        except Exception as e:
            # Log any errors and fall back to the original behavior
            logging.error(f"Error in LLM completion detection: {e}")
            
            # Fall back to counting sections
            sections_found = sum(1 for section in required_sections if section in content)
            threshold = 3 if phase == "phase1" else 2
            return sections_found >= threshold

# Define the end condition check function
    def check_end_conditions(state: MessagesState) -> Dict[str, str]:
        """
        Check if specific end conditions are met using LLM assistance when available
        Returns {"result": "end"} if the graph should end, {"result": "continue"} if it should continue
        """
        messages = state["messages"]
        if not messages:
            return {"result": "continue"}
            
        last_message = messages[-1]
        
        # Situation 1: Check if the last message is a tool response
        # Check if we've reached max iterations
        max_iterations = config_data.get("max_iterations", 30)
        ai_messages = [m for m in messages if getattr(m, "type", "") == "ai"]
        if len(ai_messages) > max_iterations:
            logging.info(f"Ending graph: reached max iterations ({max_iterations})")
            return {"result": "end"}
            
        # Skip content checks if the last message isn't from the AI
        if getattr(last_message, "type", "") != "ai":
            return {"result": "continue"}
            
        content = getattr(last_message, "content", "")
        if not content:
            return {"result": "continue"}

        # Situation 2: Check if has explicit end markers in the content using LLM
        if check_explicit_end_markers_with_llm(content, model):
            logging.info("Ending graph: LLM detected explicit end markers")
            return {"result": "end"}
        
        # Situation 3: Check for specific phrases indicating completion using LLM
        if check_completion_indicators_with_llm(content, phase, model):
            logging.info("Ending graph: LLM detected completion indicators")
            return {"result": "end"}
        
        # Situation 4: Check for convergence (model repeating itself)
        if len(ai_messages) > 3:
            # Compare the last message with the third-to-last message (skipping the tool response in between)
            last_content = content
            third_to_last_content = getattr(ai_messages[-3], "content", "")
            
            # Simple similarity check - if they start with the same paragraph
            if last_content and third_to_last_content:
                # Get first 100 chars of each message
                last_start = last_content[:100] if len(last_content) > 100 else last_content
                third_start = third_to_last_content[:100] if len(third_to_last_content) > 100 else third_to_last_content
                
                if last_start == third_start:
                    logging.info("Ending graph: detected convergence (model repeating itself)")
                    return {"result": "end"}
        
        # Default: continue execution
        return {"result": "continue"}

    # Build state graph
    logging.info("Building state graph with enhanced end conditions")
    builder = StateGraph(MessagesState)
    
    logging.info("Adding node: call_model")
    builder.add_node("call_model", call_model)
    
    # Add tools for both analysis and remediation phases
    logging.info("Importing and defining remediation tools")
    from tools import define_remediation_tools
    tools = define_remediation_tools()
    
    logging.info("Adding node: tools (SerialToolNode for sequential execution)")
    # Create SerialToolNode instance
    serial_tool_node = SerialToolNode(tools)
    
    # Register hook functions
    serial_tool_node.register_before_call_hook(before_call_tools_hook)
    serial_tool_node.register_after_call_hook(after_call_tools_hook)
    
    # Add node to the graph
    builder.add_node("tools", serial_tool_node)
    
    logging.info("Adding node: check_end")
    builder.add_node("check_end", check_end_conditions)
    
    logging.info("Adding conditional edges for tools")
    builder.add_conditional_edges(
        "call_model",
        tools_condition,
        {
            "tools": "tools",
            "none": "check_end",  # Instead of going directly to END, go to check_end
            "end": "check_end",
            "__end__": "check_end"
        }
    )
    
    logging.info("Adding conditional edges from check_end node")
    builder.add_conditional_edges(
        "check_end",
        lambda state: check_end_conditions(state)["result"],
        {
            "end": END,
            "__end__": END,
            "continue": "call_model"  # Loop back if conditions not met
        }
    )
    
    logging.info("Adding edge: tools -> call_model")
    builder.add_edge("tools", "call_model")
    
    logging.info("Adding edge: START -> call_model")
    builder.add_edge(START, "call_model")
    
    logging.info("Compiling graph")
    graph = builder.compile()
    
    logging.info("Graph compilation complete")
    return graph
