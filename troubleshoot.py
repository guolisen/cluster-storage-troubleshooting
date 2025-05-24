#!/usr/bin/env python3
"""
Kubernetes Volume I/O Error Troubleshooting Script with Phase 0 Information Collection

This script uses a 3-phase approach:
- Phase 0: Information Collection - Pre-collect all diagnostic data upfront
- Phase 1: Analysis - Analyze pre-collected data with Knowledge Graph
- Phase 2: Remediation - Execute fix plan based on analysis

Enhanced with Knowledge Graph integration for comprehensive root cause analysis.
"""

import os
import sys
import yaml
import logging
import asyncio
import time
import subprocess
import json
import paramiko
import uuid
import shlex
import re
import argparse
from typing import Dict, List, Any, Optional, Tuple
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from knowledge_graph import KnowledgeGraph
from tools import define_remediation_tools, execute_command
from graph import create_troubleshooting_graph_with_context
from information_collector import ComprehensiveInformationCollector

# Global variables
CONFIG_DATA = None
INTERACTIVE_MODE = False
SSH_CLIENTS = {}
KNOWLEDGE_GRAPH = None

async def run_analysis_with_graph(query: str, graph: StateGraph, timeout_seconds: int = 60) -> Tuple[str, str]:
    """
    Run an analysis using the provided LangGraph StateGraph
    
    Args:
        query: The initial query to send to the graph
        graph: LangGraph StateGraph to use
        timeout_seconds: Maximum execution time in seconds
        
    Returns:
        Tuple[str, str]: Root cause and fix plan
    """
    try:
        formatted_query = {"messages": [{"role": "user", "content": query}]}
        
        # Run graph with timeout
        logging.info(f"Starting analysis with graph, timeout: {timeout_seconds}s")
        try:
            response = await asyncio.wait_for(
                graph.ainvoke(formatted_query, config={"recursion_limit": 50}),
                timeout=timeout_seconds
            )
        except Exception as e:
            logging.error(f"Error during graph execution: {str(e)}")
            return (
                "Analysis encountered an error during graph execution",
                "Review collected diagnostic information manually for troubleshooting"
            )
        
        # Extract analysis results
        if response["messages"]:
            if isinstance(response["messages"], list):
                final_message = response["messages"][-1].content
            else:
                final_message = response["messages"].content
        else:
            final_message = "Failed to generate analysis results"
        
        # Parse root cause and fix plan
        root_cause = "Unknown"
        fix_plan = "No specific fix plan generated"

        try:
            # Look for JSON block in the response
            json_start = final_message.find('{')
            json_end = final_message.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = final_message[json_start:json_end]
                parsed_json = json.loads(json_str)
                root_cause = parsed_json.get("root_cause", "Unknown root cause")
                fix_plan = parsed_json.get("fix_plan", "No fix plan provided")
                logging.info(f"Root cause identified: {root_cause}")
            else:
                # If no JSON found, use heuristic to extract information
                if "root cause" in final_message.lower():
                    root_parts = final_message.lower().split("root cause")
                    if len(root_parts) > 1:
                        root_cause = root_parts[1].strip().split("\n")[0]
                
                if "fix plan" in final_message.lower():
                    fix_parts = final_message.lower().split("fix plan")
                    if len(fix_parts) > 1:
                        fix_plan = fix_parts[1].strip().split("\n")[0]
        except Exception as e:
            logging.warning(f"Error parsing LLM response: {str(e)}")
            # Return raw message if parsing fails
            return final_message, final_message
        
        return root_cause, fix_plan
    except Exception as e:
        logging.error(f"Error in run_analysis_with_graph: {str(e)}")
        return "Error in analysis", str(e)

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

async def run_information_collection_phase(pod_name: str, namespace: str, volume_path: str) -> Dict[str, Any]:
    """
    Run Phase 0: Information Collection - Gather all necessary data upfront
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        
    Returns:
        Dict[str, Any]: Pre-collected diagnostic information
    """
    global CONFIG_DATA, KNOWLEDGE_GRAPH
    
    logging.info("Starting Phase 0: Information Collection")
    
    try:
        # Initialize information collector
        info_collector = ComprehensiveInformationCollector(CONFIG_DATA)
        
        # Run comprehensive collection
        collection_result = await info_collector.comprehensive_collect(
            target_pod=pod_name,
            target_namespace=namespace,
            target_volume_path=volume_path
        )
        
        # Update the global knowledge graph
        KNOWLEDGE_GRAPH = collection_result.get('knowledge_graph')
        
        # Format collected data into expected structure
        collected_info = {
            "pod_info": collection_result.get('collected_data', {}).get('kubernetes', {}).get('pods', {}),
            "pvc_info": collection_result.get('collected_data', {}).get('kubernetes', {}).get('pvcs', {}),
            "pv_info": collection_result.get('collected_data', {}).get('kubernetes', {}).get('pvs', {}),
            "node_info": collection_result.get('collected_data', {}).get('kubernetes', {}).get('nodes', {}),
            "csi_driver_info": collection_result.get('collected_data', {}).get('csi_baremetal', {}),
            "storage_class_info": {},  # Will be included in kubernetes data
            "system_info": collection_result.get('collected_data', {}).get('system', {}),
            "knowledge_graph_summary": collection_result.get('context_summary', {})
        }
        
        # Print Knowledge Graph
        print("=" * 80)
        print("PHASE 0: INFORMATION COLLECTION - KNOWLEDGE GRAPH")
        print("=" * 80)
        print()
        formatted_output = KNOWLEDGE_GRAPH.print_graph()
        print(formatted_output)
        print("\n" + "=" * 80)
        
        return collected_info
        
    except Exception as e:
        error_msg = f"Error during information collection phase: {str(e)}"
        logging.error(error_msg)
        collected_info = {
            "collection_error": error_msg,
            "pod_info": {},
            "pvc_info": {},
            "pv_info": {},
            "node_info": {},
            "csi_driver_info": {},
            "storage_class_info": {},
            "system_info": {},
            "knowledge_graph_summary": {}
        }
        return collected_info


