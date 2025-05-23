# Project Structure Documentation

This document provides a detailed overview of the project structure for the Kubernetes Volume I/O Error Troubleshooting System with comprehensive mode capabilities.

## 📁 Directory Structure

```mermaid
graph TD
    Root[cluster-storage-troubleshooting/] --> Core[Core Components]
    Root --> Docs[docs/]
    Root --> Scripts[scripts/]
    Root --> Config[Configuration Files]
    Root --> Tests[Test Files]
    
    subgraph "Core Components"
        Core --> TS[troubleshoot.py]
        Core --> KG[knowledge_graph.py]
        Core --> IC[issue_collector.py]
        Core --> RCM[run_comprehensive_mode.py]
        Core --> MON[monitor.py]
    end
    
    subgraph "Documentation"
        Docs --> CM[COMPREHENSIVE_MODE.md]
        Docs --> PS[PROJECT_STRUCTURE.md]
        Docs --> DR[design_requirement.md]
    end
    
    subgraph "Scripts"
        Scripts --> SM[start_monitoring.sh]
        Scripts --> RCT[run_comprehensive_troubleshoot.sh]
    end
    
    subgraph "Configuration"
        Config --> YAML[config.yaml]
        Config --> REQ[requirements.txt]
        Config --> PY[pyproject.toml]
    end
```

## 🏗️ Component Architecture

### Core Engine Components

```mermaid
graph TB
    subgraph "Main Components"
        TS[troubleshoot.py<br/>Main Engine]
        KG[knowledge_graph.py<br/>Graph Engine]
        IC[issue_collector.py<br/>Data Collector]
        RCM[run_comprehensive_mode.py<br/>Mode Runner]
        MON[monitor.py<br/>Background Monitor]
    end
    
    subgraph "Component Relationships"
        TS --> |imports| KG
        TS --> |imports| IC
        RCM --> |uses| TS
        RCM --> |uses| IC
        RCM --> |uses| KG
        MON --> |calls| TS
        IC --> |builds| KG
    end
```

## 📄 File Descriptions

### Core Files

#### `troubleshoot.py` - Main Troubleshooting Engine
**Purpose**: Primary troubleshooting script with LangGraph ReAct agents
**Size**: ~1,200 lines
**Key Components**:
- LangGraph ReAct agent implementation
- Tool definitions (kubectl, ssh, test pod creation)
- Command execution and validation
- SSH client management
- Comprehensive mode integration

```mermaid
graph TD
    subgraph "troubleshoot.py Structure"
        Config[Configuration Loading]
        Tools[Tool Definitions]
        Agent[LangGraph Agent]
        Exec[Command Execution]
        SSH[SSH Management]
        Comp[Comprehensive Integration]
        
        Config --> Tools
        Tools --> Agent
        Agent --> Exec
        Exec --> SSH
        Agent --> Comp
    end
```

#### `knowledge_graph.py` - Knowledge Graph Engine
**Purpose**: Manages issue relationships and comprehensive analysis
**Size**: ~800 lines
**Key Components**:
- `IssueKnowledgeGraph` class
- `IssueNode` data structure
- Issue type and severity enums
- Relationship management
- Analysis algorithms

```mermaid
graph TD
    subgraph "knowledge_graph.py Structure"
        Enums[Issue Types & Severity]
        Node[IssueNode Class]
        Graph[IssueKnowledgeGraph Class]
        Relations[Relationship Management]
        Analysis[Analysis Algorithms]
        
        Enums --> Node
        Node --> Graph
        Graph --> Relations
        Graph --> Analysis
    end
```

#### `issue_collector.py` - Comprehensive Issue Collector
**Purpose**: Systematically collects issues across all infrastructure layers
**Size**: ~600 lines
**Key Components**:
- `ComprehensiveIssueCollector` class
- Layer-specific collection methods
- Issue discovery patterns
- Tool integration

```mermaid
graph TD
    subgraph "issue_collector.py Structure"
        Collector[ComprehensiveIssueCollector]
        Pod[Pod Layer Collection]
        Node[Node Layer Collection]
        Storage[Storage Layer Collection]
        CSI[CSI Layer Collection]
        System[System Layer Collection]
        
        Collector --> Pod
        Collector --> Node
        Collector --> Storage
        Collector --> CSI
        Collector --> System
    end
```

#### `run_comprehensive_mode.py` - Comprehensive Mode Runner
**Purpose**: Entry point for comprehensive analysis mode
**Size**: ~200 lines
**Key Components**:
- Command-line interface
- Configuration management
- Comprehensive analysis orchestration
- Result formatting

#### `monitor.py` - Background Monitoring Service
**Purpose**: Continuous monitoring for storage issues
**Size**: ~400 lines
**Key Components**:
- Background monitoring loop
- Issue detection patterns
- Alert generation
- Integration with troubleshooting engine

