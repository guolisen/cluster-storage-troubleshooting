# Kubernetes Cluster Storage Troubleshooting System

An enhanced AI-powered troubleshooting system for Kubernetes volume I/O errors with CSI Baremetal driver support, featuring LangGraph ReAct agents and Knowledge Graph integration for comprehensive root cause analysis.

## 🆕 Enhanced Features (v2.0)

### Core Enhancements
- **🧠 Knowledge Graph Integration**: NetworkX-based graph database for organizing diagnostic data, entities, and relationships
- **🔄 LangGraph ReAct Agents**: Intelligent AI agents for automated reasoning and tool execution
- **📊 Two-Phase Analysis**: Separate Analysis and Remediation phases with user approval controls
- **🔧 Enhanced Tool System**: 25+ specialized diagnostic tools for comprehensive troubleshooting
- **⚡ Real-time Issue Collection**: Advanced pattern matching for volume I/O error detection
- **🛡️ Enhanced Security**: Prefix/wildcard command validation with fine-grained control

### Knowledge Graph Features
- **Entity Management**: Pods, PVCs, PVs, Drives, Nodes, StorageClass, LVG, AC entities
- **Relationship Mapping**: Comprehensive entity relationships and dependencies
- **Root Cause Analysis**: Graph-based pattern detection and correlation analysis
- **Fix Plan Generation**: Automated, prioritized remediation strategies
- **Issue Tracking**: Severity-based categorization and impact assessment

### LangGraph ReAct Tools
- **Kubernetes Core**: `kubectl_get`, `kubectl_describe`, `kubectl_logs`, `kubectl_exec`
- **CSI Baremetal**: `kubectl_get_drive`, `kubectl_get_ac`, `kubectl_get_lvg`, `kubectl_get_csibmnode`
- **SSH Diagnostics**: `ssh_smartctl`, `ssh_fio_read`, `ssh_mount`, `ssh_xfs_repair_n`
- **System Analysis**: `dmesg_grep_error`, `journalctl_kubelet`, `df_h`, `lsblk`
- **Knowledge Graph**: `build_knowledge_graph`, `analyze_knowledge_graph`

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Enhanced Architecture v2.0                    │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: Analysis                │  Phase 2: Remediation       │
│  ┌─────────────────────────────┐   │  ┌─────────────────────────┐ │
│  │   Knowledge Graph Builder   │   │  │   Fix Plan Executor     │ │
│  │   ├─ Entity Recognition     │   │  │   ├─ Tool Validation    │ │
│  │   ├─ Relationship Mapping   │   │  │   ├─ Safety Checks      │ │
│  │   └─ Issue Collection       │   │  │   └─ Result Verification│ │
│  └─────────────────────────────┘   │  └─────────────────────────┘ │
│             │                      │             │                │
│  ┌─────────────────────────────┐   │  ┌─────────────────────────┐ │
│  │   LangGraph ReAct Agent     │   │  │   LangGraph ReAct Agent │ │
│  │   ├─ 25+ Diagnostic Tools   │   │  │   ├─ Remediation Tools  │ │
│  │   ├─ Pattern Detection      │   │  │   ├─ Progress Tracking  │ │
│  │   └─ Root Cause Analysis    │   │  │   └─ Success Validation │ │
│  └─────────────────────────────┘   │  └─────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Enhanced Issue Collector          │  Security & Validation      │
│  ┌─────────────────────────────┐   │  ┌─────────────────────────┐ │
│  │   Real-time Monitoring      │   │  │   Command Validation    │ │
│  │   ├─ Pattern Matching       │   │  │   ├─ Prefix/Wildcard    │ │
│  │   ├─ Severity Classification│   │  │   ├─ Interactive Mode   │ │
│  │   └─ Knowledge Graph Update │   │  │   └─ Approval Controls  │ │
│  └─────────────────────────────┘   │  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd cluster-storage-troubleshooting

# Install dependencies
pip install -r requirements.txt

