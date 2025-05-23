# Comprehensive Troubleshooting Mode

This document describes the comprehensive troubleshooting mode added to the Kubernetes Volume Troubleshooting System.

## Overview

The Comprehensive Troubleshooting Mode enhances the standard troubleshooting workflow by collecting all issues across all layers before performing analysis. This approach provides a more holistic view of the system, enabling the identification of complex, multi-layered root causes and their relationships.

## Key Components

### 1. Issue Collector (`issue_collector.py`)

The Issue Collector systematically gathers all issues across three layers:

- **Kubernetes Layer**: Issues with pods, PVCs, PVs, CSI driver, etc.
- **Linux Operating System Layer**: Issues with the kernel, filesystem, I/O, mounts, etc.
- **Storage Hardware Layer**: Issues with disks, controllers, performance, SMART data, etc.

Each issue is collected with metadata including:
- Layer (kubernetes, linux, storage)
- Component (pod_logs, filesystem, smart, etc.)
- Severity (critical, warning, info)
- Message
- Evidence (command output or data)
- Related issues (if known)

### 2. Knowledge Graph (`knowledge_graph.py`)

The Knowledge Graph models relationships between issues to identify root causes:

- **Nodes**: Individual issues from all layers
- **Edges**: Relationships between issues (causes, related_to)
- **Patterns**: Predefined knowledge about how issues relate to each other
- **Root Cause Analysis**: Algorithm to identify most likely root causes based on graph structure and domain knowledge

### 3. Comprehensive Mode Runner (`run_comprehensive_mode.py`)

The Comprehensive Mode Runner orchestrates the entire process:

1. Collects all issues using the Issue Collector
2. Builds a knowledge graph of issue relationships
3. Identifies root causes using both graph analysis and LLM evaluation
4. Provides a comprehensive fix plan addressing all related issues
5. Includes verification steps to ensure all issues are resolved

### 4. Shell Script Launcher (`run_comprehensive_troubleshoot.sh`)

A convenient script to run the comprehensive troubleshooting mode with command-line options:
- Output format (text or JSON)
- Output file specification

## Integration with Existing System

### Configuration

The comprehensive mode is configurable in `config.yaml`:

```yaml
troubleshoot:
  timeout_seconds: 300
  interactive_mode: false
  auto_fix: false
  mode: "standard" # Options: "standard" or "comprehensive"
```

### Command-Line Interface

The main `troubleshoot.py` script supports a new `--mode` parameter:

```bash
python3 troubleshoot.py <pod_name> <namespace> <volume_path> [--mode standard|comprehensive]
```

### Monitoring Integration

The `monitor.py` script respects the configured mode in `config.yaml`.

## Workflow Comparison

### Standard Mode (Original)

1. Analysis phase identifies a single root cause
2. Remediation phase addresses that specific issue
3. Focus on simplicity and speed for straightforward issues

### Comprehensive Mode (New)

1. Collection phase gathers ALL issues across ALL layers
2. Knowledge graph models relationships between issues
3. Analysis phase identifies primary and contributing factors
4. Fix plan addresses all related issues holistically
5. Verification ensures all issues are resolved

## Benefits of Comprehensive Mode

1. **Better handles complex scenarios** where multiple issues contribute to the problem
2. **Identifies hidden relationships** between seemingly unrelated issues
3. **Reduces recurrence** by addressing underlying issues rather than just symptoms
4. **Provides rich context** for operators to understand the full system state
5. **Documents all identified issues** for future reference and pattern recognition

## When to Use Each Mode

- **Standard Mode**: For quick diagnostics of simple issues
- **Comprehensive Mode**: For complex or recurring issues, or when standard mode fails to resolve the problem

## Example Output

```
===== COMPREHENSIVE VOLUME I/O ERROR ANALYSIS =====

POD: database-0 in namespace app
VOLUME PATH: /var/lib/mysql

ISSUE COUNTS:
- Total: 5
- Kubernetes layer: 2
- Linux layer: 1
- Storage layer: 2
- Critical issues: 3

PRIMARY ROOT CAUSE:
Hardware disk failure detected by SMART - bad sectors

CONTRIBUTING FACTORS:
- Filesystem mounted read-only due to errors
- Node reporting DiskPressure condition

SUMMARY OF ALL ISSUES:
Multiple issues detected across all three layers. The primary issue is bad sectors on the 
physical disk as reported by SMART. This has caused the filesystem to be remounted read-only,
which is preventing the pod from writing to its volume. Additionally, the node is experiencing
disk pressure which may be related to or exacerbating the issue.

FIX PLAN:
1. Back up all data from the affected disk
   - kubectl exec -n app database-0-backup -- rsync -av /var/lib/mysql /backup
2. Cordon the affected node to prevent new workloads
   - kubectl cordon worker-node-3
3. Replace the physical disk
   - Contact hardware team to replace the disk with UUID 3a4b7c9d
4. Drain pods from the affected node
   - kubectl drain worker-node-3 --ignore-daemonsets
5. Once new disk is installed, uncordon the node
   - kubectl uncordon worker-node-3
6. Verify filesystem is correctly formatted and mounted
   - kubectl exec -n kube-system node-checker -- mount | grep /var/lib/mysql

VERIFICATION:
1. Check SMART data on new disk shows no errors
   - smartctl -a /dev/sda | grep -i error
2. Verify pod can start successfully
   - kubectl get pod database-0 -n app
3. Confirm pod can read and write to volume
   - kubectl exec -n app database-0 -- dd if=/dev/zero of=/var/lib/mysql/test bs=1M count=10
4. Monitor for recurrence of issues for 24 hours
   - kubectl describe pod database-0 -n app | grep -i error

===== END OF REPORT =====
```

## Implementation Details

The comprehensive troubleshooting mode leverages both rules-based analysis (patterns in the knowledge graph) and machine learning (LLM analysis) to provide the most accurate root cause identification and fix plans.

### Issue Collection Methods

- **Kubernetes Layer**: Uses `kubectl` commands to gather information from the Kubernetes API
- **Linux Layer**: Uses `kubectl exec` to run commands on the relevant node
- **Storage Layer**: Uses a combination of `kubectl` commands and direct node commands via SSH

### Knowledge Graph Analysis

The knowledge graph uses several techniques to identify root causes:

1. **Pattern Matching**: Applies predefined patterns to match known issue relationships
2. **Graph Traversal**: Finds nodes with many outgoing "causes" edges
3. **Layer-Based Heuristics**: Prioritizes storage layer issues as more likely to be root causes
4. **Confidence Scoring**: Assigns confidence scores based on evidence quality and relationship strength

### Integration with LLM

The LLM enhances the analysis by:

1. Reviewing all collected issues holistically
2. Analyzing relationships identified in the knowledge graph
3. Providing expert assessment based on broader knowledge
4. Creating comprehensive fix plans that address all issues
5. Generating verification steps to ensure resolution
