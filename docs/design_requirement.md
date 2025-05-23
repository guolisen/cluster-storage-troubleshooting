# Design Requirements Document

This document outlines the design requirements and architectural decisions for the Kubernetes Volume I/O Error Troubleshooting System with comprehensive mode capabilities.

## 🎯 System Overview

### Vision Statement
Create an intelligent, comprehensive troubleshooting system that can analyze ALL related storage issues across Kubernetes/Linux/storage layers, identify root causes, understand issue relationships, and provide actionable fix plans.

### Mission
Transform storage troubleshooting from reactive single-issue resolution to proactive ecosystem-wide analysis using knowledge graphs and AI-powered reasoning.

### Project Evolution
- **Previous Design**: Single-issue focused troubleshooting ("meet one issue → give final response")
- **Current Design**: Comprehensive multi-issue analysis using knowledge graphs ("collect ALL related issues → build relationships → comprehensive analysis")

## 📋 Functional Requirements

### FR-1: Dual Mode Operation

```mermaid
graph LR
    subgraph "Operation Modes"
        Single[Single Mode<br/>- Focused analysis<br/>- Specific pod issues<br/>- Fast resolution]
        
        Comprehensive[Comprehensive Mode<br/>- Ecosystem analysis<br/>- Multi-layer discovery<br/>- Knowledge graphs]
    end
    
    User[User] --> Choice{Choose Mode}
    Choice -->|Quick Fix| Single
    Choice -->|Deep Analysis| Comprehensive
```

**Requirements**:
- **FR-1.1**: Support traditional single-issue troubleshooting mode
- **FR-1.2**: Provide comprehensive multi-issue analysis mode
- **FR-1.3**: Allow mode selection via CLI parameters
- **FR-1.4**: Maintain backward compatibility with existing usage

### FR-2: Comprehensive Issue Discovery

```mermaid
flowchart TD
    Start[Initial Issue] --> Discover[Issue Discovery Engine]
    
    subgraph "Discovery Layers"
        Discover --> Pod[Pod Layer<br/>- Pod status/events<br/>- Container logs<br/>- Volume mounts<br/>- Resource limits]
        
        Discover --> Node[Node Layer<br/>- Node conditions<br/>- Kubelet status<br/>- System resources<br/>- Mount points]
        
        Discover --> Storage[Storage Layer<br/>- Physical drives<br/>- File systems<br/>- I/O performance<br/>- SMART status]
        
        Discover --> CSI[CSI Driver Layer<br/>- Controller status<br/>- Node driver<br/>- Volume attachments<br/>- Storage classes]
        
        Discover --> System[System Layer<br/>- Kernel messages<br/>- System services<br/>- Network connectivity<br/>- Security policies]
    end
    
    Pod --> Graph[Knowledge Graph]
    Node --> Graph
    Storage --> Graph
    CSI --> Graph
    System --> Graph
```

**Requirements**:
- **FR-2.1**: Discover issues across all infrastructure layers systematically
- **FR-2.2**: Build relationships between discovered issues
- **FR-2.3**: Classify issues by type, severity, and impact
- **FR-2.4**: Support configurable discovery depth and scope

### FR-3: Knowledge Graph Engine

```mermaid
graph TD
    subgraph "Knowledge Graph Components"
        Issues[Issue Nodes<br/>- Type classification<br/>- Severity levels<br/>- Resource context<br/>- Timestamps]
        
        Relations[Relationships<br/>- CAUSES<br/>- AFFECTS<br/>- RELATED_TO<br/>- DEPENDS_ON]
        
        Analysis[Analysis Engine<br/>- Root cause identification<br/>- Cascading failure detection<br/>- Issue clustering<br/>- Priority ranking]
    end
    
    Issues --> Relations
    Relations --> Analysis
    Analysis --> Results[Comprehensive Results]
```

**Requirements**:
- **FR-3.1**: Model issues as nodes with rich metadata
- **FR-3.2**: Support multiple relationship types between issues
- **FR-3.3**: Implement graph traversal algorithms for analysis
- **FR-3.4**: Generate visual representations of issue relationships

### FR-4: Comprehensive Analysis Algorithms

