# Sample Investigation Plan With Historical Experience

This is an example of an Investigation Plan generated for the Plan Phase, demonstrating how historical experience data is leveraged to guide the investigation.

```
Investigation Plan:
Target: Pod default/app-db-0, Volume Path: /data
Generated Steps: 5 main steps, 2 fallback steps

HYPOTHESES ANALYSIS:

1. Hardware Failure in Underlying Disk
   - Description: The volume I/O errors may be caused by hardware failures in the underlying physical disk, such as bad sectors or disk degradation.
   - Evidence: Volume read errors in pod logs with I/O error messages, matching the phenomenon described in historical experience.
   - Historical Experience Reference: Similar to "Volume read errors in pod logs" with root cause "Hardware failure in the underlying disk, such as bad sectors or disk degradation, causing read operations to fail."
   - Likelihood: HIGH

2. Insufficient Storage Capacity
   - Description: The pod might be experiencing I/O errors due to a lack of storage space on the volume.
   - Evidence: Knowledge Graph shows PVC utilization is high, similar to "Disk/volume size not enough" in historical experience.
   - Historical Experience Reference: "Disk/volume size not enough" with root cause "Insufficient storage capacity allocated to the PVC or PV, causing out-of-space errors during write operations."
   - Likelihood: MEDIUM

3. PVC Access Mode Configuration Issue
   - Description: The PVC may be configured with incorrect access mode, causing write failures when the pod attempts to write to the volume.
   - Evidence: Pod logs show "Permission denied" errors similar to historical experience.
   - Historical Experience Reference: "PVC metadata defined as 'ReadOnlyMany' causing write failures" with root cause "PVC access mode set to 'ReadOnlyMany', restricting the pod to read-only access and preventing write operations."
   - Likelihood: LOW

INVESTIGATION PLAN:

Step 1: Query error logs for volume I/O errors | Tool: kg_query_nodes(type='log', time_range='24h', filters={'message': 'I/O error'}) | Expected: List of I/O error messages from pod app-db-0 to confirm hardware failure symptoms | Historical Experience: Based on localization method from "Volume read errors in pod logs"

Step 2: Check disk health of underlying drive | Tool: check_disk_health(node='node-1', disk_id='disk1') | Expected: Disk health status showing potential hardware issues like bad sectors | Historical Experience: Direct recommendation from localization method in "Volume read errors in pod logs"

Step 3: Check volume capacity and usage | Tool: kg_get_node_metadata(node_type='pvc', filters={'name': 'data-pvc'}) | Expected: Storage capacity and usage information to determine if disk space is insufficient | Historical Experience: Based on localization method from "Disk/volume size not enough"

Step 4: Verify PVC access mode configuration | Tool: kg_get_node_metadata(node_type='pvc', filters={'name': 'data-pvc'}) | Expected: Access mode configuration of the PVC to check if it's set to ReadOnlyMany | Historical Experience: Based on localization method from "PVC metadata defined as 'ReadOnlyMany' causing write failures"

Step 5: Confirm pod security context and volume permissions | Tool: kg_query_nodes(type='pod', filters={'name': 'app-db-0'}) | Expected: Pod security context and volume mount permissions to verify permission-related issues | Historical Experience: Related to permission issues in multiple historical experiences

Fallback Steps (if main steps fail):

Step F1: Check general node health | Tool: kg_query_nodes(type='node', filters={'Ready': 'false'}) | Expected: List of nodes with health issues that might affect storage | Trigger: If check_disk_health fails or returns inconclusive results

Step F2: Examine general storage system logs | Tool: kg_query_nodes(type='log', time_range='24h', filters={'service': 'storage'}) | Expected: General storage system logs to identify any system-wide issues | Trigger: If no specific issues are found in previous steps
```

## How Historical Experience Is Used

1. **Hypothesis Formation:** Each hypothesis references relevant historical experience entries, incorporating both the phenomenon and root cause from past incidents.

2. **Likelihood Assessment:** Hypotheses are prioritized (HIGH, MEDIUM, LOW) based in part on how closely they match historical experience patterns.

3. **Tool Selection:** Tools are chosen based on successful localization methods from historical experience, such as using `check_disk_health` based on the "Volume read errors in pod logs" historical experience.

4. **Expected Outcomes:** The expected outcomes for each step incorporate knowledge from historical experience about what symptoms to look for.

5. **Fallback Planning:** Fallback steps provide alternative approaches when primary approaches fail, ensuring comprehensive coverage even when the issue doesn't match historical patterns exactly.

This structured approach ensures that the investigation leverages past experience while remaining adaptable to new or unique issues that might not match historical patterns perfectly.
