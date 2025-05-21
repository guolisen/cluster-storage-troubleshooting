#!/usr/bin/env python3
"""
Test script for the Kubernetes Volume Troubleshooting System

This script simulates a volume I/O error in a Kubernetes pod and demonstrates
how to use the troubleshooting workflow to diagnose and resolve the issue.
"""

import os
import sys
import yaml
import logging
import subprocess
import time
import argparse
from kubernetes import client, config

def setup_logging():
    """Set up logging for the test script"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

def init_kubernetes_client():
    """Initialize Kubernetes client"""
    try:
        # Try to load in-cluster config first (when running inside a pod)
        if 'KUBERNETES_SERVICE_HOST' in os.environ:
            config.load_incluster_config()
            logging.info("Using in-cluster Kubernetes configuration")
        else:
            # Fall back to kubeconfig file
            config.load_kube_config()
            logging.info("Using kubeconfig file for Kubernetes configuration")
        
        return client.CoreV1Api()
    except Exception as e:
        logging.error(f"Failed to initialize Kubernetes client: {e}")
        sys.exit(1)

def create_test_pod_with_volume(kube_client, namespace="default"):
    """
    Create a test pod with a volume that will simulate an I/O error
    
    Args:
        kube_client: Kubernetes API client
        namespace: Namespace to create the pod in
        
    Returns:
        tuple: (pod_name, volume_path)
    """
    # Generate unique names
    pod_name = f"test-pod-{int(time.time())}"
    pvc_name = f"test-pvc-{int(time.time())}"
    
    # Create PVC YAML
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
  storageClassName: csi-baremetal-sc-ssd
"""
    
    # Create Pod YAML
    pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
  namespace: {namespace}
spec:
  containers:
  - name: test-container
    image: busybox
    command: ["/bin/sh", "-c", "echo 'Test' > /mnt/test.txt && cat /mnt/test.txt && sleep 3600"]
    volumeMounts:
    - mountPath: "/mnt"
      name: test-volume
  volumes:
  - name: test-volume
    persistentVolumeClaim:
      claimName: {pvc_name}
"""
    
    # Write YAML files
    with open(f"{pvc_name}.yaml", "w") as f:
        f.write(pvc_yaml)
    
    with open(f"{pod_name}.yaml", "w") as f:
        f.write(pod_yaml)
    
    # Apply YAML files
    logging.info(f"Creating PVC {namespace}/{pvc_name}")
    subprocess.run(["kubectl", "apply", "-f", f"{pvc_name}.yaml"], check=True)
    
    logging.info(f"Creating Pod {namespace}/{pod_name}")
    subprocess.run(["kubectl", "apply", "-f", f"{pod_name}.yaml"], check=True)
    
    # Wait for pod to start
    logging.info("Waiting for pod to start...")
    time.sleep(10)
    
    # Get pod status
    pod_status = subprocess.run(
        ["kubectl", "get", "pod", pod_name, "-n", namespace],
        check=True,
        capture_output=True,
        text=True
    )
    logging.info(f"Pod status:\n{pod_status.stdout}")
    
    # Return pod name and volume path
    volume_path = "/mnt"
    return pod_name, volume_path

def simulate_volume_io_error(kube_client, pod_name, volume_path, namespace="default"):
    """
    Simulate a volume I/O error by adding an annotation to the pod
    
    Args:
        kube_client: Kubernetes API client
        pod_name: Name of the pod
        volume_path: Path of the volume
        namespace: Namespace of the pod
    """
    try:
        # Get the pod
        pod = kube_client.read_namespaced_pod(pod_name, namespace)
        
        # Add annotation
        if pod.metadata.annotations is None:
            pod.metadata.annotations = {}
        
        pod.metadata.annotations["volume-io-error"] = volume_path
        
        # Update the pod
        kube_client.patch_namespaced_pod(
            name=pod_name,
            namespace=namespace,
            body=pod
        )
        
        logging.info(f"Added volume-io-error annotation to pod {namespace}/{pod_name} for volume path {volume_path}")
    except Exception as e:
        logging.error(f"Failed to simulate volume I/O error: {e}")
        sys.exit(1)

def run_troubleshooting(pod_name, namespace, volume_path):
    """
    Run the troubleshooting workflow
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
    """
    logging.info(f"Running troubleshooting workflow for pod {namespace}/{pod_name}, volume {volume_path}")
    
    try:
        # Run troubleshooting script
        subprocess.run(
            ["python", "troubleshoot.py", pod_name, namespace, volume_path],
            check=True
        )
    except subprocess.CalledProcessError as e:
        logging.error(f"Troubleshooting failed with exit code {e.returncode}")
    except Exception as e:
        logging.error(f"Failed to run troubleshooting: {e}")

def cleanup(pod_name, pvc_name, namespace="default"):
    """
    Clean up test resources
    
    Args:
        pod_name: Name of the pod to delete
        pvc_name: Name of the PVC to delete
        namespace: Namespace of the resources
    """
    try:
        logging.info(f"Cleaning up test resources in namespace {namespace}")
        
        # Delete pod
        subprocess.run(
            ["kubectl", "delete", "pod", pod_name, "-n", namespace],
            check=True
        )
        
        # Delete PVC
        subprocess.run(
            ["kubectl", "delete", "pvc", pvc_name, "-n", namespace],
            check=True
        )
        
        # Delete YAML files
        if os.path.exists(f"{pod_name}.yaml"):
            os.remove(f"{pod_name}.yaml")
        
        if os.path.exists(f"{pvc_name}.yaml"):
            os.remove(f"{pvc_name}.yaml")
        
        logging.info("Cleanup completed")
    except Exception as e:
        logging.error(f"Failed to clean up resources: {e}")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test the Kubernetes Volume Troubleshooting System")
    parser.add_argument("--namespace", default="default", help="Namespace to create test resources in")
    parser.add_argument("--cleanup", action="store_true", help="Clean up test resources after running")
    parser.add_argument("--existing-pod", help="Use an existing pod instead of creating a new one")
    parser.add_argument("--volume-path", default="/mnt", help="Volume path to use for the error")
    
    return parser.parse_args()

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging
    setup_logging()
    
    logging.info("Starting Kubernetes Volume Troubleshooting System test")
    
    # Initialize Kubernetes client
    kube_client = init_kubernetes_client()
    
    pod_name = args.existing_pod
    volume_path = args.volume_path
    pvc_name = None
    
    try:
        # Create test pod if not using an existing one
        if not pod_name:
            pod_name, volume_path = create_test_pod_with_volume(kube_client, args.namespace)
            pvc_name = f"test-pvc-{pod_name.split('-')[-1]}"
        
        # Simulate volume I/O error
        simulate_volume_io_error(kube_client, pod_name, volume_path, args.namespace)
        
        # Run troubleshooting
        run_troubleshooting(pod_name, args.namespace, volume_path)
        
        # Clean up if requested
        if args.cleanup and pvc_name:
            cleanup(pod_name, pvc_name, args.namespace)
    except KeyboardInterrupt:
        logging.info("Test stopped by user")
    except Exception as e:
        logging.error(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
