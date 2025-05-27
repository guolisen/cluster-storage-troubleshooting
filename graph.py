#!/usr/bin/env python3
"""
LangGraph Graph Building Components for Kubernetes Volume I/O Error Troubleshooting

This module contains functions for creating and configuring LangGraph state graphs
used in the analysis and remediation phases of Kubernetes volume troubleshooting.
"""

import json
import logging

# Configure logging (file only, no console output)
logger = logging.getLogger('langgraph')
logger.setLevel(logging.INFO)
# Don't propagate to root logger to avoid console output
logger.propagate = False

from typing import Dict, List, Any

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI


def create_troubleshooting_graph_with_context(collected_info: Dict[str, Any], phase: str = "phase1", config_data: Dict[str, Any] = None):
    """
    Create a LangGraph ReAct graph for troubleshooting with pre-collected context
    
    Args:
        collected_info: Pre-collected diagnostic information from Phase 0
        phase: Current troubleshooting phase ("phase1" for investigation, "phase2" for action)
        config_data: Configuration data
        
    Returns:
        StateGraph: LangGraph StateGraph
    """
    if config_data is None:
        raise ValueError("Configuration data is required")
    
    # Initialize language model
    model = ChatOpenAI(
        model=config_data['llm']['model'],
        api_key=config_data['llm']['api_key'],
        base_url=config_data['llm']['api_endpoint'],
        temperature=config_data['llm']['temperature'],
        max_tokens=config_data['llm']['max_tokens']
    )
    
    # Define function to call the model with pre-collected context
    def call_model(state: MessagesState):
        logging.info(f"Processing state with {len(state['messages'])} messages")
        
        # Add comprehensive system prompt with pre-collected context
        phase_specific_guidance = ""
        if phase == "phase1":
            phase_specific_guidance = """
You are currently in Phase 1 (Investigation). Your primary task is to perform comprehensive root cause analysis and evidence collection using investigation tools only.

PHASE 1 TOOLS AVAILABLE (24 investigation tools):
- Knowledge Graph Analysis (7 tools): kg_get_entity_info, kg_get_related_entities, kg_get_all_issues, kg_find_path, kg_get_summary, kg_analyze_issues, kg_print_graph
- Read-only Kubernetes (4 tools): kubectl_get, kubectl_describe, kubectl_logs, kubectl_exec (read-only)
- CSI Baremetal Info (6 tools): kubectl_get_drive, kubectl_get_csibmnode, kubectl_get_availablecapacity, kubectl_get_logicalvolumegroup, kubectl_get_storageclass, kubectl_get_csidrivers
- System Information (5 tools): df_command, lsblk_command, mount_command, dmesg_command, journalctl_command
- Hardware Information (2 tools): smartctl_check, ssh_execute (read-only)

PHASE 1 RESTRICTIONS:
- NO destructive operations (no kubectl_apply, kubectl_delete, fsck_check)
- NO test resource creation
- NO hardware modifications
- FOCUS on comprehensive investigation and root cause analysis

ROOT CAUSE ANALYSIS REQUIREMENTS:
1. Knowledge Graph Analysis
   - MUST use kg_get_all_issues first to identify existing issues
   - Use kg_analyze_issues to identify patterns and relationships
   - Cross-reference issues with system metrics and logs
   - Calculate probability scores for each potential cause

2. Issue Classification
   - Categorize issues by:
     * Severity (critical/high/medium/low)
     * Type (hardware/software/configuration/permission)
     * Scope (pod/node/cluster level)
   - Identify primary and secondary issues
   - Calculate impact radius for each issue

3. Evidence Collection
   - List all supporting evidence for each issue
   - Include relevant logs, metrics, and events
   - Document relationship patterns between components
   - Track issue occurrence frequency and timing

4. Impact Analysis
   - Document affected components
   - Calculate service impact percentage
   - Identify potential cascade effects
   - Estimate time-to-impact if not addressed

DIAGNOSTIC PROCESS:
Follow this structured process for local HDD/SSD/NVMe disks managed by CSI Baremetal:
a. **Knowledge Graph Analysis**: First use kg_get_all_issues and kg_analyze_issues
b. **Confirm Issue**: Use kubectl_logs and kubectl_describe for error identification
c. **Verify Configurations**: Check Pod, PVC, PV configurations and relationships
d. **Check CSI Driver**: Verify driver status and resources
e. **Verify Node Health**: Check for node-level issues
f. **Check Permissions**: Verify security settings
g. **Inspect Control Plane**: Review controller/scheduler logs
h. **Test Hardware**: Check disk health and performance
i. **Pattern Analysis**: Identify recurring patterns and relationships

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

Remember to provide clear, concise explanations and avoid technical jargon where possible. The goal is to present a comprehensive understanding of the current state of the system and the issues it's facing.

EXECUTION GUIDELINES:
1. Root Cause Analysis:
   - Start with Knowledge Graph tools
   - Progress from high-severity to low-severity issues
   - Document all possible causes with probability rankings
   - Include comprehensive evidence for each cause
   - List all potential impacts and risks

2. Fix Plan Generation:
   - Order steps by priority and dependencies
   - Include clear success criteria for each step
   - Provide specific commands and parameters
   - Include verification steps after each action
   - Document rollback procedures
   - Estimate time for each step

3. Quality Requirements:
   - All steps must be specific and actionable
   - Include command parameters and expected outputs
   - Provide clear verification methods
   - Document prerequisites and dependencies
   - Include safety checks and validations

Remember: You have 50 tool usage attempts. Prioritize critical issues and gather comprehensive evidence before proposing fixes.
"""
        elif phase == "phase2":
            phase_specific_guidance = """
You are currently in Phase 2 (Action/Remediation). You have access to all Phase 1 investigation tools PLUS action tools for implementing fixes.

PHASE 2 TOOLS AVAILABLE (34+ tools):
All Phase 1 tools (24 investigation tools) PLUS:
- Kubernetes Action Tools (2): kubectl_apply, kubectl_delete
- Hardware Action Tools (2): fio_performance_test, fsck_check
- Test Pod Creation (3): create_test_pod, create_test_pvc, create_test_storage_class
- Volume Testing (4): run_volume_io_test, validate_volume_mount, test_volume_permissions, run_volume_stress_test
- Resource Cleanup (5): cleanup_test_resources, list_test_resources, cleanup_specific_test_pod, cleanup_orphaned_pvs, force_cleanup_stuck_resources

PHASE 2 CAPABILITIES:
- Execute remediation actions based on Phase 1 findings
- Create test resources to validate fixes
- Run comprehensive volume testing
- Perform hardware diagnostics and repairs
- Clean up test resources after validation

REMEDIATION PROCESS:
1. Review Phase 1 findings and root cause analysis
2. Implement fixes in order of priority and dependencies
3. Create test resources to validate each fix
4. Run volume tests to ensure functionality
5. Clean up test resources
6. Verify final resolution status

SAFETY REQUIREMENTS:
- Always backup data before destructive operations
- Use test resources for validation before affecting production
- Follow proper cleanup procedures
- Verify each step before proceeding to the next
- Document all changes and their outcomes

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
        
        # Prepare context from collected information
        context_summary = f"""
