#!/usr/bin/env python3
"""
LangGraph Graph Building Components for Kubernetes Volume I/O Error Troubleshooting

This module contains functions for creating and configuring LangGraph state graphs
used in the analysis and remediation phases of Kubernetes volume troubleshooting.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional, Callable, Tuple

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from rich.console import Console
from rich.panel import Panel

# Configure logging (file only, no console output)
logger = logging.getLogger('langgraph')
logger.setLevel(logging.INFO)
# Don't propagate to root logger to avoid console output
logger.propagate = False

# Initialize console for rich output
console = Console()

# Create log directory if it doesn't exist
os.makedirs('logs', exist_ok=True)
log_file_path = 'logs/troubleshoot.log'
file_console = Console(file=open(log_file_path, 'a'))


def create_troubleshooting_graph_with_context(collected_info: Dict[str, Any], phase: str = "phase1", 
                                            config_data: Dict[str, Any] = None) -> StateGraph:
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
    model = _initialize_language_model(config_data)
    
    # Define function to call the model with pre-collected context
    def call_model(state: MessagesState):
        logging.info(f"Processing state with {len(state['messages'])} messages")
        
        # Prepare messages with context
        prepared_messages = _prepare_messages_with_context(state, collected_info, phase)
        state["messages"] = prepared_messages
        
        # Select tools based on phase
        tools = _select_tools_for_phase(phase)
        
        # Call the model with tools
        response = model.bind_tools(tools).invoke(state["messages"])
        
        logging.info(f"Model response: {response.content[:100]}...")
        
        # Display and log thinking process and tool usage
        _display_and_log_response(response)
        
        return {"messages": state["messages"] + [response]}
    
    # Build and return the state graph
    return _build_state_graph(call_model)


def _initialize_language_model(config_data: Dict[str, Any]) -> ChatOpenAI:
    """
    Initialize the language model with configuration
    
    Args:
        config_data: Configuration data containing LLM settings
        
    Returns:
        ChatOpenAI: Initialized language model
    """
    try:
        return ChatOpenAI(
            model=config_data['llm']['model'],
            api_key=config_data['llm']['api_key'],
            base_url=config_data['llm']['api_endpoint'],
            temperature=config_data['llm']['temperature'],
            max_tokens=config_data['llm']['max_tokens']
        )
    except KeyError as e:
        missing_key = str(e)
        raise ValueError(f"Missing required configuration key: {missing_key}")
    except Exception as e:
        raise ValueError(f"Error initializing language model: {str(e)}")


def _prepare_messages_with_context(state: MessagesState, collected_info: Dict[str, Any], 
                                 phase: str) -> List[Dict[str, str]]:
    """
    Prepare messages with context for the model
    
    Args:
        state: Current state with messages
        collected_info: Pre-collected diagnostic information
        phase: Current troubleshooting phase
        
    Returns:
        List[Dict[str, str]]: Prepared messages with context
    """
    # Get phase-specific guidance
    phase_specific_guidance = _get_phase_specific_guidance(phase)
    
    # Prepare context from collected information
    context_summary = _prepare_context_summary(collected_info)
    
    # Get example of expected output format
    final_output_example = _get_output_example()
    
    # Create system message with guidance
    system_message = _create_system_message(phase_specific_guidance)
    
    # Create context message with pre-collected context and output example
    context_message = {
        "role": "user",
        "content": f"""Pre-collected diagnostic context:
{context_summary}

OUTPUT EXAMPLE:
{final_output_example}"""
    }
    
    # Prepare message list with system message, context message, and existing user messages
    return _prepare_message_list(state["messages"], system_message, context_message)


def _get_phase_specific_guidance(phase: str) -> str:
    """
    Get phase-specific guidance for the LLM
    
    Args:
        phase: Current troubleshooting phase ("phase1" for investigation, "phase2" for action)
        
    Returns:
        str: Phase-specific guidance
    """
    if phase == "phase1":
        return """
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
"""
    elif phase == "phase2":
        return """
You are currently in Phase 2 (Action/Remediation). You have access to all Phase 1 investigation tools PLUS action tools for implementing fixes.

PHASE 2 TOOLS AVAILABLE (34+ tools):
All Phase 1 tools (24 investigation tools) PLUS:
- Kubernetes Action Tools (2): kubectl_apply, kubectl_delete
- Hardware Action Tools (2): fio_performance_test, fsck_check
- Test Pod Creation (3): create_test_pod, create_test_pvc, create_test_storage_class
- Volume Testing (4): run_volume_io_test, validate_volume_mount, test_volume_permissions, run_volume_stress_test
- Resource Cleanup (5): cleanup_test_resources, list_test_resources, cleanup_specific_test_pod, cleanup_orphaned_pvs, force_cleanup_stuck_resources

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
        return """
You are in a legacy mode. Please specify either 'phase1' for investigation or 'phase2' for action/remediation.
"""