### Configuration Files

#### `config.yaml` - Main Configuration
**Purpose**: System configuration and settings
**Structure**:
```yaml
llm:              # LLM model configuration
troubleshoot:     # Troubleshooting settings
commands:         # Command validation rules
logging:          # Logging configuration
monitoring:       # Background monitoring settings
comprehensive_mode: # Comprehensive analysis settings
```

#### `requirements.txt` - Python Dependencies
**Purpose**: Python package dependencies
**Key Dependencies**:
- `langgraph`: ReAct agent framework
- `langchain`: LLM integration
- `kubernetes`: Kubernetes API client
- `paramiko`: SSH client
- `pyyaml`: YAML configuration parsing

#### `pyproject.toml` - Project Metadata
**Purpose**: Project packaging and metadata
**Contains**:
- Project description
- Author information
- Version management
- Build configuration

## 🔄 Data Flow Architecture

### Single Mode Flow

```mermaid
flowchart TD
    Input[User Input] --> Parse[Parse Arguments]
    Parse --> Config[Load Configuration]
    Config --> Init[Initialize Components]
    Init --> Agent[Create LangGraph Agent]
    Agent --> Tools[Execute Tools]
    Tools --> Analysis[Single Issue Analysis]
    Analysis --> Result[Generate Results]
    Result --> Output[Display Output]
```

### Comprehensive Mode Flow

```mermaid
flowchart TD
    Input[User Input] --> Parse[Parse Arguments]
    Parse --> Config[Load Configuration]
    Config --> Init[Initialize Components]
    Init --> Collector[Create Issue Collector]
    Collector --> Discover[Multi-Layer Discovery]
    
    subgraph "Discovery Layers"
        Discover --> L1[Pod Layer]
        Discover --> L2[Node Layer]
        Discover --> L3[Storage Layer]
        Discover --> L4[CSI Layer]
        Discover --> L5[System Layer]
    end
    
    L1 --> Graph[Build Knowledge Graph]
    L2 --> Graph
    L3 --> Graph
    L4 --> Graph
    L5 --> Graph
    
    Graph --> Analysis[Comprehensive Analysis]
    Analysis --> Format[Format Results]
    Format --> Output[Display Output]
```

## 🧩 Module Dependencies

### Import Hierarchy

```mermaid
graph TD
    subgraph "External Dependencies"
        LG[langgraph]
        LC[langchain]
        K8S[kubernetes]
        SSH[paramiko]
        YAML[pyyaml]
    end
    
    subgraph "Project Modules"
        TS[troubleshoot.py]
        KG[knowledge_graph.py]
        IC[issue_collector.py]
        RCM[run_comprehensive_mode.py]
        MON[monitor.py]
    end
    
    TS --> LG
    TS --> LC
    TS --> K8S
    TS --> SSH
    TS --> KG
    TS --> IC
    
    KG --> YAML
    IC --> K8S
    IC --> KG
    
    RCM --> TS
    RCM --> IC
    RCM --> KG
    
    MON --> TS
    MON --> K8S
```

### Component Interfaces

```mermaid
graph LR
    subgraph "Public Interfaces"
        TS_Interface[troubleshoot.py<br/>- run_comprehensive_analysis<br/>- define_tools<br/>- execute_command]
        
        KG_Interface[knowledge_graph.py<br/>- IssueKnowledgeGraph<br/>- IssueNode<br/>- generate_comprehensive_analysis]
        
        IC_Interface[issue_collector.py<br/>- ComprehensiveIssueCollector<br/>- collect_comprehensive_issues<br/>- collect_*_layer_issues]
    end
```

## 📊 File Size and Complexity

### Code Metrics

```mermaid
graph TD
    subgraph "File Complexity"
        TS_Size[troubleshoot.py<br/>~1,200 lines<br/>High Complexity]
        KG_Size[knowledge_graph.py<br/>~800 lines<br/>Medium Complexity]
        IC_Size[issue_collector.py<br/>~600 lines<br/>Medium Complexity]
        RCM_Size[run_comprehensive_mode.py<br/>~200 lines<br/>Low Complexity]
        MON_Size[monitor.py<br/>~400 lines<br/>Medium Complexity]
    end
    
    TS_Size --> |High LOC| High[High Maintenance]
    KG_Size --> |Medium LOC| Medium[Medium Maintenance]
    IC_Size --> |Medium LOC| Medium
    RCM_Size --> |Low LOC| Low[Low Maintenance]
    MON_Size --> |Medium LOC| Medium
```

## 🔒 Security Considerations

### Security Architecture