```mermaid
flowchart TD
    Graph[Knowledge Graph] --> RootCause[Root Cause Analysis]
    Graph --> Cascading[Cascading Failure Detection]
    Graph --> Clustering[Issue Clustering]
    
    subgraph "Root Cause Logic"
        RootCause --> Check1{Has Incoming<br/>CAUSES edges?}
        Check1 -->|No| Primary[Primary Root Cause]
        Check1 -->|Yes| Secondary[Secondary Root Cause]
    end
    
    subgraph "Cascade Analysis"
        Cascading --> Paths[Find Impact Paths]
        Paths --> Score[Calculate Impact Scores]
    end
    
    subgraph "Clustering Logic"
        Clustering --> Group[Group by Similarity]
        Group --> Pattern[Identify Patterns]
    end
    
    Primary --> Priority[Priority Ranking]
    Secondary --> Priority
    Score --> Priority
    Pattern --> Priority
    
    Priority --> Plan[Comprehensive Fix Plan]
```

**Requirements**:
- **FR-4.1**: Identify true root causes vs symptoms
- **FR-4.2**: Map cascading failure patterns
- **FR-4.3**: Group related issues into clusters
- **FR-4.4**: Generate prioritized fix plans considering dependencies

## 🔧 Technical Requirements

### General Requirements
- **Deployment Environment**: Runs on the Kubernetes master node (host)
- **Language and Framework**: Python 3.8+ with LangGraph ReAct module for agent-based troubleshooting
- **New Components**:
  - `knowledge_graph.py`: Knowledge graph implementation
  - `issue_collector.py`: Comprehensive issue collector
  - `run_comprehensive_mode.py`: Comprehensive mode runner

### Tool Integration
- Executes Linux commands (e.g., `kubectl`, `df`, `lsblk`, `smartctl`, `fio`) to gather cluster and system information
- Uses SSH to run diagnostic commands on worker nodes hosting the affected disks
- Supports CSI Baremetal-specific commands (e.g., `kubectl get drive`, `kubectl get csibmnode`, `kubectl get ac`, `kubectl get lvg`) to inspect drive and capacity details
- All commands (read-only and write/change operations) are defined in a configuration file (`config.yaml`) with allow/deny permissions

### Configuration File Enhancement

```yaml
# Enhanced Configuration for Comprehensive Mode
comprehensive_mode:
  # Maximum issues to collect per layer
  max_issues_per_layer: 20
  
  # Analysis depth (1-5, higher = more thorough)
  analysis_depth: 3
  
  # Enable specific analysis types
  enable_cascading_analysis: true
  enable_clustering: true
  enable_trend_analysis: false
  
  # Relationship detection sensitivity
  relationship_threshold: 0.7
  
  # Output format options
  include_graph_visualization: true
  include_detailed_logs: false
  max_root_causes_displayed: 5

# LLM Configuration
llm:
  model: "gpt-4"
  api_endpoint: "https://api.openai.com/v1"
  api_key: ''
  temperature: 0.1
  max_tokens: 4000

# Troubleshooting Configuration
troubleshoot:
  timeout_seconds: 300
  interactive_mode: true
  mode: "comprehensive"  # single or comprehensive
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

# Command Validation
commands:
  allowed:
    - "kubectl*"
    - "smartctl*"
    - "df"
    - "dmesg"
    - "lsblk"
    - "fio*"
  disallowed:
    - "fsck*"
    - "rm*"
    - "dd*"
    - "mkfs*"
```

## 🏗️ System Architecture

### Comprehensive Mode Architecture

```mermaid
graph TB
    subgraph "User Interface Layer"
        CLI[CLI Interface]
        Monitor[Monitor Service]
    end
    
    subgraph "Core Engine Layer"
        TS[troubleshoot.py<br/>Main Engine]
        LG[LangGraph ReAct Agent]
        
        subgraph "Mode Selection"
            SM[Single Mode<br/>Traditional Analysis]
            CM[Comprehensive Mode<br/>Multi-Issue Analysis]
        end
    end
    
    subgraph "Knowledge Graph Layer"
        KG[IssueKnowledgeGraph<br/>Graph Management]
        IC[ComprehensiveIssueCollector<br/>Multi-Layer Discovery]
        AN[Analysis Engine<br/>Root Cause & Clustering]
    end
    
    subgraph "Tool Execution Layer"
        Tools[Tool Suite<br/>kubectl/ssh/diagnostics]
        Exec[Command Executor<br/>Validation & Security]
        SSH[SSH Client Manager<br/>Remote Execution]
    end
    
    subgraph "Data Sources"
        K8s[Kubernetes API<br/>Cluster State]
        Nodes[Worker Nodes<br/>System Diagnostics]
        CSI[CSI Baremetal Driver<br/>Storage Resources]
    end
    
    CLI --> TS
    Monitor --> TS
    TS --> LG
    LG --> SM
    LG --> CM
    CM --> IC
    IC --> KG
    KG --> AN
    LG --> Tools
    Tools --> Exec
    Tools --> SSH
    Exec --> K8s
    SSH --> Nodes
    Tools --> CSI
```