=== PRE-COLLECTED DIAGNOSTIC CONTEXT ===
Instructions:
    You can use the pre-collected diagnostic information to understand the current state of the Kubernetes cluster and the volume I/O issues being faced. Use this information to guide your troubleshooting process.

Knowledge Graph Summary:
{json.dumps(collected_info.get('knowledge_graph_summary', {}), indent=2)}

Pod Information:
{collected_info.get('pod_info', {}).get('description', 'No pod information available')[:2000]}

PVC Information:
{str(collected_info.get('pvc_info', {}))[:2000]}

PV Information:
{str(collected_info.get('pv_info', {}))[:2000]}

Node Information Summary:
{str(collected_info.get('node_info', {}))[:2000]}

CSI Driver Information:
{str(collected_info.get('csi_driver_info', {}))[:2000]}

System Information:
{str(collected_info.get('system_info', {}))[:2000]}

<<< Current Issues >>>
Issues Summary:
{str(collected_info.get('issues', {}))[:2000]}

=== END PRE-COLLECTED CONTEXT ===
"""

        final_output_example = """ 
=== FINAL OUTPUT EXAMPLE ===
1. Summary of Findings:
- The pod "test-pod-1-0" in namespace "default" is running and ready, with the volume mounted at /usr/share/storop-nginx/html-1.
- The PVC "www-1-test-pod-1-0" and PV "pvc-8005fc35-9987-4874-a1a0-929c439d3cf7" are bound and use local path provisioner storage class "standard".
- The PV uses a hostPath volume at /var/local-path-provisioner/pvc-8005fc35-9987-4874-a1a0-929c439d3cf7_default_www-1-test-pod-1-0 on node "kind-control-plane".
- The node "kind-control-plane" is Ready with no disk pressure or memory pressure.
- The volume is mounted on /dev/sda2 partition on the node, which has 72% usage.
- The Knowledge Graph shows no issues related to drives, CSI Baremetal resources, or volumes.
- However, enhanced log analysis detected multiple medium severity kernel log patterns on the node related to nvme errors, ssd failures, disk timeouts, scsi errors, ata errors, bad sectors, I/O errors, filesystem errors, mount failures, and CSI errors.
- The CSI Baremetal driver resources (drives, csibmnode, available capacity, lvg, volumes) are not present in the cluster, indicating the CSI Baremetal driver may not be installed or active.
- The storage class used is "rancher.io/local-path", which is a local path provisioner, not CSI Baremetal.

