# Kubernetes Volume Troubleshooting Project Requirements

## Project Overview
This Python-based troubleshooting system uses the LangGraph ReAct module to monitor and resolve volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver. Deployed on the Kubernetes master node, it consists of two workflows: a monitoring workflow to detect volume I/O errors via pod annotations and a troubleshooting workflow to diagnose and resolve these errors. The system integrates Linux tools, supports SSH for worker node interactions, and uses a configuration file for customizable settings, including an interactive mode for user approval before executing commands. The troubleshooting process focuses on local storage (excluding remote storage like NFS, Ceph, or cloud-based solutions) and covers Pod, PersistentVolumeClaim (PVC), PersistentVolume (PV), CSI Baremetal driver, AvailableCapacity (AC), LogicalVolumeGroup (LVG), and hardware disk diagnostics.

## Functional Requirements

### General Requirements
- **Deployment Environment**: Runs on the Kubernetes master node (host).
- **Language and Framework**: Python 3.8+ with LangGraph ReAct module for agent-based troubleshooting.
- **Troubleshooting Modes**:
  - **Standard Mode**: Traditional two-phase approach focusing on a single root cause
  - **Comprehensive Mode**: Advanced multi-layer analysis that collects all issues before analysis
- **Tool Integration**:
  - Executes Linux commands (e.g., `kubectl`, `df`, `lsblk`, `smartctl`, `fio`) to gather cluster and system information.
  - Uses SSH to run diagnostic commands on worker nodes hosting the affected disks.
  - Supports CSI Baremetal-specific commands (e.g., `kubectl get drive`, `kubectl get csibmnode`, `kubectl get ac`, `kubectl get lvg`) to inspect drive and capacity details.
  - All commands (read-only and write/change operations) are defined in a configuration file (`config.yaml`) with allow/deny permissions.
- **Configuration File**:
  - A YAML configuration file (`config.yaml`) defines:
    - LLM settings (e.g., model, API endpoint, temperature).
    - Allowed and disallowed commands (e.g., diagnostic vs. write operations).
    - SSH connection settings (e.g., credentials, target nodes).
    - Interactive mode enable/disable flag.
    - Troubleshooting mode selection ("standard" or "comprehensive").
    - Default disablement of write/change commands (e.g., `chmod`, `fsck`, `dd`).
- **Interactive Mode**:
  - When enabled in `config.yaml`, prompts the user for permission before executing any command or tool, providing a description of the command’s purpose.
  - If disabled, executes allowed commands automatically, respecting `config.yaml` restrictions.
- **Security**:
  - Write/change commands (e.g., `fsck`, `chmod`, `dd`) are disabled by default in `config.yaml`.
  - Only commands explicitly listed in `commands.allowed` can be executed.
  - SSH commands are logged for auditing, with credentials stored securely (e.g., encrypted or via environment variables).

### Workflow 1: Monitoring Workflow
- **Script File**: `monitor.py`
- **Purpose**: Periodically monitors all pods in the Kubernetes cluster for volume I/O errors by checking pod annotations.
- **Functionality**:
  - Queries pod annotations using the Kubernetes Python client (`kubernetes.client`).
  - Detects the annotation `volume-io-error:<volume-path>` indicating a volume I/O error.
  - Invokes the troubleshooting workflow (`troubleshoot.py`) with parameters:
    - `PodName`: Name of the affected pod.
    - `PodNamespace`: Namespace of the affected pod.
    - `VolumePath`: Volume path from the annotation.
  - Monitoring interval is configurable in `config.yaml` (default: 60 seconds).
- **Dependencies**:
  - Kubernetes Python client (`kubernetes`).
  - YAML parser (`pyyaml`).
- **Error Handling**:
  - Logs errors for unreachable Kubernetes API or malformed annotations.
  - Retries failed API calls with exponential backoff (configurable in `config.yaml`).

