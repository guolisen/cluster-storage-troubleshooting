# Kubernetes Volume I/O Error Troubleshooting System

An intelligent troubleshooting system for Kubernetes pod volume I/O errors using LangGraph ReAct agents with comprehensive multi-issue analysis powered by knowledge graphs.

## 🎯 Overview

This system automatically diagnoses and resolves volume I/O errors in Kubernetes pods backed by local HDD/SSD/NVMe disks managed by the CSI Baremetal driver. It features two modes:

- **Single Mode**: Focuses on specific pod issues with targeted analysis
- **Comprehensive Mode**: Systematically analyzes ALL related storage issues across K8s/Linux/storage layers using knowledge graphs

## 🏗️ System Architecture

```mermaid
graph TB
    subgraph "User Interface"
        CLI[CLI Interface]
        Monitor[Monitor Service]
    end
    
    subgraph "Core Engine"
        TS[troubleshoot.py]
        LG[LangGraph ReAct Agent]
        
        subgraph "Analysis Modes"
            SM[Single Mode]
            CM[Comprehensive Mode]
        end
    end
    
    subgraph "Knowledge Graph System"
        KG[IssueKnowledgeGraph]
        IC[ComprehensiveIssueCollector]
        IN[IssueNode]
    end
    
    subgraph "Tools & Executors"
        Tools[kubectl/ssh Tools]
        Exec[Command Executor]
        SSH[SSH Client]
    end
    
    subgraph "Data Sources"
        K8s[Kubernetes API]
        Nodes[Cluster Nodes]
        CSI[CSI Baremetal Driver]
        Storage[Storage Systems]
    end
    
    CLI --> TS
    Monitor --> TS
    TS --> LG
    LG --> SM
    LG --> CM
    CM --> IC
    IC --> KG
    KG --> IN
    LG --> Tools
    Tools --> Exec
    Tools --> SSH
    Exec --> K8s
    SSH --> Nodes
    Tools --> CSI
    Tools --> Storage
```

## 🚀 Quick Start

### Prerequisites

- Kubernetes cluster with CSI Baremetal driver
- kubectl configured
- Python 3.8+
- Required dependencies (see `requirements.txt`)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd cluster-storage-troubleshooting
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the system:
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
```

### Basic Usage

#### Single Mode (Traditional)
```bash
python troubleshoot.py --pod-name <pod-name> --namespace <namespace> --volume-path <path>
```

#### Comprehensive Mode (Enhanced)
```bash
python run_comprehensive_mode.py --pod-name <pod-name> --namespace <namespace> --volume-path <path>
```

#### Monitoring Mode
```bash
./start_monitoring.sh
```

## 📊 Comprehensive Mode Workflow

```mermaid
flowchart TD
    Start([Start Comprehensive Analysis]) --> Init[Initialize Components]
    Init --> Collect[Collect Primary Issue]
    
    Collect --> KG[Build Knowledge Graph]
    KG --> Expand[Expand Issue Discovery]
    
    subgraph "Issue Discovery Layers"
        L1[Pod Layer Issues]
        L2[Node Layer Issues] 
        L3[Storage Layer Issues]
        L4[CSI Driver Issues]
        L5[System Layer Issues]
    end
    
    Expand --> L1
    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> L5
    
    L5 --> Analyze[Comprehensive Analysis]
    
    subgraph "Analysis Engine"
        RC[Root Cause Analysis]
        CF[Cascading Failures]
        CL[Issue Clustering]
        PR[Priority Ranking]
    end
    
    Analyze --> RC
    RC --> CF
    CF --> CL
    CL --> PR
    
    PR --> Generate[Generate Results]
    
    subgraph "Output Components"
        Summary[Summary Report]
        Visualization[Graph Visualization]
        RootCauses[Root Causes]
        FixPlan[Comprehensive Fix Plan]
        Priority[Fix Priority Order]
    end
    
    Generate --> Summary
    Generate --> Visualization
    Generate --> RootCauses
    Generate --> FixPlan
    Generate --> Priority
    
    Priority --> End([Complete Analysis])