### Data Flow Architecture

```mermaid
flowchart TD
    Input[User Input<br/>Pod/Namespace/Volume] --> Mode{Select Mode}
    
    Mode -->|Single| SingleFlow[Single Mode Flow]
    Mode -->|Comprehensive| CompFlow[Comprehensive Mode Flow]
    
    subgraph "Single Mode"
        SingleFlow --> SA[Single Analysis]
        SA --> SR[Single Results]
    end
    
    subgraph "Comprehensive Mode"
        CompFlow --> Init[Initialize Collector]
        Init --> Discovery[Multi-Layer Discovery]
        
        subgraph "Discovery Process"
            Discovery --> L1[Pod Layer Issues]
            Discovery --> L2[Node Layer Issues]
            Discovery --> L3[Storage Layer Issues]
            Discovery --> L4[CSI Layer Issues]
            Discovery --> L5[System Layer Issues]
        end
        
        L1 --> BuildGraph[Build Knowledge Graph]
        L2 --> BuildGraph
        L3 --> BuildGraph
        L4 --> BuildGraph
        L5 --> BuildGraph
        
        BuildGraph --> Analyze[Comprehensive Analysis]
        
        subgraph "Analysis Types"
            Analyze --> RC[Root Cause Analysis]
            Analyze --> CF[Cascading Failures]
            Analyze --> CL[Issue Clustering]
            Analyze --> PR[Priority Ranking]
        end
        
        RC --> Format[Format Results]
        CF --> Format
        CL --> Format
        PR --> Format
        
        Format --> CR[Comprehensive Results]
    end
    
    SR --> Output[Display Output]
    CR --> Output
```

## 🔄 Workflow Specifications

### Workflow 1: Monitoring Workflow
- **Script File**: `monitor.py`
- **Purpose**: Periodically monitors all pods in the Kubernetes cluster for volume I/O errors
- **Enhanced Functionality**:
  - Detects annotation `volume-io-error:<volume-path>` indicating a volume I/O error
  - Can trigger either single or comprehensive mode based on configuration
  - Supports batch processing of multiple detected issues
  - Integrates with comprehensive analysis for pattern detection

### Workflow 2: Single Mode Troubleshooting
- **Script File**: `troubleshoot.py` (single mode)
- **Purpose**: Traditional single-issue focused troubleshooting
- **Process**: Follows existing troubleshooting steps for focused analysis

### Workflow 3: Comprehensive Mode Troubleshooting
- **Script File**: `run_comprehensive_mode.py`
- **Purpose**: Multi-issue ecosystem-wide analysis using knowledge graphs

```mermaid
flowchart TD
    Start([Start Comprehensive Analysis]) --> Init[Initialize Components]
    Init --> Collect[Collect Primary Issue]
    
    Collect --> KGBuild[Build Initial Knowledge Graph]
    KGBuild --> Expand[Expand Issue Discovery]
    
    subgraph "Layer-by-Layer Discovery"
        Expand --> PodDiscover[Pod Layer Discovery<br/>- Status & events<br/>- Logs & mounts<br/>- Resource constraints]
        
        PodDiscover --> NodeDiscover[Node Layer Discovery<br/>- Node conditions<br/>- System resources<br/>- Mount points<br/>- Kubelet status]
        
        NodeDiscover --> StorageDiscover[Storage Layer Discovery<br/>- Drive health<br/>- File systems<br/>- I/O performance<br/>- SMART data]
        
        StorageDiscover --> CSIDiscover[CSI Layer Discovery<br/>- Driver status<br/>- Volume attachments<br/>- Storage classes<br/>- AC/LVG health]
        
        CSIDiscover --> SystemDiscover[System Layer Discovery<br/>- Kernel messages<br/>- System services<br/>- Network issues<br/>- Security policies]
    end
    
    SystemDiscover --> Relationships[Build Issue Relationships]
    Relationships --> Analysis[Comprehensive Analysis]
    
    subgraph "Analysis Engine"
        Analysis --> RootCause[Root Cause Identification]
        Analysis --> Cascading[Cascading Failure Detection]
        Analysis --> Clustering[Issue Clustering]
        Analysis --> Priority[Priority Ranking]
    end
    
    RootCause --> Results[Generate Comprehensive Results]
    Cascading --> Results
    Clustering --> Results
    Priority --> Results
    
    Results --> Output[Format & Display Output]
    Output --> End([Complete Analysis])
```