### Workflow 2: Troubleshooting Workflow
- **Script File**: `troubleshoot.py`
- **Purpose**: Uses LangGraph ReAct module to diagnose and resolve volume I/O errors for a specified pod and volume, focusing on local HDD/SSD/NVMe disks managed by the CSI Baremetal driver.
- **Parameters** (minimum):
  - `PodName`: Name of the pod with the error.
  - `PodNamespace`: Namespace of the pod.
  - `VolumePath`: Path of the volume experiencing I/O errors.
- **Functionality**:
  - Implements a LangGraph ReAct agent to reason through diagnostic steps and propose remediations, following the enhanced troubleshooting process below.
  - Uses tools to gather information (e.g., `kubectl logs`, `kubectl describe`, `df -h`, `lsblk`, `smartctl`, `kubectl get drive`, SSH commands to worker nodes).
  - In interactive mode, prompts the user to approve each command or remediation action.
  - Write/change commands (e.g., `fsck`, `chmod`) require explicit user approval and must be enabled in `config.yaml`.
- **Troubleshooting Process** (enhanced with CSI Baremetal driver knowledge):
  1. **Confirm the Issue**:
     - Run `kubectl logs <pod-name> -n <namespace>` and `kubectl describe pod <pod-name> -n <namespace>` to identify error types (e.g., "Input/Output Error", "Permission Denied", "FailedMount").
     - Check for messages indicating disk or driver issues.
  2. **Verify Pod and Volume Configuration**:
     - Inspect configurations with `kubectl get pod/pvc/pv <name> -n <namespace> -o yaml`.
     - Confirm PV uses local volume type and points to a valid disk path (e.g., `/dev/sda`, `/dev/nvme0n1`).
     - Verify `nodeAffinity` in PV matches the correct node.
     - Check mount points: `kubectl exec <pod-name> -n <namespace> -- df -h` and `ls -ld <mount-path>`.
  3. **Check CSI Baremetal Driver and Resources**:
     - Identify driver: `kubectl get storageclass <storageclass-name> -o yaml` (e.g., `csi-baremetal-sc-ssd`).
     - Verify driver pod status: `kubectl get pods -n kube-system -l app=csi-baremetal` and `kubectl logs <driver-pod-name> -n kube-system`.
     - Check CSI driver registration: `kubectl get csidrivers`.
     - Inspect drive details: `kubectl get drive -o wide` and `kubectl get drive <drive-uuid> -o yaml` to verify `Health: GOOD`, `Status: ONLINE`, and `Usage: IN_USE`.
     - Map drive to node: `kubectl get csibmnode` to correlate `NodeId` with node hostname and IP.
     - Check AvailableCapacity (AC): `kubectl get ac -o wide` to confirm size, storage class, and location (drive UUID).
     - Check LogicalVolumeGroup (LVG): `kubectl get lvg` to verify `Health: GOOD` and associated drive UUIDs.
  4. **Test Driver Functionality**:
     - Create a test PVC and Pod to validate read/write operations:
       ```yaml
       apiVersion: v1
       kind: PersistentVolumeClaim
       metadata:
         name: test-pvc
         namespace: <namespace>
       spec:
         accessModes:
           - ReadWriteOnce
         resources:
           requests:
             storage: 1Gi
         storageClassName: csi-baremetal-sc-ssd
       ---
       apiVersion: v1
       kind: Pod
       metadata:
         name: test-pod
         namespace: <namespace>
       spec:
         containers:
         - name: test-container
           image: busybox
           command: ["/bin/sh", "-c", "echo 'Test' > /mnt/test.txt && cat /mnt/test.txt && sleep 3600"]
           volumeMounts:
           - mountPath: "/mnt"
             name: test-volume
         volumes:
         - name: test-volume
           persistentVolumeClaim:
             claimName: test-pvc
         nodeName: <node-name>
       ```
     - Apply and check: `kubectl apply -f test-pod.yaml` and `kubectl logs test-pod -n <namespace>`.
     - Verify successful read/write operations and check events for errors.
  5. **Verify Node Health**:
     - Check node status: `kubectl get nodes` and `kubectl describe node <node-name>`.
     - Confirm node is in `Ready` state with no `DiskPressure` condition.
     - Verify disk mounting via SSH: `mount | grep <disk-path>`.
  6. **Check Permissions**:
     - Verify file system permissions: `kubectl exec <pod-name> -n <namespace> -- ls -ld <mount-path>`.
     - Check Pod `SecurityContext` for UID/GID or `fsGroup` settings.
  7. **Inspect Kubernetes Control Plane**:
     - Check logs: `kubectl logs <kube-controller-manager-pod> -n kube-system` and `kubectl logs <kube-scheduler-pod> -n kube-system`.
     - Look for errors related to PVC binding or volume attachment.
  8. **Test Hardware Disk**:
     - Identify disk device: `kubectl get pv <pv-name> -o yaml` and `kubectl get drive <drive-uuid> -o yaml` to confirm `Path` (e.g., `/dev/sda`).
     - Verify drive health: `kubectl get drive <drive-uuid> -o yaml` and `ssh <node-name> sudo smartctl -a /dev/<disk-device>`.
     - Check SMART data for `Health: GOOD`, zero `Reallocated_Sector_Ct`, or `Current_Pending_Sector`.
     - Test performance: `ssh <node-name> sudo fio --name=read_test --filename=/dev/<disk-device> --rw=read --bs=4k --size=100M --numjobs=1 --iodepth=1 --runtime=60 --time_based --group_reporting`.
     - Check file system (if unmounted): `ssh <node-name> sudo fsck /dev/<disk-device>` (requires approval).
     - Test disk via Pod:
       ```yaml
       apiVersion: v1
       kind: Pod
       metadata:
         name: disk-test-pod
         namespace: <namespace>
       spec:
         containers:
         - name: test-container
           image: busybox
           command: ["/bin/sh", "-c", "dd if=/dev/zero of=/mnt/testfile bs=1M count=100 && echo 'Write OK' && dd if=/mnt/testfile of=/dev/null bs=1M && echo 'Read OK' && sleep 3600"]
           volumeMounts:
           - mountPath: "/mnt"
             name: test-volume
         volumes:
         - name: test-volume
           persistentVolumeClaim:
             claimName: <pvc-name>
         nodeName: <node-name>
       ```
     - Apply and check: `kubectl apply -f disk-test-pod.yaml` and `kubectl logs disk-test-pod -n <namespace>`.
  9. **Propose Remediations**:
     - Bad sectors: Recommend disk replacement if SMART or `kubectl get drive` shows issues (e.g., `Health: BAD`).
     - Performance issues: Suggest optimizing I/O scheduler or replacing disk if `fio` results show low IOPS.
     - File system corruption: Recommend `fsck` (if enabled/approved) after data backup.
     - Driver issues: Restart CSI Baremetal driver pod if logs indicate errors (requires approval).
