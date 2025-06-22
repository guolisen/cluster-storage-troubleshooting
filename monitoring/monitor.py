#!/usr/bin/env python3
"""
Kubernetes Volume I/O Error Monitoring Script

This script monitors all pods in a Kubernetes cluster for volume I/O errors
by checking for the 'volume-io-error' annotation. When an error is detected,
it invokes the troubleshooting workflow.
"""

import os
import time
import yaml
import logging
import subprocess
import sys
import json
import tempfile
import glob
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Dictionary to track ongoing troubleshooting processes
# Key: "{namespace}/{pod_name}/{volume_path}", Value: (process, start_time)
active_troubleshooting = {}

# Directory where troubleshooting results are stored
RESULTS_DIR = os.path.join(tempfile.gettempdir(), "k8s-troubleshooting-results")

def load_config():
    """Load configuration from config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        sys.exit(1)

def setup_logging(config_data):
    """Configure logging based on configuration"""
    log_file = config_data['logging']['file']
    log_to_stdout = config_data['logging']['stdout']
    
    handlers = []
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    if log_to_stdout:
        handlers.append(logging.StreamHandler())
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
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

def add_troubleshooting_result_annotation(kube_client, pod_name, namespace, result_summary):
    """
    Add the troubleshooting result as an annotation to a pod
    
    Args:
        kube_client: Kubernetes API client
        pod_name: Name of the pod
        namespace: Namespace of the pod
        result_summary: Summary of the investigation result
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the current pod
        pod = kube_client.read_namespaced_pod(name=pod_name, namespace=namespace)
        
        # Ensure annotations dictionary exists
        if not pod.metadata.annotations:
            pod.metadata.annotations = {}
        
        # Add the result annotation
        pod.metadata.annotations['volume-io-troubleshooting-result'] = result_summary
        
        # Update the pod
        kube_client.patch_namespaced_pod(
            name=pod_name,
            namespace=namespace,
            body={"metadata": {"annotations": pod.metadata.annotations}}
        )
        
        logging.info(f"Successfully added troubleshooting result annotation to pod {namespace}/{pod_name}")
        return True
    except ApiException as e:
        logging.error(f"Kubernetes API error while adding result annotation: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error while adding result annotation: {e}")
        return False

