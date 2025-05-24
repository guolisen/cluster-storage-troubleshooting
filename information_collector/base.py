"""
Base functionality for Information Collector

Contains base class with initialization, configuration, and core utilities.
"""

import os
import logging
import time
from typing import Dict, List, Any, Optional
from kubernetes import client, config
from knowledge_graph import KnowledgeGraph


class InformationCollectorBase:
    """Base class for Information Collector with core functionality"""
    
    def __init__(self, config_data: Dict[str, Any]):
        """Initialize the Information Collector Base"""
        self.config = config_data
        self.k8s_client = None
        self.knowledge_graph = KnowledgeGraph()
        self.collected_data = {
            'kubernetes': {},
            'csi_baremetal': {},
            'logs': {},
            'system': {},
            'ssh_data': {},
            'tool_outputs': {},  # Store individual tool outputs
            'errors': []
        }
        
        # Initialize Kubernetes client
        self._init_kubernetes_client()
        
        # SSH clients cache
        self.ssh_clients = {}
        
        # Interactive mode setting
        self.interactive_mode = config_data.get('troubleshoot', {}).get('interactive_mode', False)
        
        logging.info("Information Collector Base initialized")
    
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
    
    def _prompt_user_approval(self, tool_name: str, purpose: str) -> bool:
        """
        Prompt user for tool execution approval in interactive mode
        
        Args:
            tool_name: Name of the tool to execute
            purpose: Purpose of the tool execution
            
        Returns:
            bool: True if approved, False if denied
        """
        if not self.interactive_mode:
            return True
        
        try:
            response = input(f"Proposed tool: {tool_name}. Purpose: {purpose}. Approve? (y/n): ").strip().lower()
            return response in ['y', 'yes']
        except (EOFError, KeyboardInterrupt):
            logging.info("User interrupted tool approval")
            return False
    
    def _execute_tool_with_validation(self, tool_func, tool_args: List[Any], tool_name: str, purpose: str) -> str:
        """
        Execute a LangGraph tool with command validation and approval
        
        Args:
            tool_func: Tool function to execute
            tool_args: Arguments for the tool
            tool_name: Name of the tool for logging
            purpose: Purpose of the tool execution
            
        Returns:
            str: Tool output or error message
        """
        try:
            # Check user approval in interactive mode
            if not self._prompt_user_approval(tool_name, purpose):
                return f"Tool execution denied by user: {tool_name}"
            
            # Execute the tool
            logging.info(f"Executing tool: {tool_name} - {purpose}")
            if tool_args:
                result = tool_func(*tool_args)
            else:
                result = tool_func()
            
            # Store the result
            self.collected_data['tool_outputs'][f"{tool_name}_{int(time.time())}"] = {
                'tool': tool_name,
                'purpose': purpose,
                'output': result,
                'timestamp': time.time()
            }
            
            logging.debug(f"Tool {tool_name} completed successfully")
            return result
            
        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
            return f"Error: {error_msg}"
    
    def _create_enhanced_context_summary(self, analysis: Dict[str, Any], fix_plan: Dict[str, Any], volume_chain: Dict[str, List[str]]) -> Dict[str, Any]:
        """Create enhanced context summary for troubleshooting"""
        return {
            'volume_chain_summary': {
                'total_pvcs': len(volume_chain.get('pvcs', [])),
                'total_pvs': len(volume_chain.get('pvs', [])),
                'total_drives': len(volume_chain.get('drives', [])),
                'total_nodes': len(volume_chain.get('nodes', [])),
                'storage_classes': volume_chain.get('storage_classes', [])
            },
            'collection_summary': {
                'total_tools_executed': len(self.collected_data['tool_outputs']),
                'total_errors': len(self.collected_data['errors']),
                'data_categories': list(self.collected_data.keys())
            },
            'knowledge_graph_summary': self.knowledge_graph.get_summary(),
            'analysis_summary': analysis,
            'fix_plan_summary': fix_plan
        }
