# Cluster Storage Troubleshooting - Main Workflow Chart

This document provides a visual representation of the main workflow in the cluster-storage-troubleshooting project.

## Overall Troubleshooting Workflow

The following diagram illustrates the complete workflow of the system, from monitoring to remediation:

```mermaid
graph TD
    start([Start]) --> monitor[Monitor Kubernetes Pods]
    monitor --> detect{Detect volume-io-error annotation?}
    detect -->|No| monitor
    detect -->|Yes| phase0[Phase 0: Information Collection]
    phase0 --> buildKG[Build Knowledge Graph]
    buildKG --> planPhase[Plan Phase: Generate Investigation Plan]
    planPhase --> phase1[Phase 1: ReAct Investigation]
    phase1 --> analyzeIssues[Analyze Issues]
    analyzeIssues --> requiresFix{Requires Fix?}
    requiresFix -->|Yes| phase2[Phase 2: Remediation]
    requiresFix -->|No| skipPhase2[Skip Phase 2]
    phase2 --> complete[Complete Troubleshooting]
    skipPhase2 --> complete
    complete --> report[Generate Report]
    report --> monitor
```

## Detailed Phase Workflows

### Phase 0: Information Collection

```mermaid
graph TD
    start([Start]) --> initCollector[Initialize Information Collector]
    initCollector --> discoverVolume[Discover Volume Dependency Chain]
    discoverVolume --> execPodTools[Execute Pod Discovery Tools]
    execPodTools --> execVolumeTools[Execute Volume Chain Tools]
    execVolumeTools --> execCSITools[Execute CSI Baremetal Tools]
    execCSITools --> execNodeTools[Execute Node/System Tools]
    execNodeTools --> execSMARTTools[Execute SMART Data Tools]
    execSMARTTools --> execLogTools[Execute Log Analysis Tools]
    execLogTools --> buildKG[Build Knowledge Graph]
    buildKG --> analyzeKG[Analyze Knowledge Graph]
    analyzeKG --> genFixPlan[Generate Fix Plan]
    genFixPlan --> createSummary[Create Context Summary]
    createSummary --> returnResults[Return Collected Information]
    returnResults --> END
```

### Plan Phase: Investigation Planning

```mermaid
graph TD
    start([Start]) --> initPlanner[Initialize Investigation Planner]
    initPlanner --> checkReact{Use ReAct?}
    checkReact -->|Yes| reactPlan[Generate Plan with ReAct]
    checkReact -->|No| traditionalPlan[Generate Traditional Plan]
    traditionalPlan --> ruleBasedSteps[Generate Rule-Based Steps]
    ruleBasedSteps --> staticSteps[Add Static Plan Steps]
    staticSteps --> llmRefinement[LLM Refinement]
    reactPlan --> parsePlan[Parse Investigation Plan]
    llmRefinement --> parsePlan
    parsePlan --> structurePlan[Structure Plan for Phase 1]
    structurePlan --> returnPlan[Return Investigation Plan]
    returnPlan --> END
```

### Phase 1: ReAct Investigation

```mermaid
graph TD
    start([Start]) --> initGraph[Initialize LangGraph]
    initGraph --> prepareContext[Prepare Context with Investigation Plan]
    prepareContext --> executeGraph[Execute LangGraph]
    executeGraph --> callModel[Call Model]
    callModel --> toolCall{Tool Call?}
    toolCall -->|Yes| executeTool[Execute Tool]
    executeTool --> updateState[Update State]
    updateState --> callModel
    toolCall -->|No| checkEnd{End Condition?}
    checkEnd -->|No| callModel
    checkEnd -->|Yes| extractResults[Extract Results]
    extractResults --> analyzeOutput[Analyze Output]
    analyzeOutput --> checkSpecialCase{Special Case?}
    checkSpecialCase -->|No Issues| markSkip1[Mark Skip Phase 2]
    checkSpecialCase -->|Manual Intervention| markSkip2[Mark Skip Phase 2]
    checkSpecialCase -->|Auto Fix Possible| prepareFix[Prepare Fix Plan]
    markSkip1 --> returnResults[Return Results]
    markSkip2 --> returnResults
    prepareFix --> returnResults
    returnResults --> END
```

