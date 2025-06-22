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
from typing import Dict, List, Any, Optional, Tuple
from langgraph.graph import StateGraph
from kubernetes import config
#from troubleshooting.graph import create_troubleshooting_graph_with_context
from information_collector import ComprehensiveInformationCollector
from phases import (
    run_information_collection_phase,
    run_plan_phase,
    run_analysis_phase_with_plan,
    run_remediation_phase
)
import tempfile
import json
import os
from phases.chat_mode import ChatMode
from tools.core.mcp_adapter import initialize_mcp_adapter, get_mcp_adapter
from rich.logging import RichHandler
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn # Retained if progress is used elsewhere
from rich.panel import Panel # Retained for potential direct use if any
from rich.table import Table # Retained for potential direct use if any
# from rich.tree import Tree # Not used directly in troubleshoot.py after UI extraction
from rich import print as rprint # Retained for potential direct use if any
from .ui import TroubleshootingUI # Import the new UI class

# Initialize rich console
console = Console() # Retained for general console output not covered by TroubleshootingUI
file_console = Console(file=open('troubleshoot.log', 'w')) # Retained for file logging

# Global UI instance
troubleshooting_ui: Optional[TroubleshootingUI] = None

# Custom filter for internal logging
class InternalLogFilter(logging.Filter):
    """Filter out internal logging messages from console output"""
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

# Set up logging handlers for module-specific loggers
def configure_module_loggers():
    """Set up file handlers for module-specific loggers"""
    # Create file handler for log file
    file_handler = logging.FileHandler('troubleshoot.log', mode='a')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # Configure langgraph logger
    langgraph_logger = logging.getLogger('langgraph')
    langgraph_logger.addHandler(file_handler)
    
    # Configure knowledge_graph logger
    kg_logger = logging.getLogger('knowledge_graph')
    kg_logger.addHandler(file_handler)
    
    # Configure knowledge_graph.tools logger
    kg_tools_logger = logging.getLogger('knowledge_graph.tools')
    kg_tools_logger.addHandler(file_handler)
    
    # Configure other module loggers as needed
    for module in ['tools', 'information_collector', 'kubernetes', 'urllib3']:
        module_logger = logging.getLogger(module)
        module_logger.addHandler(file_handler)

# Global variables
CONFIG_DATA = None
INTERACTIVE_MODE = False
SSH_CLIENTS = {}
KNOWLEDGE_GRAPH = None
RESULTS_DIR = os.path.join(tempfile.gettempdir(), "k8s-troubleshooting-results")

#os.environ['LANGCHAIN_TRACING_V2'] = "true"   
#os.environ['LANGCHAIN_ENDPOINT'] = "https://api.smith.langchain.com"   
#os.environ['LANGCHAIN_API_KEY'] = "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"   
#os.environ['LANGCHAIN_PROJECT'] = "pr-silver-bank-1"

