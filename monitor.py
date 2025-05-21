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
from kubernetes import client, config
from kubernetes.client.rest import ApiException

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
                    invoke_troubleshooting(pod_name, namespace, volume_path)
            
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

def invoke_troubleshooting(pod_name, namespace, volume_path):
    """
    Invoke the troubleshooting workflow for a pod with volume I/O error
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
    """
    try:
        cmd = ["python3", "troubleshoot.py", pod_name, namespace, volume_path]
        logging.info(f"Invoking troubleshooting: {' '.join(cmd)}")
        
        # Use Popen to run the troubleshooting script in the background
        subprocess.Popen(cmd)
        logging.info(f"Troubleshooting workflow started for pod {namespace}/{pod_name}, volume {volume_path}")
    except Exception as e:
        logging.error(f"Failed to invoke troubleshooting: {e}")

def main():
    """Main function"""
    # Load configuration
    config_data = load_config()
    
    # Set up logging
    setup_logging(config_data)
    
    logging.info("Starting Kubernetes volume I/O error monitoring")
    
    # Initialize Kubernetes client
    kube_client = init_kubernetes_client()
    
    # Get monitoring interval
    interval = config_data['monitor']['interval_seconds']
    logging.info(f"Monitoring interval: {interval} seconds")
    
    # Main monitoring loop
    try:
        while True:
            monitor_pods(kube_client, config_data)
            time.sleep(interval)
    except KeyboardInterrupt:
        logging.info("Monitoring stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
