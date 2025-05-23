#!/usr/bin/env python3
"""
Enhanced Issue Collector for Kubernetes Volume Troubleshooting

This module collects volume I/O errors from Kubernetes pods and integrates
with the Knowledge Graph system for comprehensive issue tracking and analysis.

Enhanced with LangGraph ReAct integration for intelligent issue collection
and prioritization.
"""

import asyncio
import logging
import time
import yaml
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from knowledge_graph import KnowledgeGraph


class EnhancedIssueCollector:
    """
    Enhanced Issue Collector with Knowledge Graph integration
    """
    
    def __init__(self, config_data: Dict[str, Any]):
        """
        Initialize the Enhanced Issue Collector
        
        Args:
            config_data: Configuration dictionary from config.yaml
        """
        self.config = config_data
        self.k8s_client = None
        self.knowledge_graph = KnowledgeGraph()
        self.collected_issues = []
        
        # Initialize Kubernetes client
        self._init_kubernetes_client()
        
        # Initialize LLM for LangGraph ReAct
        self.llm = init_chat_model(
            self.config['llm']['model'],
            api_key=self.config['llm']['api_key'],
            base_url=self.config['llm']['api_endpoint'],
            temperature=self.config['llm']['temperature'],
            max_tokens=self.config['llm']['max_tokens']
        )
        
        logging.info("Enhanced Issue Collector initialized with Knowledge Graph integration")
    
    def _init_kubernetes_client(self):
        """Initialize Kubernetes client"""
        try:
            # Try to load in-cluster config first
            if 'KUBERNETES_SERVICE_HOST' in os.environ:
                config.load_incluster_config()
                logging.info("Using in-cluster Kubernetes configuration")
            else:
                # Fall back to kubeconfig file
                config.load_kube_config()
                logging.info("Using kubeconfig file for Kubernetes configuration")
            
            self.k8s_client = client.CoreV1Api()
        except Exception as e:
            logging.error(f"Failed to initialize Kubernetes client: {e}")
            raise
    
    def is_volume_io_error(self, log_line: str) -> bool:
        """
        Enhanced detection of volume I/O errors using pattern matching
        
        Args:
            log_line: Log line to analyze
            
        Returns:
            bool: True if the line contains a volume I/O error
        """
        io_error_patterns = [
            r'Input/[Oo]utput [Ee]rror',
            r'I/O [Ee]rror',
            r'Read-only file system',
            r'No space left on device',
            r'Permission denied.*\/mnt',
            r'Permission denied.*\/data',
            r'Transport endpoint is not connected',
            r'Device or resource busy',
            r'Connection timed out',
            r'Remote I/O error',
            r'Structure needs cleaning',
            r'Bad file descriptor',
            r'Stale file handle',
            r'Operation not permitted.*mount',
            r'Mount.*failed',
            r'Cannot allocate memory.*I/O',
            r'EXT.*error',
            r'XFS.*error',
            r'Unable to mount.*volume',
            r'Volume.*not ready',
            r'PVC.*pending',
            r'FailedMount',
            r'MountVolume.SetUp failed'
        ]
        
        for pattern in io_error_patterns:
            if re.search(pattern, log_line, re.IGNORECASE):
                return True
        
        return False
    
    def extract_volume_path(self, log_line: str, pod_spec: Dict[str, Any]) -> Optional[str]:
        """
        Extract volume path from log line and pod specification
        
        Args:
            log_line: Log line containing the error
            pod_spec: Pod specification from Kubernetes API
            
        Returns:
            Optional[str]: Volume path if found, None otherwise
        """
        # Try to extract path from error message
        path_patterns = [
            r'/mnt/[^\s]+',
            r'/data/[^\s]+',
            r'/var/[^\s]+',
            r'/opt/[^\s]+',
            r'/app/[^\s]+',
            r'/storage/[^\s]+',
            r'/pvc[^\s]*'
        ]
        
        for pattern in path_patterns:
            match = re.search(pattern, log_line)
            if match:
                return match.group(0)
        
        # If no path found in log, try to get from pod spec
        if 'spec' in pod_spec and 'containers' in pod_spec['spec']:
            for container in pod_spec['spec']['containers']:
                if 'volumeMounts' in container:
                    for volume_mount in container['volumeMounts']:
                        mount_path = volume_mount.get('mountPath', '')
                        if mount_path and any(keyword in log_line for keyword in ['mount', 'volume', 'permission']):
                            return mount_path
        
        return "/mnt"  # Default fallback
    
    def categorize_issue_severity(self, error_type: str, error_count: int) -> str:
        """
        Categorize issue severity based on error type and frequency
        
        Args:
            error_type: Type of error detected
            error_count: Number of times this error occurred
            
        Returns:
            str: Severity level (critical, high, medium, low)
        """
        critical_patterns = [
            'Input/Output Error',
            'I/O Error',
            'Read-only file system',
            'No space left on device'
        ]
        
        high_patterns = [
            'Permission denied',
            'Transport endpoint is not connected',
            'Device or resource busy',
            'FailedMount',
            'MountVolume.SetUp failed'
        ]
        
        medium_patterns = [
            'Connection timed out',
            'Remote I/O error',
            'Structure needs cleaning',
            'Volume.*not ready'
        ]
        
        # Determine base severity
        if any(pattern in error_type for pattern in critical_patterns):
            base_severity = 'critical'
        elif any(pattern in error_type for pattern in high_patterns):
            base_severity = 'high'
        elif any(pattern in error_type for pattern in medium_patterns):
            base_severity = 'medium'
        else:
            base_severity = 'low'
        
        # Escalate severity based on frequency
        if error_count >= 10 and base_severity != 'critical':
            if base_severity == 'high':
                return 'critical'
            elif base_severity == 'medium':
                return 'high'
            elif base_severity == 'low':
                return 'medium'
        elif error_count >= 5 and base_severity == 'low':
            return 'medium'
        
        return base_severity
    
    async def collect_pod_issues(self, namespace: str = None) -> List[Dict[str, Any]]:
        """
        Collect volume I/O issues from all pods
        
        Args:
            namespace: Specific namespace to check, or None for all namespaces
            
        Returns:
            List[Dict[str, Any]]: List of collected issues
        """
        issues = []
        
        try:
            # Get all pods
            if namespace:
                pods = self.k8s_client.list_namespaced_pod(namespace)
            else:
                pods = self.k8s_client.list_pod_for_all_namespaces()
            
            for pod in pods.items:
                pod_name = pod.metadata.name
                pod_namespace = pod.metadata.namespace
                
                try:
                    # Get pod logs
                    logs = self.k8s_client.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=pod_namespace,
                        tail_lines=100
                    )
                    
                    # Analyze logs for I/O errors
                    pod_issues = await self._analyze_pod_logs(pod_name, pod_namespace, logs, pod.to_dict())
                    issues.extend(pod_issues)
                    
                except ApiException as e:
                    if e.status != 404:  # Ignore not found errors
                        logging.warning(f"Failed to get logs for pod {pod_namespace}/{pod_name}: {e}")
                except Exception as e:
                    logging.warning(f"Error processing pod {pod_namespace}/{pod_name}: {e}")
        
        except ApiException as e:
            logging.error(f"Failed to list pods: {e}")
        except Exception as e:
            logging.error(f"Unexpected error during issue collection: {e}")
        
        self.collected_issues = issues
        return issues
    
    async def _analyze_pod_logs(self, pod_name: str, namespace: str, logs: str, pod_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyze pod logs for volume I/O errors
        
        Args:
            pod_name: Name of the pod
            namespace: Namespace of the pod
            logs: Pod logs
            pod_spec: Pod specification
            
        Returns:
            List[Dict[str, Any]]: List of issues found in this pod
        """
        issues = []
        error_counts = {}
        
        for line in logs.split('\n'):
            if self.is_volume_io_error(line):
                # Extract error type
                error_type = self._extract_error_type(line)
                
                # Count occurrences
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
                
                # Extract volume path
                volume_path = self.extract_volume_path(line, pod_spec)
                
                # Create issue
                issue = {
                    'pod_name': pod_name,
                    'namespace': namespace,
                    'error_type': error_type,
                    'volume_path': volume_path,
                    'log_line': line.strip(),
                    'timestamp': time.time(),
                    'severity': 'medium',  # Will be updated after counting
                    'node_name': pod_spec.get('spec', {}).get('nodeName', 'unknown')
                }
                
                issues.append(issue)
        
        # Update severity based on error counts
        for issue in issues:
            error_type = issue['error_type']
            error_count = error_counts[error_type]
            issue['severity'] = self.categorize_issue_severity(error_type, error_count)
            issue['error_count'] = error_count
        
        return issues
    
    def _extract_error_type(self, log_line: str) -> str:
        """
        Extract the error type from a log line
        
        Args:
            log_line: Log line containing the error
            
        Returns:
            str: Extracted error type
        """
        # Priority patterns for specific error types
        priority_patterns = [
            (r'Input/[Oo]utput [Ee]rror', 'Input/Output Error'),
            (r'I/O [Ee]rror', 'I/O Error'),
            (r'Read-only file system', 'Read-only file system'),
            (r'No space left on device', 'No space left on device'),
            (r'Permission denied', 'Permission denied'),
            (r'FailedMount', 'FailedMount'),
            (r'MountVolume.SetUp failed', 'Mount Setup Failed'),
            (r'Transport endpoint is not connected', 'Transport endpoint disconnected'),
            (r'Device or resource busy', 'Device busy'),
            (r'Connection timed out', 'Connection timeout'),
            (r'Structure needs cleaning', 'Filesystem corruption'),
            (r'Bad file descriptor', 'Bad file descriptor'),
            (r'Stale file handle', 'Stale file handle')
        ]
        
        for pattern, error_type in priority_patterns:
            if re.search(pattern, log_line, re.IGNORECASE):
                return error_type
        
        return 'Volume Error'  # Generic fallback
    
    async def populate_knowledge_graph(self, issues: List[Dict[str, Any]]):
        """
        Populate the Knowledge Graph with collected issues
        
        Args:
            issues: List of collected issues
        """
        # Reset Knowledge Graph
        self.knowledge_graph = KnowledgeGraph()
        
        # Track processed entities to avoid duplicates
        processed_pods = set()
        processed_nodes = set()
        
        for issue in issues:
            pod_name = issue['pod_name']
            namespace = issue['namespace']
            volume_path = issue['volume_path']
            node_name = issue['node_name']
            
            # Add pod to Knowledge Graph
            pod_id = f"{namespace}/{pod_name}"
            if pod_id not in processed_pods:
                kg_pod_id = self.knowledge_graph.add_pod(pod_name, namespace, volume_path=volume_path)
                processed_pods.add(pod_id)
            else:
                kg_pod_id = f"Pod:{namespace}/{pod_name}"
            
            # Add node to Knowledge Graph
            if node_name != 'unknown' and node_name not in processed_nodes:
                kg_node_id = self.knowledge_graph.add_node(node_name)
                processed_nodes.add(node_name)
                
                # Link pod to node
                if kg_pod_id:
                    self.knowledge_graph.add_relationship(kg_pod_id, kg_node_id, "scheduled_on")
            
            # Add issue to Knowledge Graph
            self.knowledge_graph.add_issue(
                kg_pod_id,
                issue['error_type'].lower().replace(' ', '_').replace('/', '_'),
                f"{issue['error_type']}: {issue['log_line'][:100]}...",
                issue['severity']
            )
        
        logging.info(f"Knowledge Graph populated with {len(issues)} issues from {len(processed_pods)} pods")
    
    def create_issue_analysis_graph(self):
        """
        Create a LangGraph ReAct graph for issue analysis
        
        Returns:
            StateGraph: LangGraph StateGraph for issue analysis
        """
        # Define tools for issue analysis
        @tool
        def get_collected_issues() -> str:
            """Get the list of collected issues"""
            if not self.collected_issues:
                return "No issues have been collected yet."
            
            issue_summary = {
                'total_issues': len(self.collected_issues),
                'by_severity': {},
                'by_error_type': {},
                'by_namespace': {}
            }
            
            for issue in self.collected_issues:
                # Count by severity
                severity = issue['severity']
                issue_summary['by_severity'][severity] = issue_summary['by_severity'].get(severity, 0) + 1
                
                # Count by error type
                error_type = issue['error_type']
                issue_summary['by_error_type'][error_type] = issue_summary['by_error_type'].get(error_type, 0) + 1
                
                # Count by namespace
                namespace = issue['namespace']
                issue_summary['by_namespace'][namespace] = issue_summary['by_namespace'].get(namespace, 0) + 1
            
            return json.dumps(issue_summary, indent=2)
        
        @tool
        def get_knowledge_graph_summary() -> str:
            """Get Knowledge Graph summary"""
            if not self.knowledge_graph:
                return "Knowledge Graph not initialized."
            
            summary = self.knowledge_graph.get_summary()
            return json.dumps(summary, indent=2)
        
        @tool
        def analyze_issue_patterns() -> str:
            """Analyze patterns in collected issues"""
            if not self.knowledge_graph:
                return "Knowledge Graph not available for pattern analysis."
            
            analysis = self.knowledge_graph.analyze_issues()
            return json.dumps({
                'total_issues': analysis['total_issues'],
                'potential_root_causes': analysis['potential_root_causes'],
                'issue_patterns': analysis['issue_patterns']
            }, indent=2, default=str)
        
        @tool
        def get_critical_issues() -> str:
            """Get critical and high severity issues"""
            critical_issues = [issue for issue in self.collected_issues if issue['severity'] in ['critical', 'high']]
            
            if not critical_issues:
                return "No critical or high severity issues found."
            
            return json.dumps(critical_issues, indent=2, default=str)
        
        tools = [get_collected_issues, get_knowledge_graph_summary, analyze_issue_patterns, get_critical_issues]
        
        # Define function to call the model
        def call_model(state: MessagesState):
            system_message = {
                "role": "system",
                "content": """You are an AI assistant for analyzing Kubernetes volume I/O issues using Knowledge Graph analysis. 

Your role is to:
1. Analyze collected issues using available tools
2. Identify patterns and correlations
3. Prioritize issues based on severity and impact
4. Recommend next steps for troubleshooting

Use the available tools to gather information about collected issues and provide insights based on Knowledge Graph analysis. Focus on identifying the most critical issues that need immediate attention."""
            }
            
            # Ensure system message is first
            if state["messages"]:
                if isinstance(state["messages"], list):
                    if state["messages"][0].get("role") != "system":
                        state["messages"] = [system_message] + state["messages"]
                else:
                    state["messages"] = [system_message, state["messages"]]
            else:
                state["messages"] = [system_message]
            
            # Call the model and bind tools
            response = self.llm.bind_tools(tools).invoke(state["messages"])
            return {"messages": state["messages"] + [response]}
        
        # Build state graph
        builder = StateGraph(MessagesState)
        builder.add_node("call_model", call_model)
        builder.add_node("tools", ToolNode(tools))
        builder.add_edge(START, "call_model")
        builder.add_conditional_edges(
            "call_model",
            tools_condition,
            {
                "tools": "tools",
                "none": END
            }
        )
        builder.add_edge("tools", "call_model")
        graph = builder.compile()
        
        return graph
    
    async def analyze_collected_issues(self) -> Dict[str, Any]:
        """
        Analyze collected issues using LangGraph ReAct
        
        Returns:
            Dict[str, Any]: Analysis results
        """
        if not self.collected_issues:
            return {"error": "No issues collected for analysis"}
        
        # Populate Knowledge Graph with collected issues
        await self.populate_knowledge_graph(self.collected_issues)
        
        # Create analysis graph
        analysis_graph = self.create_issue_analysis_graph()
        
        # Run analysis
        query = """Analyze the collected Kubernetes volume I/O issues. Please:
1. Get an overview of collected issues
2. Check the Knowledge Graph summary
3. Analyze issue patterns and root causes
4. Identify critical issues that need immediate attention
5. Provide recommendations for next steps

Focus on the most critical issues and provide actionable insights."""
        
        formatted_query = {"messages": [{"role": "user", "content": query}]}
        
        try:
            response = await analysis_graph.ainvoke(formatted_query)
            
            # Extract analysis results
            if response["messages"]:
                if isinstance(response["messages"], list):
                    analysis_result = response["messages"][-1].content
                else:
                    analysis_result = response["messages"].content
            else:
                analysis_result = "Failed to generate analysis results"
            
            return {
                "analysis": analysis_result,
                "total_issues": len(self.collected_issues),
                "knowledge_graph_summary": self.knowledge_graph.get_summary(),
                "critical_issues": [issue for issue in self.collected_issues if issue['severity'] in ['critical', 'high']]
            }
            
        except Exception as e:
            logging.error(f"Error during issue analysis: {e}")
            return {"error": f"Analysis failed: {str(e)}"}
    
    async def run_continuous_collection(self, interval_seconds: int = 60):
        """
        Run continuous issue collection
        
        Args:
            interval_seconds: Collection interval in seconds
        """
        logging.info(f"Starting continuous issue collection with {interval_seconds}s interval")
        
        while True:
            try:
                # Collect issues
                issues = await self.collect_pod_issues()
                
                if issues:
                    logging.info(f"Collected {len(issues)} volume I/O issues")
                    
                    # Analyze issues
                    analysis = await self.analyze_collected_issues()
                    
                    # Log critical issues
                    critical_issues = analysis.get('critical_issues', [])
                    if critical_issues:
                        logging.warning(f"Found {len(critical_issues)} critical/high severity issues")
                        for issue in critical_issues:
                            logging.warning(f"CRITICAL: {issue['namespace']}/{issue['pod_name']} - {issue['error_type']}")
                else:
                    logging.info("No volume I/O issues found")
                
                # Wait for next collection cycle
                await asyncio.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logging.info("Issue collection stopped by user")
                break
            except Exception as e:
                logging.error(f"Error during issue collection cycle: {e}")
                await asyncio.sleep(interval_seconds)


async def main():
    """Main function for standalone execution"""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description='Enhanced Kubernetes Volume Issue Collector')
    parser.add_argument('--config', default='config.yaml', help='Configuration file path')
    parser.add_argument('--namespace', help='Specific namespace to monitor')
    parser.add_argument('--continuous', action='store_true', help='Run continuous collection')
    parser.add_argument('--interval', type=int, default=60, help='Collection interval in seconds')
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        with open(args.config, 'r') as f:
            config_data = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        return 1
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('issue_collector.log'),
            logging.StreamHandler()
        ]
    )
    
    # Create issue collector
    collector = EnhancedIssueCollector(config_data)
    
    try:
        if args.continuous:
            # Run continuous collection
            await collector.run_continuous_collection(args.interval)
        else:
            # Run single collection
            issues = await collector.collect_pod_issues(args.namespace)
            
            if issues:
                print(f"\nCollected {len(issues)} volume I/O issues:")
                
                # Analyze issues
                analysis = await collector.analyze_collected_issues()
                print("\n=== Issue Analysis ===")
                print(analysis.get('analysis', 'No analysis available'))
                
                # Show critical issues
                critical_issues = analysis.get('critical_issues', [])
                if critical_issues:
                    print(f"\n=== Critical Issues ({len(critical_issues)}) ===")
                    for issue in critical_issues:
                        print(f"- {issue['namespace']}/{issue['pod_name']}: {issue['error_type']}")
                        print(f"  Path: {issue['volume_path']}")
                        print(f"  Severity: {issue['severity']}")
                        print(f"  Count: {issue.get('error_count', 1)}")
                        print()
            else:
                print("No volume I/O issues found.")
    
    except KeyboardInterrupt:
        print("\nCollection stopped by user")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