## 🧠 Enhanced System Prompts

### Comprehensive Mode System Prompt

```
You are an AI assistant powering a comprehensive Kubernetes volume troubleshooting system using LangGraph ReAct and knowledge graphs. Your role is to systematically analyze ALL related storage issues across Kubernetes/Linux/storage layers, build issue relationships, and provide comprehensive root cause analysis and fix plans.

COMPREHENSIVE MODE INSTRUCTIONS:

1. **Multi-Layer Issue Discovery**:
   - Systematically collect issues from Pod, Node, Storage, CSI, and System layers
   - Use the ComprehensiveIssueCollector to discover related problems
   - Build a knowledge graph of all discovered issues and their relationships

2. **Knowledge Graph Analysis**:
   - Classify issues by type (POD_*, NODE_*, STORAGE_*, CSI_*, SYSTEM_*)
   - Assign severity levels (CRITICAL, HIGH, MEDIUM, LOW)
   - Establish relationships (CAUSES, AFFECTS, RELATED_TO, DEPENDS_ON)
   - Identify root causes vs symptoms through graph traversal

3. **Comprehensive Analysis Process**:
   a. Root Cause Identification: Find issues with no incoming CAUSES relationships
   b. Cascading Failure Detection: Map how root causes propagate through the system
   c. Issue Clustering: Group related issues by type, node, timing, or symptoms
   d. Priority Ranking: Order fixes by impact, dependencies, and feasibility

4. **Enhanced Output Requirements**:
   - Provide summary statistics (total issues, severity breakdown, primary issue)
   - Include knowledge graph visualization
   - List root causes ordered by impact
   - Show cascading failure patterns
   - Present issue clusters with dominant types
   - Generate comprehensive root cause analysis narrative
   - Provide comprehensive fix plan with priority order

5. **Safety and Validation**:
   - All existing safety requirements apply
   - Enhanced validation for comprehensive scope
   - Interactive approval for any write/change operations
   - Comprehensive logging of all discovery and analysis steps

You must collect ALL related storage issues, analyze their relationships comprehensively, and provide holistic solutions rather than addressing isolated symptoms.
```

## 📊 Performance Requirements

### Performance Characteristics

```mermaid
graph TD
    subgraph "Performance Comparison"
        Single[Single Mode<br/>Duration: 30-120s<br/>Memory: ~50MB<br/>API Calls: ~20-50]
        
        Comprehensive[Comprehensive Mode<br/>Duration: 120-300s<br/>Memory: ~200MB<br/>API Calls: ~100-500]
    end
    
    subgraph "Optimization Targets"
        Parallel[Parallel Discovery<br/>Multi-threaded collection]
        Cache[Intelligent Caching<br/>Reduce redundant calls]
        Filter[Smart Filtering<br/>Relevant issues only]
    end
```

**Requirements**:
- Single mode: Complete within 2 minutes
- Comprehensive mode: Complete within 5 minutes
- Memory usage: < 500MB peak
- API rate limiting: Respect cluster limits
- Concurrent analysis: Support up to 3 simultaneous comprehensive analyses

## 🔒 Security Requirements

### Enhanced Security Architecture

```mermaid
graph TD
    subgraph "Security Layers"
        CommandVal[Command Validation<br/>Enhanced for comprehensive scope]
        DataAccess[Data Access Control<br/>Multi-layer permissions]
        GraphSec[Knowledge Graph Security<br/>Sensitive data handling]
        OutputSec[Output Security<br/>Information disclosure control]
    end
    
    subgraph "Security Controls"
        CommandVal --> AllowList[Enhanced Allow Lists]
        CommandVal --> Validation[Comprehensive Validation]
        
        DataAccess --> RBAC[Kubernetes RBAC]
        DataAccess --> NodeAuth[Node Authentication]
        
        GraphSec --> Encryption[Data Encryption]
        GraphSec --> Anonymization[Data Anonymization]
        
        OutputSec --> Filtering[Sensitive Data Filtering]
        OutputSec --> Audit[Comprehensive Audit Logs]
    end
```

## 🧪 Testing Requirements

### Comprehensive Testing Strategy

