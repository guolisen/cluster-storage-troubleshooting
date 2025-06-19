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
from phases.chat_mode import ChatMode
from tools.core.mcp_adapter import initialize_mcp_adapter, get_mcp_adapter
from rich.logging import RichHandler
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich import print as rprint

# Initialize rich console
console = Console()
file_console = Console(file=open('troubleshoot.log', 'w'))

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
    logging.info("Logging initialized - internal logs redirected to log file only")

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
    
    # Initialize the Knowledge Graph in the tools module with the one from Phase0
    if KNOWLEDGE_GRAPH:
        from tools.core.knowledge_graph import initialize_knowledge_graph
        initialize_knowledge_graph(KNOWLEDGE_GRAPH)
        logging.info("Knowledge Graph from Phase0 initialized for tools")
    else:
        logging.warning("No Knowledge Graph available from Phase0")
    
    return collected_info

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
    
    results = {
        "pod_name": pod_name,
        "namespace": namespace,
        "volume_path": volume_path,
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
        "phases": {}
    }

    try:
        # Phase 0: Information Collection
        console.print("\n")
        console.print(Panel(
            f"[bold white]Starting troubleshooting for Pod: [green]{namespace}/{pod_name}[/green]\n"
            f"Volume Path: [blue]{volume_path}[/blue]\n"
            f"Start Time: [yellow]{results['start_time']}[/yellow]",
            title="[bold cyan]KUBERNETES VOLUME TROUBLESHOOTING",
            border_style="cyan",
            padding=(1, 2)
        ))
        
        collected_info = await run_information_collection_phase_wrapper(pod_name, namespace, volume_path)
        results["phases"]["phase_0_collection"] = {
            "status": "completed",
            "summary": collected_info.get("knowledge_graph_summary", {}),
            "duration": time.time() - start_time
        }
        
        if "collection_error" in collected_info:
            results["phases"]["phase_0_collection"]["status"] = "failed"
            results["phases"]["phase_0_collection"]["error"] = collected_info["collection_error"]
            return results
        
        # Add Knowledge Graph to collected_info for Plan Phase
        collected_info["knowledge_graph"] = KNOWLEDGE_GRAPH
        
        plan_phase_start = time.time()
        
        # Plan Phase: Generate Investigation Plan
        try:
            # Initialize chat mode
            chat_mode_enabled = CONFIG_DATA.get('chat_mode', {}).get('enabled', True)
            chat_mode_entry_points = CONFIG_DATA.get('chat_mode', {}).get('entry_points', ["plan_phase", "phase1"])
            
            # Create chat mode instance
            chat_mode = ChatMode()
            # Skip chat mode if disabled or plan_phase entry point not enabled
            if not chat_mode_enabled or "plan_phase" not in chat_mode_entry_points:
                investigation_plan, plan_phase_message_list = await run_plan_phase(
                    pod_name, namespace, volume_path, collected_info, CONFIG_DATA
                )
                
                # Print the Investigation Plan to the console
                console.print("\n")
                console.print(Panel(
                    f"[bold white]{investigation_plan}",
                    title="[bold blue]INVESTIGATION PLAN",
                    border_style="blue",
                    padding=(1, 2)
                ))
                
                results["phases"]["plan_phase"] = {
                    "status": "completed",
                    "investigation_plan": investigation_plan[:5000] + "..." if len(investigation_plan) > 5000 else investigation_plan,
                    "duration": time.time() - plan_phase_start
                }
            else:
                # Initialize message list for Plan Phase
                plan_phase_message_list = None
                investigation_plan = None
                exit_flag = False
                
                while True:
                    # Generate or regenerate Investigation Plan
                    investigation_plan, plan_phase_message_list = await run_plan_phase(
                        pod_name, namespace, volume_path, collected_info, CONFIG_DATA, plan_phase_message_list
                    )
                    
                    # Print the Investigation Plan to the console
                    console.print(Panel(
                        f"[bold white]{investigation_plan}",
                        title="[bold blue]INVESTIGATION PLAN",
                        border_style="blue",
                        padding=(1, 2)
                    ))
                    
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
            
            results["phases"]["plan_phase"] = {
                "status": "completed",
                "investigation_plan": investigation_plan[:5000] + "..." if len(investigation_plan) > 5000 else investigation_plan,  # Truncate for summary
                "duration": time.time() - plan_phase_start
            }
            
        except Exception as e:
            error_msg = f"Error during Plan Phase: {str(e)}"
            logging.error(error_msg)
            results["phases"]["plan_phase"] = {
                "status": "failed",
                "error": error_msg,
                "duration": time.time() - plan_phase_start
            }
            # Use a basic fallback plan
            investigation_plan = f"""Investigation Plan:
Target: Pod {namespace}/{pod_name}, Volume Path: {volume_path}
Generated Steps: 3 fallback steps (Plan Phase failed)

Step 1: Get all critical issues | Tool: kg_get_all_issues(severity='primary') | Expected: Critical issues in the system
Step 2: Analyze issue patterns | Tool: kg_analyze_issues() | Expected: Root cause analysis and patterns
Step 3: Get system overview | Tool: kg_get_summary() | Expected: Overall system health statistics

Fallback Steps (if main steps fail):
Step F1: Print Knowledge Graph | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Complete system visualization | Trigger: plan_phase_failed
"""

        phase_1_start = time.time()
        
        # Initialize message list for Phase1
        phase1_message_list = None
        phase1_final_response = None
        exit_flag = False
        skip_phase2 = False
        
        # Skip chat mode if disabled or phase1 entry point not enabled
        if not chat_mode_enabled or "phase1" not in chat_mode_entry_points:
            # Run Phase1 analysis without chat mode
            phase1_final_response, skip_phase2, phase1_message_list = await run_analysis_phase_wrapper(
                pod_name, namespace, volume_path, collected_info, investigation_plan
            )
            
            # Print the Fix Plan to the console
            console.print("\n")
            console.print(Panel(
                f"[bold white]{phase1_final_response}",
                title="[bold blue]FIX PLAN",
                border_style="blue",
                padding=(1, 2)
            ))
            
            results["phases"]["phase_1_analysis"] = {
                "status": "completed",
                "final_response": str(phase1_final_response),
                "duration": time.time() - phase_1_start,
                "skip_phase2": "true" if skip_phase2 else "false"
            }
        else:
            # Use chat mode for Phase1
            while True:
                # Run Phase1 analysis
                phase1_final_response, skip_phase2, phase1_message_list = await run_analysis_phase_wrapper(
                    pod_name, namespace, volume_path, collected_info, investigation_plan, phase1_message_list
                )
                
                # Print the Fix Plan to the console
                console.print(Panel(
                    f"[bold white]{phase1_final_response}",
                    title="[bold blue]FIX PLAN",
                    border_style="blue",
                    padding=(1, 2)
                ))
                
                # Enter chat mode after Phase1
                phase1_message_list, exit_flag = chat_mode.chat_after_phase1(
                    phase1_message_list, phase1_final_response
                )
                
                # Exit if requested
                if exit_flag:
                    console.print("[bold red]Exiting program as requested by user[/bold red]")
                    sys.exit(0)
                
                # Break loop if user approved the plan
                if phase1_message_list[-1]["role"] != "user":
                    break
            
            results["phases"]["phase_1_analysis"] = {
                "status": "completed",
                "final_response": str(phase1_final_response),
                "duration": time.time() - phase_1_start,
                "skip_phase2": "true" if skip_phase2 else "false"
            }
        
        # Only proceed to Phase 2 if not skipped
        remediation_result = None
        if not skip_phase2:
            phase_2_start = time.time()
            
            remediation_result, _ = await run_remediation_phase_wrapper(phase1_final_response, collected_info, phase1_message_list)
            
            results["phases"]["phase_2_remediation"] = {
                "status": "completed",
                "result": remediation_result,
                "duration": time.time() - phase_2_start
            }
        else:
            # Phase 2 skipped - add to results
            console.print("\n")
            console.print(Panel(
                "[bold white]Phase 2 skipped - no remediation needed or manual intervention required",
                title="[bold yellow]PHASE 2: SKIPPED",
                border_style="yellow",
                padding=(1, 2)
            ))
            results["phases"]["phase_2_remediation"] = {
                "status": "skipped",
                "result": "Phase 2 skipped - no remediation needed or manual intervention required",
                "reason": "No issues detected or manual intervention required",
                "duration": 0
            }

        # Final summary
        total_duration = time.time() - start_time
        results["total_duration"] = total_duration
        results["status"] = "completed"

        # Create a rich formatted summary table
        summary_table = Table(
            title="[bold]TROUBLESHOOTING SUMMARY",
            #show_header=True,
            header_style="bold cyan",
            #box=True,
            border_style="blue",
            #safe_box=True  # Explicitly set safe_box to True
        )

        # Add columns
        summary_table.add_column("Phase", style="dim")
        summary_table.add_column("Duration", justify="right")
        summary_table.add_column("Status", justify="center")
        
        # Add rows for each phase
        summary_table.add_row(
            "Phase 0: Information Collection", 
            f"{results['phases']['phase_0_collection']['duration']:.2f}s",
            "[green]Completed"
        )
        # Add Plan Phase row
        plan_phase_status = "[green]Completed" if results["phases"].get("plan_phase", {}).get("status") == "completed" else "[red]Failed"
        plan_phase_duration = results["phases"].get("plan_phase", {}).get("duration", 0)
        summary_table.add_row(
            "Plan Phase: Investigation Plan", 
            f"{plan_phase_duration:.2f}s",
            plan_phase_status
        )
        summary_table.add_row(
            "Phase 1: ReAct Investigation", 
            f"{results['phases']['phase_1_analysis']['duration']:.2f}s",
            "[green]Completed"
        )
        
        # Add Phase 2 row with appropriate status
        if results["phases"]["phase_2_remediation"]["status"] == "completed":
            summary_table.add_row(
                "Phase 2: Remediation", 
                f"{results['phases']['phase_2_remediation']['duration']:.2f}s",
                "[green]Completed"
            )
        else:
            summary_table.add_row(
                "Phase 2: Remediation", 
                "0.00s",
                "[yellow]Skipped"
            )
        summary_table.add_row(
            "Total", 
            f"{total_duration:.2f}s", 
            "[bold green]Completed"
        )
        # Create root cause and resolution panels - ensure strings for content
        # Convert values to strings first to avoid 'bool' has no attribute 'substitute' errors
        root_cause_str = phase1_final_response if phase1_final_response is not None else "Unknown"
        remediation_result_str = remediation_result if remediation_result is not None else "No result"
        root_cause_panel = Panel(
            f"[bold yellow]{root_cause_str}",
            title="[bold red]Root Cause",
            border_style="red",
            padding=(1, 2),
            safe_box=True  # Explicitly set safe_box to True
        )
        resolution_panel = Panel(
            f"[bold green]{remediation_result_str}",
            title="[bold blue]Resolution Status",
            border_style="green",
            padding=(1, 2),
            safe_box=True  # Explicitly set safe_box to True
        )

        try:
            console.print(summary_table)
        except Exception as e:
            console.print(f"Error printing rich summary table: {e}")

        console.print("\n")
        console.print(root_cause_panel)
        console.print("\n")
        console.print(resolution_panel)
        
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
        
        # Initialize MCP adapter
        mcp_adapter = await initialize_mcp_adapter(CONFIG_DATA)
        
        # Validate inputs
        if not args.pod_name or not args.namespace or not args.volume_path:
            logging.error("Pod name, namespace, and volume path are required")
            sys.exit(1)
        llm_provider = CONFIG_DATA.get("llm").get("provider")
        current_api_key = CONFIG_DATA.get("llm").get(llm_provider, "openai").get("api_key")
        if len(current_api_key) < 10:
            logging.error("AI key is empty!")
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
                
        # Clean up MCP connections
        mcp_adapter = get_mcp_adapter()
        if mcp_adapter:
            await mcp_adapter.close()

if __name__ == "__main__":
    asyncio.run(main())
