# Key Components and Implementations

## 1. Knowledge Graph

The Knowledge Graph is a central component that organizes diagnostic data into a structured representation of entities and relationships. It's implemented using NetworkX, a Python library for graph analytics.

### Entity Types

The Knowledge Graph supports the following entity types:

- **Pod**: Kubernetes Pod with attributes like name, namespace, errors, SecurityContext
- **PVC**: PersistentVolumeClaim with attributes like name, storageClass, bound PV
- **PV**: PersistentVolume with attributes like name, diskPath, nodeAffinity
- **Drive**: Physical disk with attributes like UUID, Health, Status, Path
- **Node**: Kubernetes Node with attributes like name, Ready, DiskPressure
- **StorageClass**: Kubernetes StorageClass with attributes like name, provisioner
- **LVG**: LogicalVolumeGroup with attributes like name, Health, drive UUIDs
- **AC**: AvailableCapacity with attributes like name, size, storage class, location
- **Volume**: Volume with attributes like name, namespace, Health, LocationType
- **System**: System entity with attributes like name, subtype (logs, service, hardware)
- **ClusterNode**: Cluster node with attributes like name and various system metrics
- **HistoricalExperience**: Past troubleshooting experiences with attributes like observation, diagnosis, resolution

### Relationship Types

The Knowledge Graph models relationships between entities:

- **Pod → PVC**: "uses" - Pod uses a PersistentVolumeClaim
- **PVC → PV**: "bound_to" - PVC is bound to a PersistentVolume
- **PV → Drive**: "maps_to" - PV maps to a physical drive
- **Drive → Node**: "located_on" - Drive is located on a node
- **PV → Node**: "affinity_to" - PV has affinity to a node
- **LVG → Drive**: "contains" - LVG contains drives
- **AC → Node**: "available_on" - AvailableCapacity is available on a node

### Key Functionality

The Knowledge Graph provides several key functions:

- **Issue Tracking**: Records and categorizes issues by severity and type
- **Path Finding**: Finds paths between entities to trace dependencies
- **Root Cause Analysis**: Identifies potential root causes based on graph topology
- **Pattern Detection**: Identifies patterns in issues across the graph
- **Fix Plan Generation**: Generates prioritized fix plans based on analysis

### Implementation

The Knowledge Graph is implemented in `knowledge_graph/knowledge_graph.py` with the following key methods:

- Entity management: `add_gnode_pod()`, `add_gnode_pvc()`, etc.
- Relationship management: `add_relationship()`
- Issue management: `add_issue()`, `get_issues_by_severity()`, `get_all_issues()`
- Graph traversal: `find_nodes_by_type()`, `find_connected_nodes()`, `find_path()`
- Analysis: `analyze_issues()`, `_identify_root_causes()`, `_identify_patterns()`
- Fix plan generation: `generate_fix_plan()`
- Visualization: `print_graph()`, `export_graph()`

## 2. LangGraph ReAct Agent

The LangGraph ReAct agent implements the reasoning and acting loop for investigation and remediation using the LangGraph framework.

### Core Components

- **StateGraph**: Manages the flow of execution through the graph
- **Call Model Node**: Invokes the LLM with the current state
- **Execute Tool Node**: Executes tools based on LLM instructions
- **End Condition Node**: Determines when to terminate the graph

### State Management

The agent uses an enhanced message state that tracks:

- Messages: Conversation history between the agent and tools
- Iteration count: Number of iterations through the graph
- Tool call count: Number of tool calls made
- Goals achieved: List of achieved goals
- Root cause identified: Whether a root cause has been identified
- Fix plan provided: Whether a fix plan has been provided

### Tool Execution

The agent supports both parallel and serial tool execution:

- **Parallel Tools**: Tools that can be executed concurrently
- **Serial Tools**: Tools that must be executed sequentially

Tool execution is managed by the `ExecuteToolNode` class, which:

1. Parses tool calls from the LLM response
2. Validates tools against allowed/disallowed commands
3. Executes tools in parallel or serially based on configuration
4. Formats tool results and updates the state

### End Conditions

The agent uses various end conditions to determine when to terminate the graph:

- **Content-based endings**: Checking for specific sections in the response
- **Maximum iterations**: Ending after a certain number of steps
- **Goal achievement**: Verifying if specific objectives are met
- **Convergence detection**: Ending if the model repeats itself

### Implementation

The LangGraph ReAct agent is implemented in `troubleshooting/graph.py` with the following key functions:

- Graph creation: `create_troubleshooting_graph_with_context()`
- LLM initialization: `_initialize_llm()`
- Message preparation: `_prepare_messages()`
- Tool management: `_get_tools_for_phase()`, `_create_execute_tool_node()`
- Graph building: `_build_graph()`

## 3. Phased Workflow System

The phased workflow system implements the different phases of the troubleshooting process.

### Phase 0: Information Collection

Phase 0 is responsible for gathering all necessary diagnostic data upfront and building the knowledge graph.

**Implementation**: `phases/phase_information_collection.py`

Key components:
- `InformationCollectionPhase` class: Manages the collection process
- `collect_information()`: Main entry point for Phase 0
- `_format_collected_data()`: Formats collected data into expected structure
- `_print_knowledge_graph_summary()`: Visualizes the knowledge graph

### Plan Phase: Investigation Planning

The Plan Phase generates a structured investigation plan based on the knowledge graph and historical experience.

**Implementation**: `phases/phase_plan_phase.py`