def load_config():
    """Load configuration from config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        sys.exit(1)

def setup_results_dir():
    """Set up the directory for storing troubleshooting results"""
    try:
        if not os.path.exists(RESULTS_DIR):
            os.makedirs(RESULTS_DIR)
            logging.debug(f"Created results directory: {RESULTS_DIR}")
    except Exception as e:
        logging.error(f"Failed to create results directory: {e}")

def write_investigation_result(pod_name, namespace, volume_path, result_summary):
    """
    Write investigation result to a file for the monitor to pick up
    
    Args:
        pod_name: Name of the pod
        namespace: Namespace of the pod
        volume_path: Path of the volume
        result_summary: Summary of the investigation result
    """
    try:
        # Create a unique filename based on pod details
        filename = f"{namespace}_{pod_name}_{volume_path.replace('/', '_')}.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        
        # Create a result object
        result_data = {
            "pod_name": pod_name,
            "namespace": namespace,
            "volume_path": volume_path,
            "timestamp": time.time(),
            "result_summary": result_summary
        }
        
        # Write to file
        with open(filepath, 'w') as f:
            json.dump(result_data, f)
            
        logging.info(f"Investigation result written to {filepath}")
    except Exception as e:
        logging.error(f"Failed to write investigation result: {e}")

def setup_logging(config_data):
    """Configure logging based on configuration with rich formatting"""
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
    # logging.info("Logging initialized - internal logs redirected to log file only")
    # This specific message can be removed or kept depending on preference,
    # RichHandler itself might log its initialization.

# Helper function to initialize UI if not already done
def _initialize_ui_if_needed():
    global troubleshooting_ui
    if troubleshooting_ui is None:
        # Ensure console and file_console are initialized before this call
        troubleshooting_ui = TroubleshootingUI(console, file_console)

async def _execute_information_collection_phase(pod_name: str, namespace: str, volume_path: str, results: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Executes Phase 0: Information Collection.
    Updates results with phase data.
    Returns collected_info and knowledge_graph.
    """
    global CONFIG_DATA, KNOWLEDGE_GRAPH, troubleshooting_ui
    _initialize_ui_if_needed()

    phase_start_time = time.time()
    troubleshooting_ui.display_initial_banner(pod_name, namespace, volume_path, results["start_time"])

    collected_info = await run_information_collection_phase(pod_name, namespace, volume_path, CONFIG_DATA)
    
    KNOWLEDGE_GRAPH = collected_info.get('knowledge_graph')
    if KNOWLEDGE_GRAPH:
        from tools.core.knowledge_graph import initialize_knowledge_graph
        initialize_knowledge_graph(KNOWLEDGE_GRAPH)
        logging.info("Knowledge Graph from Phase0 initialized for tools")
    else:
        logging.warning("No Knowledge Graph available from Phase0")

    phase_duration = time.time() - phase_start_time
    results["phases"]["phase_0_collection"] = {
        "status": "completed",
        "summary": collected_info.get("knowledge_graph_summary", {}),
        "duration": phase_duration
    }

    if "collection_error" in collected_info:
        results["phases"]["phase_0_collection"]["status"] = "failed"
        results["phases"]["phase_0_collection"]["error"] = collected_info["collection_error"]
        troubleshooting_ui.display_error_panel(f"Information Collection Failed: {collected_info['collection_error']}")
        return None, KNOWLEDGE_GRAPH # Indicate failure

    # Add Knowledge Graph to collected_info for subsequent phases
    collected_info["knowledge_graph"] = KNOWLEDGE_GRAPH
    return collected_info, KNOWLEDGE_GRAPH

# _execute_information_collection_phase remains as previously defined.
# run_information_collection_phase_wrapper remains as previously defined (deprecated).


async def _handle_chat_interaction_for_phase(
    chat_mode: ChatMode,
    phase_execution_fn: callable,
    chat_interaction_fn: callable,
    initial_args: list,
    initial_message_list: Optional[List[Dict[str, str]]],
    ui_display_fn: callable,
    phase_name: str # For logging and error messages
) -> Tuple[Any, Optional[List[Dict[str, str]]], bool, List[Any]]:
    """
    Handles the common loop for chat interaction within a phase.
    Returns the primary phase result, final message list, exit flag, and other auxiliary results from phase_execution_fn.
    """
    global troubleshooting_ui
    _initialize_ui_if_needed()

    current_message_list = initial_message_list
    phase_primary_result = None
    other_results = []
    exit_flag = False

    while True:
        phase_fn_args = initial_args + [current_message_list]

        try:
            returned_values = await phase_execution_fn(*phase_fn_args)
        except Exception as e:
            logging.error(f"Error during {phase_name} execution: {e}", exc_info=True)
            # Return a generic error result, null message list, and no exit
            # The caller phase function should handle this by setting its own error status
            return f"{phase_name} execution failed: {e}", current_message_list, False, []


        if isinstance(returned_values, tuple):
            phase_primary_result = returned_values[0]
            current_message_list = returned_values[-1]
            other_results = list(returned_values[1:-1])
        else:
            phase_primary_result = returned_values
            # If message_list is not the last item, this needs adjustment or phase_execution_fn needs to conform.
            # Assuming for now that if not a tuple, it's just the primary result and message list is managed via args.

        ui_display_fn(phase_primary_result)

        # Special handling for analysis summary if present in other_results
        if phase_name == "Analysis" and len(other_results) >= 2: # skip_flag, summary
            analysis_summary = other_results[1]
            if analysis_summary:
                troubleshooting_ui.display_event_summary(analysis_summary)
        
        chat_args_for_interaction = [current_message_list, phase_primary_result]
        # Example: chat_after_phase1 might take (message_list, phase1_response)

        current_message_list, exit_flag = chat_interaction_fn(*chat_args_for_interaction)

        if exit_flag:
            troubleshooting_ui.display_exit_message(f"Exiting program as requested by user during {phase_name}.")
            sys.exit(0)

        if not current_message_list or current_message_list[-1].get("role") != "user":
            return phase_primary_result, current_message_list, exit_flag, other_results

    # Fallback, should ideally not be reached if loop logic is correct
    return phase_primary_result, current_message_list, exit_flag, other_results