def _prepare_context_summary(collected_info: Dict[str, Any]) -> str:
    """
    Prepare context summary from collected information
    
    Args:
        collected_info: Pre-collected diagnostic information from Phase 0
        
    Returns:
        str: Formatted context summary
    """
    # Extract and format key information from collected_info
    knowledge_graph_summary = _format_dict_for_context(
        collected_info.get('knowledge_graph_summary', {}), 2000
    )
    
    pod_info = _format_dict_for_context(
        collected_info.get('pod_info', {}), 2000
    )
    
    pvc_info = _format_dict_for_context(
        collected_info.get('pvc_info', {}), 2000
    )
    
    pv_info = _format_dict_for_context(
        collected_info.get('pv_info', {}), 2000
    )
    
    node_info = _format_dict_for_context(
        collected_info.get('node_info', {}), 2000
    )
    
    csi_driver_info = _format_dict_for_context(
        collected_info.get('csi_driver_info', {}), 2000
    )
    
    system_info = _format_dict_for_context(
        collected_info.get('system_info', {}), 2000
    )
    
    issues = _format_dict_for_context(
        collected_info.get('issues', {}), 2000
    )
    
    # Combine all information into a formatted context summary
    return f"""
=== PRE-COLLECTED DIAGNOSTIC CONTEXT ===
Instructions:
    You can use the pre-collected diagnostic information to understand the current state of the Kubernetes cluster and the volume I/O issues being faced. Use this information to guide your troubleshooting process.

Knowledge Graph Summary:
{knowledge_graph_summary}

Pod Information:
{pod_info}

PVC Information:
{pvc_info}

PV Information:
{pv_info}

Node Information Summary:
{node_info}

CSI Driver Information:
{csi_driver_info}

System Information:
{system_info}

<<< Current Issues >>>
Issues Summary:
{issues}

=== END PRE-COLLECTED CONTEXT ===
"""


def _format_dict_for_context(data: Any, max_length: int = 2000) -> str:
    """
    Format dictionary data for context summary with length limit
    
    Args:
        data: Data to format (dictionary or other)
        max_length: Maximum length of the formatted string
        
    Returns:
        str: Formatted string
    """
    try:
        if isinstance(data, dict):
            formatted = json.dumps(data, indent=2)
        else:
            formatted = str(data)
        
        # Truncate if too long
        if len(formatted) > max_length:
            return formatted[:max_length] + "... [truncated]"
        
        return formatted
    except Exception as e:
        logging.warning(f"Error formatting data for context: {str(e)}")
        return str(data)[:max_length]


def _get_output_example() -> str:
    """
    Get an example of expected output format
    
    Returns:
        str: Example output format
    """
    return """
=== GRAPH END OUTPUT EXAMPLE ===
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
- Hardware Failure on Node Disk: Likely bad sectors or I/O errors on /dev/sda2, as indicated by kernel log patterns. Evidence: Pre-collected issues; dmesg shows boot logs but no new errors. Likelihood: High.
- Incomplete Knowledge Graph: Missing entity data in KG, preventing full analysis. Evidence: Tool errors. Likelihood: Medium.
- Configuration Mismatch: Use of local path provisioner instead of CSI Baremetal, leading to poor error handling. Evidence: PVC/PV details. Likelihood: High.
- Connectivity or Access Issues: SSH failures for smartctl, possibly due to network problems. Evidence: Tool errors. Likelihood: Medium.

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

8. Root Cause:
- The volume I/O errors are likely caused by underlying disk hardware or driver issues on the node's local disk (/dev/sda2), as indicated by multiple kernel log error patterns.
- Additionally, the cluster is not using the CSI Baremetal driver for local volume management, instead using rancher.io/local-path provisioner, which may lack advanced error handling and monitoring.

9. Fix Plan:
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
=== GRAPH END OUTPUT EXAMPLE ===
"""