Key components:
- `PlanPhase` class: Orchestrates the planning process
- `execute()`: Main entry point for the Plan Phase
- `_generate_investigation_plan()`: Generates the investigation plan
- `_parse_investigation_plan()`: Parses the plan into a structured format

### Phase 1: ReAct Investigation

Phase 1 executes the investigation plan using the LangGraph ReAct agent to perform root cause analysis and generate a fix plan.

**Implementation**: `phases/phase_analysis.py`

Key components:
- `AnalysisPhase` class: Manages the investigation process
- `run_investigation()`: Main entry point for Phase 1
- `_extract_final_message()`: Extracts results from the graph response
- `process_analysis_result()`: Processes the analysis result

### Phase 2: Remediation

Phase 2 executes the fix plan to resolve identified issues and validate the fixes.

**Implementation**: `phases/phase_remediation.py`

Key components:
- `RemediationPhase` class: Manages the remediation process
- `execute_fix_plan()`: Main entry point for Phase 2
- `run_remediation_with_graph()`: Runs remediation using the LangGraph
- `_extract_final_message()`: Extracts results from the graph response

## 4. Information Collector

The Information Collector is responsible for gathering diagnostic data and building the knowledge graph in Phase 0.

### Components

- **Base Collector**: Core collection functionality
- **Volume Discovery**: Discovers volume dependency chains
- **Tool Executors**: Executes diagnostic tools and commands
- **Knowledge Builder**: Builds the knowledge graph from collected data
- **Metadata Parsers**: Parses Kubernetes resource metadata

### Implementation

The Information Collector is implemented in `information_collector/` with the following key classes:

- `InformationCollectorBase`: Base class with core functionality
- `VolumeDiscovery`: Discovers volume dependency chains
- `ToolExecutors`: Executes diagnostic tools
- `KnowledgeBuilder`: Builds the knowledge graph
- `ComprehensiveInformationCollector`: Main class that combines all components

Key methods:
- `comprehensive_collect()`: Main entry point for Phase 0
- `_discover_volume_dependency_chain()`: Discovers volume dependencies
- `_execute_pod_discovery_tools()`: Executes pod discovery tools
- `_execute_volume_chain_tools()`: Executes volume chain tools
- `_execute_csi_baremetal_tools()`: Executes CSI Baremetal tools
- `_execute_node_system_tools()`: Executes node and system tools
- `_execute_smart_data_tools()`: Executes SMART data tools
- `_execute_enhanced_log_analysis_tools()`: Executes log analysis tools
- `_build_knowledge_graph_from_tools()`: Builds the knowledge graph
- `_create_enhanced_context_summary()`: Creates a context summary

## 5. Tool Registry

The Tool Registry provides a collection of diagnostic and remediation tools that can be used by the LangGraph agent.

### Tool Categories

- **Core Tools**: Configuration, knowledge graph access, MCP adapter
- **Diagnostic Tools**: Disk analysis, monitoring, performance testing
- **Kubernetes Tools**: Core API, CSI Baremetal driver interaction
- **Testing Tools**: Pod creation, resource cleanup, volume testing

### Tool Types

- **Knowledge Graph Tools**: Query and update the knowledge graph
- **Kubernetes Tools**: Interact with the Kubernetes API
- **System Tools**: Execute system commands
- **SSH Tools**: Execute commands on remote nodes
- **CSI Baremetal Tools**: Interact with the CSI Baremetal driver
- **Testing Tools**: Create and test resources

### Implementation

The Tool Registry is implemented in `tools/` with the following structure:

- `tools/core/`: Core tools for configuration, knowledge graph, MCP
- `tools/diagnostics/`: Diagnostic tools for disk, system, performance
- `tools/kubernetes/`: Kubernetes API tools
- `tools/testing/`: Testing tools for pods, volumes, resources

Key functions:
- `get_phase1_tools()`: Gets tools for Phase 1
- `get_phase2_tools()`: Gets tools for Phase 2
- `define_remediation_tools()`: Defines all remediation tools

## 6. MCP Integration

The Model Context Protocol (MCP) integration enables communication with external MCP servers to extend the system's capabilities.

### Components

- **MCP Adapter**: Main adapter for MCP communication
- **MCP Server**: External server providing tools and resources
- **MCP Tools**: Tools provided by MCP servers
- **MCP Resources**: Resources provided by MCP servers

### Implementation

The MCP integration is implemented in `tools/core/mcp_adapter.py` with the following key functions:

- `initialize_mcp_adapter()`: Initializes the MCP adapter
- `get_mcp_adapter()`: Gets the MCP adapter instance
- `get_tools_for_phase()`: Gets MCP tools for a specific phase
- `use_mcp_tool()`: Uses an MCP tool
- `access_mcp_resource()`: Accesses an MCP resource

## 7. Chat Mode

The Chat Mode enables interactive troubleshooting by allowing users to interact with the system during the troubleshooting process.

### Entry Points

- **Plan Phase**: After generating the investigation plan
- **Phase 1**: After analyzing issues and generating the fix plan

### Implementation

The Chat Mode is implemented in `phases/chat_mode.py` with the following key methods:

- `chat_after_plan_phase()`: Enables chat after the Plan Phase
- `chat_after_phase1()`: Enables chat after Phase 1
- `_get_user_input()`: Gets input from the user
- `_process_user_input()`: Processes user input
- `_update_message_list()`: Updates the message list based on user input
