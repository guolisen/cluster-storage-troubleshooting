#!/usr/bin/env python3
"""
Kubernetes Volume I/O Error Troubleshooting Script with Phase 0 Information Collection

This script uses a 3-phase approach:
- Phase 0: Information Collection - Pre-collect all diagnostic data upfront
- Phase 1: ReAct Investigation - Actively investigate using tools with pre-collected data as base knowledge
- Phase 2: Remediation - Execute fix plan based on analysis

Enhanced with Knowledge Graph integration and ReAct methodology for comprehensive root cause analysis.
"""

import os
import sys
import yaml
import logging
import asyncio
import time
import json
import argparse
import atexit
from typing import Dict, List, Any, Optional, Tuple
from langgraph.graph import StateGraph
from kubernetes import config
from troubleshooting.graph import create_troubleshooting_graph_with_context
from information_collector import ComprehensiveInformationCollector
from phases import (
    run_information_collection_phase,
    run_plan_phase,
    run_analysis_phase_with_plan,
    run_remediation_phase
)
from phases.chat_mode import ChatMode
from troubleshooting.utils import (
    GraphExecutor,
    ErrorHandler,
    MessageListManager,
    OutputFormatter
)
from rich.logging import RichHandler
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich import print as rprint

# Initialize rich console
console = Console()
log_file = open('troubleshoot.log', 'w')
file_console = Console(file=log_file)

# Register cleanup function to close log file
@atexit.register
def cleanup_resources():
    """Close resources when the script exits"""
    try:
        if log_file and not log_file.closed:
            log_file.close()
            logging.info("Log file closed")
    except Exception as e:
        logging.error(f"Error closing log file: {e}")

# Global variables
CONFIG_DATA = None
INTERACTIVE_MODE = False
SSH_CLIENTS = {}
KNOWLEDGE_GRAPH = None


class InternalLogFilter(logging.Filter):
    """
    Filter out internal logging messages from console output
    
    This filter prevents internal debugging logs from cluttering the console
    while still allowing them to be written to the log file.
    """
    def filter(self, record):
        # Check if this is an internal log that should be filtered from console
        
        # Filter out logs from LangGraph module
        if 'LangGraph' in record.msg or getattr(record, 'name', '').startswith('langgraph'):
            return False
            
        # Filter out logs from standard logging modules
        if getattr(record, 'name', '') in ['kubernetes', 'urllib3', 'asyncio', 'langchain', 'httpx']:
            return False
            
        # Filter out specific log patterns that are meant for internal debugging
        internal_patterns = [
            'Executing command:',
            'Command output:',
            'Starting enhanced logging',
            'Loaded',
            'Building',
            'Adding node',
            'Adding edge',
            'Adding conditional',
            'Compiling graph',
            'Model response:',
            'Model invoking tool:',
            'Tool arguments:',
            'Using Phase',
            'Processing state',
            'Graph compilation',
            'Running',
            'Starting'
        ]
        
        if any(pattern in record.msg for pattern in internal_patterns):
            return False
            
        # Allow all other logs to pass to console
        return True


def configure_module_loggers():
    """
    Set up file handlers for module-specific loggers
    
    This function configures logging for various modules to ensure
    their logs are properly captured in the log file.
    """
    # Create file handler for log file
    file_handler = logging.FileHandler('troubleshoot.log', mode='a')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # Configure module loggers
    modules_to_configure = [
        'langgraph', 'knowledge_graph', 'knowledge_graph.tools',
        'tools', 'information_collector', 'kubernetes', 'urllib3'
    ]
    
    for module in modules_to_configure:
        module_logger = logging.getLogger(module)
        module_logger.addHandler(file_handler)


def load_config(config_path: str = 'config.yaml') -> Dict[str, Any]:
    """
    Load configuration from config.yaml
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Dict[str, Any]: Configuration data
        
    Raises:
        SystemExit: If configuration loading fails
    """
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        sys.exit(1)