2. Detailed Analysis:
Primary Issues:
- The volume is provisioned using rancher.io/local-path provisioner, not CSI Baremetal. This means the volume is a hostPath directory on the node's filesystem (/var/local-path-provisioner/...), backed by the node's local disk partition /dev/sda2.
- The node's kernel logs show multiple medium severity disk-related errors (nvme, ssd, disk timeout, scsi, ata, bad sectors, I/O, filesystem, mount, CSI errors). These indicate underlying hardware or driver issues on the node's local disk subsystem.
- The CSI Baremetal driver resources are missing, so the CSI Baremetal driver is not managing any drives or volumes in this cluster.
- The pod's volume mount permissions are wide open (drwxrwxrwx), so permission issues are unlikely.
- The node is healthy from Kubernetes perspective (Ready, no disk pressure), but kernel logs indicate disk subsystem problems.

Secondary Issues:
- The absence of CSI Baremetal driver resources suggests the cluster is not using CSI Baremetal for local volumes, which may be a misconfiguration if CSI Baremetal is expected.
- The local path provisioner may not handle disk errors or recovery as robustly as CSI Baremetal.

System Metrics:
- Disk usage on /dev/sda2 is 72%, which is moderate.
- No other abnormal system metrics reported.

Environmental Factors:
- The node is a single node cluster (kind-control-plane).
- The storage class is rancher.io/local-path, not CSI Baremetal.

3. Relationship Analysis:
- The pod uses a PVC bound to a PV that uses local path provisioner storage class.
- The PV maps to a hostPath directory on the node's local disk partition.
- Kernel logs on the node show disk errors that could cause volume I/O errors in the pod.
- The absence of CSI Baremetal driver resources means no CSI Baremetal management or monitoring of drives.

4. Investigation Process:
- Checked pod status and volume mounts.
- Retrieved PVC and PV details to confirm volume provisioning method.
- Checked node status and disk usage.
- Reviewed kernel log pattern issues from pre-collected data.
- Checked CSI Baremetal driver resources presence.
- Verified storage class used by PVC/PV.

5. Potential Root Causes:
- Underlying hardware or driver issues on node's local disk (/dev/sda2) causing I/O errors.
- Use of local path provisioner instead of CSI Baremetal driver, leading to lack of advanced volume management and error handling.
- Missing or not installed CSI Baremetal driver in the cluster.

Likelihood:
- High confidence in disk hardware/driver issues due to kernel log patterns.
- High confidence in misconfiguration or absence of CSI Baremetal driver.

6. Open Questions:
- Is CSI Baremetal driver intended to be used in this cluster?
- Are there any recent hardware changes or failures on the node?
- Are there any pod logs showing specific I/O errors?

7. Next Steps:
- Verify if CSI Baremetal driver is installed and configured properly in the cluster.
- If CSI Baremetal is intended, install and configure it to manage local volumes.
- Check node kernel logs in detail for disk errors (dmesg, journalctl).
- Run smartctl on /dev/sda to check disk health.
- Run fio performance test on /dev/sda to check disk I/O performance.
- Consider migrating volumes to CSI Baremetal managed volumes for better reliability.
- Backup data before any disk repair or fsck operations.

Root Cause:
- The volume I/O errors are likely caused by underlying disk hardware or driver issues on the node's local disk (/dev/sda2), as indicated by multiple kernel log error patterns.
- Additionally, the cluster is not using the CSI Baremetal driver for local volume management, instead using rancher.io/local-path provisioner, which may lack advanced error handling and monitoring.

Fix Plan:
1. Verify CSI Baremetal driver installation:
   - Command: kubectl get pods -n kube-system -l app=csi-baremetal
   - Expected: CSI Baremetal driver pods running
2. If not installed, install CSI Baremetal driver according to documentation.
3. Check node kernel logs for disk errors:
   - Command: journalctl -k -b | grep -iE "nvme|ssd|disk|scsi|ata|error|fail|timeout|sector|i/o|filesystem|mount|csi"