def _create_system_message(phase_specific_guidance: str) -> Dict[str, str]:
    """
    Create system message with guidance for the LLM
    
    Args:
        phase_specific_guidance: Phase-specific guidance to include in the system message
        
    Returns:
        Dict[str, str]: System message dictionary
    """
    return {
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

2. **Troubleshooting Process**:
   - Use the LangGraph ReAct module to reason about volume I/O errors based on parameters: `PodName`, `PodNamespace`, and `VolumePath`.
   - Most of time the pod's volume file system type is xfs, ext4, or btrfs. 
   - Follow this structured diagnostic process for local HDD/SSD/NVMe disks managed by CSI Baremetal.

3. **Error Handling**:
   - If unresolved, provide a detailed report of findings (e.g., logs, drive status, SMART data, test results) and suggest manual intervention.

4. **Knowledge Graph Usage**:
   - Use kg_print_graph to get a human-readable overview of the entire system state.
   - First check issues with kg_get_all_issues before running diagnostic commands.
   - Use kg_get_summary to get high-level statistics about the cluster state.
   - For root cause analysis, use kg_analyze_issues to identify patterns across the system.

5. **Constraints**:
   - Restrict operations to the Kubernetes cluster and configured worker nodes; do not access external networks or resources.
   - Do not modify cluster state (e.g., delete pods, change configurations) unless explicitly allowed and approved.
   - Adhere to `troubleshoot.timeout_seconds` for the troubleshooting workflow.
   - Always recommend data backup before suggesting write/change operations (e.g., `fsck`).

6. **Output**:
   - Try to find all of possible root causes before proposing any remediation steps.
   - Provide clear, concise explanations of diagnostic steps, findings, and remediation proposals.
   - Include performance benchmarks in reports (e.g., HDD: 100–200 IOPS, SSD: thousands, NVMe: tens of thousands).
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
    # Fix Plan

You must adhere to these guidelines at all times to ensure safe, reliable, and effective troubleshooting of local disk issues in Kubernetes with the CSI Baremetal driver.
"""
    }


def _prepare_message_list(messages: List[Dict[str, str]], system_message: Dict[str, str], 
                        context_message: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Prepare message list with system message, context message, and existing user messages
    
    Args:
        messages: Existing messages
        system_message: System message to add
        context_message: Context message to add
        
    Returns:
        List[Dict[str, str]]: Updated message list
    """
    user_messages = []
    
    if messages:
        # Extract existing user messages (skip system message if present)
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") != "system":
                user_messages.append(msg)
            elif hasattr(msg, "type") and msg.type != "system":
                # Convert to dict if it's an object with type attribute
                user_messages.append({
                    "role": msg.type,
                    "content": msg.content
                })
        
        # Create new message list with system message, context message, and existing user messages
        return [system_message, context_message] + user_messages
    else:
        return [system_message, context_message]


def _select_tools_for_phase(phase: str) -> List[Any]:
    """
    Select tools based on the current phase
    
    Args:
        phase: Current troubleshooting phase ("phase1" for investigation, "phase2" for action)
        
    Returns:
        List[Any]: List of tools for the current phase
    """
    try:
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
        
        return tools
    except ImportError as e:
        logging.error(f"Error importing tools: {str(e)}")
        raise ValueError(f"Error importing tools: {str(e)}")
    except Exception as e:
        logging.error(f"Error selecting tools for phase {phase}: {str(e)}")
        raise ValueError(f"Error selecting tools for phase {phase}: {str(e)}")


def _display_and_log_response(response: Any) -> None:
    """
    Display and log thinking process and tool usage
    
    Args:
        response: Model response
    """
    # Display thinking process
    console.print(f"[bold cyan]LangGraph thinking process:[/bold cyan]")

    if hasattr(response, 'content') and response.content:
        console.print(Panel(
            f"[bold green]{response.content[:500]}...[/bold green]",
            title="[bold magenta]Thinking step",
            border_style="magenta",
            safe_box=True
        ))
    
    # Log tool usage
    _log_tool_usage(response)


def _log_tool_usage(response: Any) -> None:
    """
    Log tool usage and thinking process with rich formatting
    
    Args:
        response: Model response
    """
    if not hasattr(response, 'additional_kwargs') or 'tool_calls' not in response.additional_kwargs:
        return
    
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
        logging.warning(f"Rich formatting failed for tool output: {str(e)}")
        for tool_call in response.additional_kwargs['tool_calls']:
            logging.info(f"Model invoking tool: {tool_call['function']['name']}")
            if 'arguments' in tool_call['function']:
                logging.info(f"Tool arguments: {tool_call['function']['arguments']}")
            else:
                logging.info("No arguments provided for tool call")


def _build_state_graph(call_model: Callable) -> StateGraph:
    """
    Build and compile the state graph
    
    Args:
        call_model: Function to call the model
        
    Returns:
        StateGraph: Compiled state graph
    """
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


# Close the log file when the module is unloaded
import atexit

@atexit.register
def _cleanup():
    """
    Clean up resources when the module is unloaded
    """
    try:
        if hasattr(file_console, 'file') and file_console.file is not None:
            file_console.file.close()
    except Exception as e:
        logging.warning(f"Error closing log file: {str(e)}")
