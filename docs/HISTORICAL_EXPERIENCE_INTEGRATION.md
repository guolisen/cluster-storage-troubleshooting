# Historical Experience Integration in Kubernetes Storage Troubleshooting

This document describes the integration of historical experience data into the Kubernetes storage troubleshooting system. Historical experience data provides valuable information about previously encountered volume I/O failures, their root causes, and effective resolution methods, allowing the system to more effectively troubleshoot similar issues.

## Overview

Historical experience data is integrated into the Knowledge Graph during Phase0 and leveraged by all subsequent phases of the troubleshooting process:

1. **Phase0**: Loads historical experience data from a JSON file and integrates it into the Knowledge Graph
2. **Plan Phase**: Uses historical experience data to inform the Investigation Plan generation
3. **Phase1**: Leverages historical experience during the investigation process
4. **Phase2**: Uses historical experience to guide remediation steps

## Historical Experience Data Structure

Historical experience data is stored in a human-readable, editable JSON file (`historical_experience.json`) with the following structure:

```json
[
  {
    "phenomenon": "Volume read errors in pod logs",
    "root_cause": "Hardware failure in the underlying disk, such as bad sectors or disk degradation, causing read operations to fail.",
    "localization_method": "Query error logs with `kg_query_nodes(type='log', time_range='24h', filters={'message': 'I/O error'})` and check disk health with `check_disk_health(node='node-1', disk_id='disk1')`",
    "resolution_method": "Replace the faulty disk identified in `check_disk_health`. Restart the affected service with `systemctl restart db-service` and verify pod status with `kubectl get pods`."
  }
]
```

Each entry contains:

- **phenomenon**: A description of the observed issue (e.g., "Volume read errors in pod logs")
- **root_cause**: An analysis of the underlying cause (e.g., "Hardware failure in the underlying disk")
- **localization_method**: Steps or tools to diagnose the issue (e.g., tool usage examples)
- **resolution_method**: Steps or actions to resolve the issue (e.g., commands to fix the problem)

## Integration in Knowledge Graph

Historical experience data is loaded into the Knowledge Graph as nodes of type `HistoricalExperience` with attributes for phenomenon, root_cause, localization_method, and resolution_method. These nodes are linked to relevant system components based on their phenomenon description:

- Volume read errors link to Logs, Drives, and Pods
- PVC issues link to PVC entities
- Drive health issues link to Drive entities

## Usage in Troubleshooting Phases

### Plan Phase

The Plan Phase leverages historical experience data to:

1. Identify potential root causes based on past similar incidents
2. Prioritize hypotheses based on historical experience
3. Generate investigation steps informed by proven localization methods

The LLM system prompt explicitly instructs the planner to use the historical experience data when generating the Investigation Plan.

### Phase1 (Analysis)

Phase1 uses historical experience to:

1. Identify patterns in the current issue that match previous incidents
2. Follow diagnostic steps that were successful in similar past cases
3. Compare observed symptoms with previously documented phenomena
4. Reference root causes from historical experience in the analysis

### Phase2 (Remediation)

Phase2 uses historical experience to:

1. Select resolution methods that were successful for similar root causes
2. Implement fixes based on proven solutions
3. Adapt historical resolution methods to the current environment

## Extending Historical Experience

Users can extend the historical experience database by adding new entries to the `historical_experience.json` file. Each entry should include:

1. A clear description of the phenomenon (observable symptoms)
2. A detailed root cause analysis
3. Specific localization methods that work with the current tool set
4. Effective resolution methods that address the root cause

When adding new entries, ensure they follow the same format as existing entries and contain all required fields. The system will automatically load and integrate new entries on the next run.

## Testing Historical Experience Integration

You can test the historical experience integration using:

```bash
./run_historical_experience_test.sh
```

This script:
1. Verifies the historical experience file can be loaded correctly
2. Tests the integration with the Knowledge Graph
3. Runs a comprehensive troubleshooting scenario that leverages historical experience