def setup_logging(config_data: Dict[str, Any]) -> None:
    """
    Configure logging based on configuration with rich formatting
    
    Args:
        config_data: Configuration data containing logging settings
    """
    log_file = config_data['logging']['file']
    log_to_stdout = config_data['logging']['stdout']
    
    handlers = []
    if log_file:
        # File handler for regular log file with timestamps
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        handlers.append(file_handler)
        
        # Rich console file handler for enhanced log file
        file_console.log("Starting enhanced logging to troubleshoot.log")
    
    if log_to_stdout:
        # Rich console handler for beautiful terminal output - with filter
        rich_handler = RichHandler(
            rich_tracebacks=True,
            console=console,
            show_time=True,
            show_level=True,
            show_path=False,
            enable_link_path=False
        )
        # Add filter to prevent internal logs from going to console
        rich_handler.addFilter(InternalLogFilter())
        handlers.append(rich_handler)
    
    # Configure the root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        datefmt='[%X]',
        handlers=handlers
    )
    
    # Configure module-specific loggers
    configure_module_loggers()
    
    # Log startup message to file only
    logging.info("Logging initialized - internal logs redirected to log file only")


def initialize_kubernetes_config() -> None:
    """
    Initialize Kubernetes configuration
    
    Attempts to load in-cluster config first, then falls back to kubeconfig
    
    Raises:
        SystemExit: If Kubernetes configuration loading fails
    """
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


async def run_information_collection_phase_wrapper(pod_name: str, namespace: str, volume_path: str) -> Dict[str, Any]:
    """
    Wrapper for Phase 0: Information Collection from phases module
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        
    Returns:
        Dict[str, Any]: Pre-collected diagnostic information
    """
    global CONFIG_DATA, KNOWLEDGE_GRAPH
    
    # Call the actual implementation from phases module
    collected_info = await run_information_collection_phase(pod_name, namespace, volume_path, CONFIG_DATA)
    
    # Update the global knowledge graph
    KNOWLEDGE_GRAPH = collected_info.get('knowledge_graph')
    
    return collected_info