### Phase 2: Remediation

```mermaid
graph TD
    start([Start]) --> initGraph[Initialize LangGraph]
    initGraph --> prepareContext[Prepare Context with Fix Plan]
    prepareContext --> executeGraph[Execute LangGraph]
    executeGraph --> callModel[Call Model]
    callModel --> toolCall{Tool Call?}
    toolCall -->|Yes| executeTool[Execute Tool]
    executeTool --> updateState[Update State]
    updateState --> callModel
    toolCall -->|No| checkEnd{End Condition?}
    checkEnd -->|No| callModel
    checkEnd -->|Yes| extractResults[Extract Results]
    extractResults --> validateFixes[Validate Fixes]
    validateFixes --> generateReport[Generate Remediation Report]
    generateReport --> returnResults[Return Results]
    returnResults --> END
```

## End-to-End Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant Monitor
    participant InfoCollector
    participant KnowledgeGraph
    participant PlanPhase
    participant Phase1
    participant Phase2
    participant Tools
    
    User->>Monitor: Start monitoring
    loop Monitoring Loop
        Monitor->>Monitor: Check pod annotations
        Monitor->>Monitor: Detect volume-io-error
    end
    
    Monitor->>InfoCollector: Trigger troubleshooting
    InfoCollector->>InfoCollector: Collect diagnostic data
    InfoCollector->>KnowledgeGraph: Build knowledge graph
    InfoCollector->>PlanPhase: Pass collected info
    
    PlanPhase->>KnowledgeGraph: Query knowledge graph
    PlanPhase->>PlanPhase: Generate investigation plan
    PlanPhase->>Phase1: Pass investigation plan
    
    Phase1->>KnowledgeGraph: Query knowledge graph
    Phase1->>Tools: Execute investigation tools
    Tools->>Phase1: Return tool results
    Phase1->>Phase1: Analyze issues
    Phase1->>Phase1: Generate fix plan
    Phase1->>Phase1: Check if fix needed
    
    alt Fix Needed
        Phase1->>Phase2: Pass fix plan
        Phase2->>Tools: Execute remediation tools
        Tools->>Phase2: Return tool results
        Phase2->>Phase2: Validate fixes
        Phase2->>Phase2: Generate remediation report
        Phase2->>User: Return remediation results
    else No Fix Needed
        Phase1->>User: Return analysis results
    end
```

## LangGraph ReAct Loop

The LangGraph ReAct agent operates in a loop of reasoning and acting:

```mermaid
graph TD
    subgraph "LangGraph Core Architecture"
        START([Start]) --> callModel[Call Model Node]
        callModel --> toolsCondition{Tools Condition}
        toolsCondition -->|"Tool calls detected"| serialToolNode[Serial Tool Node]
        toolsCondition -->|"No tool calls"| endCondition[End Condition Node]
        serialToolNode --> callModel
        endCondition --> endCheck{Meet End Criteria?}
        endCheck -->|Yes| END([End])
        endCheck -->|No| callModel
    end

    subgraph "SerialToolNode Execution Flow"
        serialToolNode --> parseTool[Parse Tool Call]
        parseTool --> validateTool{Valid Tool?}
        validateTool -->|No| errorMsg[Return Error Message]
        validateTool -->|Yes| executeTool[Execute Tool Sequentially]
        executeTool --> toolResponse[Create Tool Message Response]
        toolResponse --> returnToModel[Return to Call Model]
    end

    subgraph "State Flow"
        callModel -->|Update Messages State| updateState[Update State]
        serialToolNode -->|Add Tool Results to State| updateState
    end