```mermaid
graph TD
    subgraph "Security Layers"
        CommandVal[Command Validation]
        SSHSecurity[SSH Security]
        ConfigSec[Configuration Security]
        APIAccess[API Access Control]
    end
    
    subgraph "Security Controls"
        CommandVal --> Allow[Allowed Commands List]
        CommandVal --> Block[Blocked Commands List]
        
        SSHSecurity --> KeyAuth[SSH Key Authentication]
        SSHSecurity --> NodeList[Allowed Nodes List]
        
        ConfigSec --> SecretMgmt[Secret Management]
        ConfigSec --> PermCheck[Permission Validation]
        
        APIAccess --> RBAC[Kubernetes RBAC]
        APIAccess --> TokenMgmt[Token Management]
    end
```

## 🧪 Testing Structure

### Test Organization

```mermaid
graph TD
    subgraph "Test Categories"
        Unit[Unit Tests]
        Integration[Integration Tests]
        E2E[End-to-End Tests]
        Security[Security Tests]
    end
    
    subgraph "Test Coverage"
        Unit --> TS_Test[troubleshoot.py tests]
        Unit --> KG_Test[knowledge_graph.py tests]
        Unit --> IC_Test[issue_collector.py tests]
        
        Integration --> API_Test[Kubernetes API tests]
        Integration --> SSH_Test[SSH integration tests]
        
        E2E --> Comp_Test[Comprehensive mode tests]
        E2E --> Monitor_Test[Monitoring tests]
        
        Security --> Command_Test[Command validation tests]
        Security --> Auth_Test[Authentication tests]
    end
```

## 📈 Performance Considerations

### Performance Profiles

```mermaid
graph TD
    subgraph "Performance Characteristics"
        Single[Single Mode<br/>Fast: 10-30s<br/>Low Memory: ~50MB]
        Comp[Comprehensive Mode<br/>Moderate: 60-180s<br/>High Memory: ~200MB]
        Monitor[Monitoring Mode<br/>Continuous<br/>Low Memory: ~30MB]
    end
    
    subgraph "Bottlenecks"
        Network[Network I/O<br/>Kubernetes API calls<br/>SSH connections]
        CPU[CPU Usage<br/>Knowledge graph analysis<br/>Pattern matching]
        Memory[Memory Usage<br/>Issue storage<br/>Graph relationships]
    end
```

## 🚀 Deployment Patterns

### Deployment Options

```mermaid
graph TD
    subgraph "Deployment Modes"
        Standalone[Standalone CLI<br/>Local execution<br/>Manual invocation]
        
        InCluster[In-Cluster Pod<br/>Kubernetes deployment<br/>Automated execution]
        
        CI_CD[CI/CD Integration<br/>Pipeline execution<br/>Automated testing]
        
        Monitor_Deploy[Monitoring Service<br/>Background daemon<br/>Continuous operation]
    end
    
    subgraph "Access Patterns"
        Direct[Direct CLI Access]
        API[REST API Access]
        WebUI[Web UI Access]
        Webhook[Webhook Integration]
    end
```

## 🔧 Configuration Management

### Configuration Hierarchy

```mermaid
graph TD
    subgraph "Configuration Sources"
        Default[Default Values]
        File[config.yaml]
        Env[Environment Variables]
        Args[Command Line Args]
    end
    
    Default --> Override1[Override Level 1]
    File --> Override1
    Override1 --> Override2[Override Level 2]
    Env --> Override2
    Override2 --> Final[Final Configuration]
    Args --> Final
```

## 📝 Documentation Structure

### Documentation Hierarchy

```mermaid
graph TD
    Root_Doc[README.md<br/>Main Overview] --> Guides[User Guides]
    Root_Doc --> Reference[Reference Docs]
    Root_Doc --> Dev[Developer Docs]
    
    Guides --> Comp_Guide[COMPREHENSIVE_MODE.md]
    Guides --> Quick[Quick Start Guide]
    
    Reference --> Structure[PROJECT_STRUCTURE.md]
    Reference --> API[API Reference]
    
    Dev --> Design[design_requirement.md]
    Dev --> Contributing[Contributing Guide]
```

## 🔄 Maintenance Guidelines

### Code Maintenance

1. **Regular Updates**:
   - Update dependencies monthly
   - Review security patches weekly
   - Update documentation with changes

2. **Code Quality**:
   - Maintain test coverage >80%
   - Follow Python PEP 8 standards
   - Regular code reviews

3. **Performance Monitoring**:
   - Track analysis execution times
   - Monitor memory usage patterns
   - Optimize critical paths

4. **Security Audits**:
   - Review command validation rules
   - Audit SSH access controls
   - Validate API permissions

---

**This project structure supports scalable, maintainable, and secure Kubernetes storage troubleshooting.**