```

## 🧠 Knowledge Graph Structure

```mermaid
graph TD
    subgraph "Issue Types"
        POD[Pod Issues]
        NODE[Node Issues]
        STORAGE[Storage Issues]
        CSI[CSI Driver Issues]
        NETWORK[Network Issues]
        SYSTEM[System Issues]
    end
    
    subgraph "Severity Levels"
        CRITICAL[Critical]
        HIGH[High]
        MEDIUM[Medium]
        LOW[Low]
    end
    
    subgraph "Relationships"
        CAUSES[Causes]
        AFFECTS[Affects]
        RELATED[Related To]
        DEPENDS[Depends On]
    end
    
    subgraph "Example Knowledge Graph"
        DiskFull[Disk Full - Critical]
        PodFail[Pod Mount Fail - High]
        LogErrors[Log Errors - Medium]
        SlowIO[Slow I/O - Medium]
        
        DiskFull -->|CAUSES| PodFail
        DiskFull -->|CAUSES| LogErrors
        PodFail -->|AFFECTS| SlowIO
        LogErrors -->|RELATED| SlowIO
    end
```

## 📁 Project Structure

```
cluster-storage-troubleshooting/
├── troubleshoot.py              # Main troubleshooting engine
├── knowledge_graph.py           # Knowledge graph implementation
├── issue_collector.py           # Comprehensive issue collector
├── run_comprehensive_mode.py    # Comprehensive mode runner
├── monitor.py                   # Background monitoring service
├── config.yaml                  # Configuration file
├── requirements.txt             # Python dependencies
├── docs/                        # Documentation
│   ├── COMPREHENSIVE_MODE.md    # Comprehensive mode guide
│   ├── PROJECT_STRUCTURE.md     # Project structure details
│   └── design_requirement.md    # Design requirements
└── scripts/                     # Utility scripts
    ├── start_monitoring.sh      # Start monitoring service
    └── run_comprehensive_troubleshoot.sh  # Run comprehensive analysis
```

## 🔧 Configuration

The system is configured via `config.yaml`:

```yaml
# LLM Configuration
llm:
  model: "gpt-4"
  api_key: "your-api-key"
  api_endpoint: "https://api.openai.com/v1"
  temperature: 0.1
  max_tokens: 4000

# Troubleshooting Settings
troubleshoot:
  interactive_mode: true
  phase: "analysis"  # analysis or remediation
  mode: "comprehensive"  # single or comprehensive

# SSH Configuration
ssh:
  enabled: true
  nodes: ["node1", "node2"]
  user: "root"
  key_path: "/path/to/ssh/key"

# Command Validation
commands:
  allowed: ["kubectl*", "smartctl*", "df", "dmesg"]
  disallowed: ["rm*", "fsck*", "dd*"]
```

## 📈 Features

### Core Capabilities
- ✅ **Intelligent Analysis**: LangGraph ReAct agents for systematic troubleshooting
- ✅ **Multi-Layer Discovery**: Pod → Node → Storage → CSI → System analysis
- ✅ **Knowledge Graphs**: Relationship mapping between issues
- ✅ **Root Cause Analysis**: True cause identification vs symptom treatment
- ✅ **Comprehensive Fix Plans**: Ordered remediation considering dependencies
- ✅ **Safety Controls**: Command validation and interactive approval
- ✅ **Monitoring Integration**: Continuous background monitoring

### Enhanced Analysis
- 🔍 **Issue Clustering**: Groups related problems by type and severity
- 🔗 **Cascading Failure Detection**: Identifies how issues propagate
- 📊 **Priority Ranking**: Intelligent fix ordering based on impact
- 🎯 **Comprehensive Scope**: Analyzes entire storage ecosystem
- 📈 **Trend Analysis**: Pattern recognition across multiple incidents

## 🎯 Use Cases

1. **Reactive Troubleshooting**: Diagnose and fix active volume I/O issues
2. **Proactive Monitoring**: Detect potential storage problems before they impact workloads
3. **Comprehensive Analysis**: Understand complex multi-component storage failures
4. **Knowledge Building**: Build organizational knowledge about storage patterns
5. **Compliance**: Maintain audit trails of storage incidents and resolutions

## 🛠️ Development

### Adding New Issue Types
1. Update `IssueType` enum in `knowledge_graph.py`
2. Add detection logic in `issue_collector.py`
3. Update analysis patterns in troubleshooting prompts

### Extending Tool Capabilities
1. Add new tools in `troubleshoot.py`
2. Update command validation in `config.yaml`
3. Test with safety controls enabled

## 📚 Documentation

- [Comprehensive Mode Guide](docs/COMPREHENSIVE_MODE.md)
- [Project Structure](docs/PROJECT_STRUCTURE.md)
- [Design Requirements](docs/design_requirement.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add comprehensive tests
4. Update documentation
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation in `/docs`
- Review configuration examples

---

**Built with ❤️ for Kubernetes storage reliability**