async def run_analysis_phase_with_context(pod_name: str, namespace: str, volume_path: str, collected_info: Dict[str, Any]) -> Tuple[str, str]:
    """
    Run Phase 1: Analysis with pre-collected information
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        
    Returns:
        Tuple[str, str]: Root cause and fix plan
    """
    global CONFIG_DATA, KNOWLEDGE_GRAPH
    
    try:
        # Create troubleshooting graph with pre-collected context
        graph = create_troubleshooting_graph_with_context(collected_info, phase="analysis", config_data=CONFIG_DATA)
        
        # Initial query for analysis phase with context
        query = f"""Phase 1 - Analysis: Analyze the pre-collected diagnostic information for volume I/O error in pod {pod_name} in namespace {namespace} at volume path {volume_path}.

All necessary diagnostic information has been collected in Phase 0 and is provided in the system context. Please:

1. Review all the pre-collected diagnostic data
2. Analyze the Knowledge Graph relationships to understand the storage stack
3. Identify root cause(s) based on the available information
4. Generate a comprehensive fix plan
5. Present findings as JSON with "root_cause" and "fix_plan" keys

Focus on comprehensive analysis of the pre-collected data - no additional commands need to be executed.
"""
        # Set timeout
        timeout_seconds = CONFIG_DATA['troubleshoot']['timeout_seconds']
        
        # Run analysis using the tools module
        root_cause, fix_plan = await run_analysis_with_graph(
            query=query,
            graph=graph,
            timeout_seconds=timeout_seconds
        )
        
        return root_cause, fix_plan

    except Exception as e:
        error_msg = f"Error during analysis phase: {str(e)}"
        logging.error(error_msg)
        return error_msg, "Unable to generate fix plan due to analysis error"

async def run_remediation_phase(root_cause: str, fix_plan: str, collected_info: Dict[str, Any]) -> str:
    """
    Run Phase 2: Remediation based on analysis results
    
    Args:
        root_cause: Root cause identified in Phase 1
        fix_plan: Fix plan generated in Phase 1
        collected_info: Pre-collected diagnostic information from Phase 0
        
    Returns:
        str: Remediation result
    """
    global CONFIG_DATA, INTERACTIVE_MODE
    
    logging.info("Starting Phase 2: Remediation")
    
    try:
        # Create troubleshooting graph for remediation
        graph = create_troubleshooting_graph_with_context(collected_info, phase="remediation", config_data=CONFIG_DATA)
        
        # Remediation query
        query = f"""Phase 2 - Remediation: Execute the fix plan to resolve the identified issue.

Root Cause: {root_cause}

Fix Plan: {fix_plan}

Please implement the fix plan step by step. Use available tools if needed, but respect security constraints and interactive mode settings.
Provide a final status report on whether the issues have been resolved.
"""
        
        # Set timeout
        timeout_seconds = CONFIG_DATA['troubleshoot']['timeout_seconds']
        
        # Run analysis with graph
        try:
            root_cause, remediation_result = await run_analysis_with_graph(
                query=query,
                graph=graph,
                timeout_seconds=timeout_seconds
            )
            return remediation_result
        except asyncio.TimeoutError:
            return "Remediation phase timed out - manual intervention may be required"
        except Exception as e:
            logging.error(f"Error during remediation graph execution: {str(e)}")
            return f"Remediation encountered an error: {str(e)}"
        
    except Exception as e:
        error_msg = f"Error during remediation phase: {str(e)}"
        logging.error(error_msg)
        return error_msg