- **Dependencies**:
  - LangGraph ReAct module (`langgraph`).
  - Kubernetes Python client (`kubernetes`).
  - Paramiko for SSH (`paramiko`).
  - YAML parser (`pyyaml`).
- **Error Handling**:
  - Logs all actions, including tool outputs, SSH results, and user interactions.
  - Handles SSH and API failures with retries (configurable in `config.yaml`).
  - Falls back to reporting findings if issues cannot be resolved.

## Non-Functional Requirements
- **Performance**:
  - Monitoring workflow minimizes API calls to avoid overloading the Kubernetes API server.
  - Troubleshooting workflow completes within 5 minutes (configurable timeout in `config.yaml`).
- **Scalability**:
  - Handles clusters with up to 1000 pods.
  - Configurable monitoring intervals and retry policies.
- **Security**:
  - SSH credentials stored securely (e.g., encrypted or via environment variables).
  - Commands validated against `config.yaml` allow/deny lists.
  - Write/change commands disabled by default.
- **Logging**:
  - Logs to `troubleshoot.log` and optionally stdout (configurable).
  - Log format: `%(asctime)s - %(levelname)s - %(message)s`.

## Configuration File Example (`config.yaml`)
```yaml
# LLM Configuration
llm:
  model: "gpt4-o4-mini"
  api_endpoint: "https://x.ai/api"
  api_key: ''
  temperature: 0.7
  max_tokens: 1000

# Monitoring Configuration
monitor:
  interval_seconds: 60
  api_retries: 3
  retry_backoff_seconds: 5

# Troubleshooting Configuration
troubleshoot:
  timeout_seconds: 300
  interactive_mode: true
  ssh:
    enabled: true
    user: "admin"
    key_path: "/path/to/ssh/key"
    nodes:
      - "workernode1"
      - "workernode2"
      - "masternode1"
    retries: 3
    retry_backoff_seconds: 5

# Allowed Commands
commands:
  allowed:
    - "kubectl get pod"
    - "kubectl describe pod"
    - "kubectl logs"
    - "kubectl get pvc"
    - "kubectl get pv"
    - "kubectl get storageclass"
    - "kubectl get csidrivers"
    - "kubectl get drive"
    - "kubectl get csibmnode"
    - "kubectl get ac"
    - "kubectl get lvg"
    - "kubectl top node"
    - "kubectl describe node"
    - "df -h"
    - "lsblk"
    - "cat /proc/mounts"
    - "smartctl -a"
    - "fio --name=read_test"
    - "fio --name=write_test"
    - "dmesg | grep -i disk"
    - "dmesg | grep -i error"
	- "dmesg | grep -i xfs"
    - "journalctl -u kubelet"
  disallowed:
    - "fsck"
    - "chmod"
    - "chown"
    - "dd"
    - "mkfs"
    - "rm"
    - "kubectl delete pod"

# Logging Configuration
logging:
  file: "troubleshoot.log"
  stdout: true
```