4. Check disk health with smartctl:
   - Command: smartctl -a /dev/sda (run via SSH on node)
5. Run fio performance test:
   - Command: fio --name=read_test --filename=/dev/sda --rw=read --bs=4k --size=100M --numjobs=1 --iodepth=1 --runtime=60 --time_based --group_reporting
6. Consider migrating PVCs to CSI Baremetal managed volumes.
7. Backup data before any disk repair.
8. If disk health is bad, plan disk replacement.
9. Monitor pod logs for I/O errors after remediation.
=== END FINAL OUTPUT EXAMPLE ===

"""


        system_message = {
            "role": "system", 
            "content": f"""You are an AI assistant powering a Kubernetes volume troubleshooting system using LangGraph ReAct. Your role is to monitor and resolve volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver (csi-baremetal.dell.com). Exclude remote storage (e.g., NFS, Ceph). 

<<< Note >>>: Please provide the root cause and fix plan analysis within 30 tool calls.

{phase_specific_guidance}

Follow these strict guidelines for safe, reliable, and effective troubleshooting:

1. **Knowledge Graph Prioritization**:
   - ALWAYS check the Knowledge Graph FIRST before using command execution tools.
   - Use kg_get_entity_info to retrieve detailed information about specific entities.
   - Use kg_get_related_entities to understand relationships between components.
   - Use kg_get_all_issues to find already detected issues in the system.
   - Use kg_find_path to trace dependencies between entities (e.g., Pod → PVC → PV → Drive).
   - Use kg_analyze_issues to identify patterns and root causes from the Knowledge Graph.
   - Only execute commands like kubectl or SSH when Knowledge Graph lacks needed information.

2. **Safety and Security**:
   - Only execute commands listed in `commands.allowed` in `config.yaml` (e.g., `kubectl get drive`, `smartctl -a`, `fio`).
   - Never execute commands in `commands.disallowed` (e.g., `fsck`, `chmod`, `dd`, `kubectl delete pod`) unless explicitly enabled in `config.yaml` and approved by the user in interactive mode.
   - Validate all commands for safety and relevance before execution.
   - Log all SSH commands and outputs for auditing, using secure credential handling as specified in `config.yaml`.

4. **Troubleshooting Process**:
   - Use the LangGraph ReAct module to reason about volume I/O errors based on parameters: `PodName`, `PodNamespace`, and `VolumePath`.
   - Follow this structured diagnostic process for local HDD/SSD/NVMe disks managed by CSI Baremetal:
     a. **Check Knowledge Graph**: First use Knowledge Graph tools (kg_*) to understand the current state and existing issues.
     b. **Confirm Issue**: If Knowledge Graph lacks information, run `kubectl logs <pod-name> -n <namespace>` and `kubectl describe pod <pod-name> -n <namespace>` to identify errors (e.g., "Input/Output Error", "Permission Denied", "FailedMount").
     c. **Verify Configurations**: Check Pod, PVC, and PV with `kubectl get pod/pvc/pv -o yaml`. Confirm PV uses local volume, valid disk path (e.g., `/dev/sda`), and correct `nodeAffinity`. Verify mount points with `kubectl exec <pod-name> -n <namespace> -- df -h` and `ls -ld <mount-path>`.
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
        - Check file system (if unmounted): `ssh <node-name> sudo fsck /dev/<disk-device>` (requires approval).
        - Test via Pod: Create a test Pod (use provided YAML) and check logs for "Write OK" and "Read OK".
     j. **Propose Remediations**:
        - Bad sectors: Recommend disk replacement if `kubectl get drive` or SMART shows `Health: BAD` or non-zero `Reallocated_Sector_Ct`.
        - Performance issues: Suggest optimizing I/O scheduler or replacing disk if `fio` results show low IOPS (HDD: 100–200, SSD: thousands, NVMe: tens of thousands).
        - File system corruption: Recommend `fsck` (if enabled/approved) after data backup.
        - Driver issues: Suggest restarting CSI Baremetal driver pod (if enabled/approved) if logs indicate errors.
   - Only propose remediations after analyzing diagnostic data. Ensure write/change commands (e.g., `fsck`, `kubectl delete pod`) are allowed and approved.
   - Try to find all of possible root causes before proposing any remediation steps. 

5. **Error Handling**:
   - Log all actions, command outputs, SSH results, and errors to the configured log file and stdout (if enabled).
   - Handle Kubernetes API or SSH failures with retries as specified in `config.yaml`.
   - If unresolved, provide a detailed report of findings (e.g., logs, drive status, SMART data, test results) and suggest manual intervention.