def remove_volume_io_error_annotation(kube_client, pod_name, namespace):
    """
    Remove the 'volume-io-error' annotation from a pod
    
    Args:
        kube_client: Kubernetes API client
        pod_name: Name of the pod
        namespace: Namespace of the pod
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the current pod
        pod = kube_client.read_namespaced_pod(name=pod_name, namespace=namespace)
        
        # If the pod has no annotations or no volume-io-error annotation, nothing to do
        if not pod.metadata.annotations or 'volume-io-error' not in pod.metadata.annotations:
            logging.debug(f"No 'volume-io-error' annotation found on pod {namespace}/{pod_name}")
            return True
        
        # Create a JSON patch to explicitly remove the annotation
        patch_body = {
            "metadata": {
                "annotations": {
                    "volume-io-error": None  # Setting to None explicitly removes the key
                }
            }
        }
        
        # Update the pod with explicit removal
        kube_client.patch_namespaced_pod(
            name=pod_name,
            namespace=namespace,
            body=patch_body
        )
        
        # Verify the annotation was actually removed
        updated_pod = kube_client.read_namespaced_pod(name=pod_name, namespace=namespace)
        if updated_pod.metadata.annotations and 'volume-io-error' in updated_pod.metadata.annotations:
            logging.warning(f"Failed to remove 'volume-io-error' annotation from pod {namespace}/{pod_name} - annotation still exists after patch")
            return False
            
        logging.info(f"Successfully removed 'volume-io-error' annotation from pod {namespace}/{pod_name}")
        return True
    except ApiException as e:
        logging.error(f"Kubernetes API error while removing annotation: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error while removing annotation: {e}")
        return False

def find_troubleshooting_result(namespace, pod_name, volume_path):
    """
    Find the troubleshooting result file for a specific pod and volume
    
    Args:
        namespace: Namespace of the pod
        pod_name: Name of the pod
        volume_path: Path of the volume
    
    Returns:
        tuple: (result_summary, filepath) or (None, None) if not found
    """
    try:
        # Create the expected filename pattern
        filename = f"{namespace}_{pod_name}_{volume_path.replace('/', '_')}.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        
        # Check if the file exists
        if os.path.exists(filepath):
            # Read the file
            with open(filepath, 'r') as f:
                result_data = json.load(f)
                
            # Return the result summary
            return result_data.get('result_summary'), filepath
    except Exception as e:
        logging.error(f"Error reading troubleshooting result file: {e}")
    
    return None, None

def check_completed_troubleshooting(kube_client):
    """
    Check for completed troubleshooting processes and clean up
    
    Args:
        kube_client: Kubernetes API client
    """
    global active_troubleshooting
    
    # List of keys to remove
    completed = []
    
    # Check each active troubleshooting process
    for key, (process, _) in active_troubleshooting.items():
        # Check if process has completed (poll() returns None if still running)
        if process.poll() is not None:
            # Process has completed
            namespace, pod_name, volume_path = key.split('/', 2)
            
            # Look for troubleshooting result
            result_summary, result_filepath = find_troubleshooting_result(namespace, pod_name, volume_path)
            
            # Add the result as an annotation if found
            if result_summary:
                if add_troubleshooting_result_annotation(kube_client, pod_name, namespace, result_summary):
                    logging.info(f"Added troubleshooting result annotation to pod {namespace}/{pod_name}")
                    
                    # Remove the result file
                    try:
                        os.remove(result_filepath)
                        logging.debug(f"Removed result file {result_filepath}")
                    except Exception as e:
                        logging.warning(f"Failed to remove result file {result_filepath}: {e}")
                else:
                    logging.warning(f"Failed to add troubleshooting result annotation to pod {namespace}/{pod_name}")
            
            # Remove the error annotation
            if remove_volume_io_error_annotation(kube_client, pod_name, namespace):
                logging.info(f"Troubleshooting completed for {key}, annotation removed")
            else:
                logging.warning(f"Failed to remove annotation for {key} after troubleshooting completed")
            
            # Mark for removal
            completed.append(key)
    
    # Remove completed processes from tracking
    for key in completed:
        del active_troubleshooting[key]
        logging.debug(f"Removed {key} from active troubleshooting tracking")

def monitor_pods(kube_client, config_data):
    """
    Monitor all pods for volume I/O errors
    
    Args:
        kube_client: Kubernetes API client
        config_data: Configuration data from config.yaml
    """
    retry_count = 0
    max_retries = config_data['monitor']['api_retries']
    backoff_seconds = config_data['monitor']['retry_backoff_seconds']
    
    # First, check for any completed troubleshooting processes
    check_completed_troubleshooting(kube_client)
    
    while retry_count <= max_retries:
        try:
            pods = kube_client.list_pod_for_all_namespaces(watch=False)
            logging.debug(f"Found {len(pods.items)} pods in the cluster")
            
            for pod in pods.items:
                if pod.metadata.annotations and 'volume-io-error' in pod.metadata.annotations:
                    volume_path = pod.metadata.annotations['volume-io-error']
                    pod_name = pod.metadata.name
                    namespace = pod.metadata.namespace
                    
                    logging.info(f"Detected volume I/O error in pod {namespace}/{pod_name} at path {volume_path}")
                    invoke_troubleshooting(kube_client, pod_name, namespace, volume_path)
            
            # If we get here, the API call was successful
            return
            
        except ApiException as e:
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = backoff_seconds * (2 ** (retry_count - 1))  # Exponential backoff
                logging.warning(f"Kubernetes API error: {e}. Retrying in {wait_time} seconds (attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
            else:
                logging.error(f"Failed to monitor pods after {max_retries} retries: {e}")
                return
        except Exception as e:
            logging.error(f"Unexpected error monitoring pods: {e}")
            return

def invoke_troubleshooting(kube_client, pod_name, namespace, volume_path):
    """
    Invoke the troubleshooting workflow for a pod with volume I/O error
    
    Args:
        kube_client: Kubernetes API client
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
    """
    global active_troubleshooting
    
    # Create a unique key for this volume
    key = f"{namespace}/{pod_name}/{volume_path}"
    
    # Check if troubleshooting is already in progress for this volume
    if key in active_troubleshooting:
        process, start_time = active_troubleshooting[key]
        
        # Check if process is still running
        if process.poll() is None:
            # Process is still running
            elapsed = time.time() - start_time
            logging.info(f"Troubleshooting already in progress for {key} (started {elapsed:.1f} seconds ago)")
            return
        else:
            # Process has completed but wasn't cleaned up
            logging.info(f"Previous troubleshooting for {key} completed, removing annotation and tracking")
            remove_volume_io_error_annotation(kube_client, pod_name, namespace)
            del active_troubleshooting[key]
    
    try:
        cmd = ["python3", "troubleshooting/troubleshoot.py", pod_name, namespace, volume_path]
        logging.info(f"Invoking troubleshooting: {' '.join(cmd)}")
        
        # Use Popen to run the troubleshooting script in the background
        process = subprocess.Popen(cmd)
        
        # Track the process
        active_troubleshooting[key] = (process, time.time())
        
        logging.info(f"Troubleshooting workflow started for pod {namespace}/{pod_name}, volume {volume_path}")
        logging.info(f"Two-phase process will run: Analysis followed by Remediation (if approved or auto_fix is enabled)")
    except Exception as e:
        logging.error(f"Failed to invoke troubleshooting: {e}")

def ensure_results_dir():
    """Ensure the results directory exists"""
    try:
        if not os.path.exists(RESULTS_DIR):
            os.makedirs(RESULTS_DIR)
            logging.debug(f"Created results directory: {RESULTS_DIR}")
    except Exception as e:
        logging.error(f"Failed to create results directory: {e}")

def main():
    """Main function"""
    # Load configuration
    config_data = load_config()
    
    # Set up logging
    setup_logging(config_data)
    
    # Ensure results directory exists
    ensure_results_dir()
    
    logging.info("Starting Kubernetes volume I/O error monitoring")
    
    # Initialize Kubernetes client
    kube_client = init_kubernetes_client()
    
    # Get monitoring interval
    interval = config_data['monitor']['interval_seconds']
    logging.info(f"Monitoring interval: {interval} seconds")
    
    # Log troubleshooting mode settings
    interactive_mode = config_data['troubleshoot']['interactive_mode']
    auto_fix = config_data['troubleshoot']['auto_fix']
    logging.info(f"Troubleshooting settings: interactive_mode={interactive_mode}, auto_fix={auto_fix}")
    
    # Main monitoring loop
    try:
        while True:
            monitor_pods(kube_client, config_data)
            # Log active troubleshooting count
            if active_troubleshooting:
                logging.debug(f"Active troubleshooting processes: {len(active_troubleshooting)}")
            time.sleep(interval)
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