## Global Health Check Instruction (System Prompt for LLM)
You can use langchain hub to get an react prompt plus following prompt.
The enhanced system prompt incorporates CSI Baremetal driver-specific diagnostics to ensure structured, safe, and effective troubleshooting for local HDD/SSD/NVMe disks:

**System knowledge Prompt example**:
```
You are an AI assistant powering a Kubernetes volume troubleshooting system using LangGraph ReAct. Your role is to monitor and resolve volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver (csi-baremetal.dell.com). Exclude remote storage (e.g., NFS, Ceph). Follow these strict guidelines for safe, reliable, and effective troubleshooting:

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

You must adhere to these guidelines at all times to ensure safe, reliable, and effective troubleshooting of local disk issues in Kubernetes with the CSI Baremetal driver.
```

## Technical Requirements
- **Dependencies**:
  - Python packages: `kubernetes`, `langgraph`, `paramiko`, `pyyaml`.
  - Install via: `pip install kubernetes langgraph paramiko pyyaml`.
- **Kubernetes Access**:
  - Master node requires a valid `kubeconfig` or in-cluster configuration.
  - Service account with permissions to read pod metadata, annotations, PVCs, PVs, nodes, control plane logs, and CSI Baremetal resources (`drive`, `csibmnode`, `ac`, `lvg`).
- **SSH Setup**:
  - SSH private key accessible on the master node.
  - Worker nodes (`workernode1`, `workernode2`, `masternode1`) must allow SSH access for the configured user.
- **Logging**:
  - Uses Python’s `logging` module for file and stdout output.
  - Log format: `%(asctime)s - %(levelname)s - %(message)s`.

## Example Workflow Execution
1. **Monitoring Workflow**:
   - `monitor.py` runs every 60 seconds, querying pod annotations.
   - Detects `volume-io-error:/data` on pod `app-1` in namespace `default`.
   - Invokes `troubleshoot.py app-1 default /data`.