async def _execute_plan_phase(pod_name: str, namespace: str, volume_path: str,
                            collected_info: Dict[str, Any], results: Dict[str, Any]) \
                            -> Tuple[Optional[str], Optional[List[Dict[str, str]]]]:
    """
    Executes the Plan Phase. Updates results. Returns investigation_plan, plan_phase_message_list.
    """
    global CONFIG_DATA, troubleshooting_ui
    _initialize_ui_if_needed()

    plan_phase_start_time = time.time()
    investigation_plan = None
    plan_phase_message_list = None # This will be the message list *after* this phase

    results["phases"]["plan_phase"] = { # Initialize results for this phase
        "status": "pending", "duration": 0, "investigation_plan": None
    }

    try:
        chat_mode_enabled = CONFIG_DATA.get('chat_mode', {}).get('enabled', True)
        plan_phase_chat_enabled = chat_mode_enabled and \
                                  "plan_phase" in CONFIG_DATA.get('chat_mode', {}).get('entry_points', [])

        if not plan_phase_chat_enabled:
            investigation_plan, plan_phase_message_list = await run_plan_phase(
                pod_name, namespace, volume_path, collected_info, CONFIG_DATA, None
            )
            troubleshooting_ui.display_investigation_plan(investigation_plan)
        else:
            chat_mode = ChatMode()
            investigation_plan, plan_phase_message_list, _, _ = await _handle_chat_interaction_for_phase(
                chat_mode=chat_mode,
                phase_execution_fn=run_plan_phase, # Expected to return: plan_text, message_list
                chat_interaction_fn=chat_mode.chat_after_plan_phase, # Expected args: message_list, plan_text
                initial_args=[pod_name, namespace, volume_path, collected_info, CONFIG_DATA],
                initial_message_list=None, # No prior message list for plan phase start
                ui_display_fn=troubleshooting_ui.display_investigation_plan,
                phase_name="Plan Generation"
            )

        results["phases"]["plan_phase"]["status"] = "completed"
        results["phases"]["plan_phase"]["investigation_plan"] = investigation_plan[:5000] + "..." if investigation_plan and len(investigation_plan) > 5000 else investigation_plan

    except Exception as e:
        error_msg = f"Error during Plan Phase: {str(e)}"
        logging.error(error_msg, exc_info=True)
        results["phases"]["plan_phase"]["status"] = "failed"
        results["phases"]["plan_phase"]["error"] = error_msg
        investigation_plan = f"Fallback Plan (Plan Phase Error): {error_msg}"
        troubleshooting_ui.display_investigation_plan(investigation_plan)

    results["phases"]["plan_phase"]["duration"] = time.time() - plan_phase_start_time
    return investigation_plan, plan_phase_message_list


async def run_analysis_phase_wrapper(pod_name: str, namespace: str, volume_path: str,
                                  collected_info: Dict[str, Any], investigation_plan: Optional[str], # Optional
                                  message_list: List[Dict[str, str]] = None) -> Tuple[str, bool, str, List[Dict[str, str]]]:
    global CONFIG_DATA
    if not investigation_plan:
        # This case should ideally be handled before calling, or run_analysis_phase_with_plan must handle None
        logging.warning("run_analysis_phase_wrapper called with no investigation_plan.")
        investigation_plan = "Error: Investigation plan was not generated."
    return await run_analysis_phase_with_plan(
        pod_name, namespace, volume_path, collected_info, investigation_plan, CONFIG_DATA, message_list
    )