# Configure the system
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
```

### 2. Configuration

Update `config.yaml` with your environment settings:

```yaml
# LLM Configuration for LangGraph ReAct
llm:
  model: "gpt-4.1-mini-2025-04-14"
  api_endpoint: "https://api.zhizengzeng.com/v1"
  api_key: "your-api-key"
  temperature: 0
  max_tokens: 32768

# Enhanced Command Validation
commands:
  allowed:
    - "kubectl *"
    - "smartctl *"
    - "fio *"
    - "xfs_repair -n *"  # Only diagnostic mode
  disallowed:
    - "rm *"
    - "kubectl delete *"
    - "mkfs *"

# Troubleshooting Configuration
troubleshoot:
  interactive_mode: false
  auto_fix: false  # Two-phase approach
  ssh:
    enabled: true
    nodes: ["worker-node-1", "worker-node-2"]
```

### 3. Usage

#### Enhanced Two-Phase Troubleshooting

```bash
# Run comprehensive troubleshooting with Knowledge Graph
python troubleshoot.py <pod_name> <namespace> <volume_path>

# Example:
python troubleshoot.py my-app default /mnt/data
```

**Phase 1 - Analysis with Knowledge Graph:**
- Builds comprehensive Knowledge Graph of cluster entities
- Executes 25+ diagnostic tools via LangGraph ReAct agent
- Performs root cause analysis using graph algorithms
- Generates prioritized fix plan
- Requires user approval before proceeding to remediation

**Phase 2 - Remediation (Optional):**
- Executes fix plan using validated tools
- Implements safety checks and progress tracking
- Verifies successful resolution
- Reports final status

#### Real-time Issue Collection

```bash
# Run enhanced issue collector
python issue_collector.py --continuous --interval 60

# Analyze specific namespace
python issue_collector.py --namespace production

# Single collection with Knowledge Graph analysis
python issue_collector.py
```

#### Monitoring and Alerting

```bash
# Start comprehensive monitoring
./start_monitoring.sh

# Run comprehensive analysis mode
./run_comprehensive_troubleshoot.sh
```

## Core Components

### 1. Knowledge Graph (`knowledge_graph.py`)
- **Entity Management**: Comprehensive entity types (Pod, PVC, PV, Drive, Node, etc.)
- **Relationship Mapping**: Complex entity relationships and dependencies
- **Issue Tracking**: Severity-based categorization and impact analysis
- **Pattern Detection**: Graph algorithms for root cause identification
- **Fix Generation**: Automated remediation plan creation

### 2. Enhanced Troubleshooter (`troubleshoot.py`)
- **LangGraph ReAct Integration**: AI-powered diagnostic reasoning
- **Two-Phase Architecture**: Analysis → User Approval → Remediation
- **25+ Specialized Tools**: Comprehensive diagnostic capabilities
- **Knowledge Graph Integration**: Entity-aware troubleshooting
- **Security Controls**: Command validation and interactive approvals

### 3. Issue Collector (`issue_collector.py`)
- **Real-time Monitoring**: Continuous volume error detection
- **Advanced Pattern Matching**: 20+ error pattern types
- **Knowledge Graph Population**: Automatic entity relationship building
- **LangGraph Analysis**: AI-powered issue prioritization
- **Severity Classification**: Dynamic severity escalation

### 4. Monitor (`monitor.py`)
- **Cluster Health Monitoring**: Comprehensive cluster status tracking
- **CSI Driver Health**: Baremetal driver status monitoring
- **Resource Tracking**: Storage capacity and utilization monitoring
- **Alert Generation**: Proactive issue detection and alerting

## Enhanced Tool Categories

### Kubernetes Core Tools
- `kubectl_get()` - Resource retrieval with YAML output
- `kubectl_describe()` - Detailed resource descriptions
- `kubectl_logs()` - Container log analysis
- `kubectl_exec()` - In-container command execution

### CSI Baremetal Specific Tools
- `kubectl_get_drive()` - Drive health and status
- `kubectl_get_csibmnode()` - Node drive mapping
- `kubectl_get_ac()` - Available capacity analysis
- `kubectl_get_lvg()` - Logical volume group status

### SSH-based Hardware Tools
- `ssh_smartctl()` - SMART disk health analysis
- `ssh_fio_read()` - I/O performance testing
- `ssh_mount()` - Filesystem mount analysis
- `ssh_xfs_repair_n()` - Filesystem diagnostic checks

### System Diagnostic Tools
- `dmesg_grep_error()` - Kernel error analysis
- `journalctl_kubelet()` - Kubelet service logs
- `df_h()` - Disk space analysis
- `lsblk()` - Block device information

### Knowledge Graph Tools
- `build_knowledge_graph()` - Entity relationship construction
- `analyze_knowledge_graph()` - Root cause analysis and fix planning

## Security Features

### Enhanced Command Validation
- **Prefix/Wildcard Matching**: Flexible command pattern validation
- **Dual Validation**: Both allowed and disallowed command lists
- **Context-Aware Permissions**: Tool-specific validation logic
- **Audit Logging**: Complete command execution tracking

### Interactive Safety Controls
- **User Approval Gates**: Interactive confirmation for sensitive operations
- **Two-Phase Architecture**: Mandatory approval between analysis and remediation
- **Granular Controls**: Per-tool approval requirements
- **Override Mechanisms**: Emergency bypass capabilities

## Configuration Reference

### LLM Configuration
```yaml
llm:
  model: "gpt-4.1-mini-2025-04-14"        # LangGraph ReAct model
  api_endpoint: "https://api.example.com"  # LLM API endpoint
  api_key: "your-api-key"                  # API authentication
  temperature: 0                           # Response randomness (0-1)
  max_tokens: 32768                        # Maximum response length
