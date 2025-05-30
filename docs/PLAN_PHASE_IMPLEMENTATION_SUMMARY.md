# Plan Phase Implementation Summary

This document provides an overview of the Plan Phase implementation for the Kubernetes Volume Troubleshooting system. The Plan Phase is responsible for analyzing the Knowledge Graph from Phase 0, hypothesizing the most likely causes of volume read/write errors, prioritizing them by likelihood, and generating a step-by-step Investigation Plan for Phase 1.

## Architecture Overview

The Plan Phase has been implemented with a modular architecture that separates concerns and allows for flexibility in how investigation plans are generated. The key components are:

1. **PlanPhase**: The main orchestrator that coordinates the plan generation process
2. **InvestigationPlanner**: The core component that generates investigation plans
3. **KGContextBuilder**: Prepares Knowledge Graph context for consumption by the LLM
4. **ToolRegistryBuilder**: Prepares the tool registry for consumption by the LLM
5. **LLMPlanGenerator**: Generates investigation plans using LLMs
6. **RuleBasedPlanGenerator**: Generates investigation plans using rule-based approaches

This modular design allows for easy maintenance, testing, and extension of the Plan Phase.

## Component Details

### PlanPhase

The `PlanPhase` class is the main entry point for the Plan Phase. It:

- Receives the Knowledge Graph from Phase 0
- Initializes the Investigation Planner
- Generates the Investigation Plan
- Parses the plan into a structured format for Phase 1
- Returns the results to the caller

### InvestigationPlanner

The `InvestigationPlanner` class is responsible for generating investigation plans. It:

- Analyzes the Knowledge Graph to identify patterns and issues
- Determines whether to use LLM-based or rule-based plan generation
- Coordinates the plan generation process
- Returns the formatted Investigation Plan

### KGContextBuilder

The `KGContextBuilder` class prepares Knowledge Graph context for consumption by the LLM. It:

- Extracts relevant nodes and relationships from the Knowledge Graph
- Analyzes existing issues to identify patterns and priorities
- Formats the Knowledge Graph data for LLM consumption

### ToolRegistryBuilder

The `ToolRegistryBuilder` class prepares the tool registry for consumption by the LLM. It:

- Extracts tool information from the system
- Formats the tool registry for LLM consumption
- Groups tools by category for easier consumption

### LLMPlanGenerator

The `LLMPlanGenerator` class generates investigation plans using LLMs. It:

- Initializes the LLM with the appropriate configuration
- Generates system prompts for the LLM
- Calls the LLM to generate the Investigation Plan
- Formats the LLM output into the required format

### RuleBasedPlanGenerator

The `RuleBasedPlanGenerator` class generates investigation plans using rule-based approaches. It:

- Determines investigation priorities based on issue severity and target entities
- Generates step-by-step investigation steps based on priorities
- Adds fallback steps for incomplete data
- Formats the final plan into the required format

## Workflow

The Plan Phase workflow is as follows:

1. The `PlanPhase` receives the Knowledge Graph from Phase 0, along with the pod name, namespace, and volume path
2. The `PlanPhase` initializes the `InvestigationPlanner` with the Knowledge Graph and configuration data
3. The `InvestigationPlanner` determines whether to use LLM-based or rule-based plan generation
4. If using LLM-based generation:
   - The `KGContextBuilder` prepares the Knowledge Graph context
   - The `ToolRegistryBuilder` prepares the tool registry
   - The `LLMPlanGenerator` generates the Investigation Plan
5. If using rule-based generation:
   - The `KGContextBuilder` analyzes existing issues
   - The `KGContextBuilder` identifies target entities
   - The `RuleBasedPlanGenerator` generates the Investigation Plan
6. The `PlanPhase` parses the Investigation Plan into a structured format for Phase 1
7. The `PlanPhase` returns the results to the caller

## Investigation Plan Format

The Investigation Plan is formatted as a structured string with the following sections:

```
Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}
Generated Steps: {num_steps} main steps, {num_fallback_steps} fallback steps

Step 1: [Description] | Tool: [tool_name(parameters)] | Expected: [expected_outcome]
Step 2: [Description] | Tool: [tool_name(parameters)] | Expected: [expected_outcome]
...
Step N: [Description] | Tool: [tool_name(parameters)] | Expected: [expected_outcome]

Fallback Steps (if main steps fail):
Step F1: [Description] | Tool: [tool_name(parameters)] | Expected: [expected_outcome] | Trigger: [failure_condition]
Step F2: [Description] | Tool: [tool_name(parameters)] | Expected: [expected_outcome] | Trigger: [failure_condition]
...
Step FN: [Description] | Tool: [tool_name(parameters)] | Expected: [expected_outcome] | Trigger: [failure_condition]
```

The LLM-based plan generator also includes a Hypotheses Analysis section that lists the top potential causes of the volume read/write errors, along with evidence from the Knowledge Graph and likelihood rankings.

## Integration with Phase 1

The Plan Phase integrates with Phase 1 by providing a structured Investigation Plan that Phase 1 can execute using the ReAct framework. The structured plan includes:

- A list of steps to execute, each with a description, tool name, arguments, and expected outcome
- A list of fallback steps to execute if the main steps fail, each with a trigger condition
- Prioritized hypotheses for the volume read/write errors (for LLM-based plans)

Phase 1 executes the steps in order, with the results of each step informing the next. If a step fails, the corresponding fallback step is executed based on the trigger condition.

## Error Handling

The Plan Phase includes robust error handling to ensure that it can generate a useful Investigation Plan even in the face of incomplete or malformed data:

- If the LLM-based plan generation fails, it falls back to rule-based generation
- If both LLM-based and rule-based generation fail, it generates a basic fallback plan
- If the Knowledge Graph is incomplete, it includes fallback steps to gather missing data
- If the tool registry is incomplete, it includes fallback steps to use alternative tools

## Configuration

The Plan Phase can be configured through the system configuration data:

- `plan_phase.use_llm`: Whether to use LLM-based plan generation (default: true)
- `llm.model`: The LLM model to use (default: gpt-4)
- `llm.api_key`: The API key for the LLM
- `llm.api_endpoint`: The API endpoint for the LLM
- `llm.temperature`: The temperature for the LLM (default: 0.1)
- `llm.max_tokens`: The maximum number of tokens for the LLM (default: 4000)

## Example

See [Sample Investigation Plan](sample_investigation_plan.md) for an example of the Investigation Plan generated by the Plan Phase.

## Future Enhancements

Potential future enhancements to the Plan Phase include:

1. **Enhanced Hypothesis Generation**: Improve the LLM's ability to generate hypotheses by providing more context and examples
2. **Dynamic Tool Selection**: Allow the LLM to dynamically select tools based on the hypotheses and available data
3. **Feedback Loop**: Incorporate feedback from Phase 1 to improve future plan generation
4. **Multi-LLM Approach**: Use multiple LLMs for different aspects of plan generation (e.g., one for hypothesis generation, one for tool selection)
5. **Explainable Plans**: Enhance the Investigation Plan with explanations of why each step is included and how it relates to the hypotheses
