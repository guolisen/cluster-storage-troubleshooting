#!/usr/bin/env python3
"""
Pod and resource creation tools for testing volume functionality.

This module provides tools for creating test pods, PVCs, and storage classes
to validate volume functionality during troubleshooting.
"""

import json
import yaml
from typing import Dict, Any
from langchain_core.tools import tool
from tools.core.config import validate_command, execute_command

@tool
def create_test_pod(pod_name: str, namespace: str = "default", 
                   pvc_name: str = None, mount_path: str = "Need a mount path",
                   image: str = "busybox:latest", storage_class: str = None) -> str:
    """
    Create a test pod with volume mount for testing volume functionality
    
    Args:
        pod_name: Name for the test pod
        namespace: Kubernetes namespace (default: default)
        pvc_name: Name of PVC to mount (if None, creates one)
        mount_path: Path to mount the volume in the pod, must have a valid path
        image: Container image to use (default: busybox:latest)
        storage_class: Storage class for PVC creation
        
    Returns:
        str: Result of pod creation
    """
    # If no PVC name provided, generate one
    if not pvc_name:
        pvc_name = f"{pod_name}-pvc"
    
    # Create PVC first if storage_class is provided
    pvc_yaml = None
    if storage_class:
        pvc_yaml = f"""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {pvc_name}
  namespace: {namespace}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: {storage_class}
"""
    
    # Create test pod YAML
    pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
  namespace: {namespace}
  labels:
    app: volume-test
    test-type: troubleshooting
spec:
  containers:
  - name: test-container
    image: {image}
    command: ["/bin/sh"]
    args: ["-c", "while true; do echo 'Test pod running...'; sleep 30; done"]
    volumeMounts:
    - name: test-volume
      mountPath: {mount_path}
  volumes:
  - name: test-volume
    persistentVolumeClaim:
      claimName: {pvc_name}
  restartPolicy: Never
"""
    
    results = []
    
    # Create PVC if needed
    if pvc_yaml:
        try:
            cmd = ["kubectl", "apply", "-f", "-"]
            # Create a process with stdin pipe to pass the YAML
            import subprocess
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            stdout, stderr = process.communicate(input=pvc_yaml)
            result = stdout if process.returncode == 0 else f"Error: {stderr}"
            results.append(f"PVC Creation: {result}")
        except Exception as e:
            return f"Error creating PVC: {str(e)}"
    
    # Create pod
    try:
        cmd = ["kubectl", "apply", "-f", "-"]
        # Create a process with stdin pipe to pass the YAML
        import subprocess
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, stderr = process.communicate(input=pod_yaml)
        result = stdout if process.returncode == 0 else f"Error: {stderr}"
        results.append(f"Pod Creation: {result}")
        
        # Wait for pod to be ready (optional check)
        cmd = ["kubectl", "wait", "--for=condition=Ready", f"pod/{pod_name}", 
               "-n", namespace, "--timeout=60s"]
        wait_result = execute_command(cmd, purpose="Waiting for pod to be ready")
        results.append(f"Pod Ready Status: {wait_result}")
        
        return "\n".join(results)
        
    except Exception as e:
        return f"Error creating test pod: {str(e)}"

@tool
def create_test_pvc(pvc_name: str, namespace: str = "default", 
                   storage_class: str = "csi-baremetal-sc-ssd", 
                   size: str = "1Gi", access_mode: str = "ReadWriteOnce") -> str:
    """
    Create a test PVC for volume testing
    
    Args:
        pvc_name: Name for the PVC
        namespace: Kubernetes namespace
        storage_class: Storage class to use
        size: Storage size (e.g., 1Gi, 500Mi)
        access_mode: Access mode (ReadWriteOnce, ReadWriteMany, etc.)
        
    Returns:
        str: Result of PVC creation
    """
    pvc_yaml = f"""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {pvc_name}
  namespace: {namespace}
  labels:
    test-type: troubleshooting
spec:
  accessModes:
    - {access_mode}
  resources:
    requests:
      storage: {size}
  storageClassName: {storage_class}
"""
    
    try:
        cmd = ["kubectl", "apply", "-f", "-"]
        # Create a process with stdin pipe to pass the YAML
        import subprocess
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, stderr = process.communicate(input=pvc_yaml)
        result = stdout if process.returncode == 0 else f"Error: {stderr}"
        
        # Check PVC status
        cmd = ["kubectl", "get", "pvc", pvc_name, "-n", namespace, "-o", "yaml"]
        status_result = execute_command(cmd, purpose="Checking PVC status")
        
        return f"PVC Creation: {result}\n\nPVC Status:\n{status_result}"
        
    except Exception as e:
        return f"Error creating test PVC: {str(e)}"

@tool
def create_test_storage_class(sc_name: str, provisioner: str = "csi-baremetal.dell.com",
                             drive_type: str = "SSD", fs_type: str = "ext4") -> str:
    """
    Create a test storage class for CSI Baremetal testing
    
    Args:
        sc_name: Name for the storage class
        provisioner: CSI provisioner (default: csi-baremetal.dell.com)
        drive_type: Drive type (SSD, HDD, NVMe)
        fs_type: Filesystem type (ext4, xfs)
        
    Returns:
        str: Result of storage class creation
    """
    sc_yaml = f"""
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: {sc_name}
  labels:
    test-type: troubleshooting
provisioner: {provisioner}
parameters:
  driveType: {drive_type}
  fsType: {fs_type}
allowVolumeExpansion: false
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Delete
"""
    
    try:
        cmd = ["kubectl", "apply", "-f", "-"]
        # Create a process with stdin pipe to pass the YAML
        import subprocess
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, stderr = process.communicate(input=sc_yaml)
        result = stdout if process.returncode == 0 else f"Error: {stderr}"
        
        # Verify storage class
        cmd = ["kubectl", "get", "storageclass", sc_name, "-o", "yaml"]
        verify_result = execute_command(cmd, purpose="Verifying storage class")
        
        return f"Storage Class Creation: {result}\n\nStorage Class Details:\n{verify_result}"
        
    except Exception as e:
        return f"Error creating test storage class: {str(e)}"
