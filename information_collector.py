#!/usr/bin/env python3
"""
Comprehensive Information Collector for Kubernetes Volume Troubleshooting

This module implements the pre-collection phase that gathers all necessary
diagnostic information before LangGraph execution, builds a complete Knowledge Graph,
and provides rich context for efficient troubleshooting.

This module is designed to be imported by troubleshoot.py for the main orchestration.
"""

import os
import yaml
import logging
import asyncio
import time
import subprocess
import json
import paramiko
from typing import Dict, List, Any, Optional, Set
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from knowledge_graph import KnowledgeGraph


class ComprehensiveInformationCollector:
    """Comprehensive Information Collector for pre-collection phase"""
    
    def __init__(self, config_data: Dict[str, Any]):
        """Initialize the Comprehensive Information Collector"""
        self.config = config_data
        self.k8s_client = None
        self.knowledge_graph = KnowledgeGraph()
        self.collected_data = {
            'kubernetes': {},
            'csi_baremetal': {},
            'logs': {},
            'system': {},
            'ssh_data': {},
            'errors': []
        }
        
        # Initialize Kubernetes client
        self._init_kubernetes_client()
        
        # SSH clients cache
        self.ssh_clients = {}
        
        logging.info("Comprehensive Information Collector initialized")
    
    def _init_kubernetes_client(self):
        """Initialize Kubernetes client"""
        try:
            if 'KUBERNETES_SERVICE_HOST' in os.environ:
                config.load_incluster_config()
                logging.info("Using in-cluster Kubernetes configuration")
            else:
                config.load_kube_config()
                logging.info("Using kubeconfig file for Kubernetes configuration")
            
            self.k8s_client = client.CoreV1Api()
        except Exception as e:
            logging.error(f"Failed to initialize Kubernetes client: {e}")
            raise
    
    def _execute_command_safe(self, command_list: List[str], purpose: str) -> str:
        """Execute a command safely and return its output"""
        try:
            logging.debug(f"Executing command: {' '.join(command_list)}")
            result = subprocess.run(
                command_list, 
                shell=False, 
                check=True,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=30
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed with exit code {e.returncode}: {e.stderr}"
            logging.warning(f"Command failed ({purpose}): {error_msg}")
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Failed to execute command: {str(e)}"
            logging.warning(f"Command execution error ({purpose}): {error_msg}")
            return f"Error: {error_msg}"
    
    async def comprehensive_collect(self, 
                                   target_pod: str = None, 
                                   target_namespace: str = None,
                                   target_volume_path: str = None) -> Dict[str, Any]:
        """
        Perform comprehensive data collection across all sources
        
        This is the main entry point for Phase 0: Pre-Collection
        All kubectl commands and data gathering happens here to avoid tool loops
        """
        logging.info("=== PHASE 0: PRE-COLLECTION - Starting comprehensive data collection ===")
        start_time = time.time()
        
        try:
            # Collect Kubernetes resources
            logging.info("Collecting Kubernetes resources...")
            k8s_data = await self._collect_kubernetes_resources()
            self.collected_data['kubernetes'] = k8s_data
            
            # Collect CSI Baremetal resources
            logging.info("Collecting CSI Baremetal resources...")
            csi_data = await self._collect_csi_baremetal_resources()
            self.collected_data['csi_baremetal'] = csi_data
            
            # Collect logs and events
            logging.info("Collecting logs and events...")
            logs_data = await self._collect_logs_and_events(target_pod, target_namespace)
            self.collected_data['logs'] = logs_data
            
            # Collect system diagnostics
            logging.info("Collecting system diagnostics...")
            system_data = await self._collect_system_diagnostics()
            self.collected_data['system'] = system_data
            
            # Build comprehensive Knowledge Graph
            logging.info("Building comprehensive Knowledge Graph...")
            self.knowledge_graph = await self._build_comprehensive_knowledge_graph(
                target_pod, target_namespace, target_volume_path
            )
            
            # Perform analysis
            analysis = self.knowledge_graph.analyze_issues()
            fix_plan = self.knowledge_graph.generate_fix_plan(analysis)
            
            # Create context summary
            context_summary = self._create_context_summary(analysis, fix_plan)
            
            # Final collection summary
            collection_time = time.time() - start_time
            
            result = {
                'collected_data': self.collected_data,
                'knowledge_graph': self.knowledge_graph,
                'context_summary': context_summary,
                'collection_metadata': {
                    'collection_time': collection_time,
                    'target_pod': target_pod,
                    'target_namespace': target_namespace,
                    'target_volume_path': target_volume_path,
                    'total_errors': len(self.collected_data['errors'])
                }
            }
            
            logging.info(f"=== PHASE 0: PRE-COLLECTION completed in {collection_time:.2f} seconds ===")
            return result
            
        except Exception as e:
            error_msg = f"Error during comprehensive collection: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
            raise
    
    async def _collect_kubernetes_resources(self) -> Dict[str, Any]:
        """Collect all relevant Kubernetes resources"""
        k8s_data = {
            'pods': {},
            'pvcs': {},
            'pvs': {},
            'nodes': {},
            'events': {}
        }
        
        try:
            # Collect pods from all namespaces
            pods = self.k8s_client.list_pod_for_all_namespaces()
            for pod in pods.items:
                pod_key = f"{pod.metadata.namespace}/{pod.metadata.name}"
                k8s_data['pods'][pod_key] = pod.to_dict()
            
            # Collect PVCs from all namespaces
            pvcs = self.k8s_client.list_persistent_volume_claim_for_all_namespaces()
            for pvc in pvcs.items:
                pvc_key = f"{pvc.metadata.namespace}/{pvc.metadata.name}"
                k8s_data['pvcs'][pvc_key] = pvc.to_dict()
            
            # Collect PVs
            pvs = self.k8s_client.list_persistent_volume()
            for pv in pvs.items:
                k8s_data['pvs'][pv.metadata.name] = pv.to_dict()
            
            # Collect nodes
            nodes = self.k8s_client.list_node()
            for node in nodes.items:
                k8s_data['nodes'][node.metadata.name] = node.to_dict()
            
            # Collect events
            events = self.k8s_client.list_event_for_all_namespaces()
            for event in events.items:
                event_key = f"{event.metadata.namespace}/{event.metadata.name}"
                k8s_data['events'][event_key] = event.to_dict()
            
            logging.info(f"Collected Kubernetes resources: {len(k8s_data['pods'])} pods, "
                        f"{len(k8s_data['pvcs'])} PVCs, {len(k8s_data['pvs'])} PVs")
            
        except Exception as e:
            error_msg = f"Error collecting Kubernetes resources: {e}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
        
        return k8s_data
    
    async def _collect_csi_baremetal_resources(self) -> Dict[str, Any]:
        """Collect CSI Baremetal specific resources"""
        csi_data = {
            'drives': {},
            'crd_status': {}
        }
        
        # Check for CSI Baremetal drives
        drives_cmd = self._execute_command_safe(
            ["kubectl", "get", "drives", "-o", "yaml"],
            "Get CSI Baremetal drives"
        )
        
        csi_data['crd_status']['drives'] = not drives_cmd.startswith("Error:")
        
        if csi_data['crd_status']['drives']:
            try:
                import yaml as yaml_parser
                parsed_data = yaml_parser.safe_load(drives_cmd)
                if parsed_data and 'items' in parsed_data:
                    for item in parsed_data['items']:
                        drive_name = item.get('metadata', {}).get('name', 'unknown')
                        csi_data['drives'][drive_name] = item
            except Exception as e:
                logging.warning(f"Failed to parse drives YAML: {e}")
        
        return csi_data
    
    async def _collect_logs_and_events(self, target_pod: str = None, target_namespace: str = None) -> Dict[str, Any]:
        """Collect logs and events"""
        logs_data = {
            'pod_logs': {},
            'volume_events': []
        }
        
        # Collect target pod logs
        if target_pod and target_namespace:
            try:
                pod_logs = self.k8s_client.read_namespaced_pod_log(
                    name=target_pod,
                    namespace=target_namespace,
                    tail_lines=200
                )
                logs_data['pod_logs'][f"{target_namespace}/{target_pod}"] = pod_logs
            except Exception as e:
                logging.warning(f"Failed to collect logs for pod {target_namespace}/{target_pod}: {e}")
        
        # Collect volume-related events
        try:
            events = self.k8s_client.list_event_for_all_namespaces()
            volume_keywords = ['volume', 'mount', 'pvc', 'pv', 'storage', 'disk', 'io']
            
            for event in events.items:
                event_message = event.message.lower() if event.message else ""
                event_reason = event.reason.lower() if event.reason else ""
                
                if any(keyword in event_message or keyword in event_reason for keyword in volume_keywords):
                    logs_data['volume_events'].append({
                        'namespace': event.metadata.namespace,
                        'name': event.metadata.name,
                        'reason': event.reason,
                        'message': event.message,
                        'type': event.type
                    })
        except Exception as e:
            logging.warning(f"Failed to collect events: {e}")
        
        return logs_data
    
    async def _collect_system_diagnostics(self) -> Dict[str, Any]:
        """Collect system-level diagnostics"""
        system_data = {
            'disk_usage': {},
            'kernel_logs': {}
        }
        
        # Disk usage
        df_output = self._execute_command_safe(["df", "-h"], "Get disk usage")
        if not df_output.startswith("Error:"):
            system_data['disk_usage']['df_h'] = df_output
        
        # Kernel error messages
        dmesg_errors = self._execute_command_safe(
            ["sh", "-c", "dmesg | grep -i 'error\\|disk\\|io' | tail -20"],
            "Get kernel error messages"
        )
        if not dmesg_errors.startswith("Error:"):
            system_data['kernel_logs']['dmesg_errors'] = dmesg_errors
        
        return system_data
    
    async def _build_comprehensive_knowledge_graph(self, 
                                                  target_pod: str = None, 
                                                  target_namespace: str = None,
                                                  target_volume_path: str = None) -> KnowledgeGraph:
        """Build comprehensive Knowledge Graph from collected data"""
        logging.info("Building comprehensive Knowledge Graph...")
        
        # Reset Knowledge Graph
        self.knowledge_graph = KnowledgeGraph()
        
        # Process Kubernetes resources
        if 'kubernetes' in self.collected_data:
            k8s_data = self.collected_data['kubernetes']
            
            # Add pods and their relationships
            for pod_key, pod_data in k8s_data.get('pods', {}).items():
                namespace = pod_data.get('metadata', {}).get('namespace', 'unknown')
                name = pod_data.get('metadata', {}).get('name', 'unknown')
                node_name = pod_data.get('spec', {}).get('nodeName', 'unknown')
                
                pod_id = self.knowledge_graph.add_pod(
                    name, namespace, 
                    volume_path=target_volume_path if name == target_pod else '',
                    node_name=node_name,
                    status=pod_data.get('status', {}).get('phase', 'Unknown')
                )
                
                # Add node relationships and issues
                if node_name != 'unknown':
                    node_data = k8s_data.get('nodes', {}).get(node_name, {})
                    conditions = node_data.get('status', {}).get('conditions', [])
                    
                    node_ready = True
                    disk_pressure = False
                    for condition in conditions:
                        if condition.get('type') == 'Ready':
                            node_ready = condition.get('status') == 'True'
                        elif condition.get('type') == 'DiskPressure':
                            disk_pressure = condition.get('status') == 'True'
                    
                    node_id = self.knowledge_graph.add_node(
                        node_name,
                        Ready=node_ready,
                        DiskPressure=disk_pressure
                    )
                    
                    self.knowledge_graph.add_relationship(pod_id, node_id, "scheduled_on")
                    
                    # Add issues for unhealthy nodes
                    if not node_ready or disk_pressure:
                        self.knowledge_graph.add_issue(
                            node_id,
                            "node_health",
                            f"Node issues: Ready={node_ready}, DiskPressure={disk_pressure}",
                            "high" if not node_ready else "medium"
                        )
        
        # Process CSI Baremetal drives
        if 'csi_baremetal' in self.collected_data:
            csi_data = self.collected_data['csi_baremetal']
            
            for drive_name, drive_data in csi_data.get('drives', {}).items():
                health = drive_data.get('status', {}).get('Health', 'UNKNOWN')
                status = drive_data.get('status', {}).get('Status', 'UNKNOWN')
                
                drive_id = self.knowledge_graph.add_drive(
                    drive_name,
                    Health=health,
                    Status=status
                )
                
                # Add issues for unhealthy drives
                if health in ['SUSPECT', 'BAD']:
                    self.knowledge_graph.add_issue(
                        drive_id,
                        "disk_health",
                        f"Drive health issue: {health}",
                        "critical" if health == 'BAD' else "high"
                    )
        
        # Log final summary
        summary = self.knowledge_graph.get_summary()
        logging.info(f"Knowledge Graph built: {summary['total_nodes']} nodes, "
                    f"{summary['total_edges']} edges, {summary['total_issues']} issues")
        
        return self.knowledge_graph
    
    def _create_context_summary(self, analysis: Dict[str, Any], fix_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a comprehensive context summary for LangGraph"""
        summary = {
            'collection_overview': {
                'kubernetes_resources': {},
                'csi_baremetal_status': {},
                'critical_findings': [],
                'system_health': {}
            },
            'knowledge_graph_analysis': analysis,
            'recommended_fix_plan': fix_plan,
            'data_availability': {},
            'collection_errors': self.collected_data.get('errors', [])
        }
        
        # Kubernetes resources overview
        k8s_data = self.collected_data.get('kubernetes', {})
        summary['collection_overview']['kubernetes_resources'] = {
            'pods_count': len(k8s_data.get('pods', {})),
            'pvcs_count': len(k8s_data.get('pvcs', {})),
            'pvs_count': len(k8s_data.get('pvs', {})),
            'nodes_count': len(k8s_data.get('nodes', {})),
            'events_count': len(k8s_data.get('events', {}))
        }
        
        # CSI Baremetal status
        csi_data = self.collected_data.get('csi_baremetal', {})
        summary['collection_overview']['csi_baremetal_status'] = {
            'crd_availability': csi_data.get('crd_status', {}),
            'drives_count': len(csi_data.get('drives', {}))
        }
        
        # Critical findings
        critical_issues = [issue for issue in analysis.get('potential_root_causes', []) 
                          if issue.get('severity') in ['critical', 'high']]
        summary['collection_overview']['critical_findings'] = critical_issues[:5]  # Top 5
        
        # Data availability flags
        summary['data_availability'] = {
            'kubernetes_data': bool(k8s_data),
            'csi_baremetal_data': bool(csi_data),
            'logs_data': bool(self.collected_data.get('logs')),
            'system_data': bool(self.collected_data.get('system')),
            'knowledge_graph_built': bool(self.knowledge_graph and self.knowledge_graph.graph.number_of_nodes() > 0)
        }
        
        return summary
    
    def close_connections(self):
        """Close all SSH connections and cleanup"""
        for node, client in self.ssh_clients.items():
            try:
                client.close()
                logging.info(f"SSH connection to {node} closed")
            except Exception as e:
                logging.warning(f"Error closing SSH connection to {node}: {e}")
        
        self.ssh_clients = {}