async def _execute_analysis_phase(pod_name: str, namespace: str, volume_path: str,
                                collected_info: Dict[str, Any], investigation_plan: Optional[str],
                                initial_message_list: Optional[List[Dict[str, str]]],
                                results: Dict[str, Any]) \
                                -> Tuple[Optional[str], bool, Optional[List[Dict[str, str]]]]:
    """
    Executes Phase 1: ReAct Investigation. Updates results.
    Returns final response, skip_phase2 flag, and message list for remediation.
    """
    global CONFIG_DATA, troubleshooting_ui
    _initialize_ui_if_needed()

    phase_1_start_time = time.time()
    phase1_final_response = None
    skip_phase2 = False
    phase1_message_list = initial_message_list # Message list *after* this phase

    results["phases"]["phase_1_analysis"] = { # Initialize
        "status": "pending", "duration": 0, "final_response": None, "skip_phase2": "false"
    }

    if not investigation_plan:
        investigation_plan = "No investigation plan available (Plan Phase likely failed or generated no plan)."
        results["phases"]["phase_1_analysis"]["final_response"] = "Skipped due to missing investigation plan."
        results["phases"]["phase_1_analysis"]["status"] = "skipped"
        results["phases"]["phase_1_analysis"]["duration"] = time.time() - phase_1_start_time
        troubleshooting_ui.display_error_panel("Analysis skipped: Investigation plan not available.", "[bold yellow]ANALYSIS SKIPPED[/bold yellow]")
        return "Analysis skipped due to missing plan.", True, phase1_message_list

    try:
        chat_mode_enabled = CONFIG_DATA.get('chat_mode', {}).get('enabled', True)
        phase1_chat_enabled = chat_mode_enabled and \
                              "phase1" in CONFIG_DATA.get('chat_mode', {}).get('entry_points', [])

        if not phase1_chat_enabled:
            # run_analysis_phase_wrapper returns: (Analysis result, Skip Phase2 flag, Summary, Updated message list)
            phase1_final_response, skip_phase2, analysis_summary, phase1_message_list = await run_analysis_phase_wrapper(
                pod_name, namespace, volume_path, collected_info, investigation_plan, phase1_message_list
            )
            troubleshooting_ui.display_fix_plan(phase1_final_response)
            if analysis_summary: troubleshooting_ui.display_event_summary(analysis_summary)
        else:
            chat_mode = ChatMode()
            # Expected return from phase_execution_fn (run_analysis_phase_wrapper): response, skip_flag, summary, msg_list
            # Expected other_results from _handle_chat: [skip_flag, summary]
            phase1_final_response, phase1_message_list, _, other_results = await _handle_chat_interaction_for_phase(
                chat_mode=chat_mode,
                phase_execution_fn=run_analysis_phase_wrapper,
                chat_interaction_fn=chat_mode.chat_after_phase1, # Expected args: msg_list, phase1_response
                initial_args=[pod_name, namespace, volume_path, collected_info, investigation_plan],
                initial_message_list=phase1_message_list,
                ui_display_fn=troubleshooting_ui.display_fix_plan,
                phase_name="Analysis"
            )
            if other_results and len(other_results) > 0: skip_phase2 = other_results[0] # First item in other_results is skip_flag
            # analysis_summary is handled by _handle_chat_interaction_for_phase for display

        results["phases"]["phase_1_analysis"]["status"] = "completed"
        results["phases"]["phase_1_analysis"]["final_response"] = str(phase1_final_response)
        results["phases"]["phase_1_analysis"]["skip_phase2"] = "true" if skip_phase2 else "false"

    except Exception as e:
        error_msg = f"Error during Analysis Phase: {str(e)}"
        logging.error(error_msg, exc_info=True)
        results["phases"]["phase_1_analysis"]["status"] = "failed"
        results["phases"]["phase_1_analysis"]["error"] = error_msg
        results["phases"]["phase_1_analysis"]["skip_phase2"] = "true" # Skip Phase2 if analysis fails
        phase1_final_response = f"Analysis failed: {error_msg}"
        troubleshooting_ui.display_error_panel(phase1_final_response, title="[bold red]ANALYSIS FAILED[/bold red]")
        skip_phase2 = True # Ensure skip_phase2 is true on exception

    results["phases"]["phase_1_analysis"]["duration"] = time.time() - phase_1_start_time
    return phase1_final_response, skip_phase2, phase1_message_list


