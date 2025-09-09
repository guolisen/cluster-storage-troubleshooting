# Cluster Storage Troubleshooting - Components Relationship Chart

This document provides a visual representation of the high-level components and their relationships in the cluster-storage-troubleshooting project.

## Core Components Overview

The following diagram illustrates the main components of the system and their relationships:

```mermaid
graph TD
    subgraph "Core Components"
        Monitor["Monitoring Component"]
        TWF["Troubleshooting Workflow"]
        InfoCol["Information Collector"]
        KG["Knowledge Graph"]
        IP["Investigation Planner"]
        ReAct["LangGraph ReAct Agent"]
        Tools["Diagnostic Tools"]
        PM["Prompt Management"]
        MCP["MCP Integration"]
    end
    
    Monitor -->|"Triggers"| TWF
    TWF -->|"Activates Phase 0"| InfoCol
    InfoCol -->|"Populates"| KG
    InfoCol -->|"Executes"| Tools
    TWF -->|"Activates Plan Phase"| IP
    IP -->|"Uses Context From"| KG
    IP -->|"Generates Plan For"| ReAct
    TWF -->|"Activates Phase 1 & 2"| ReAct
    ReAct -->|"Queries"| KG
    ReAct -->|"Invokes"| Tools
    ReAct -->|"Gets Prompts From"| PM
    ReAct -->|"Uses"| MCP
    Tools -->|"Updates"| KG
```

## Detailed Component Relationships

### Monitoring Component Relationships

```mermaid
graph TD
    subgraph "Monitoring Component"
        Monitor["Monitor.py"]
        K8sAPI["Kubernetes API"]
        Config["Configuration"]
    end
    
    Monitor -->|"Queries"| K8sAPI
    Monitor -->|"Reads"| Config
    Monitor -->|"Triggers"| TWF["Troubleshooting Workflow"]
    K8sAPI -->|"Returns Pod Annotations"| Monitor
```

### Information Collector Relationships

```mermaid
graph TD
    subgraph "Information Collector"
        BaseCol["Base Collector"]
        VolDisc["Volume Discovery"]
        ToolExec["Tool Executors"]
        KnowBuild["Knowledge Builder"]
        MetaParse["Metadata Parsers"]
    end
    
    BaseCol -->|"Uses"| VolDisc
    BaseCol -->|"Uses"| ToolExec
    BaseCol -->|"Uses"| MetaParse
    ToolExec -->|"Executes"| Tools["Diagnostic Tools"]
    VolDisc -->|"Discovers"| K8sRes["Kubernetes Resources"]
    MetaParse -->|"Parses"| K8sRes
    KnowBuild -->|"Builds"| KG["Knowledge Graph"]
    BaseCol -->|"Uses"| KnowBuild
```

### Knowledge Graph Relationships

```mermaid
graph TD
    subgraph "Knowledge Graph"
        Entities["Entities"]
        Relationships["Relationships"]
        Issues["Issues"]
        Analysis["Analysis"]
        FixPlan["Fix Plan"]
    end
    
    Entities -->|"Connected by"| Relationships
    Entities -->|"Have"| Issues
    Entities -->|"Used in"| Analysis
    Analysis -->|"Generates"| FixPlan
    
    subgraph "Entity Types"
        Pod["Pod"]
        PVC["PVC"]
        PV["PV"]
        Drive["Drive"]
        Node["Node"]
        SC["StorageClass"]
        LVG["LVG"]
        AC["AC"]
        System["System"]
    end
    
    Pod -->|"uses"| PVC
    PVC -->|"bound_to"| PV
    PV -->|"maps_to"| Drive
    Drive -->|"located_on"| Node
    PV -->|"affinity_to"| Node
    LVG -->|"contains"| Drive
    AC -->|"available_on"| Node
```

### LangGraph ReAct Agent Relationships

```mermaid
graph TD
    subgraph "LangGraph ReAct Agent"
        StateGraph["StateGraph"]
        CallModel["Call Model Node"]
        ExecTool["Execute Tool Node"]
        EndCond["End Condition Node"]
    end
    
    StateGraph -->|"Contains"| CallModel
    StateGraph -->|"Contains"| ExecTool
    StateGraph -->|"Contains"| EndCond
    CallModel -->|"Invokes"| LLM["Large Language Model"]
    ExecTool -->|"Executes"| Tools["Diagnostic Tools"]
    LLM -->|"Generates"| ToolCalls["Tool Calls"]
    ToolCalls -->|"Processed by"| ExecTool
    ExecTool -->|"Returns Results to"| CallModel
    CallModel -->|"Checks"| EndCond
```

