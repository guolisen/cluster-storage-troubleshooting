# Plan Phase Implementation

## Overview

The Plan Phase is a critical component of the Kubernetes cluster storage troubleshooting system, generating a step-by-step Investigation Plan that Phase1 will execute. The refactored Plan Phase follows a three-step process to generate a comprehensive, actionable plan:

1. **Rule-Based Preliminary Steps**: Generate high-priority initial investigation steps based on issue severity and historical experience
2. **Static Plan Steps Integration**: Add mandatory steps from a configurable JSON file
3. **LLM Refinement**: Refine and supplement the plan via direct LLM invocation with Phase1 tool information

## Three-Step Process

### Step 1: Rule-Based Preliminary Steps

The first step uses a rule-based approach to generate a small number of high-priority initial investigation steps based on:

- Issue severity (critical, high, medium, low)
- Knowledge Graph entities involved in the issue
- Historical experience data with root cause information

This step is implemented in `rule_based_plan_generator.py` which:

- Analyzes issues by severity
- Prioritizes steps based on historical experience patterns
- Generates 1-3 critical initial steps tailored to the issue context
- Includes appropriate tools and expected outcomes for each step

Example rule-based step:
```
{
  "step": 1,
  "description": "Check disk health on the affected node",
  "tool": "check_disk_health",
  "arguments": {"node": "node-1", "disk_id": "disk1"},
  "expected_outcome": "Disk status and hardware errors",
  "priority": "high",
  "category": "hardware_investigation"
}
```

### Step 2: Static Plan Steps Integration

The second step reads static plan steps from a configurable JSON file (`static_plan_step.json`) and integrates them into the draft plan. These steps:

- Are mandatory and cannot be optimized or skipped
- Come from a JSON file with configurable path in `config.yaml`
- Follow a predefined format with description, tool name with parameters, and expected outcome

This step is implemented in `static_plan_step_reader.py` which:

- Reads the static steps file from the configured path
- Validates the format of static steps
- Appends the static steps to the preliminary steps from Step 1
- Marks the static steps as mandatory for the LLM refinement in Step 3

Example static step JSON file:
```json
[
  {
    "description": "Check recent system logs for volume errors",
    "tool": "kg_query_nodes(type='log', time_range='24h', filters={'message': 'I/O error'})",
    "expected": "List of error logs indicating volume issues"
  },
  {
    "description": "Verify pod-to-PVC binding",
    "tool": "kg_query_relationships(source='pod', target='pvc')",
    "expected": "Confirmation of correct PVC binding"
  }
]
```

### Step 3: LLM Refinement

The final step uses direct LLM invocation (without LangGraph) to refine and supplement the draft plan:

- Accepts the draft plan, Knowledge Graph, historical experience, and Phase1 tool registry
- Includes all Phase1 tools in the context (names, descriptions, parameters, invocation methods)
- Respects existing steps from the draft plan (both rule-based and static steps)
- Adds additional steps, reorders for logical flow, and refines descriptions
- Does not invoke any tools, only references them in the plan

This step is implemented in `llm_plan_generator.py` which:

- Uses a static system prompt with guiding principles
- Passes dynamic data as query message to the LLM
- Ensures the LLM has all Phase1 tool information to reference correctly
- Formats the final plan in the required format for Phase1 execution

Example of the LLM input context:
```
DRAFT PLAN:
[
  {
    "step": 1,
    "description": "Check disk health on the affected node",
    "tool": "check_disk_health",
    "arguments": {"node": "node-1", "disk_id": "disk1"},
    "expected_outcome": "Disk status and hardware errors"
  },
  {
    "step": 2,
    "description": "Check recent system logs for volume errors",
    "tool": "kg_query_nodes(type='log', time_range='24h', filters={'message': 'I/O error'})",
    "expected": "List of error logs indicating volume issues",
    "source": "static"
  }
]

AVAILABLE TOOLS FOR PHASE1:
[
  {
    "name": "kg_query_nodes",
    "description": "Queries nodes in the Knowledge Graph by type and optional filters.",
    "parameters": {"type": "string", "time_range": "string (optional)", "filters": "object (optional)"},
    "invocation": "kg_query_nodes(type='log', time_range='24h', filters={'message': 'I/O error'})"
  },
  ...
]
```

## Configuration

The Plan Phase can be configured in `config.yaml`:

```yaml
plan_phase:
  use_llm: true  # Whether to use LLM refinement (Step 3)
  timeout_seconds: 120  # Timeout for plan generation
  static_plan_step_path: "static_plan_step.json"  # Path to static steps file
```

## Integration with System Workflow

The Plan Phase is integrated with the overall system workflow through:

1. **phase_plan_phase.py**: Orchestrates the Plan Phase execution
2. **investigation_planner.py**: Implements the three-step process
3. **Knowledge Graph Context**: Receives Knowledge Graph and historical experience from Phase0
4. **Tool Registry**: Accesses the Phase1 tool registry for LLM context
5. **Output**: Passes the final Investigation Plan to Phase1 for execution

## Testing

The Plan Phase implementation can be tested using the provided `test_plan_phase.py` script, which:

1. Creates a mock Knowledge Graph with sample data
2. Tests each step of the process individually
3. Tests the full end-to-end plan generation process
4. Outputs the plan at each step for verification

Run the test with:
```
python test_plan_phase.py
```

## Benefits of the Refactored Architecture

The three-step process offers several benefits:

1. **Prioritization of Critical Steps**: Rule-based generation ensures high-priority steps are included
2. **Mandatory Steps Integration**: Static steps ensure consistent investigation steps
3. **Comprehensive Plan Generation**: LLM refinement adds context-aware steps and logical flow
4. **No Tool Invocation During Planning**: Tools are only referenced, not invoked
5. **Historical Experience Integration**: Past root causes inform plan generation
6. **Modularity**: Each step can be improved or replaced independently
