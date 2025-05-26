#!/usr/bin/env python3
"""
Resource cleanup tools for managing test resources.

This module provides tools for cleaning up test pods, PVCs, and other
resources created during troubleshooting and testing.
"""

import json
from typing import Dict, Any, List
from langchain_core.tools import tool
from tools.core.config import validate_command, execute_command

@tool
def cleanup_test_resources(namespace: str = "default", 
                          resource_types: str = "pod,pvc,storageclass",
                          label_selector: str = "test-type=troubleshooting") -> str:
    """
    Clean up test resources created during troubleshooting
    
    Args:
        namespace: Kubernetes namespace to clean up
        resource_types: Comma-separated list of resource types (pod,pvc,storageclass)
        label_selector: Label selector to identify test resources
        
    Returns:
        str: Results of cleanup operations
    """
    results = []
    resource_list = [rt.strip() for rt in resource_types.split(",")]
    
    try:
        for resource_type in resource_list:
            # List resources first
            cmd = ["kubectl", "get", resource_type, "-n", namespace, 
                   "-l", label_selector, "-o", "name"]
            list_result = execute_command(cmd)
            
            if list_result.strip():
                results.append(f"Found {resource_type} resources to delete:\n{list_result}")
                
                # Delete resources
                cmd = ["kubectl", "delete", resource_type, "-n", namespace, 
                       "-l", label_selector, "--ignore-not-found=true"]
                delete_result = execute_command(cmd)
                results.append(f"Deleted {resource_type} resources:\n{delete_result}")
            else:
                results.append(f"No {resource_type} resources found with label {label_selector}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error cleaning up test resources: {str(e)}"

@tool
def list_test_resources(namespace: str = "default", 
                       resource_types: str = "pod,pvc,storageclass,pv",
                       label_selector: str = "test-type=troubleshooting") -> str:
    """
    List all test resources created during troubleshooting
    
    Args:
        namespace: Kubernetes namespace to search
        resource_types: Comma-separated list of resource types to list
        label_selector: Label selector to identify test resources
        
    Returns:
        str: List of test resources
    """
    results = []
    resource_list = [rt.strip() for rt in resource_types.split(",")]
    
    try:
        for resource_type in resource_list:
            # For cluster-scoped resources like PV and StorageClass, don't use namespace
            if resource_type.lower() in ['pv', 'persistentvolume', 'storageclass']:
                cmd = ["kubectl", "get", resource_type, "-l", label_selector, "-o", "wide"]
            else:
                cmd = ["kubectl", "get", resource_type, "-n", namespace, 
                       "-l", label_selector, "-o", "wide"]
            
            list_result = execute_command(cmd)
            
            if list_result.strip():
                results.append(f"{resource_type.upper()} Resources:\n{list_result}")
            else:
                results.append(f"No {resource_type} resources found with label {label_selector}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error listing test resources: {str(e)}"

@tool
def cleanup_specific_test_pod(pod_name: str, namespace: str = "default", 
                             cleanup_pvc: bool = True) -> str:
    """
    Clean up a specific test pod and optionally its PVC
    
    Args:
        pod_name: Name of the pod to delete
        namespace: Kubernetes namespace
        cleanup_pvc: Whether to also delete associated PVC
        
    Returns:
        str: Results of cleanup operation
    """
    results = []
    
    try:
        # Get pod details first
        cmd = ["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "yaml"]
        pod_details = execute_command(cmd)
        
        # Extract PVC names from pod spec if cleanup_pvc is True
        pvc_names = []
        if cleanup_pvc:
            try:
                import yaml
                pod_data = yaml.safe_load(pod_details)
                volumes = pod_data.get('spec', {}).get('volumes', [])
                for volume in volumes:
                    if 'persistentVolumeClaim' in volume:
                        pvc_name = volume['persistentVolumeClaim']['claimName']
                        pvc_names.append(pvc_name)
            except Exception as e:
                results.append(f"Warning: Could not parse pod YAML to find PVCs: {str(e)}")
        
        # Delete the pod
        cmd = ["kubectl", "delete", "pod", pod_name, "-n", namespace, "--ignore-not-found=true"]
        pod_delete_result = execute_command(cmd)
        results.append(f"Pod Deletion:\n{pod_delete_result}")
        
        # Delete associated PVCs if requested
        if cleanup_pvc and pvc_names:
            for pvc_name in pvc_names:
                cmd = ["kubectl", "delete", "pvc", pvc_name, "-n", namespace, "--ignore-not-found=true"]
                pvc_delete_result = execute_command(cmd)
                results.append(f"PVC Deletion ({pvc_name}):\n{pvc_delete_result}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error cleaning up test pod {pod_name}: {str(e)}"

@tool
def cleanup_orphaned_pvs(label_selector: str = "test-type=troubleshooting") -> str:
    """
    Clean up orphaned PVs that are no longer bound to PVCs
    
    Args:
        label_selector: Label selector to identify test PVs
        
    Returns:
        str: Results of PV cleanup
    """
    results = []
    
    try:
        # List PVs with the label selector
        cmd = ["kubectl", "get", "pv", "-l", label_selector, "-o", "json"]
        pv_list_result = execute_command(cmd)
        
        if not pv_list_result.strip():
            return "No test PVs found with the specified label selector"
        
        try:
            import json
            pv_data = json.loads(pv_list_result)
            orphaned_pvs = []
            
            for pv in pv_data.get('items', []):
                pv_name = pv['metadata']['name']
                pv_status = pv.get('status', {}).get('phase', 'Unknown')
                
                # Check if PV is Available (not bound) or Failed
                if pv_status in ['Available', 'Failed']:
                    orphaned_pvs.append(pv_name)
                    results.append(f"Found orphaned PV: {pv_name} (Status: {pv_status})")
            
            # Delete orphaned PVs
            for pv_name in orphaned_pvs:
                cmd = ["kubectl", "delete", "pv", pv_name, "--ignore-not-found=true"]
                delete_result = execute_command(cmd)
                results.append(f"Deleted PV {pv_name}: {delete_result}")
            
            if not orphaned_pvs:
                results.append("No orphaned PVs found to clean up")
                
        except json.JSONDecodeError as e:
            return f"Error parsing PV list JSON: {str(e)}"
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error cleaning up orphaned PVs: {str(e)}"

@tool
def force_cleanup_stuck_resources(namespace: str = "default", 
                                 resource_type: str = "pod", 
                                 resource_name: str = None,
                                 label_selector: str = "test-type=troubleshooting") -> str:
    """
    Force cleanup of stuck resources using finalizer removal
    
    Args:
        namespace: Kubernetes namespace
        resource_type: Type of resource (pod, pvc, etc.)
        resource_name: Specific resource name (optional)
        label_selector: Label selector for multiple resources
        
    Returns:
        str: Results of force cleanup
    """
    results = []
    
    try:
        # Get list of resources to force delete
        if resource_name:
            resources = [resource_name]
        else:
            if resource_type.lower() in ['pv', 'persistentvolume', 'storageclass']:
                cmd = ["kubectl", "get", resource_type, "-l", label_selector, "-o", "name"]
            else:
                cmd = ["kubectl", "get", resource_type, "-n", namespace, 
                       "-l", label_selector, "-o", "name"]
            
            list_result = execute_command(cmd)
            resources = [r.split('/')[-1] for r in list_result.strip().split('\n') if r.strip()]
        
        if not resources:
            return f"No {resource_type} resources found to force cleanup"
        
        for resource in resources:
            # Try normal delete first
            if resource_type.lower() in ['pv', 'persistentvolume', 'storageclass']:
                cmd = ["kubectl", "delete", resource_type, resource, "--timeout=30s"]
            else:
                cmd = ["kubectl", "delete", resource_type, resource, "-n", namespace, "--timeout=30s"]
            
            try:
                delete_result = execute_command(cmd)
                results.append(f"Normal delete of {resource}: {delete_result}")
            except Exception:
                # If normal delete fails, try force delete
                results.append(f"Normal delete failed for {resource}, trying force delete...")
                
                # Remove finalizers
                patch_cmd = '{"metadata":{"finalizers":null}}'
                if resource_type.lower() in ['pv', 'persistentvolume', 'storageclass']:
                    cmd = ["kubectl", "patch", resource_type, resource, 
                           "-p", patch_cmd, "--type=merge"]
                else:
                    cmd = ["kubectl", "patch", resource_type, resource, "-n", namespace,
                           "-p", patch_cmd, "--type=merge"]
                
                try:
                    patch_result = execute_command(cmd)
                    results.append(f"Removed finalizers from {resource}: {patch_result}")
                except Exception as e:
                    results.append(f"Failed to remove finalizers from {resource}: {str(e)}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error force cleaning up resources: {str(e)}"