async def run_plan_phase_wrapper(pod_name: str, namespace: str, volume_path: str, 
                               collected_info: Dict[str, Any], 
                               message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
    """
    Wrapper for Plan Phase from phases module
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        message_list: Optional message list for chat mode
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: (Investigation Plan, Updated message list)
    """
    global CONFIG_DATA
    
    try:
        # Call the actual implementation from phases module
        return await run_plan_phase(
            pod_name, namespace, volume_path, collected_info, CONFIG_DATA, message_list
        )
    except Exception as exception:
        error_msg = f"Error during Plan Phase: {str(exception)}"
        logging.error(error_msg)
        
        # Generate fallback plan
        fallback_plan = generate_fallback_plan(pod_name, namespace, volume_path)
        
        # Update message list if provided
        if message_list is not None:
            message_list = MessageListManager.add_to_message_list(message_list, fallback_plan)
        
        return fallback_plan, message_list


def generate_fallback_plan(pod_name: str, namespace: str, volume_path: str) -> str:
    """
    Generate a fallback investigation plan when the Plan Phase fails
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        
    Returns:
        str: Basic fallback Investigation Plan
    """
    return f"""Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}
Generated Steps: 3 fallback steps (Plan Phase failed)

Step 1: Get all critical issues | Tool: kg_get_all_issues(severity='critical') | Expected: Critical issues in the system
Step 2: Analyze issue patterns | Tool: kg_analyze_issues() | Expected: Root cause analysis and patterns
Step 3: Get system overview | Tool: kg_get_summary() | Expected: Overall system health statistics

Fallback Steps (if main steps fail):
Step F1: Print Knowledge Graph | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Complete system visualization | Trigger: plan_phase_failed
"""


async def run_analysis_phase_wrapper(pod_name: str, namespace: str, volume_path: str, 
                                  collected_info: Dict[str, Any], investigation_plan: str,
                                  message_list: List[Dict[str, str]] = None) -> Tuple[str, bool, List[Dict[str, str]]]:
    """
    Wrapper for Phase 1: ReAct Investigation from phases module
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        investigation_plan: Investigation Plan generated by the Plan Phase
        message_list: Optional message list for chat mode
        
    Returns:
        Tuple[str, bool, List[Dict[str, str]]]: (Analysis result, Skip Phase2 flag, Updated message list)
    """
    global CONFIG_DATA

    # Call the actual implementation from phases module
    return await run_analysis_phase_with_plan(
        pod_name, namespace, volume_path, collected_info, investigation_plan, CONFIG_DATA, message_list
    )


async def run_remediation_phase_wrapper(phase1_final_response: str, collected_info: Dict[str, Any], 
                                      message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
    """
    Wrapper for Phase 2: Remediation from phases module
    
    Args:
        phase1_final_response: Response from Phase 1 containing root cause and fix plan
        collected_info: Pre-collected diagnostic information from Phase 0
        message_list: Optional message list for chat mode
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: (Remediation result, Updated message list)
    """
    global CONFIG_DATA
    
    # Call the actual implementation from phases module
    return await run_remediation_phase(phase1_final_response, collected_info, CONFIG_DATA, message_list)


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
    global CONFIG_DATA, KNOWLEDGE_GRAPH

    start_time = time.time()
    
    results = initialize_results(pod_name, namespace, volume_path, start_time)

    try:
        # Display initial troubleshooting panel
        display_troubleshooting_start_panel(pod_name, namespace, volume_path, results['start_time'])
        
        # Phase 0: Information Collection
        collected_info = await run_phase0_information_collection(pod_name, namespace, volume_path, results, start_time)
        
        if "collection_error" in collected_info:
            handle_collection_error(collected_info, results)
            return results
        
        # Add Knowledge Graph to collected_info for Plan Phase
        collected_info["knowledge_graph"] = KNOWLEDGE_GRAPH
        
        # Run Plan Phase
        plan_phase_result = await run_plan_phase_with_chat(pod_name, namespace, volume_path, collected_info, results)
        
        # Run Phase 1: Analysis
        phase1_result = await run_phase1_analysis_with_chat(
            pod_name, namespace, volume_path, collected_info, 
            plan_phase_result, results
        )
        
        # Run Phase 2: Remediation (if not skipped)
        if not phase1_result["skip_phase2"]:
            await run_phase2_remediation(phase1_result, collected_info, results)
        else:
            handle_skipped_phase2(results)

        # Create final summary
        create_final_summary(results, start_time, phase1_result["final_response"], 
                           results["phases"].get("phase_2_remediation", {}).get("result"))
        
        return results
        
    except Exception as e:
        handle_critical_error(e, results, start_time)
        return results


def initialize_results(pod_name: str, namespace: str, volume_path: str, start_time: float) -> Dict[str, Any]:
    """
    Initialize the results dictionary
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        start_time: Start time of troubleshooting
        
    Returns:
        Dict[str, Any]: Initialized results dictionary
    """
    return {
        "pod_name": pod_name,
        "namespace": namespace,
        "volume_path": volume_path,
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
        "phases": {}
    }


def display_troubleshooting_start_panel(pod_name: str, namespace: str, volume_path: str, start_time: str) -> None:
    """
    Display the initial troubleshooting panel
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        start_time: Formatted start time
    """
    console.print("\n")
    console.print(Panel(
        f"[bold white]Starting troubleshooting for Pod: [green]{namespace}/{pod_name}[/green]\n"
        f"Volume Path: [blue]{volume_path}[/blue]\n"
        f"Start Time: [yellow]{start_time}[/yellow]",
        title="[bold cyan]KUBERNETES VOLUME TROUBLESHOOTING",
        border_style="cyan",
        padding=(1, 2)
    ))


async def run_phase0_information_collection(pod_name: str, namespace: str, volume_path: str, 
                                          results: Dict[str, Any], start_time: float) -> Dict[str, Any]:
    """
    Run Phase 0: Information Collection
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        results: Results dictionary to update
        start_time: Start time of troubleshooting
        
    Returns:
        Dict[str, Any]: Pre-collected diagnostic information
    """
    # Phase 0: Information Collection
    collected_info = await run_information_collection_phase_wrapper(pod_name, namespace, volume_path)
    
    # Update results
    results["phases"]["phase_0_collection"] = create_phase_result(
        "completed", collected_info.get("knowledge_graph_summary", {}), time.time() - start_time
    )
    
    return collected_info


def handle_collection_error(collected_info: Dict[str, Any], results: Dict[str, Any]) -> None:
    """
    Handle errors during information collection
    
    Args:
        collected_info: Collected information with error
        results: Results dictionary to update
    """
    results["phases"]["phase_0_collection"]["status"] = "failed"
    results["phases"]["phase_0_collection"]["error"] = collected_info["collection_error"]


def create_phase_result(status: str, summary: Any, duration: float) -> Dict[str, Any]:
    """
    Create a standardized phase result dictionary
    
    Args:
        status: Status of the phase (completed, failed, skipped)
        summary: Summary data from the phase
        duration: Duration of the phase in seconds
        
    Returns:
        Dict[str, Any]: Phase result dictionary
    """
    return {
        "status": status,
        "summary": summary,
        "duration": duration
    }


async def run_plan_phase_with_chat(pod_name: str, namespace: str, volume_path: str, 
                                 collected_info: Dict[str, Any], 
                                 results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the Plan Phase with chat mode support
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        results: Results dictionary to update
        
    Returns:
        Dict[str, Any]: Plan Phase result
    """
    global CONFIG_DATA
    
    plan_phase_start = time.time()
    
    try:
        # Check if chat mode is enabled for plan phase
        chat_mode_enabled = is_chat_mode_enabled_for("plan_phase")
        
        if not chat_mode_enabled:
            # Run plan phase without chat mode
            return await run_plan_phase_without_chat(
                pod_name, namespace, volume_path, collected_info, 
                plan_phase_start, results
            )
        else:
            # Run plan phase with chat mode
            return await run_plan_phase_with_chat_mode(
                pod_name, namespace, volume_path, collected_info, 
                plan_phase_start, results
            )
            
    except Exception as e:
        # Handle errors during plan phase
        return handle_plan_phase_error(
            e, pod_name, namespace, volume_path, 
            plan_phase_start, results
        )


def is_chat_mode_enabled_for(entry_point: str) -> bool:
    """
    Check if chat mode is enabled for a specific entry point
    
    Args:
        entry_point: Entry point to check
        
    Returns:
        bool: True if chat mode is enabled for the entry point, False otherwise
    """
    global CONFIG_DATA
    
    chat_mode_enabled = CONFIG_DATA.get('chat_mode', {}).get('enabled', True)
    chat_mode_entry_points = CONFIG_DATA.get('chat_mode', {}).get('entry_points', ["plan_phase", "phase1"])
    
    return chat_mode_enabled and entry_point in chat_mode_entry_points


async def run_plan_phase_without_chat(pod_name: str, namespace: str, volume_path: str, 
                                    collected_info: Dict[str, Any], 
                                    plan_phase_start: float, results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the Plan Phase without chat mode
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        plan_phase_start: Start time of the Plan Phase
        results: Results dictionary to update
        
    Returns:
        Dict[str, Any]: Plan Phase result
    """
    investigation_plan, plan_phase_message_list = await run_plan_phase_wrapper(
        pod_name, namespace, volume_path, collected_info
    )
    
    # Display the Investigation Plan
    display_investigation_plan(investigation_plan)
    
    # Update results
    results["phases"]["plan_phase"] = {
        "status": "completed",
        "investigation_plan": OutputFormatter.truncate_long_text(investigation_plan, 5000),
        "duration": time.time() - plan_phase_start
    }
    
    return {
        "status": "completed",
        "investigation_plan": investigation_plan,
        "message_list": plan_phase_message_list
    }


async def run_plan_phase_with_chat_mode(pod_name: str, namespace: str, volume_path: str, 
                                      collected_info: Dict[str, Any], 
                                      plan_phase_start: float, results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the Plan Phase with chat mode
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        plan_phase_start: Start time of the Plan Phase
        results: Results dictionary to update
        
    Returns:
        Dict[str, Any]: Plan Phase result
    """
    # Create chat mode instance
    chat_mode = ChatMode()
    
    # Initialize message list for Plan Phase
    plan_phase_message_list = None
    investigation_plan = None
    exit_flag = False
    
    while True:
        # Generate or regenerate Investigation Plan
        investigation_plan, plan_phase_message_list = await run_plan_phase_wrapper(
            pod_name, namespace, volume_path, collected_info, plan_phase_message_list
        )
        
        # Display the Investigation Plan
        display_investigation_plan(investigation_plan)
        
        # Enter chat mode after Plan Phase
        plan_phase_message_list, exit_flag = chat_mode.chat_after_plan_phase(
            plan_phase_message_list, investigation_plan
        )
        
        # Exit if requested
        if exit_flag:
            console.print("[bold red]Exiting program as requested by user[/bold red]")
            sys.exit(0)
        
        # Break loop if user approved the plan
        if plan_phase_message_list[-1]["role"] != "user":
            break
    
    # Update results
    results["phases"]["plan_phase"] = {
        "status": "completed",
        "investigation_plan": OutputFormatter.truncate_long_text(investigation_plan, 5000),
        "duration": time.time() - plan_phase_start
    }
    
    return {
        "status": "completed",
        "investigation_plan": investigation_plan,
        "message_list": plan_phase_message_list
    }


def handle_plan_phase_error(exception: Exception, pod_name: str, namespace: str, 
                          volume_path: str, plan_phase_start: float, 
                          results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle errors during the Plan Phase
    
    Args:
        exception: Exception that occurred
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        plan_phase_start: Start time of the Plan Phase
        results: Results dictionary to update
        
    Returns:
        Dict[str, Any]: Plan Phase result with error
    """
    error_msg = f"Error during Plan Phase: {str(exception)}"
    logging.error(error_msg)
    
    # Generate fallback plan
    fallback_plan = generate_fallback_plan(pod_name, namespace, volume_path)
    
    # Update results
    results["phases"]["plan_phase"] = {
        "status": "failed",
        "error": error_msg,
        "duration": time.time() - plan_phase_start
    }
    
    return {
        "status": "failed",
        "error": error_msg,
        "fallback_plan": fallback_plan,
        "message_list": None
    }


def display_investigation_plan(investigation_plan: str) -> None:
    """
    Display the Investigation Plan in a formatted panel
    
    Args:
        investigation_plan: Investigation Plan to display
    """
    console.print("\n")
    console.print(Panel(
        f"[bold white]{investigation_plan}",
        title="[bold blue]INVESTIGATION PLAN",
        border_style="blue",
        padding=(1, 2)
    ))


async def run_phase1_analysis_with_chat(pod_name: str, namespace: str, volume_path: str, 
                                      collected_info: Dict[str, Any], plan_phase_result: Dict[str, Any],
                                      results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run Phase 1 Analysis with chat mode support
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        plan_phase_result: Result from Plan Phase
        results: Results dictionary to update
        
    Returns:
        Dict[str, Any]: Phase 1 result
    """
    phase_1_start = time.time()
    
    # Get investigation plan and message list from plan phase result
    if plan_phase_result["status"] == "failed":
        # Use fallback plan if Plan Phase failed
        investigation_plan = plan_phase_result["fallback_plan"]
        plan_phase_message_list = None
    else:
        investigation_plan = plan_phase_result["investigation_plan"]
        plan_phase_message_list = plan_phase_result["message_list"]
    
    # Check if chat mode is enabled for phase1
    chat_mode_enabled = is_chat_mode_enabled_for("phase1")
    
    if not chat_mode_enabled:
        # Run Phase1 analysis without chat mode
        return await run_phase1_analysis_without_chat(
            pod_name, namespace, volume_path, collected_info, 
            investigation_plan, plan_phase_message_list, 
            phase_1_start, results
        )
    else:
        # Run Phase1 analysis with chat mode
        return await run_phase1_analysis_with_chat_mode(
            pod_name, namespace, volume_path, collected_info, 
            investigation_plan, plan_phase_message_list, 
            phase_1_start, results
        )


async def run_phase1_analysis_without_chat(pod_name: str, namespace: str, volume_path: str, 
                                         collected_info: Dict[str, Any], investigation_plan: str,
                                         plan_phase_message_list: List[Dict[str, str]], 
                                         phase_1_start: float, results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run Phase 1 Analysis without chat mode
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        investigation_plan: Investigation Plan from Plan Phase
        plan_phase_message_list: Message list from Plan Phase
        phase_1_start: Start time of Phase 1
        results: Results dictionary to update
        
    Returns:
        Dict[str, Any]: Phase 1 result
    """
    # Run Phase1 analysis without chat mode
    phase1_final_response, skip_phase2, phase1_message_list = await run_analysis_phase_wrapper(
        pod_name, namespace, volume_path, collected_info, investigation_plan, plan_phase_message_list
    )
    
    # Display the Fix Plan
    display_fix_plan(phase1_final_response)
    
    # Update results
    results["phases"]["phase_1_analysis"] = {
        "status": "completed",
        "final_response": str(phase1_final_response),
        "duration": time.time() - phase_1_start,
        "skip_phase2": "true" if skip_phase2 else "false"
    }
    
    return {
        "status": "completed",
        "final_response": phase1_final_response,
        "skip_phase2": skip_phase2,
        "message_list": phase1_message_list
    }


async def run_phase1_analysis_with_chat_mode(pod_name: str, namespace: str, volume_path: str, 
                                           collected_info: Dict[str, Any], investigation_plan: str,
                                           plan_phase_message_list: List[Dict[str, str]], 
                                           phase_1_start: float, results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run Phase 1 Analysis with chat mode
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        investigation_plan: Investigation Plan from Plan Phase
        plan_phase_message_list: Message list from Plan Phase
        phase_1_start: Start time of Phase 1
        results: Results dictionary to update
        
    Returns:
        Dict[str, Any]: Phase 1 result
    """
    # Create chat mode instance
    chat_mode = ChatMode()
    
    # Initialize message list for Phase1
    phase1_message_list = plan_phase_message_list
    phase1_final_response = None
    exit_flag = False
    skip_phase2 = False
    
    while True:
        # Run Phase1 analysis
        phase1_final_response, skip_phase2, phase1_message_list = await run_analysis_phase_wrapper(
            pod_name, namespace, volume_path, collected_info, investigation_plan, phase1_message_list
        )
        
        # Display the Fix Plan
        display_fix_plan(phase1_final_response)
        
        # Enter chat mode after Phase1
        phase1_message_list, exit_flag = chat_mode.chat_after_phase1(
            phase1_message_list, phase1_final_response
        )
        
        # Exit if requested
        if exit_flag:
            console.print("[bold red]Exiting program as requested by user[/bold red]")
            sys.exit(0)
        
        # Break loop if user approved the analysis
        if phase1_message_list[-1]["role"] != "user":
            break
    
    # Update results
    results["phases"]["phase_1_analysis"] = {
        "status": "completed",
        "final_response": str(phase1_final_response),
        "duration": time.time() - phase_1_start,
        "skip_phase2": "true" if skip_phase2 else "false"
    }
    
    return {
        "status": "completed",
        "final_response": phase1_final_response,
        "skip_phase2": skip_phase2,
        "message_list": phase1_message_list
    }


def display_fix_plan(fix_plan: str) -> None:
    """
    Display the Fix Plan in a formatted panel
    
    Args:
        fix_plan: Fix Plan to display
    """
    console.print("\n")
    console.print(Panel(
        f"[bold white]{fix_plan}",
        title="[bold green]FIX PLAN",
        border_style="green",
        padding=(1, 2)
    ))


async def run_phase2_remediation(phase1_result: Dict[str, Any], collected_info: Dict[str, Any], 
                               results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run Phase 2: Remediation
    
    Args:
        phase1_result: Result from Phase 1
        collected_info: Pre-collected diagnostic information from Phase 0
        results: Results dictionary to update
        
    Returns:
        Dict[str, Any]: Phase 2 result
    """
    phase_2_start = time.time()
    
    # Get final response and message list from phase1 result
    phase1_final_response = phase1_result["final_response"]
    phase1_message_list = phase1_result["message_list"]
    
    # Run Phase2 remediation
    remediation_result, phase2_message_list = await run_remediation_phase_wrapper(
        phase1_final_response, collected_info, phase1_message_list
    )
    
    # Display the remediation result
    display_remediation_result(remediation_result)
    
    # Update results
    results["phases"]["phase_2_remediation"] = {
        "status": "completed",
        "result": str(remediation_result),
        "duration": time.time() - phase_2_start
    }
    
    return {
        "status": "completed",
        "result": remediation_result,
        "message_list": phase2_message_list
    }


def handle_skipped_phase2(results: Dict[str, Any]) -> None:
    """
    Handle skipped Phase 2
    
    Args:
        results: Results dictionary to update
    """
    console.print("\n")
    console.print(Panel(
        "[bold white]Phase 2 (Remediation) was skipped based on Phase 1 analysis.",
        title="[bold yellow]PHASE 2: SKIPPED",
        border_style="yellow",
        padding=(1, 2)
    ))
    
    # Update results
    results["phases"]["phase_2_remediation"] = {
        "status": "skipped",
        "reason": "Phase 1 indicated no remediation needed or manual intervention required"
    }


def display_remediation_result(remediation_result: str) -> None:
    """
    Display the remediation result in a formatted panel
    
    Args:
        remediation_result: Remediation result to display
    """
    console.print("\n")
    console.print(Panel(
        f"[bold white]{remediation_result}",
        title="[bold green]REMEDIATION RESULT",
        border_style="green",
        padding=(1, 2)
    ))


def create_final_summary(results: Dict[str, Any], start_time: float, 
                       phase1_result: str, phase2_result: Optional[str] = None) -> None:
    """
    Create and display the final troubleshooting summary
    
    Args:
        results: Results dictionary
        start_time: Start time of troubleshooting
        phase1_result: Result from Phase 1
        phase2_result: Optional result from Phase 2
    """
    # Calculate total duration
    total_duration = time.time() - start_time
    
    # Create summary table
    table = Table(title="Troubleshooting Summary")
    
    # Add columns
    table.add_column("Phase", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Duration", style="yellow")
    
    # Add rows for each phase
    for phase_name, phase_data in results["phases"].items():
        status = phase_data.get("status", "unknown")
        duration = phase_data.get("duration", "N/A")
        
        if isinstance(duration, (int, float)):
            duration = f"{duration:.2f}s"
        
        table.add_row(
            phase_name.replace("_", " ").title(),
            status.title(),
            str(duration)
        )
    
    # Add total duration
    table.add_row(
        "Total",
        "Completed",
        f"{total_duration:.2f}s",
        style="bold"
    )
    
    # Display summary
    console.print("\n")
    console.print(Panel(
        f"[bold white]Troubleshooting completed for Pod: [green]{results['namespace']}/{results['pod_name']}[/green]\n"
        f"Volume Path: [blue]{results['volume_path']}[/blue]\n"
        f"Start Time: [yellow]{results['start_time']}[/yellow]\n"
        f"End Time: [yellow]{time.strftime('%Y-%m-%d %H:%M:%S')}[/yellow]\n"
        f"Total Duration: [bold yellow]{total_duration:.2f}s[/bold yellow]",
        title="[bold cyan]TROUBLESHOOTING COMPLETE",
        border_style="cyan",
        padding=(1, 2)
    ))
    
    # Display summary table
    console.print(table)
    
    # Display root cause and fix plan summary
    display_root_cause_summary(phase1_result, phase2_result)


def display_root_cause_summary(phase1_result: str, phase2_result: Optional[str] = None) -> None:
    """
    Display the root cause and fix plan summary
    
    Args:
        phase1_result: Result from Phase 1
        phase2_result: Optional result from Phase 2
    """
    # Extract root cause and fix plan from phase1 result
    root_cause = OutputFormatter.extract_section_from_text(phase1_result, "Root Cause")
    fix_plan = OutputFormatter.extract_section_from_text(phase1_result, "Fix Plan")
    
    # Create summary panel
    summary_content = f"[bold white]Root Cause:[/bold white]\n[green]{root_cause or 'Not found in analysis'}[/green]\n\n"
    
    if phase2_result:
        # Extract resolution status from phase2 result
        resolution_status = OutputFormatter.extract_section_from_text(phase2_result, "Resolution Status")
        summary_content += f"[bold white]Resolution Status:[/bold white]\n[blue]{resolution_status or 'Not found in remediation result'}[/blue]"
    else:
        summary_content += f"[bold white]Fix Plan:[/bold white]\n[yellow]{fix_plan or 'Not found in analysis'}[/yellow]"
    
    # Display summary panel
    console.print("\n")
    console.print(Panel(
        summary_content,
        title="[bold magenta]ROOT CAUSE AND RESOLUTION SUMMARY",
        border_style="magenta",
        padding=(1, 2)
    ))


def handle_critical_error(exception: Exception, results: Dict[str, Any], start_time: float) -> None:
    """
    Handle critical errors during troubleshooting
    
    Args:
        exception: Exception that occurred
        results: Results dictionary to update
        start_time: Start time of troubleshooting
    """
    error_msg = f"Critical error during troubleshooting: {str(exception)}"
    logging.error(error_msg)
    
    # Update results
    results["status"] = "failed"
    results["error"] = error_msg
    results["duration"] = time.time() - start_time
    
    # Display error panel
    console.print("\n")
    console.print(Panel(
        f"[bold white]Critical error occurred during troubleshooting:\n[red]{str(exception)}[/red]",
        title="[bold red]ERROR",
        border_style="red",
        padding=(1, 2)
    ))


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Kubernetes Volume I/O Error Troubleshooting')
    parser.add_argument('--pod', required=True, help='Name of the pod with the error')
    parser.add_argument('--namespace', default='default', help='Namespace of the pod')
    parser.add_argument('--volume-path', required=True, help='Path of the volume with I/O error')
    parser.add_argument('--config', default='config.yaml', help='Path to configuration file')
    parser.add_argument('--interactive', action='store_true', help='Enable interactive mode')
    
    return parser.parse_args()


async def main() -> None:
    """
    Main function
    """
    global CONFIG_DATA, INTERACTIVE_MODE
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Load configuration
    CONFIG_DATA = load_config(args.config)
    
    # Set interactive mode
    INTERACTIVE_MODE = args.interactive
    CONFIG_DATA['troubleshoot']['interactive_mode'] = INTERACTIVE_MODE
    
    # Setup logging
    setup_logging(CONFIG_DATA)
    
    # Initialize Kubernetes configuration
    initialize_kubernetes_config()
    
    # Run comprehensive troubleshooting
    results = await run_comprehensive_troubleshooting(args.pod, args.namespace, args.volume_path)
    
    # Save results to file
    save_results_to_file(results)


def save_results_to_file(results: Dict[str, Any]) -> None:
    """
    Save troubleshooting results to file
    
    Args:
        results: Troubleshooting results
    """
    try:
        # Create results directory if it doesn't exist
        os.makedirs('results', exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"results/troubleshoot-{results['namespace']}-{results['pod_name']}-{timestamp}.json"
        
        # Save results to file
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        logging.info(f"Results saved to {filename}")
        console.print(f"[bold green]Results saved to {filename}[/bold green]")
    except Exception as e:
        logging.error(f"Error saving results to file: {e}")
        console.print(f"[bold red]Error saving results to file: {e}[/bold red]")


if __name__ == '__main__':
    asyncio.run(main())
