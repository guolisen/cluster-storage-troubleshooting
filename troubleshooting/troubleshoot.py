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
from phases import run_plan_phase
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
            "knowledge_graph_summary": collection_result.get('context_summary', {}),
            "issues": KNOWLEDGE_GRAPH.issues if KNOWLEDGE_GRAPH else []
        }
        
        # Print Knowledge Graph with rich formatting
        console.print("\n")
        console.print(Panel(
            "[bold white]Building and analyzing knowledge graph...",
            title="[bold cyan]PHASE 0: INFORMATION COLLECTION - KNOWLEDGE GRAPH",
            border_style="cyan",
            padding=(1, 2)
        ))
        
        try:
            # Try to use rich formatting with proper error handling
            formatted_output = KNOWLEDGE_GRAPH.print_graph(use_rich=True)
            
            # Handle different output types
            if formatted_output is None:
                # If there was a silent success (no return value)
                console.print("[green]Knowledge graph built successfully[/green]")
            elif isinstance(formatted_output, str):
                # Regular string output - print as is
                print(formatted_output)
            else:
                # For any other type of output
                console.print("[green]Knowledge graph analysis complete[/green]")
        except Exception as e:
            # Fall back to plain text if rich formatting fails
            logging.error(f"Error in rich formatting, falling back to plain text: {str(e)}")
            try:
                # Try plain text formatting
                formatted_output = KNOWLEDGE_GRAPH.print_graph(use_rich=False)
                print(formatted_output)
            except Exception as e2:
                # Last resort fallback
                logging.error(f"Error in plain text formatting: {str(e2)}")
                print("=" * 80)
                print("KNOWLEDGE GRAPH SUMMARY (FALLBACK FORMAT)")
                print("=" * 80)
                print(f"Total nodes: {KNOWLEDGE_GRAPH.graph.number_of_nodes()}")
                print(f"Total edges: {KNOWLEDGE_GRAPH.graph.number_of_edges()}")
                print(f"Total issues: {len(KNOWLEDGE_GRAPH.issues)}")
        
        console.print("\n")
        
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

async def run_analysis_with_graph(query: str, graph: StateGraph, timeout_seconds: int = 60) -> Tuple[str, str]:
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
        
        # Parse root cause and fix plan with enhanced formatting
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
                
                # Enhanced logging with rich formatting
                console.print("\n")
                root_cause_panel = Panel(
                    f"[bold yellow]{root_cause}[/bold yellow]",
                    title="[bold red]Root Cause Analysis",
                    border_style="red"
                )
                fix_plan_panel = Panel(
                    f"[bold green]{fix_plan}[/bold green]",
                    title="[bold blue]Fix Plan",
                    border_style="blue"
                )
                
                console.print(root_cause_panel)
                console.print(fix_plan_panel)
                
                # Log to file
                file_console.print(root_cause_panel)
                file_console.print(fix_plan_panel)
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

async def run_analysis_phase_with_plan(pod_name: str, namespace: str, volume_path: str, 
                                     collected_info: Dict[str, Any], investigation_plan: str) -> Tuple[str, str]:
    """
    Run Phase 1: ReAct Investigation with pre-collected information as base knowledge
    
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
        graph = create_troubleshooting_graph_with_context(collected_info, phase="phase1", config_data=CONFIG_DATA)
        
        # Updated query for ReAct investigation phase with Investigation Plan
        query = f"""Phase 1 - ReAct Investigation: Execute the Investigation Plan to actively investigate the volume I/O error in pod {pod_name} in namespace {namespace} at volume path {volume_path}.

You have:
1. Pre-collected diagnostic information from Phase 0 as base knowledge
2. A structured Investigation Plan generated by the Plan Phase

INVESTIGATION PLAN TO FOLLOW:
{investigation_plan}

Your task is to:
1. Parse the Investigation Plan and execute each step sequentially
2. Use the specified Knowledge Graph tools first (as outlined in the plan)
3. Validate expected outcomes against actual results from each step
4. If a step fails or provides unexpected results, use the fallback steps provided
5. Use additional ReAct tools for comprehensive root cause analysis and verification
6. Aggregate results from all Investigation Plan steps
7. Generate a comprehensive root cause analysis and fix plan