### Tool Registry Relationships

```mermaid
graph TD
    subgraph "Tool Registry"
        CoreTools["Core Tools"]
        DiagTools["Diagnostic Tools"]
        K8sTools["Kubernetes Tools"]
        TestTools["Testing Tools"]
    end
    
    CoreTools -->|"Includes"| KGTools["Knowledge Graph Tools"]
    CoreTools -->|"Includes"| ConfigTools["Configuration Tools"]
    CoreTools -->|"Includes"| MCPTools["MCP Adapter Tools"]
    
    DiagTools -->|"Includes"| DiskTools["Disk Analysis Tools"]
    DiagTools -->|"Includes"| MonTools["Monitoring Tools"]
    DiagTools -->|"Includes"| PerfTools["Performance Tools"]
    
    K8sTools -->|"Includes"| CoreAPI["Core API Tools"]
    K8sTools -->|"Includes"| CSITools["CSI Baremetal Tools"]
    
    TestTools -->|"Includes"| PodTools["Pod Creation Tools"]
    TestTools -->|"Includes"| CleanTools["Resource Cleanup Tools"]
    TestTools -->|"Includes"| VolTools["Volume Testing Tools"]
    
    ReAct["LangGraph ReAct Agent"] -->|"Uses"| CoreTools
    ReAct -->|"Uses"| DiagTools
    ReAct -->|"Uses"| K8sTools
    ReAct -->|"Uses"| TestTools
```

### Phased Workflow Relationships

```mermaid
graph TD
    subgraph "Phased Workflow System"
        Phase0["Phase 0: Information Collection"]
        PlanPhase["Plan Phase: Investigation Planning"]
        Phase1["Phase 1: ReAct Investigation"]
        Phase2["Phase 2: Remediation"]
    end
    
    TWF["Troubleshooting Workflow"] -->|"Orchestrates"| Phase0
    TWF -->|"Orchestrates"| PlanPhase
    TWF -->|"Orchestrates"| Phase1
    TWF -->|"Orchestrates"| Phase2
    
    Phase0 -->|"Outputs"| CollectedInfo["Collected Information"]
    CollectedInfo -->|"Input to"| PlanPhase
    PlanPhase -->|"Outputs"| InvestPlan["Investigation Plan"]
    InvestPlan -->|"Input to"| Phase1
    Phase1 -->|"Outputs"| FixPlan["Fix Plan"]
    FixPlan -->|"Input to"| Phase2
    Phase2 -->|"Outputs"| Results["Remediation Results"]
```

## System Integration Diagram

```mermaid
graph TD
    subgraph "External Systems"
        K8s["Kubernetes Cluster"]
        Nodes["Worker Nodes"]
        LLMProvider["LLM Provider"]
        MCPServers["MCP Servers"]
    end
    
    subgraph "Cluster Storage Troubleshooting System"
        Monitor["Monitoring Component"]
        TWF["Troubleshooting Workflow"]
        InfoCol["Information Collector"]
        KG["Knowledge Graph"]
        IP["Investigation Planner"]
        ReAct["LangGraph ReAct Agent"]
        Tools["Diagnostic Tools"]
        PM["Prompt Management"]
        MCP["MCP Integration"]
    end
    
    Monitor -->|"Monitors"| K8s
    InfoCol -->|"Collects from"| K8s
    InfoCol -->|"Collects from"| Nodes
    Tools -->|"Interacts with"| K8s
    Tools -->|"Interacts with"| Nodes
    ReAct -->|"Uses"| LLMProvider
    MCP -->|"Connects to"| MCPServers
    
    Monitor -->|"Triggers"| TWF
    TWF -->|"Activates"| InfoCol
    InfoCol -->|"Populates"| KG
    TWF -->|"Activates"| IP
    IP -->|"Uses"| KG
    IP -->|"Generates Plan for"| ReAct
    TWF -->|"Activates"| ReAct
    ReAct -->|"Queries"| KG
    ReAct -->|"Invokes"| Tools
    ReAct -->|"Gets Prompts from"| PM
    ReAct -->|"Uses"| MCP