```

### Command Security
```yaml
commands:
  allowed:                    # Whitelist approach (optional)
    - "kubectl *"            # All kubectl commands
    - "smartctl *"           # SMART disk tools
    - "fio *"               # I/O performance testing
    - "xfs_repair -n *"     # Read-only filesystem checks
  disallowed:                # Blacklist approach
    - "rm *"                # File deletion
    - "kubectl delete *"    # Resource deletion
    - "mkfs *"             # Filesystem creation
    - "dd *"               # Raw disk operations
```

### Troubleshooting Behavior
```yaml
troubleshoot:
  timeout_seconds: 300        # Maximum analysis time
  interactive_mode: false     # Enable user prompts
  auto_fix: false            # Skip user approval for Phase 2
  ssh:
    enabled: true            # Enable SSH-based tools
    user: "root"            # SSH username
    key_path: "~/.ssh/id_ed25519"  # SSH private key
    nodes:                   # Allowed SSH targets
      - "worker-node-1"
      - "worker-node-2"
    retries: 3              # SSH connection retries
    retry_backoff_seconds: 5 # Retry delay
```

## Supported Error Types

### Volume I/O Errors
- Input/Output Error
- Read-only file system
- No space left on device
- Device or resource busy
- Transport endpoint disconnected

### Mount/Permission Issues
- Permission denied
- FailedMount
- MountVolume.SetUp failed
- Operation not permitted

### Filesystem Issues
- Structure needs cleaning
- Bad file descriptor
- Stale file handle
- XFS/EXT filesystem errors

### Performance Issues
- Connection timeout
- Remote I/O error
- Cannot allocate memory

## Troubleshooting Workflow

### Phase 1: Analysis with Knowledge Graph
1. **Knowledge Graph Construction**
   - Entity discovery and relationship mapping
   - Issue collection and categorization
   - Dependency analysis

2. **LangGraph ReAct Execution**
   - 25+ diagnostic tools execution
   - Pattern detection and correlation
   - Evidence collection and validation

3. **Root Cause Analysis**
   - Graph algorithm analysis
   - Issue pattern identification
   - Impact assessment

4. **Fix Plan Generation**
   - Prioritized remediation steps
   - Risk assessment
   - Resource requirements

### Phase 2: Remediation (User Approved)
1. **Safety Validation**
   - Command validation checks
   - Resource availability verification
   - Impact assessment

2. **Fix Implementation**
   - Step-by-step execution
   - Progress monitoring
   - Error handling

3. **Verification**
   - Resolution confirmation
   - Performance validation
   - System stability check

## Best Practices

### For Administrators
1. **Start with Analysis Only**: Use `auto_fix: false` initially
2. **Review Fix Plans**: Always review generated fix plans before approval
3. **Monitor Logs**: Check `troubleshoot.log` for detailed execution traces
4. **Test SSH Access**: Verify SSH connectivity to all nodes
5. **Validate Commands**: Review and customize allowed/disallowed command lists

### For Developers
1. **Use Knowledge Graph**: Leverage graph analysis for complex scenarios
2. **Interactive Mode**: Enable for development and testing environments
3. **Tool Selection**: Use specific tools for targeted diagnostics
4. **Pattern Extension**: Add custom error patterns as needed
5. **Integration**: Integrate with existing monitoring and alerting systems

## Advanced Features

### Knowledge Graph Queries
```python
# Find all pods affected by a specific drive
affected_pods = knowledge_graph.trace_drive_to_pods(drive_id)