EXECUTION GUIDELINES:
- Follow the Investigation Plan steps in order
- For each step, use the specified tool with the given arguments
- Compare actual results with expected outcomes
- Log execution details for traceability
- If Knowledge Graph queries provide insufficient data, supplement with additional diagnostic tools
- Include evidence from both the Investigation Plan execution and additional tool usage

INVESTIGATION PLAN EXECUTION LOG:
Execute each step from the Investigation Plan and document:
- Step number and description
- Tool used and arguments
- Actual outcome vs expected outcome
- Any issues or unexpected results
- Follow-up actions taken

After completing the Investigation Plan, provide comprehensive root cause analysis and fix plan.

<<< Note >>>: Please provide the root cause and fix plan analysis within 30 tool calls.
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
        graph = create_troubleshooting_graph_with_context(collected_info, phase="phase2", config_data=CONFIG_DATA)
        
        # Remediation query
        query = f"""Phase 2 - Remediation: Execute the fix plan to resolve the identified issue.

Root Cause: {root_cause}

Fix Plan: {fix_plan}

<<< Note >>>: Please try to fix issue within 30 tool calls.

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
        console.print("\n")
        console.print(Panel(
            f"[bold white]Starting troubleshooting for Pod: [green]{namespace}/{pod_name}[/green]\n"
            f"Volume Path: [blue]{volume_path}[/blue]\n"
            f"Start Time: [yellow]{results['start_time']}[/yellow]",
            title="[bold cyan]KUBERNETES VOLUME TROUBLESHOOTING",
            border_style="cyan",
            padding=(1, 2)
        ))
        
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
        
        # Add Knowledge Graph to collected_info for Plan Phase
        collected_info["knowledge_graph"] = KNOWLEDGE_GRAPH
        
        plan_phase_start = time.time()
        
        # Plan Phase: Generate Investigation Plan
        try:
            investigation_plan = await run_plan_phase(
                pod_name, namespace, volume_path, collected_info, CONFIG_DATA
            )
            
            results["phases"]["plan_phase"] = {
                "status": "completed",
                "investigation_plan": investigation_plan[:500] + "..." if len(investigation_plan) > 500 else investigation_plan,  # Truncate for summary
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
        
        # Phase 1: ReAct Investigation with Investigation Plan
        console.print("\n")
        console.print(Panel(
            "[bold white]Executing Investigation Plan to actively investigate volume I/O issue...",
            title="[bold magenta]PHASE 1: REACT INVESTIGATION WITH PLAN",
            border_style="magenta",
            padding=(1, 2)
        ))
        
        root_cause, fix_plan = await run_analysis_phase_with_plan(
            pod_name, namespace, volume_path, collected_info, investigation_plan
        )
        
        results["phases"]["phase_1_analysis"] = {
            "status": "completed",
            "root_cause": root_cause,
            "fix_plan": fix_plan,
            "duration": time.time() - phase_1_start
        }
        
        phase_2_start = time.time()
        
        # Phase 2: Remediation
        console.print("\n")
        console.print(Panel(
            "[bold white]Executing fix plan to resolve identified issues...",
            title="[bold green]PHASE 2: REMEDIATION",
            border_style="green",
            padding=(1, 2)
        ))
        
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
        
        # Create a rich formatted summary table
        summary_table = Table(
            title="[bold]TROUBLESHOOTING SUMMARY",
            show_header=True,
            header_style="bold cyan",
            box=True,
            border_style="blue",
            safe_box=True  # Explicitly set safe_box to True
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
        summary_table.add_row(
            "Phase 2: Remediation", 
            f"{results['phases']['phase_2_remediation']['duration']:.2f}s",
            "[green]Completed"
        )
        summary_table.add_row(
            "Total", 
            f"{total_duration:.2f}s", 
            "[bold green]Completed"
        )
        
        # Create root cause and resolution panels - ensure strings for content
        # Convert values to strings first to avoid 'bool' has no attribute 'substitute' errors
        root_cause_str = str(root_cause) if root_cause is not None else "Unknown"
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
        
        console.print("\n")
        console.print(summary_table)
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