```mermaid
graph TD
    subgraph "Test Categories"
        Unit[Unit Tests<br/>Individual components]
        Integration[Integration Tests<br/>Layer interactions]
        E2E[End-to-End Tests<br/>Complete workflows]
        Performance[Performance Tests<br/>Scale and timing]
        Security[Security Tests<br/>Attack scenarios]
    end
    
    subgraph "Comprehensive Mode Tests"
        Unit --> KGTests[Knowledge Graph Tests]
        Unit --> CollectorTests[Issue Collector Tests]
        Unit --> AnalysisTests[Analysis Algorithm Tests]
        
        Integration --> LayerTests[Multi-Layer Integration]
        Integration --> RelationTests[Relationship Building]
        
        E2E --> ScenarioTests[Failure Scenario Tests]
        E2E --> WorkflowTests[Complete Workflow Tests]
        
        Performance --> ScaleTests[Large Cluster Tests]
        Performance --> TimingTests[Analysis Timing Tests]
        
        Security --> ValidationTests[Command Validation Tests]
        Security --> AccessTests[Access Control Tests]
    end
```

## 📈 Success Metrics

### Key Performance Indicators

```mermaid
graph LR
    subgraph "Effectiveness Metrics"
        Accuracy[Root Cause Accuracy<br/>Target: >90%]
        Coverage[Issue Coverage<br/>Target: >95%]
        Resolution[Resolution Rate<br/>Target: >80%]
    end
    
    subgraph "Efficiency Metrics"
        Speed[Analysis Speed<br/>Target: <5min]
        Resources[Resource Usage<br/>Target: <500MB]
        Automation[Automation Rate<br/>Target: >70%]
    end
    
    subgraph "Quality Metrics"
        FalsePos[False Positives<br/>Target: <5%]
        Completeness[Analysis Completeness<br/>Target: >95%]
        Usability[User Satisfaction<br/>Target: >8/10]
    end
```

## 🚀 Deployment Strategy

### Deployment Architecture

```mermaid
graph TD
    subgraph "Deployment Options"
        Standalone[Standalone CLI<br/>Direct execution<br/>Manual invocation]
        
        InCluster[In-Cluster Pod<br/>Kubernetes deployment<br/>Service integration]
        
        Operator[Kubernetes Operator<br/>Custom resource management<br/>Automated operations]
        
        Service[Microservice<br/>REST API<br/>Web interface]
    end
    
    subgraph "Integration Patterns"
        Monitoring[Monitoring Integration<br/>Prometheus/Grafana]
        Alerting[Alerting Integration<br/>AlertManager/PagerDuty]
        CI_CD[CI/CD Integration<br/>Automated testing]
        Documentation[Documentation<br/>Knowledge base]
    end
```

## 📝 Documentation Requirements

### Documentation Structure

```mermaid
graph TD
    UserDocs[User Documentation] --> QuickStart[Quick Start Guide]
    UserDocs --> CompGuide[Comprehensive Mode Guide]
    UserDocs --> Troubleshooting[Troubleshooting Guide]
    
    DevDocs[Developer Documentation] --> Architecture[Architecture Guide]
    DevDocs --> API[API Reference]
    DevDocs --> Contributing[Contributing Guide]
    
    OperatorDocs[Operator Documentation] --> Deployment[Deployment Guide]
    OperatorDocs --> Configuration[Configuration Reference]
    OperatorDocs --> Monitoring[Monitoring Guide]
```

## 🔮 Future Enhancements

### Roadmap

```mermaid
timeline
    title Enhancement Roadmap
    
    Phase 1 : Core Comprehensive Mode
            : Knowledge Graph Engine
            : Multi-Layer Discovery
            : Basic Analysis Algorithms
    
    Phase 2 : Advanced Analytics
            : Machine Learning Integration
            : Predictive Analysis
            : Trend Detection
    
    Phase 3 : Automation & Integration
            : Automated Remediation
            : External System Integration
            : Advanced Visualization
    
    Phase 4 : Enterprise Features
            : Multi-Cluster Support
            : Advanced Security
            : Compliance Reporting
```

### Planned Features
- **ML-Enhanced Analysis**: Machine learning for pattern recognition and prediction
- **Automated Remediation**: Safe automated fixes for common issues
- **Advanced Visualization**: Interactive knowledge graph exploration
- **Multi-Cluster Support**: Cross-cluster issue correlation
- **Integration APIs**: REST APIs for external system integration
- **Compliance Reporting**: Automated compliance and audit reports

---

**This comprehensive design enables intelligent, systematic troubleshooting of complex storage issues across the entire Kubernetes infrastructure.**