2. **Troubleshooting Workflow**:
   - ReAct agent runs `kubectl logs app-1 -n default` and detects "Input/Output Error."
   - Verifies PV/PVC configuration and identifies disk path `/dev/sda`.
   - Runs `kubectl get drive -o wide` and finds drive UUID `2a96dfec-47db-449d-9789-0d81660c2c4d` with `Path: /dev/sda`, `Health: GOOD`.
   - Uses `kubectl get csibmnode` to map drive to `masternode1`.
   - Checks `kubectl get ac` and `kubectl get lvg` to confirm capacity and volume group health.
   - Uses SSH to run `smartctl -a /dev/sda` on `masternode1`, finding non-zero `Reallocated_Sector_Ct`.
   - In interactive mode, prompts: "Proposed command: kubectl delete pod app-1 -n default. Purpose: Restart pod to attempt volume remount. Approve? (y/n)".
   - If unresolved, reports: "Bad sectors detected on /dev/sda (UUID: 2a96dfec-47db-449d-9789-0d81660c2c4d). Recommend disk replacement after data backup."

### Workflow 3: Comprehensive Troubleshooting Workflow
- **Script Files**: 
  - `issue_collector.py`: Collects all issues across different layers
  - `knowledge_graph.py`: Models relationships between issues
  - `run_comprehensive_mode.py`: Orchestrates the comprehensive analysis
  - `run_comprehensive_troubleshoot.sh`: Shell script to run comprehensive mode
- **Purpose**: Collects all issues across Kubernetes, Linux, and Storage layers before performing holistic analysis to identify multiple root causes and their relationships.
- **Parameters** (minimum):
  - `PodName`: Name of the pod with the error.
  - `PodNamespace`: Namespace of the pod.
  - `VolumePath`: Path of the volume experiencing I/O errors.
  - `--output/-o`: Output format (text or JSON, optional)
  - `--output-file/-f`: Output file path (optional)
- **Functionality**:
  - Systematically collects all issues across all three layers
  - Builds a knowledge graph to model relationships between issues
  - Uses both graph analysis and LLM to identify primary and contributing causes
  - Provides a comprehensive fix plan addressing all related issues
  - Includes verification steps to ensure all issues are resolved
- **Issue Collection Process**:
  1. **Kubernetes Layer Collection**:
     - Examines pod logs, events, status, PVC/PV configuration
     - Checks CSI driver status, drive resources, node conditions
     - Verifies control plane components and scheduling
  2. **Linux Layer Collection**:
     - Examines kernel logs, dmesg output
     - Checks filesystem state, mount options, disk space
     - Verifies inode usage, disk pressure, I/O scheduler settings
  3. **Storage Layer Collection**:
     - Examines SMART data, disk health, sector counts
     - Performs I/O performance tests with FIO
     - Verifies hardware controller status, NVMe error logs
- **Knowledge Graph Analysis**:
  - Nodes represent individual issues with metadata
  - Edges represent relationships between issues (causes, related_to)
  - Applies domain knowledge patterns to infer causal relationships
  - Identifies root causes with confidence scores
- **Dependencies**:
  - Same as the standard troubleshooting workflow
  - Additionally requires knowledge of graph algorithms and pattern matching
- **Error Handling**:
  - More robust error handling as multiple approaches are used for data collection
  - Graceful degradation if certain commands or resources are unavailable
  - Ability to produce partial analysis when complete data cannot be collected

## Future Enhancements
- Support for automated AvailableCapacity (AC) and LogicalVolumeGroup (LVG) diagnostics.
- Integration with Prometheus for real-time disk metrics.
- Automated remediation for common CSI Baremetal issues (e.g., stale mounts) with strict safeguards.
- Knowledge graph visualization for complex troubleshooting scenarios.
- Automated pattern learning from previous troubleshooting sessions.

## Reference:
react example python code:
/root/cluster-storage-troubleshooting/React_example.py
CSI knowledge:
/root/cluster-storage-troubleshooting/CSI_knowledge.txt