6. **Knowledge Graph Usage**:
   - Use kg_print_graph to get a human-readable overview of the entire system state.
   - First check issues with kg_get_all_issues before running diagnostic commands. this issue is critical inforamtion to find root cause
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
   - In interactive mode, format prompts as: "Proposed command: <command>. Purpose: <purpose>. Approve? (y/n)".
   - Include performance benchmarks in reports (e.g., HDD: 100–200 IOPS, SSD: thousands, NVMe: tens of thousands).
   - Log all outputs with timestamps and context for traceability.
   - **Don't output with JSON format, use plain text for better readability.**
9. **Output Example**:

{final_output_example}


Current Context Summary:
{context_summary}

You must adhere to these guidelines at all times to ensure safe, reliable, and effective troubleshooting of local disk issues in Kubernetes with the CSI Baremetal driver.
"""
        }
        
        # Ensure system message is first
        if state["messages"]:
            if isinstance(state["messages"], list):
                if state["messages"][0].type != "system":
                    state["messages"] = [system_message] + state["messages"]
            else:
                state["messages"] = [system_message, state["messages"]]
        else:
            state["messages"] = [system_message]
        
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
        
        from rich.console import Console
        from rich.panel import Panel
        
        # Create console for rich output
        console = Console()
        file_console = Console(file=open('troubleshoot.log', 'a'))
        
        # Display thinking process
        console.print(Panel(
            f"[bold cyan]LangGraph thinking process:[/bold cyan]",
            border_style="cyan",
            safe_box=True
        ))

        if response.content:
            console.print(Panel(
                f"[bold green]{response.content}[/bold green]",
                title="[bold magenta]Thinking step",
                border_style="magenta",
                safe_box=True
            ))

        # Log tool usage and thinking process with rich formatting
        if hasattr(response, 'additional_kwargs') and 'tool_calls' in response.additional_kwargs:
            try:
                for tool_call in response.additional_kwargs['tool_calls']:
                    tool_name = tool_call['function']['name']
                    
                    # Format the tool usage in a nice way
                    if 'arguments' in tool_call['function']:
                        args = tool_call['function']['arguments']
                        try:
                            # Try to parse and format JSON arguments
                            args_json = json.loads(args)
                            formatted_args = json.dumps(args_json, indent=2)
                        except:
                            # Use the raw string if not valid JSON
                            formatted_args = args
                            
                        # Print to console and log file
                        tool_panel = Panel(
                            f"[bold yellow]Tool:[/bold yellow] [green]{tool_name}[/green]\n\n"
                            f"[bold yellow]Arguments:[/bold yellow]\n[blue]{formatted_args}[/blue]",
                            title="[bold magenta]Thinking Step",
                            border_style="magenta",
                            safe_box=True
                        )
                        console.print(tool_panel)
                        file_console.print(tool_panel)
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
                        file_console.print(tool_panel)
                        
                    # Log to standard logger as well
                    logging.info(f"Model invoking tool: {tool_name}")
                    if 'arguments' in tool_call['function']:
                        logging.info(f"Tool arguments: {tool_call['function']['arguments']}")
                    else:
                        logging.info("No arguments provided for tool call")
            except Exception as e:
                # Fall back to regular logging if rich formatting fails
                logging.warning(f"Rich formatting failed for tool output: {e}")
                for tool_call in response.additional_kwargs['tool_calls']:
                    logging.info(f"Model invoking tool: {tool_call['function']['name']}")
                    if 'arguments' in tool_call['function']:
                        logging.info(f"Tool arguments: {tool_call['function']['arguments']}")
                    else:
                        logging.info("No arguments provided for tool call")
        
        return {"messages": state["messages"] + [response]}
    
    # Build state graph
    logging.info("Building state graph")
    builder = StateGraph(MessagesState)
    
    logging.info("Adding node: call_model")
    builder.add_node("call_model", call_model)
    
    # Add tools for both analysis and remediation phases
    logging.info("Importing and defining remediation tools")
    from tools import define_remediation_tools
    tools = define_remediation_tools()
    
    logging.info("Adding node: tools")
    builder.add_node("tools", ToolNode(tools))
    
    logging.info("Adding conditional edges for tools")
    builder.add_conditional_edges(
        "call_model",
        tools_condition,
        {
            "tools": "tools",
            "none": END,
            "__end__": END  # Add explicit mapping for __end__ state
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
