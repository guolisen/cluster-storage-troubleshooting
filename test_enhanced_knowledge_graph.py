#!/usr/bin/env python3
"""
Test Enhanced Knowledge Graph Implementation

This script tests the enhanced knowledge graph functionality with CSI Volume relationships.
"""

import asyncio
import logging
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from information_collector.collector import InformationCollector
from knowledge_graph import KnowledgeGraph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_enhanced_knowledge_graph():
    """Test the enhanced knowledge graph with CSI relationships"""
    print("🧪 Testing Enhanced Knowledge Graph Implementation")
    print("=" * 60)
    
    # Create mock CSI data for testing
    mock_csi_data = {
        'csi_baremetal': {
            'drives': '''
apiVersion: v1
items:
- apiVersion: csi-baremetal.dell.com/v1
  kind: Drive
  metadata:
    name: 2a96dfec-47db-449d-9789-0d81660c2c4d
  spec:
    Health: GOOD
    Status: ONLINE
    Path: /dev/sda
    Usage: IN_USE
    Size: 299573968896
    Type: SSD
    NodeId: 6e172f8c-9d8b-41ac-99cf-44dab5da25f6
    SerialNumber: 6000c293fbf5f0fa45686547adedc378
- apiVersion: csi-baremetal.dell.com/v1
  kind: Drive
  metadata:
    name: 4ae92cbd-6fed-412a-a259-f627dac829c2
  spec:
    Health: GOOD
    Status: ONLINE
    Path: /dev/sda
    Usage: IN_USE
    Size: 299573968896
    Type: SSD
    NodeId: 0c94ee22-3ac7-4114-a7a2-3b572d8574fb
            ''',
            'nodes': '''
apiVersion: v1
items:
- apiVersion: csi-baremetal.dell.com/v1
  kind: CSIBMNode
  metadata:
    name: csibmnode-6e172f8c-9d8b-41ac-99cf-44dab5da25f6
  spec:
    UUID: 6e172f8c-9d8b-41ac-99cf-44dab5da25f6
    hostname: masternode1
    nodeIP: 10.227.104.51
- apiVersion: csi-baremetal.dell.com/v1
  kind: CSIBMNode
  metadata:
    name: csibmnode-0c94ee22-3ac7-4114-a7a2-3b572d8574fb
  spec:
    UUID: 0c94ee22-3ac7-4114-a7a2-3b572d8574fb
    hostname: workernode1
    nodeIP: 10.227.104.52
            ''',
            'lvgs': '''
apiVersion: v1
items:
- apiVersion: csi-baremetal.dell.com/v1
  kind: LogicalVolumeGroup
  metadata:
    name: c15dd61c-e597-4392-bc5d-4c27b2d23a21
  spec:
    Health: GOOD
    Size: 299573968896
    Node: 6e172f8c-9d8b-41ac-99cf-44dab5da25f6
    Locations:
    - 2a96dfec-47db-449d-9789-0d81660c2c4d
- apiVersion: csi-baremetal.dell.com/v1
  kind: LogicalVolumeGroup
  metadata:
    name: eee60c88-0c93-4235-af53-e4295137eb2e
  spec:
    Health: GOOD
    Size: 299573968896
    Node: 0c94ee22-3ac7-4114-a7a2-3b572d8574fb
    Locations:
    - 4ae92cbd-6fed-412a-a259-f627dac829c2
            ''',
            'volumes': '''
apiVersion: v1
items:
- apiVersion: csi-baremetal.dell.com/v1
  kind: Volume
  metadata:
    name: vol-test-pvc-1
    namespace: default
  spec:
    Health: GOOD
    LocationType: LVG
    Size: 10737418240
    StorageClass: csi-baremetal-sc-ssdlvg
    Location: c15dd61c-e597-4392-bc5d-4c27b2d23a21
    Usage: IN_USE
    Mode: FS
    Type: LVM
    NodeId: 6e172f8c-9d8b-41ac-99cf-44dab5da25f6
- apiVersion: csi-baremetal.dell.com/v1
  kind: Volume
  metadata:
    name: vol-test-pvc-2
    namespace: default
  spec:
    Health: GOOD
    LocationType: DRIVE
    Size: 5368709120
    StorageClass: csi-baremetal-sc-ssd
    Location: 4ae92cbd-6fed-412a-a259-f627dac829c2
    Usage: IN_USE
    Mode: FS
    Type: DRIVE
    NodeId: 0c94ee22-3ac7-4114-a7a2-3b572d8574fb
            ''',
            'available_capacity': '''
apiVersion: v1
items:
- apiVersion: csi-baremetal.dell.com/v1
  kind: AvailableCapacity
  metadata:
    name: 33d8aa02-cd15-4e7f-a3c0-14c2c390fc48
  spec:
    Size: 18360985190
    StorageClass: SSD
    Location: 4fdcb98b-7beb-4811-b906-3d7da1f788b5
    Node: masternode1
    NodeId: 6e172f8c-9d8b-41ac-99cf-44dab5da25f6
            '''
        },
        'kubernetes': {
            'target_pod': '''
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
  namespace: default
spec:
  containers:
  - name: test-container
    image: nginx
status:
  phase: Running
  containerStatuses:
  - restartCount: 0
            ''',
            'pvcs': '''
apiVersion: v1
items:
- apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    name: test-pvc-1
    namespace: default
  spec:
    accessModes:
    - ReadWriteOnce
    resources:
      requests:
        storage: 10Gi
    storageClassName: csi-baremetal-sc-ssdlvg
  status:
    phase: Bound
- apiVersion: v1
  kind: PersistentVolumeClaim
  metadata:
    name: test-pvc-2
    namespace: default
  spec:
    accessModes:
    - ReadWriteOnce
    resources:
      requests:
        storage: 5Gi
    storageClassName: csi-baremetal-sc-ssd
  status:
    phase: Bound
            ''',
            'pvs': '''
apiVersion: v1
items:
- apiVersion: v1
  kind: PersistentVolume
  metadata:
    name: pv-test-1
  spec:
    capacity:
      storage: 10Gi
    accessModes:
    - ReadWriteOnce
    persistentVolumeReclaimPolicy: Delete
    storageClassName: csi-baremetal-sc-ssdlvg
    nodeAffinity:
      required:
        nodeSelectorTerms:
        - matchExpressions:
          - key: kubernetes.io/hostname
            operator: In
            values:
            - masternode1
  status:
    phase: Bound
- apiVersion: v1
  kind: PersistentVolume
  metadata:
    name: pv-test-2
  spec:
    capacity:
      storage: 5Gi
    accessModes:
    - ReadWriteOnce
    persistentVolumeReclaimPolicy: Delete
    storageClassName: csi-baremetal-sc-ssd
    nodeAffinity:
      required:
        nodeSelectorTerms:
        - matchExpressions:
          - key: kubernetes.io/hostname
            operator: In
            values:
            - workernode1
  status:
    phase: Bound
            ''',
            'nodes': '''
apiVersion: v1
items:
- apiVersion: v1
  kind: Node
  metadata:
    name: masternode1
  status:
    conditions:
    - type: Ready
      status: "True"
    - type: DiskPressure
      status: "False"
    - type: MemoryPressure
      status: "False"
    nodeInfo:
      architecture: amd64
      kernelVersion: 5.14.0
      osImage: Ubuntu 20.04.3 LTS
- apiVersion: v1
  kind: Node
  metadata:
    name: workernode1
  status:
    conditions:
    - type: Ready
      status: "True"
    - type: DiskPressure
      status: "False"
    - type: MemoryPressure
      status: "False"
    nodeInfo:
      architecture: amd64
      kernelVersion: 5.14.0
      osImage: Ubuntu 20.04.3 LTS
            '''
        },
        'system': {
            'kernel_logs': '''
[  123.456789] nvme nvme0: pci function 0000:00:04.0
[  123.456790] nvme 0000:00:04.0: enabling device (0000 -> 0002)
[  123.456791] nvme nvme0: 1/0/0 default/read/poll queues
[  234.567890] scsi 2:0:0:0: Direct-Access     VMware   Virtual disk     2.0  PQ: 0 ANSI: 6
[  234.567891] sd 2:0:0:0: [sda] 585937500 512-byte logical blocks: (300 GB/279 GiB)
[  345.678901] EXT4-fs (sda1): mounted filesystem with ordered data mode
            ''',
            'journal_storage_logs': '''
Jan 15 10:30:15 masternode1 systemd[1]: Started CSI Baremetal Node Service.
Jan 15 10:30:16 masternode1 csi-baremetal-node[1234]: INFO: Drive 2a96dfec-47db-449d-9789-0d81660c2c4d detected
Jan 15 10:30:17 masternode1 csi-baremetal-node[1234]: INFO: LVG c15dd61c-e597-4392-bc5d-4c27b2d23a21 created successfully
            ''',
            'journal_kubelet_logs': '''
Jan 15 10:31:00 masternode1 kubelet[5678]: I0115 10:31:00.123456    5678 reconciler.go:224] "operationExecutor.VerifyControllerAttachedVolume started for volume \"test-pvc-1\" (UniqueName: \"kubernetes.io/csi/csi-baremetal^vol-test-pvc-1\") pod \"test-pod\" (UID: \"12345678-1234-1234-1234-123456789012\")"
Jan 15 10:31:01 masternode1 kubelet[5678]: I0115 10:31:01.234567    5678 reconciler.go:157] "Volume attached for pod" volumeName="test-pvc-1" podName="test-pod"
            '''
        },
        'smart_data': {
            '2a96dfec-47db-449d-9789-0d81660c2c4d': '''
smartctl 7.2 2020-12-30 r5155 [x86_64-linux-5.14.0] (local build)
Copyright (C) 2002-20, Bruce Allen, Christian Franke, www.smartmontools.org

=== START OF INFORMATION SECTION ===
Model Family:     VMware Virtual Disk
Device Model:     VMware Virtual disk
Serial Number:    6000c293fbf5f0fa45686547adedc378
Firmware Version: 2.0
User Capacity:    299,573,968,896 bytes [299 GB]

=== START OF READ SMART DATA SECTION ===
SMART overall-health self-assessment test result: PASSED

SMART Attributes Data Structure revision number: 1
Vendor Specific SMART Attributes with Thresholds:
ID# ATTRIBUTE_NAME          FLAGS    VALUE WORST THRESH FAIL RAW_VALUE
  1 Raw_Read_Error_Rate     POSR--   100   100   006    -    0
  3 Spin_Up_Time            PO----   100   100   000    -    0
  4 Start_Stop_Count        -O--CK   100   100   020    -    0
  5 Reallocated_Sector_Ct   PO--CK   100   100   036    -    0
  9 Power_On_Hours          -O--CK   100   100   000    -    1234
 12 Power_Cycle_Count       -O--CK   100   100   020    -    56
194 Temperature_Celsius     -O---K   100   100   000    -    35
197 Current_Pending_Sector  -O--C-   100   100   000    -    0
198 Offline_Uncorrectable   ----C-   100   100   000    -    0
            '''
        },
        'errors': []
    }
    
    # Create information collector with mock data
    collector = InformationCollector()
    collector.collected_data = mock_csi_data
    
    # Test volume chain discovery
    print("📊 Testing volume chain discovery...")
    volume_chain = {
        'pvcs': ['default/test-pvc-1', 'default/test-pvc-2'],
        'pvs': ['pv-test-1', 'pv-test-2'],
        'drives': ['2a96dfec-47db-449d-9789-0d81660c2c4d', '4ae92cbd-6fed-412a-a259-f627dac829c2'],
        'nodes': ['masternode1', 'workernode1']
    }
    
    # Build enhanced knowledge graph
    print("🔧 Building enhanced knowledge graph...")
    kg = await collector._build_knowledge_graph_from_tools(
        target_pod='test-pod',
        target_namespace='default',
        target_volume_path='/data',
        volume_chain=volume_chain
    )
    
    # Test knowledge graph structure
    print("\n📈 Knowledge Graph Summary:")
    summary = kg.get_summary()
    for entity_type, count in summary['entity_counts'].items():
        if count > 0:
            print(f"  • {entity_type}: {count}")
    
    print(f"\n🔗 Total Relationships: {summary['total_edges']}")
    print(f"⚠️  Total Issues: {summary['total_issues']}")
    
    # Test enhanced relationships
    print("\n🔍 Testing Enhanced CSI Relationships:")
    
    # Test Volume → LVG relationship
    volume_nodes = kg.find_nodes_by_type('Volume')
    for volume_id in volume_nodes:
        volume_attrs = kg.graph.nodes[volume_id]
        volume_name = volume_attrs.get('name')
        location_type = volume_attrs.get('LocationType')
        
        print(f"\n📦 Volume: {volume_name}")
        print(f"   Location Type: {location_type}")
        
        # Check relationships
        if location_type == 'LVG':
            lvg_connections = kg.find_connected_nodes(volume_id, 'bound_to')
            for lvg_id in lvg_connections:
                if lvg_id.startswith('LVG:'):
                    print(f"   ✅ Connected to LVG: {lvg_id}")
                    
                    # Check LVG → Drive relationships
                    drive_connections = kg.find_connected_nodes(lvg_id, 'contains')
                    for drive_id in drive_connections:
                        if drive_id.startswith('Drive:'):
                            print(f"      ✅ LVG contains Drive: {drive_id}")
        
        elif location_type == 'DRIVE':
            drive_connections = kg.find_connected_nodes(volume_id, 'bound_to')
            for drive_id in drive_connections:
                if drive_id.startswith('Drive:'):
                    print(f"   ✅ Connected to Drive: {drive_id}")
    
    # Test Drive → Node relationships
    print("\n🖥️  Testing Drive → Node Relationships:")
    drive_nodes = kg.find_nodes_by_type('Drive')
    for drive_id in drive_nodes:
        drive_attrs = kg.graph.nodes[drive_id]
        drive_uuid = drive_attrs.get('uuid')
        node_connections = kg.find_connected_nodes(drive_id, 'located_on')
        
        for node_id in node_connections:
            if node_id.startswith('Node:'):
                node_name = node_id.split(':')[-1]
                print(f"   ✅ Drive {drive_uuid[:8]}... located on Node: {node_name}")
    
    # Test SMART data integration
    print("\n🔬 Testing SMART Data Integration:")
    smart_system_nodes = [node for node in kg.graph.nodes() if 'smart_monitoring' in node]
    if smart_system_nodes:
        smart_system_id = smart_system_nodes[0]
        monitored_drives = kg.find_connected_nodes(smart_system_id, 'monitors')
        print(f"   ✅ SMART monitoring system tracks {len(monitored_drives)} drives")
    
    # Test issue detection
    print("\n⚠️  Testing Issue Detection:")
    all_issues = kg.get_all_issues()
    issue_types = {}
    for issue in all_issues:
        issue_type = issue['type']
        issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
    
    for issue_type, count in issue_types.items():
        print(f"   • {issue_type}: {count} issues")
    
    # Test path finding
    print("\n🛤️  Testing Path Finding:")
    pod_nodes = kg.find_nodes_by_type('Pod')
    drive_nodes = kg.find_nodes_by_type('Drive')
    
    if pod_nodes and drive_nodes:
        pod_id = pod_nodes[0]
        drive_id = drive_nodes[0]
        path = kg.find_path(pod_id, drive_id)
        
        if path:
            print(f"   ✅ Found path from Pod to Drive ({len(path)-1} hops):")
            for i in range(len(path)-1):
                source = path[i]
                target = path[i+1]
                edge_data = kg.graph.edges[source, target]
                relationship = edge_data.get('relationship', 'connected_to')
                
                source_type = kg.graph.nodes[source].get('entity_type', 'Unknown')
                target_type = kg.graph.nodes[target].get('entity_type', 'Unknown')
                
                print(f"      {source_type} --{relationship}--> {target_type}")
    
    # Print formatted knowledge graph
    print("\n" + "="*60)
    print("📊 ENHANCED KNOWLEDGE GRAPH VISUALIZATION")
    print("="*60)
    formatted_output = kg.print_graph(
        include_detailed_entities=True,
        include_relationships=True,
        include_issues=True,
        include_analysis=True
    )
    print(formatted_output)
    
    print("\n✅ Enhanced Knowledge Graph Test Completed Successfully!")
    return kg

if __name__ == "__main__":
    asyncio.run(test_enhanced_knowledge_graph())