async def run_comprehensive_troubleshooting(pod_name: str, namespace: str, volume_path: str) -> Dict[str, Any]:
    """
    Run comprehensive 3-phase troubleshooting
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        
    Returns:
        Dict[str, Any]: Complete troubleshooting results
    """
    start_time = time.time()
    
    results = {
        "pod_name": pod_name,
        "namespace": namespace,
        "volume_path": volume_path,
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
        "phases": {}
    }
    
    try:
        # Phase 0: Information Collection
        print("=" * 80)
        print("STARTING COMPREHENSIVE KUBERNETES VOLUME TROUBLESHOOTING")
        print("=" * 80)
        print(f"Pod: {namespace}/{pod_name}")
        print(f"Volume Path: {volume_path}")
        print(f"Start Time: {results['start_time']}")
        print()
        
        collected_info = await run_information_collection_phase(pod_name, namespace, volume_path)
        results["phases"]["phase_0_collection"] = {
            "status": "completed",
            "summary": collected_info.get("knowledge_graph_summary", {}),
            "duration": time.time() - start_time
        }
        
        if "collection_error" in collected_info:
            results["phases"]["phase_0_collection"]["status"] = "failed"
            results["phases"]["phase_0_collection"]["error"] = collected_info["collection_error"]
            return results
        
        phase_1_start = time.time()
        
        # Phase 1: Analysis
        print("=" * 80)
        print("PHASE 1: ANALYSIS")
        print("=" * 80)
        print("Analyzing pre-collected diagnostic information...")
        print()
        
        root_cause, fix_plan = await run_analysis_phase_with_context(
            pod_name, namespace, volume_path, collected_info
        )
        
        results["phases"]["phase_1_analysis"] = {
            "status": "completed",
            "root_cause": root_cause,
            "fix_plan": fix_plan,
            "duration": time.time() - phase_1_start
        }
        
        print(f"Root Cause: {root_cause}")
        print(f"Fix Plan: {fix_plan}")
        print()
        
        phase_2_start = time.time()
        
        # Phase 2: Remediation
        print("=" * 80)
        print("PHASE 2: REMEDIATION")
        print("=" * 80)
        print("Executing fix plan...")
        print()
        
        remediation_result = await run_remediation_phase(root_cause, fix_plan, collected_info)
        
        results["phases"]["phase_2_remediation"] = {
            "status": "completed",
            "result": remediation_result,
            "duration": time.time() - phase_2_start
        }
        
        print(f"Remediation Result: {remediation_result}")
        print()
        
        # Final summary
        total_duration = time.time() - start_time
        results["total_duration"] = total_duration
        results["status"] = "completed"
        
        print("=" * 80)
        print("TROUBLESHOOTING SUMMARY")
        print("=" * 80)
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"Phase 0 (Collection): {results['phases']['phase_0_collection']['duration']:.2f}s")
        print(f"Phase 1 (Analysis): {results['phases']['phase_1_analysis']['duration']:.2f}s")
        print(f"Phase 2 (Remediation): {results['phases']['phase_2_remediation']['duration']:.2f}s")
        print()
        print(f"Root Cause: {root_cause}")
        print(f"Resolution Status: {remediation_result}")
        print("=" * 80)
        
        return results
        
    except Exception as e:
        error_msg = f"Critical error during troubleshooting: {str(e)}"
        logging.error(error_msg)
        results["status"] = "failed"
        results["error"] = error_msg
        results["total_duration"] = time.time() - start_time
        return results

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Kubernetes Volume I/O Error Troubleshooting Script")
    parser.add_argument("pod_name", help="Name of the pod with the error")
    parser.add_argument("namespace", help="Namespace of the pod")
    parser.add_argument("volume_path", help="Path of the volume with I/O error")
    parser.add_argument("--interactive", "-i", action="store_true", 
                       help="Enable interactive mode for command confirmation")
    parser.add_argument("--config", "-c", default="config.yaml",
                       help="Path to configuration file (default: config.yaml)")
    parser.add_argument("--output", "-o", help="Output file for results (JSON format)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    
    return parser.parse_args()

async def main():
    """Main function"""
    global CONFIG_DATA, INTERACTIVE_MODE, KNOWLEDGE_GRAPH
    
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Set interactive mode
        INTERACTIVE_MODE = args.interactive
        
        # Load configuration
        CONFIG_DATA = load_config()
        
        # Setup logging
        setup_logging(CONFIG_DATA)
        
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Validate inputs
        if not args.pod_name or not args.namespace or not args.volume_path:
            logging.error("Pod name, namespace, and volume path are required")
            sys.exit(1)
        
        # Initialize Kubernetes configuration
        try:
            config.load_incluster_config()
            logging.info("Loaded in-cluster Kubernetes configuration")
        except:
            try:
                config.load_kube_config()
                logging.info("Loaded kubeconfig from default location")
            except Exception as e:
                logging.error(f"Failed to load Kubernetes configuration: {e}")
                sys.exit(1)
        
        # Run comprehensive troubleshooting
        results = await run_comprehensive_troubleshooting(
            args.pod_name, args.namespace, args.volume_path
        )
        
        # Save results if output file specified
        if args.output:
            try:
                with open(args.output, 'w') as f:
                    json.dump(results, f, indent=2)
                logging.info(f"Results saved to {args.output}")
            except Exception as e:
                logging.error(f"Failed to save results to {args.output}: {e}")
        
        # Exit with appropriate code
        if results["status"] == "completed":
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logging.info("Troubleshooting interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Critical error in main: {str(e)}")
        sys.exit(1)
    finally:
        # Clean up SSH connections
        for client in SSH_CLIENTS.values():
            try:
                client.close()
            except:
                pass

if __name__ == "__main__":
    asyncio.run(main())
