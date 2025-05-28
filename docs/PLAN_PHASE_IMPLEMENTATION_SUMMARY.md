# Plan Phase Implementation Summary

This document provides a comprehensive overview of the Plan Phase implementation that was added to the Kubernetes Volume Troubleshooting System.

## Overview

The Plan Phase is a new phase inserted between Phase 0 (Information Collection) and Phase 1 (ReAct Investigation) that generates structured Investigation Plans based on Knowledge Graph analysis.

### Updated System Workflow

```
Phase 0: Information Collection
    ↓ (Knowledge Graph + collected_info)
Plan Phase: Investigation Plan Generation
    ↓ (Investigation Plan)
Phase 1: ReAct Investigation (Modified)
    ↓ (Root Cause + Fix Plan)
Phase 2: Remediation
```

## Implementation Details

### 1. New Files Created

#### `phases/__init__.py`
- Module initialization file for the phases package
- Exports Plan Phase components for external use

#### `phases/investigation_planner.py`
- **InvestigationPlanner class**: Core logic for generating Investigation Plans
- **Key Methods**:
  - `generate_investigation_plan()`: Main entry point for plan generation
  - `_analyze_existing_issues()`: Analyzes Knowledge Graph issues by severity/type
  - `_identify_target_entities()`: Maps Pod → PVC → PV → Drive → Node chain
  - `_determine_investigation_priority()`: Sets investigation priority based on issue severity
  - `_generate_investigation_steps()`: Creates detailed step-by-step investigation sequence
  - `_generate_fallback_steps()`: Creates fallback steps for error scenarios
  - `_format_investigation_plan()`: Formats plan into required string format

#### `phases/plan_phase.py`
- **PlanPhase class**: Orchestrates Investigation Plan generation
- **Key Functions**:
  - `run_plan_phase()`: Main async function to execute Plan Phase
  - `create_plan_phase_graph()`: Creates LangGraph StateGraph for Plan Phase
  - **Constraints**: Only uses Knowledge Graph tools (7 kg_* functions)
  - **Error Handling**: Multiple fallback mechanisms for incomplete data

#### `sample_investigation_plan.md`
- Example Investigation Plan output demonstrating the format
- Shows step-by-step structure with tools, arguments, and expected outcomes
- Includes fallback steps with trigger conditions

### 2. Modified Files

#### `troubleshoot.py`
- **New Function**: `run_analysis_phase_with_plan()` - Modified Phase 1 that accepts Investigation Plan
- **Updated Workflow**: Integrated Plan Phase into main troubleshooting flow
- **Enhanced Summary**: Added Plan Phase to results tracking and summary table
- **Error Handling**: Fallback to basic plan if Plan Phase fails

#### Key Changes:
```python
# Added Plan Phase execution
investigation_plan = await run_plan_phase(
    pod_name, namespace, volume_path, collected_info, CONFIG_DATA
)

# Modified Phase 1 to use Investigation Plan
root_cause, fix_plan = await run_analysis_phase_with_plan(
    pod_name, namespace, volume_path, collected_info, investigation_plan
)
```

### 3. Investigation Plan Format

The Plan Phase generates Investigation Plans in this structured format:

```
Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}
Generated Steps: {number} main steps, {number} fallback steps

Step 1: [Description] | Tool: [kg_tool(arguments)] | Expected: [expected_outcome]
Step 2: [Description] | Tool: [kg_tool(arguments)] | Expected: [expected_outcome]
...

Fallback Steps (if main steps fail):
Step F1: [Description] | Tool: [kg_tool(arguments)] | Expected: [expected_outcome] | Trigger: [failure_condition]
...
```

### 4. Knowledge Graph Tools Used (Plan Phase Only)

The Plan Phase is restricted to these 7 Knowledge Graph tools:
1. `kg_get_entity_info` - Get detailed entity information
2. `kg_get_related_entities` - Find related entities
3. `kg_get_all_issues` - Get issues by severity/type
4. `kg_find_path` - Find shortest path between entities
5. `kg_get_summary` - Get system overview
6. `kg_analyze_issues` - Analyze issue patterns
7. `kg_print_graph` - Get human-readable graph representation

### 5. Modified Phase 1 Behavior

Phase 1 now:
- **Accepts Investigation Plan** as primary input alongside collected_info
- **Parses each step** from the Investigation Plan
- **Executes Knowledge Graph tools** as specified in the plan
- **Validates expected outcomes** against actual results
- **Uses fallback steps** when primary steps fail
- **Supplements with additional tools** for comprehensive analysis
- **Logs execution details** for traceability

### 6. Error Handling Strategy

#### Plan Phase Failures
- **Knowledge Graph unavailable**: Uses basic fallback plan
- **Entity not found**: Searches broadly for related entities
- **Plan generation error**: Falls back to emergency plan with basic steps

