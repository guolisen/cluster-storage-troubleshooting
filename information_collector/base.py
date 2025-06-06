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
            'log_analysis': {},  # Parsed log issues and analysis
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
            tool_args: Arguments for the tool (either positional args list or dict for named args)
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
            
            # Handle different argument patterns for LangChain tools
            if hasattr(tool_func, 'invoke'):
                # New LangChain pattern - use invoke with proper argument structure
                if isinstance(tool_args, dict):
                    # Named arguments
                    result = tool_func.invoke(tool_args)
                elif isinstance(tool_args, list) and len(tool_args) > 0:
                    # Convert positional args to named args based on tool function signature
                    result = self._invoke_tool_with_positional_args(tool_func, tool_args)
                else:
                    # No arguments
                    result = tool_func.invoke({})
            else:
                # Fallback to direct function call for non-LangChain tools
                if tool_args:
                    result = tool_func(*tool_args)
                else:
                    result = tool_func()
            
            # Handle result extraction if it's wrapped in a response object
            if hasattr(result, 'content'):
                result_str = str(result.content)
            elif isinstance(result, dict) and 'output' in result:
                result_str = str(result['output'])
            else:
                result_str = str(result)
            
            # Store the result
            self.collected_data['tool_outputs'][f"{tool_name}_{int(time.time())}"] = {
                'tool': tool_name,
                'purpose': purpose,
                'output': result_str,
                'timestamp': time.time()
            }
            
            logging.debug(f"Tool {tool_name} completed successfully")
            return result_str
            
        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
            return f"Error: {error_msg}"
    
    def _invoke_tool_with_positional_args(self, tool_func, tool_args: List[Any]) -> Any:
        """
        Helper method to invoke LangChain tools with positional arguments
        converted to named arguments based on function signature
        
        Args:
            tool_func: LangChain tool function
            tool_args: List of positional arguments
            
        Returns:
            Tool execution result
        """
        import inspect
        
        try:
            # Get function signature to map positional args to named args
            if hasattr(tool_func, 'func'):
                sig = inspect.signature(tool_func.func)
            else:
                sig = inspect.signature(tool_func)
            
            param_names = list(sig.parameters.keys())
            
            # Create named argument dict, filtering out None values
            named_args = {}
            for i, arg_value in enumerate(tool_args):
                if i < len(param_names) and arg_value is not None:
                    named_args[param_names[i]] = arg_value
            
            return tool_func.invoke(named_args)
            
        except Exception as e:
            # Fallback: try with first argument as input
            if tool_args:
                return tool_func.invoke({'input': tool_args[0]})
            else:
                return tool_func.invoke({})
    
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
