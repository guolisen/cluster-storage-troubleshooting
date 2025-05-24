#!/usr/bin/env python3
"""
LangGraph Graph Building Components for Kubernetes Volume I/O Error Troubleshooting

This module contains functions for creating and configuring LangGraph state graphs
used in the analysis and remediation phases of Kubernetes volume troubleshooting.
"""

import json
import logging
from typing import Dict, List, Any

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain.chat_models import init_chat_model


def create_troubleshooting_graph_with_context(collected_info: Dict[str, Any], phase: str = "analysis", config_data: Dict[str, Any] = None):
    """
    Create a LangGraph ReAct graph for troubleshooting with pre-collected context
    
    Args:
        collected_info: Pre-collected diagnostic information from Phase 0
        phase: Current troubleshooting phase ("analysis" or "remediation")
        config_data: Configuration data
        
    Returns:
        StateGraph: LangGraph StateGraph
    """
    if config_data is None:
        raise ValueError("Configuration data is required")
    
    # Initialize language model
    model = init_chat_model(
        config_data['llm']['model'],
        api_key=config_data['llm']['api_key'],
        base_url=config_data['llm']['api_endpoint'],
        temperature=config_data['llm']['temperature'],
        max_tokens=config_data['llm']['max_tokens']
    )
    
    # Define function to call the model with pre-collected context
    def call_model(state: MessagesState):
        # Add comprehensive system prompt with pre-collected context
        phase_specific_guidance = ""
        if phase == "analysis":
            phase_specific_guidance = """
You are currently in Phase 1 (Analysis). You have pre-collected diagnostic information from Phase 0 as base knowledge, but you must now use ReAct methodology to actively investigate the volume I/O issue step by step using available tools.

Your task is to:
1. Use the pre-collected data as base knowledge to understand the initial context
2. Follow the structured diagnostic process (steps a-i below) using ReAct tools for active investigation
3. Execute tools step-by-step to gather additional evidence and verify findings
4. Identify root cause(s) based on both pre-collected data and active investigation results
5. Generate a comprehensive fix plan
6. Present findings as JSON with "root_cause" and "fix_plan" keys

Follow this structured diagnostic process for local HDD/SSD/NVMe disks managed by CSI Baremetal:
a. **Confirm Issue**: Use kubectl_logs and kubectl_describe tools to identify errors (e.g., "Input/Output Error", "Permission Denied", "FailedMount")
b. **Verify Configurations**: Check Pod, PVC, and PV with kubectl_get tool. Confirm PV uses local volume, valid disk path, and correct nodeAffinity
c. **Check CSI Baremetal Driver and Resources**: Use kubectl_get tools to verify driver pods, drive status, csibmnode, available capacity, and logical volume groups
d. **Test Driver**: Consider creating test resources if needed for verification
e. **Verify Node Health**: Use kubectl_describe for nodes and check for DiskPressure
f. **Check Permissions**: Verify file system permissions and SecurityContext settings
g. **Inspect Control Plane**: Check controller and scheduler logs if needed
h. **Test Hardware Disk**: Use system diagnostic tools to check disk health and performance
i. **Propose Remediations**: Based on investigation results, provide specific remediation steps

Use available tools actively to investigate step by step - don't just rely on pre-collected data.
"""
        elif phase == "remediation":
            phase_specific_guidance = """
You are currently in Phase 2 (Remediation). Your task is to:
1. Execute the fix plan from Phase 1 using available tools
2. Respect command validation and interactive mode settings
3. Verify that issues are resolved after implementing fixes
4. Report final resolution status

Implement the fix plan safely and effectively while following security constraints.
"""
        
        # Prepare context from collected information
        context_summary = f"""
=== PRE-COLLECTED DIAGNOSTIC CONTEXT ===

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

=== END PRE-COLLECTED CONTEXT ===
"""
        system_message = {
            "role": "system", 
            "content": f"""You are an AI assistant powering a Kubernetes volume troubleshooting system using LangGraph ReAct. Your role is to monitor and resolve volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver (csi-baremetal.dell.com). Exclude remote storage (e.g., NFS, Ceph). 

{phase_specific_guidance}

Follow these strict guidelines for safe, reliable, and effective troubleshooting:

1. **Safety and Security**:
   - Only execute commands listed in `commands.allowed` in `config.yaml` (e.g., `kubectl get drive`, `smartctl -a`, `fio`).
   - Never execute commands in `commands.disallowed` (e.g., `fsck`, `chmod`, `dd`, `kubectl delete pod`) unless explicitly enabled in `config.yaml` and approved by the user in interactive mode.
   - Validate all commands for safety and relevance before execution.
   - Log all SSH commands and outputs for auditing, using secure credential handling as specified in `config.yaml`.

2. **Interactive Mode**:
   - If `troubleshoot.interactive_mode` is `true` in `config.yaml`, prompt the user before executing any command or tool with: "Proposed command: <command>. Purpose: <purpose>. Approve? (y/n)". Include a clear purpose (e.g., "Check drive health with kubectl get drive").
   - If disabled, execute allowed commands automatically, respecting `config.yaml` restrictions.

3. **Troubleshooting Process**:
   - Use the LangGraph ReAct module to reason about volume I/O errors based on parameters: `PodName`, `PodNamespace`, and `VolumePath`.
   - Follow this structured diagnostic process for local HDD/SSD/NVMe disks managed by CSI Baremetal:
     a. **Confirm Issue**: Run `kubectl logs <pod-name> -n <namespace>` and `kubectl describe pod <pod-name> -n <namespace>` to identify errors (e.g., "Input/Output Error", "Permission Denied", "FailedMount").
     b. **Verify Configurations**: Check Pod, PVC, and PV with `kubectl get pod/pvc/pv -o yaml`. Confirm PV uses local volume, valid disk path (e.g., `/dev/sda`), and correct `nodeAffinity`. Verify mount points with `kubectl exec <pod-name> -n <namespace> -- df -h` and `ls -ld <mount-path>`.
     c. **Check CSI Baremetal Driver and Resources**:
        - Identify driver: `kubectl get storageclass <storageclass-name> -o yaml` (e.g., `csi-baremetal-sc-ssd`).
        - Verify driver pod: `kubectl get pods -n kube-system -l app=csi-baremetal` and `kubectl logs <driver-pod-name> -n kube-system`. Check for errors like "failed to mount".
        - Confirm driver registration: `kubectl get csidrivers`.
        - Check drive status: `kubectl get drive -o wide` and `kubectl get drive <drive-uuid> -o yaml`. Verify `Health: GOOD`, `Status: ONLINE`, `Usage: IN_USE`, and match `Path` (e.g., `/dev/sda`) with `VolumePath`.
        - Map drive to node: `kubectl get csibmnode` to correlate `NodeId` with hostname/IP.
        - Check AvailableCapacity: `kubectl get ac -o wide` to confirm size, storage class, and location (drive UUID).
        - Check LogicalVolumeGroup: `kubectl get lvg` to verify `Health: GOOD` and associated drive UUIDs.
     d. **Test Driver**: Create a test PVC/Pod using `csi-baremetal-sc-ssd` storage class (use provided YAML template). Check logs and events for read/write errors.
     e. **Verify Node Health**: Run `kubectl describe node <node-name>` to ensure `Ready` state and no `DiskPressure`. Verify disk mounting via SSH: `mount | grep <disk-path>`.
     f. **Check Permissions**: Verify file system permissions with `kubectl exec <pod-name> -n <namespace> -- ls -ld <mount-path>` and Pod `SecurityContext` settings.
     g. **Inspect Control Plane**: Check `kube-controller-manager` and `kube-scheduler` logs for provisioning/scheduling issues.
     h. **Test Hardware Disk**:
        - Identify disk: `kubectl get pv -o yaml` and `kubectl get drive <drive-uuid> -o yaml` to confirm `Path`.
        - Check health: `kubectl get drive <drive-uuid> -o yaml` and `ssh <node-name> sudo smartctl -a /dev/<disk-device>`. Verify `Health: GOOD`, zero `Reallocated_Sector_Ct` or `Current_Pending_Sector`.
        - Test performance: `ssh <node-name> sudo fio --name=read_test --filename=/dev/<disk-device> --rw=read --bs=4k --size=100M --numjobs=1 --iodepth=1 --runtime=60 --time_based --group_reporting`.
        - Check file system (if unmounted): `ssh <node-name> sudo fsck /dev/<disk-device>` (requires approval).
        - Test via Pod: Create a test Pod (use provided YAML) and check logs for "Write OK" and "Read OK".
     i. **Propose Remediations**:
        - Bad sectors: Recommend disk replacement if `kubectl get drive` or SMART shows `Health: BAD` or non-zero `Reallocated_Sector_Ct`.
        - Performance issues: Suggest optimizing I/O scheduler or replacing disk if `fio` results show low IOPS (HDD: 100–200, SSD: thousands, NVMe: tens of thousands).
        - File system corruption: Recommend `fsck` (if enabled/approved) after data backup.
        - Driver issues: Suggest restarting CSI Baremetal driver pod (if enabled/approved) if logs indicate errors.
   - Only propose remediations after analyzing diagnostic data. Ensure write/change commands (e.g., `fsck`, `kubectl delete pod`) are allowed and approved.

4. **Error Handling**:
   - Log all actions, command outputs, SSH results, and errors to the configured log file and stdout (if enabled).
   - Handle Kubernetes API or SSH failures with retries as specified in `config.yaml`.
   - If unresolved, provide a detailed report of findings (e.g., logs, drive status, SMART data, test results) and suggest manual intervention.

5. **Constraints**:
   - Restrict operations to the Kubernetes cluster and configured worker nodes; do not access external networks or resources.
   - Do not modify cluster state (e.g., delete pods, change configurations) unless explicitly allowed and approved.
   - Adhere to `troubleshoot.timeout_seconds` for the troubleshooting workflow.
   - Always recommend data backup before suggesting write/change operations (e.g., `fsck`).

6. **Output**:
   - Provide clear, concise explanations of diagnostic steps, findings, and remediation proposals.
   - In interactive mode, format prompts as: "Proposed command: <command>. Purpose: <purpose>. Approve? (y/n)".
   - Include performance benchmarks in reports (e.g., HDD: 100–200 IOPS, SSD: thousands, NVMe: tens of thousands).
   - Log all outputs with timestamps and context for traceability.

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
        
        # Import tools for both phases now
        from tools import define_remediation_tools
        tools = define_remediation_tools()
        
        # Call the model with tools for both phases (Phase 1 now actively investigates)
        response = model.bind_tools(tools).invoke(state["messages"])
        
        return {"messages": state["messages"] + [response]}
    
    # Build state graph
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    
    # Add tools for both analysis and remediation phases
    from tools import define_remediation_tools
    tools = define_remediation_tools()
    builder.add_node("tools", ToolNode(tools))
    builder.add_conditional_edges(
        "call_model",
        tools_condition,
        {
            "tools": "tools",
            "none": END
        }
    )
    builder.add_edge("tools", "call_model")
    
    builder.add_edge(START, "call_model")
    
    graph = builder.compile()
    return graph