#### Phase 1 Execution Failures
- **Step execution failure**: Triggers appropriate fallback steps
- **Unexpected results**: Logs differences and continues with next steps
- **Tool unavailability**: Uses alternative diagnostic tools

#### Fallback Plans
- **Basic Plan**: 3-4 essential Knowledge Graph queries
- **Emergency Plan**: Minimal system overview and issue analysis
- **Manual Fallback**: Complete Knowledge Graph visualization

### 7. Integration Benefits

#### Structured Investigation
- **Deterministic Planning**: Consistent approach across scenarios
- **Priority-Based**: Focuses on critical issues first
- **Entity-Aware**: Follows logical dependency chains

#### Enhanced Efficiency
- **Knowledge Graph First**: Leverages pre-collected data
- **Targeted Queries**: Reduces unnecessary tool calls
- **Fallback Safety**: Robust handling of incomplete data

#### Improved Traceability
- **Step Documentation**: Clear audit trail of investigation
- **Outcome Validation**: Comparison of expected vs actual results
- **Execution Logging**: Detailed logging for debugging

### 8. Configuration Options

The Plan Phase supports configuration through `config.yaml`:
```yaml
plan_phase:
  use_direct_generation: true  # Use direct generation (faster) vs LangGraph
  timeout_seconds: 120        # Timeout for plan generation
```

### 9. Rich Console Output

The Plan Phase includes enhanced console output:
- **Plan Generation Panel**: Shows Investigation Plan creation progress
- **Step Execution Panels**: Displays each Knowledge Graph query with results
- **Summary Table**: Includes Plan Phase duration and status
- **Error Panels**: Clear error reporting with fallback information

### 10. Backward Compatibility

The implementation maintains full backward compatibility:
- **Existing APIs**: No changes to external interfaces
- **Phase 2**: Unchanged remediation phase
- **Configuration**: All existing config options work as before
- **Logging**: Enhanced but compatible logging structure

## Sample Output

Here's an example of what the Plan Phase generates:

```
Investigation Plan:
Target: Pod production/nginx-app, Volume Path: /var/www/html
Generated Steps: 6 main steps, 2 fallback steps

Step 1: Get all critical issues from Knowledge Graph | Tool: kg_get_all_issues(severity='critical') | Expected: Critical issues affecting volume operations
Step 2: Analyze issue patterns and relationships | Tool: kg_analyze_issues() | Expected: Root cause analysis with probability scores
Step 3: Get detailed Pod information | Tool: kg_get_entity_info(entity_type='Pod', entity_id='nginx-app') | Expected: Pod status and configuration issues
Step 4: Find related storage entities | Tool: kg_get_related_entities(entity_type='Pod', entity_id='nginx-app', max_depth=2) | Expected: PVC, PV, Drive dependency chain
Step 5: Check Drive health status | Tool: kg_get_entity_info(entity_type='Drive', entity_id='detected-drive') | Expected: SMART data and health metrics
Step 6: Get system overview | Tool: kg_get_summary() | Expected: Overall cluster health statistics

Fallback Steps (if main steps fail):
Step F1: Get medium severity issues | Tool: kg_get_all_issues(severity='medium') | Expected: Broader issue analysis | Trigger: no_critical_issues
Step F2: Print full Knowledge Graph | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Complete visualization | Trigger: insufficient_data
```

## Implementation Quality

### Code Quality
- **Type Hints**: Full typing support throughout
- **Error Handling**: Comprehensive exception handling
- **Logging**: Structured logging with appropriate levels
- **Documentation**: Detailed docstrings and comments

### Testing Considerations
- **Unit Tests**: Classes support easy unit testing
- **Integration Tests**: Can be tested with mock Knowledge Graph
- **Error Scenarios**: Multiple fallback paths for testing

### Performance
- **Efficient Planning**: Minimal overhead in plan generation
- **Optimized Queries**: Knowledge Graph queries are targeted
- **Timeout Handling**: Prevents hanging operations

## Future Enhancements

Potential future improvements:
1. **Machine Learning**: Learn from successful Investigation Plans
2. **Custom Templates**: User-defined Investigation Plan templates
3. **Parallel Execution**: Execute independent steps in parallel
4. **Interactive Planning**: Allow user modification of generated plans
5. **Plan Optimization**: Dynamic plan adjustment based on intermediate results

## Conclusion

The Plan Phase implementation successfully meets all requirements:
- ✅ **Structured Planning**: Generates detailed Investigation Plans
- ✅ **Knowledge Graph Only**: Uses only KG tools for deterministic planning
- ✅ **Phase 1 Integration**: Modified Phase 1 to follow Investigation Plans
- ✅ **Error Handling**: Robust fallback mechanisms
- ✅ **Consistent Format**: Clear, actionable output format
- ✅ **Backward Compatibility**: No breaking changes
- ✅ **Rich Output**: Enhanced console and logging

The Plan Phase transforms the troubleshooting system from reactive investigation to planned, systematic diagnosis while maintaining the flexibility and power of the ReAct framework.
