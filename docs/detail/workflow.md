# Workflow Diagrams and Processes

## Overall Workflow

The Cluster Storage Troubleshooting System follows a structured workflow with multiple phases:

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
```

## Phase 0: Information Collection

The Information Collection phase gathers all necessary diagnostic data upfront:

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

## Plan Phase: Investigation Planning

The Plan Phase generates a structured investigation plan:

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

## Phase 1: ReAct Investigation

The ReAct Investigation phase executes the investigation plan:

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

## Phase 2: Remediation

The Remediation phase executes the fix plan:

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

## Knowledge Graph Construction

The Knowledge Graph is constructed from diagnostic data:

```mermaid
graph TD
    start([Start]) --> initKG[Initialize Knowledge Graph]
    initKG --> addEntities[Add Entities]
    addEntities --> addPods[Add Pod Nodes]
    addEntities --> addPVCs[Add PVC Nodes]
    addEntities --> addPVs[Add PV Nodes]
    addEntities --> addDrives[Add Drive Nodes]
    addEntities --> addNodes[Add Node Nodes]
    addEntities --> addSC[Add StorageClass Nodes]
    addEntities --> addLVG[Add LVG Nodes]
    addEntities --> addAC[Add AC Nodes]
    addEntities --> addSystem[Add System Nodes]
    addPods & addPVCs & addPVs & addDrives & addNodes & addSC & addLVG & addAC & addSystem --> addRelationships[Add Relationships]
    addRelationships --> addPodPVC[Pod → PVC: uses]
    addRelationships --> addPVCPV[PVC → PV: bound_to]
    addRelationships --> addPVDrive[PV → Drive: maps_to]
    addRelationships --> addDriveNode[Drive → Node: located_on]
    addRelationships --> addPVNode[PV → Node: affinity_to]
    addRelationships --> addLVGDrive[LVG → Drive: contains]
    addRelationships --> addACNode[AC → Node: available_on]
    addPodPVC & addPVCPV & addPVDrive & addDriveNode & addPVNode & addLVGDrive & addACNode --> addIssues[Add Issues]
    addIssues --> analyzeIssues[Analyze Issues]
    analyzeIssues --> identifyRootCauses[Identify Root Causes]
    identifyRootCauses --> identifyPatterns[Identify Patterns]
    identifyPatterns --> generateFixPlan[Generate Fix Plan]
    generateFixPlan --> END
```

## Chat Mode Workflow

The Chat Mode enables interactive troubleshooting:

```mermaid
graph TD
    start([Start]) --> checkEnabled{Chat Mode Enabled?}
    checkEnabled -->|No| standardFlow[Standard Flow]
    checkEnabled -->|Yes| checkEntryPoints[Check Entry Points]
    checkEntryPoints --> planPhaseEntry{Plan Phase Entry?}
    planPhaseEntry -->|Yes| genPlan[Generate Investigation Plan]
    genPlan --> showPlan[Show Plan to User]
    showPlan --> userFeedback1{User Feedback}
    userFeedback1 -->|Approve| continuePhase1[Continue to Phase 1]
    userFeedback1 -->|Modify| updatePlan[Update Plan]
    updatePlan --> showPlan
    userFeedback1 -->|Exit| exitProgram[Exit Program]
    planPhaseEntry -->|No| skipPlanChat[Skip Plan Chat]
    skipPlanChat --> phase1Entry{Phase 1 Entry?}
    continuePhase1 --> phase1Entry
    phase1Entry -->|Yes| runPhase1[Run Phase 1]
    phase1Entry -->|No| skipPhase1Chat[Skip Phase 1 Chat]
    runPhase1 --> showResults[Show Results to User]
    showResults --> userFeedback2{User Feedback}
    userFeedback2 -->|Approve| continuePhase2[Continue to Phase 2]
    userFeedback2 -->|Modify| updateAnalysis[Update Analysis]
    updateAnalysis --> runPhase1
    userFeedback2 -->|Exit| exitProgram
    skipPhase1Chat & continuePhase2 --> standardFlow
    standardFlow --> END
```

## Tool Execution Workflow

The system executes tools in both parallel and serial modes:

```mermaid
graph TD
    start([Start]) --> loadConfig[Load Tool Configuration]
    loadConfig --> categorizeTools[Categorize Tools]
    categorizeTools --> parallelTools[Parallel Tools]
    categorizeTools --> serialTools[Serial Tools]
    categorizeTools --> uncategorizedTools[Uncategorized Tools]
    uncategorizedTools --> defaultSerial[Default to Serial]
    parallelTools & defaultSerial --> toolCall{Tool Call}
    toolCall --> validateTool[Validate Tool]
    validateTool --> checkParallel{Is Parallel Tool?}
    checkParallel -->|Yes| execParallel[Execute in Parallel]
    checkParallel -->|No| execSerial[Execute Serially]
    execParallel & execSerial --> formatResult[Format Result]
    formatResult --> returnResult[Return Result]
    returnResult --> END
```

## MCP Integration Workflow

The MCP integration enables communication with external tools and resources:

```mermaid
graph TD
    start([Start]) --> loadConfig[Load MCP Configuration]
    loadConfig --> checkEnabled{MCP Enabled?}
    checkEnabled -->|No| skipMCP[Skip MCP]
    checkEnabled -->|Yes| initAdapter[Initialize MCP Adapter]
    initAdapter --> loadServers[Load MCP Servers]
    loadServers --> connectServers[Connect to Servers]
    connectServers --> registerTools[Register MCP Tools]
    registerTools --> phaseConfig{Configure for Phase}
    phaseConfig --> phase1Tools[Phase 1 Tools]
    phaseConfig --> phase2Tools[Phase 2 Tools]
    phaseConfig --> planPhaseTools[Plan Phase Tools]
    phase1Tools & phase2Tools & planPhaseTools --> toolCall{Tool Call}
    toolCall --> routeCall[Route to Appropriate Server]
    routeCall --> executeCall[Execute Tool Call]
    executeCall --> formatResult[Format Result]
    formatResult --> returnResult[Return Result]
    skipMCP & returnResult --> END
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
