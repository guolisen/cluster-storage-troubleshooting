#!/usr/bin/env python3
"""
Demo script to show the nice formatted Knowledge Graph output

This script demonstrates the print_graph functionality added to the KnowledgeGraph class.
"""

from knowledge_graph import KnowledgeGraph

def demo_knowledge_graph_print():
    """Demonstrate the formatted knowledge graph print functionality"""
    
    # Create a sample knowledge graph
    kg = KnowledgeGraph()
    
    # Add some sample entities
    pod_id = kg.add_pod("test-pod", "default", volume_path="/mnt/data")
    pvc_id = kg.add_pvc("test-pvc", "default", storageClass="csi-baremetal-sc")
    pv_id = kg.add_pv("pv-12345", disk_path="/dev/sdb1")
    drive_id = kg.add_drive("drive-uuid-123", Health="GOOD", Status="ONLINE", Path="/dev/sdb")
    node_id = kg.add_node("worker-node-1", Ready=True, DiskPressure=False)
    sc_id = kg.add_storage_class("csi-baremetal-sc", provisioner="csi-baremetal.dell.com")
    
    # Add relationships
    kg.add_relationship(pod_id, pvc_id, "uses")
    kg.add_relationship(pvc_id, pv_id, "bound_to")
    kg.add_relationship(pv_id, drive_id, "maps_to")
    kg.add_relationship(pv_id, node_id, "affinity_to")
    kg.add_relationship(pvc_id, sc_id, "uses_storage_class")
    
    # Add some sample issues
    kg.add_issue(pod_id, "permission", "Pod cannot write to volume due to permission denied", "medium")
    kg.add_issue(drive_id, "disk_health", "Drive showing early signs of wear", "low")
    
    # Add another problematic drive to show patterns
    bad_drive_id = kg.add_drive("drive-uuid-456", Health="SUSPECT", Status="ONLINE", Path="/dev/sdc")
    kg.add_issue(bad_drive_id, "disk_health", "Drive has health status: SUSPECT", "high")
    
    print("=" * 80)
    print("KNOWLEDGE GRAPH DEMO - FORMATTED OUTPUT")
    print("=" * 80)
    print()
    
    # Print the formatted graph
    formatted_output = kg.print_graph()
    print(formatted_output)
    
    print("\n" + "=" * 80)
    print("This demonstrates how the Knowledge Graph will be displayed")
    print("after build_knowledge_graph is called during troubleshooting!")
    print("=" * 80)

if __name__ == "__main__":
    demo_knowledge_graph_print()