# Analyze issue patterns
patterns = knowledge_graph.identify_patterns()

# Generate fix plan
fix_plan = knowledge_graph.generate_fix_plan(analysis)
```

### Custom Tool Development
```python
@tool
def custom_diagnostic_tool(parameter: str) -> str:
    """Custom diagnostic tool description"""
    # Tool implementation
    return execute_command(["custom-command", parameter], "Purpose", False)
```

### LangGraph ReAct Customization
```python
# Custom system prompt for specialized scenarios
system_message = {
    "role": "system",
    "content": "Custom instructions for specific troubleshooting scenarios..."
}
```

## Troubleshooting Common Issues

### LLM Connection Issues
- Verify API endpoint and key in `config.yaml`
- Check network connectivity to LLM service
- Review rate limiting and quota restrictions

### Kubernetes Access Issues
- Verify kubeconfig configuration
- Check RBAC permissions for required resources
- Ensure in-cluster configuration for pod deployment

### SSH Connection Issues
- Verify SSH key permissions and paths
- Check network connectivity to target nodes
- Review SSH daemon configuration on target nodes

### Command Validation Issues
- Review allowed/disallowed command patterns
- Check for proper wildcard usage
- Verify command executable availability

## Performance Benchmarks

### Expected I/O Performance
- **HDD**: 100-200 IOPS, 100-200 MB/s throughput
- **SSD**: 1,000-10,000 IOPS, 500-600 MB/s throughput  
- **NVMe**: 10,000-100,000 IOPS, 1-7 GB/s throughput

### Analysis Performance
- **Knowledge Graph Construction**: < 30 seconds for 100 entities
- **LangGraph ReAct Execution**: 2-5 minutes for comprehensive analysis
- **Issue Collection**: < 10 seconds for 1000 pods
- **Root Cause Analysis**: < 15 seconds for complex scenarios

## Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Install development dependencies: `pip install -r requirements-dev.txt`
4. Run tests: `python -m pytest tests/`
5. Submit a pull request

### Adding New Tools
1. Define tool function with `@tool` decorator
2. Add to `define_tools()` function
3. Update documentation
4. Add validation logic if needed

### Extending Knowledge Graph
1. Add new entity types to `KnowledgeGraph` class
2. Define relationships and analysis methods
3. Update fix plan generation logic
4. Add comprehensive tests

## License

MIT License - see LICENSE file for details.

## Support

- **Documentation**: [Project Wiki](wiki-url)
- **Issues**: [GitHub Issues](issues-url)
- **Discussions**: [GitHub Discussions](discussions-url)
- **Community**: [Slack Channel](slack-url)

---

**Enhanced Kubernetes Volume Troubleshooting v2.0** - Powered by LangGraph ReAct Agents and Knowledge Graph Technology