async def run_remediation_phase_wrapper(phase1_final_response: str, collected_info: Dict[str, Any],
                                      message_list: List[Dict[str, str]] = None) -> Tuple[str, List[Dict[str, str]]]:
    global CONFIG_DATA
    return await run_remediation_phase(phase1_final_response, collected_info, CONFIG_DATA, message_list)


async def _execute_remediation_phase(phase1_final_response: Optional[str],
                                   collected_info: Dict[str, Any],
                                   phase1_message_list: Optional[List[Dict[str, str]]],
                                   results: Dict[str, Any]) -> Optional[str]:
    """
    Executes Phase 2: Remediation. Updates results. Returns remediation_result.
    """
    global troubleshooting_ui
    _initialize_ui_if_needed()
    
    phase_2_start_time = time.time()
    remediation_result = "Phase 2: Remediation not initiated or response unavailable." # Default

    results["phases"]["phase_2_remediation"] = { # Initialize
        "status": "pending", "duration": 0, "result": remediation_result
    }

    if not phase1_final_response:
        phase1_final_response = "No analysis response available for remediation."
        logging.warning(phase1_final_response)
        # Update results to reflect that remediation cannot proceed meaningfully
        results["phases"]["phase_2_remediation"]["status"] = "skipped"
        results["phases"]["phase_2_remediation"]["reason"] = "Missing analysis response from Phase 1."
        results["phases"]["phase_2_remediation"]["result"] = "Skipped: Missing analysis response."
        results["phases"]["phase_2_remediation"]["duration"] = time.time() - phase_2_start_time
        troubleshooting_ui.display_phase2_skipped() # Or a more specific message
        return results["phases"]["phase_2_remediation"]["result"]

    try:
        troubleshooting_ui.display_remediation_start_panel()

        # run_remediation_phase_wrapper returns: (Remediation result, Updated message list)
        remediation_result_tuple = await run_remediation_phase_wrapper(
            phase1_final_response, collected_info, phase1_message_list
        )
        remediation_result = remediation_result_tuple[0]

        current_status = "completed"
        if "failed" in remediation_result.lower() or \
           "error" in remediation_result.lower() or \
           "timed out" in remediation_result.lower():
            current_status = "failed"
            troubleshooting_ui.display_remediation_failed(remediation_result)
        else:
            troubleshooting_ui.display_remediation_complete()

        results["phases"]["phase_2_remediation"]["status"] = current_status
        results["phases"]["phase_2_remediation"]["result"] = remediation_result
        
    except Exception as e:
        error_msg = f"Error during Remediation Phase: {str(e)}"
        logging.error(error_msg, exc_info=True)
        results["phases"]["phase_2_remediation"]["status"] = "failed"
        results["phases"]["phase_2_remediation"]["error"] = error_msg
        results["phases"]["phase_2_remediation"]["result"] = error_msg
        remediation_result = error_msg # Ensure remediation_result reflects the error
        troubleshooting_ui.display_remediation_failed(error_msg)

    results["phases"]["phase_2_remediation"]["duration"] = time.time() - phase_2_start_time
    return remediation_result


