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
from troubleshooting.graph import create_troubleshooting_graph_with_context
from information_collector import ComprehensiveInformationCollector
from phases import (
    run_information_collection_phase,
    run_plan_phase,
    run_analysis_phase_with_plan,
    run_remediation_phase
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
    
    return collected_info

async def run_analysis_with_graph(query: str, graph: StateGraph, timeout_seconds: int = 60) -> str:
    """
    Run an analysis using the provided LangGraph StateGraph with enhanced progress tracking
    
    Args:
        query: The initial query to send to the graph
        graph: LangGraph StateGraph to use
        timeout_seconds: Maximum execution time in seconds
        
    Returns:
        Tuple[str, str]: Root cause and fix plan
    """
    try:
        formatted_query = {"messages": [{"role": "user", "content": query}]}
        
        # First show the analysis panel
        console.print("\n")
        console.print(Panel(
            "[yellow]Starting analysis with LangGraph...\nThis may take a few minutes to complete.", 
            title="[bold blue]Analysis Phase",
            border_style="blue"
        ))
        
        # Run graph with timeout
        try:
            response = await asyncio.wait_for(
                graph.ainvoke(formatted_query, config={"recursion_limit": 100}),
                timeout=timeout_seconds
            )
            console.print("[green]Analysis complete![/green]")
        except asyncio.TimeoutError:
            console.print("[red]Analysis timed out![/red]")
            raise
        except Exception as e:
            console.print(f"[red]Analysis failed: {str(e)}[/red]")
            raise
        
        # Extract analysis results
        if response["messages"]:
            if isinstance(response["messages"], list):
                final_message = response["messages"][-1].content
            else:
                final_message = response["messages"].content
        else:
            final_message = "Failed to generate analysis results"
        
        return final_message
    except Exception as e:
        logging.error(f"Error in run_analysis_with_graph: {str(e)}")
        return "Error in analysis", str(e)

async def run_analysis_phase_wrapper(pod_name: str, namespace: str, volume_path: str, 
                                  collected_info: Dict[str, Any], investigation_plan: str) -> Tuple[str, bool]:
    """
    Wrapper for Phase 1: ReAct Investigation from phases module
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        collected_info: Pre-collected diagnostic information from Phase 0
        investigation_plan: Investigation Plan generated by the Plan Phase
        
    Returns:
        Tuple[str, bool]: (Analysis result, Skip Phase2 flag)
    """
    global CONFIG_DATA
    
    # Call the actual implementation from phases module
    return await run_analysis_phase_with_plan(
        pod_name, namespace, volume_path, collected_info, investigation_plan, CONFIG_DATA
    )

async def run_remediation_phase_wrapper(phase1_final_response: str, collected_info: Dict[str, Any]) -> str:
    """
    Wrapper for Phase 2: Remediation from phases module
    
    Args:
        phase1_final_response: Response from Phase 1 containing root cause and fix plan
        collected_info: Pre-collected diagnostic information from Phase 0
        
    Returns:
        str: Remediation result
    """
    global CONFIG_DATA
    
    # Call the actual implementation from phases module
    return await run_remediation_phase(phase1_final_response, collected_info, CONFIG_DATA)

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
            investigation_plan = await run_plan_phase(
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

Step 1: Get all critical issues | Tool: kg_get_all_issues(severity='critical') | Expected: Critical issues in the system
Step 2: Analyze issue patterns | Tool: kg_analyze_issues() | Expected: Root cause analysis and patterns
Step 3: Get system overview | Tool: kg_get_summary() | Expected: Overall system health statistics

Fallback Steps (if main steps fail):
Step F1: Print Knowledge Graph | Tool: kg_print_graph(include_details=True, include_issues=True) | Expected: Complete system visualization | Trigger: plan_phase_failed
"""
        
        phase_1_start = time.time()
        
        phase1_final_response, skip_phase2 = await run_analysis_phase_wrapper(
            pod_name, namespace, volume_path, collected_info, investigation_plan
        )
        
        results["phases"]["phase_1_analysis"] = {
            "status": "completed",
            "final_response": str(phase1_final_response),
            "duration": time.time() - phase_1_start,
            "skip_phase2": "false" if skip_phase2 else "true"
        }
        # Only proceed to Phase 2 if not skipped
        if not skip_phase2:
            phase_2_start = time.time()
            
            remediation_result = await run_remediation_phase_wrapper(phase1_final_response, collected_info)
            
            results["phases"]["phase_2_remediation"] = {
                "status": "completed",
                "result": str(remediation_result),
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
        root_cause_str = str(phase1_final_response) if phase1_final_response is not None else "Unknown"
        remediation_result_str = str(remediation_result) if remediation_result is not None else "No result"
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