async def run_comprehensive_troubleshooting(pod_name: str, namespace: str, volume_path: str) -> Dict[str, Any]:
    """
    Run comprehensive 3-phase troubleshooting.
    Orchestrates the three main phases: Information Collection, Plan/Analysis, and Remediation.
    """
    global CONFIG_DATA, KNOWLEDGE_GRAPH, troubleshooting_ui
    _initialize_ui_if_needed()

    start_time = time.time()
    # Initialize results with all expected phase keys for consistent structure
    results = {
        "pod_name": pod_name, "namespace": namespace, "volume_path": volume_path,
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
        "phases": {
            "phase_0_collection": {"status": "pending", "duration": 0, "summary": {}, "error": None},
            "plan_phase": {"status": "pending", "duration": 0, "investigation_plan": None, "error": None},
            "phase_1_analysis": {"status": "pending", "duration": 0, "final_response": None, "skip_phase2": "false", "error": None},
            "phase_2_remediation": {"status": "pending", "duration": 0, "result": "Not run", "reason": None, "error": None},
        },
        "total_duration": 0,
        "status": "pending", # Overall status
        "error": None # Overall error
    }

    phase1_final_response = "N/A" # Ensure it has a default for display_final_summary
    remediation_result = "N/A"    # Ensure it has a default

    try:
        # Phase 0: Information Collection
        collected_info, kg_from_phase0 = await _execute_information_collection_phase(
            pod_name, namespace, volume_path, results
        )
        KNOWLEDGE_GRAPH = kg_from_phase0 # Update global KG
        if results["phases"]["phase_0_collection"]["status"] == "failed":
            results["status"] = "failed"
            results["error"] = results["phases"]["phase_0_collection"].get("error", "Information collection failed.")
            # Final summary will be displayed in finally block

        # Plan Phase - only if Phase 0 succeeded
        investigation_plan = None
        plan_phase_message_list = None
        if results["status"] == "pending": # Proceed if no failure yet
            investigation_plan, plan_phase_message_list = await _execute_plan_phase(
                pod_name, namespace, volume_path, collected_info, results
            )
            if results["phases"]["plan_phase"]["status"] == "failed":
                logging.warning("Plan phase failed. Analysis may proceed with a fallback or limited plan.")
                # Overall status is not yet 'failed' unless this is critical.
                # For now, let analysis decide if it can proceed.

        # Phase 1: Analysis - only if Phase 0 succeeded (collected_info is valid)
        skip_phase2 = False
        phase1_message_list_for_remediation = plan_phase_message_list # Carry over
        if results["status"] == "pending" or results["phases"]["plan_phase"]["status"] == "completed": # Allow analysis if plan failed but info collected
            phase1_final_response, skip_phase2, phase1_message_list_for_remediation = await _execute_analysis_phase(
                pod_name, namespace, volume_path, collected_info, investigation_plan,
                plan_phase_message_list, results
            )
            if results["phases"]["phase_1_analysis"]["status"] == "failed":
                logging.warning("Analysis phase failed. Remediation will be skipped.")
                skip_phase2 = True
                results["phases"]["phase_2_remediation"]["status"] = "skipped"
                results["phases"]["phase_2_remediation"]["reason"] = "Analysis phase failed"
                results["phases"]["phase_2_remediation"]["result"] = "Skipped: Analysis phase failed"


        # Phase 2: Remediation - only if not skipped and previous phases allow
        if results["status"] == "pending" and not skip_phase2 :
            if results["phases"]["phase_1_analysis"]["status"] == "completed": # Ensure analysis completed successfully
                remediation_result = await _execute_remediation_phase(
                    phase1_final_response, collected_info, phase1_message_list_for_remediation, results
                )
            else: # Analysis did not complete successfully, or was skipped.
                skip_phase2 = True # Explicitly skip
                results["phases"]["phase_2_remediation"]["status"] = "skipped"
                results["phases"]["phase_2_remediation"]["reason"] = "Analysis phase did not complete successfully or was skipped."
                results["phases"]["phase_2_remediation"]["result"] = "Skipped: Analysis issues."
                troubleshooting_ui.display_phase2_skipped()
        elif skip_phase2: # If already marked to skip
             results["phases"]["phase_2_remediation"]["status"] = "skipped"
             if not results["phases"]["phase_2_remediation"]["reason"]:
                results["phases"]["phase_2_remediation"]["reason"] = "Skipped by analysis phase or configuration."
             results["phases"]["phase_2_remediation"]["result"] = f"Skipped: {results['phases']['phase_2_remediation']['reason']}"
             troubleshooting_ui.display_phase2_skipped()


        # Determine final overall status
        if results["phases"]["phase_0_collection"]["status"] == "failed" or \
           results["phases"]["phase_1_analysis"]["status"] == "failed" or \
           (not skip_phase2 and results["phases"]["phase_2_remediation"]["status"] == "failed") or \
           results["phases"]["plan_phase"]["status"] == "failed": # Consider plan failure as overall if critical
            results["status"] = "failed"
            if not results["error"]: # If a specific phase error wasn't propagated to overall
                results["error"] = "One or more troubleshooting phases failed."
        elif results["status"] == "pending": # If no failures, mark as completed
            results["status"] = "completed"
            
    except Exception as e:
        critical_error_msg = f"Critical unhandled error in run_comprehensive_troubleshooting: {str(e)}"
        logging.critical(critical_error_msg, exc_info=True)
        results["status"] = "failed"
        results["error"] = critical_error_msg
        # Mark all pending phases as failed due to this critical error
        for phase_key in results["phases"]:
            if results["phases"][phase_key]["status"] == "pending":
                results["phases"][phase_key]["status"] = "error_due_to_critical_failure"
                results["phases"][phase_key]["error"] = critical_error_msg
    finally:
        results["total_duration"] = time.time() - start_time
        # Ensure phase1_final_response and remediation_result are strings for the UI
        ui_phase1_response = str(results["phases"]["phase_1_analysis"].get("final_response", "N/A"))
        ui_remediation_result = str(results["phases"]["phase_2_remediation"].get("result", "N/A"))
        troubleshooting_ui.display_final_summary(results, ui_phase1_response, ui_remediation_result)

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

        # Setup logging and results directory
        setup_logging(CONFIG_DATA)
        setup_results_dir()
        
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Validate inputs
        if not args.pod_name or not args.namespace or not args.volume_path:
            logging.error("Pod name, namespace, and volume path are required")
            sys.exit(1)
        llm_provider = CONFIG_DATA.get("llm").get("provider")
        current_api_key = CONFIG_DATA.get("llm").get(llm_provider, "openai").get("api_key")
        if len(current_api_key) < 10:
            logging.error("AI key is empty!")
            sys.exit(1)

        # Initialize MCP adapter
        mcp_adapter = await initialize_mcp_adapter(CONFIG_DATA)

        # Initialize Kubernetes configuration
        try:
            config.load_incluster_config()
            logging.info("Loaded in-cluster Kubernetes configuration")
        except config.ConfigException: # More specific exception
            try:
                config.load_kube_config()
                logging.info("Loaded kubeconfig from default location")
            except Exception as e: # Catch broader exceptions for kube_config loading
                logging.error(f"Failed to load Kubernetes configuration: {e}", exc_info=True)
                if troubleshooting_ui:
                    troubleshooting_ui.display_error_panel(f"Failed to load Kubernetes configuration: {e}")
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
                if troubleshooting_ui:
                    troubleshooting_ui.display_info_panel(f"Results saved to {args.output}")
            except Exception as e:
                logging.error(f"Failed to save results to {args.output}: {e}", exc_info=True)
                if troubleshooting_ui:
                    troubleshooting_ui.display_error_panel(f"Failed to save results to {args.output}: {e}")
        
        # Exit with appropriate code
        if results.get("status") == "completed": # Use .get for safety
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        logging.info("Troubleshooting interrupted by user")
        if troubleshooting_ui:
            troubleshooting_ui.display_exit_message("Troubleshooting interrupted by user.")
        sys.exit(130) # Standard exit code for Ctrl+C
    except Exception as e:
        logging.critical(f"Critical error in main: {str(e)}", exc_info=True) # Use critical for top-level crash
        if troubleshooting_ui: # Check if UI is available
             troubleshooting_ui.display_error_panel(f"Critical error in main: {str(e)}", title="[bold red]CRITICAL APPLICATION ERROR[/bold red]")
        else:
             console.print(Panel(f"[bold red]CRITICAL ERROR IN MAIN: {str(e)}[/bold red]"))
        sys.exit(1)
    finally:
        # Clean up SSH connections
        for client in SSH_CLIENTS.values():
            try:
                client.close()
            except:
                pass
                
        # Clean up MCP connections
        mcp_adapter = get_mcp_adapter()
        if mcp_adapter:
            await mcp_adapter.close()

if __name__ == "__main__":
    asyncio.run(main())
