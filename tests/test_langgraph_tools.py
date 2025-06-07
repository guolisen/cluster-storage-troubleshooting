#!/usr/bin/env python3
"""
LangGraph Tools Test Script

This script tests all langgraph tools in the cluster-storage-troubleshooting system
and reports which tools have issues.
"""

import os
import sys
import yaml
import json
import asyncio
import logging
from typing import Dict, List, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Import necessary components
from troubleshooting.graph import create_troubleshooting_graph_with_context
from knowledge_graph.knowledge_graph import KnowledgeGraph
from tools.core.knowledge_graph import initialize_knowledge_graph

# Import all tool modules
from tools.registry import (
    get_all_tools,
    get_knowledge_graph_tools,
    get_kubernetes_tools,
    get_diagnostic_tools,
    get_testing_tools,
    get_phase1_tools,
    get_phase2_tools
)

# Initialize rich console for nice output
console = Console()

#os.environ['LANGCHAIN_TRACING_V2'] = "true"   
#os.environ['LANGCHAIN_ENDPOINT'] = "https://api.smith.langchain.com"   
#os.environ['LANGCHAIN_API_KEY'] = "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"   
#os.environ['LANGCHAIN_PROJECT'] = "pr-silver-bank-1"

def load_config():
    """Load configuration from config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Ensure the config has the necessary fields for testing
        if 'llm' not in config:
            config['llm'] = {
                'model': 'gpt-3.5-turbo',
                'api_key': 'dummy-key-for-testing',
                'api_endpoint': 'https://api.openai.com/v1',
                'temperature': 0.1,
                'max_tokens': 1000
            }
        
        if 'logging' not in config:
            config['logging'] = {
                'file': 'troubleshoot.log',
                'stdout': True
            }
        
        if 'troubleshoot' not in config:
            config['troubleshoot'] = {
                'timeout_seconds': 300
            }
            
        return config
    except Exception as e:
        console.print(f"[bold red]Failed to load configuration:[/bold red] {str(e)}")
        console.print("[yellow]Using default test configuration...[/yellow]")
        
        # Return a default test configuration
        return {
            'llm': {
                'model': 'gpt-3.5-turbo',
                'api_key': 'dummy-key-for-testing',
                'api_endpoint': 'https://api.openai.com/v1',
                'temperature': 0.1,
                'max_tokens': 1000
            },
            'logging': {
                'file': 'troubleshoot.log',
                'stdout': True
            },
            'troubleshoot': {
                'timeout_seconds': 300
            }
        }

async def test_tool(tool_func, test_args=None, config_data=None):
    """Test a single tool function with optional arguments"""
    # Handle both regular functions and StructuredTool objects
    if hasattr(tool_func, 'name'):
        # For StructuredTool objects from langchain
        tool_name = tool_func.name
    elif hasattr(tool_func, '__name__'):
        # For regular Python functions
        tool_name = tool_func.__name__
    else:
        # Fallback
        tool_name = str(tool_func)
    
    try:
        # Ensure we have a config object for StructuredTool._run()
        if config_data is None:
            config_data = {
                "llm": {
                    "model": "gpt-3.5-turbo",
                    "api_key": "dummy-key-for-testing",
                    "api_endpoint": "https://api.openai.com/v1",
                    "temperature": 0.1,
                    "max_tokens": 1000
                },
                "logging": {
                    "file": "troubleshoot.log",
                    "stdout": True
                },
                "troubleshoot": {
                    "timeout_seconds": 300
                }
            }
        
        # Prepare arguments with config
        if test_args is None:
            args_with_config = {"config": config_data}
        else:
            args_with_config = {**test_args, "config": config_data}
        
        result = None
        if hasattr(tool_func, '_run'):
            # For StructuredTool objects
            if test_args is None:
                # Call with only config
                if asyncio.iscoroutinefunction(tool_func._run):
                    result = await tool_func._run(config=config_data)
                else:
                    result = tool_func._run(config=config_data)
            else:
                # Call with test args and config
                if asyncio.iscoroutinefunction(tool_func._run):
                    result = await tool_func._run(**test_args, config=config_data)
                else:
                    result = tool_func._run(**test_args, config=config_data)
        else:
            # For regular functions
            if test_args is None:
                # Call with no args
                if asyncio.iscoroutinefunction(tool_func):
                    result = await tool_func()
                else:
                    result = tool_func()
            else:
                # Call with test args
                if asyncio.iscoroutinefunction(tool_func):
                    result = await tool_func(**test_args)
                else:
                    result = tool_func(**test_args)
        
        return {
            "name": tool_name,
            "status": "success",
            "result": result
        }
    except Exception as e:
        return {
            "name": tool_name,
            "status": "error",
            "error": str(e)
        }

async def test_knowledge_graph_tools(kg, config_data=None):
    """Test all Knowledge Graph tools"""
    console.print(Panel("Testing Knowledge Graph Tools", style="bold blue"))
    
    # Initialize test arguments for each KG tool
    test_args = {
        "kg_get_entity_info": {"entity_type": "Pod", "entity_id": "gnode:Pod:default/test-pod-1-0"},
        "kg_get_related_entities": {"entity_type": "Pod", "entity_id": "gnode:Pod:default/test-pod-1-0"},
        "kg_get_all_issues": {},
        "kg_find_path": {
            "source_entity_type": "Pod", 
            "source_entity_id": "gnode:Pod:default/test-pod-1-0",
            "target_entity_type": "Node", 
            "target_entity_id": "gnode:Node:kind-control-plane"
        },
        "kg_get_summary": None,
        "kg_analyze_issues": None,
        "kg_print_graph": {"include_details": True, "include_issues": True}
    }
    
    results = []
    for tool in get_knowledge_graph_tools():
        # Get tool name safely
        if hasattr(tool, 'name'):
            tool_name = tool.name
        elif hasattr(tool, '__name__'):
            tool_name = tool.__name__
        else:
            tool_name = str(tool)
            
        args = test_args.get(tool_name, {})
        result = await test_tool(tool, args, config_data)
        results.append(result)
        
        # Print result
        status_color = "green" if result["status"] == "success" else "red"
        console.print(f"[bold]{result['name']}[/bold]: [{status_color}]{result['status']}[/{status_color}]")
        console.print(f"Result: {result.get('result', 'No result')[:500]}")
    
    return results

async def test_kubernetes_tools(config_data=None):
    """Test all Kubernetes tools"""
    console.print(Panel("Testing Kubernetes Tools", style="bold blue"))
    
    # Initialize test arguments for each Kubernetes tool
    test_args = {
        "kubectl_get": {"resource_type": "pods", "namespace": "default"},
        "kubectl_describe": {"resource_type": "pod", "resource_name": "test-pod-1-0", "namespace": "default"},
        "kubectl_apply": {"yaml_content": "apiVersion: v1\nkind: Pod\nmetadata:\n  name: test-pod-1-0\nspec:\n  containers:\n  - name: test-container\n    image: nginx"},
        "kubectl_delete": {"resource_type": "pod", "resource_name": "test-pod-1-0", "namespace": "default"},
        "kubectl_exec": {"pod_name": "test-pod-1-0", "namespace": "default", "command": "ls -la"},
        "kubectl_logs": {"pod_name": "test-pod-1-0", "namespace": "default"},
        "kubectl_get_drive": {},
        "kubectl_get_csibmnode": {},
        "kubectl_get_availablecapacity": {},
        "kubectl_get_logicalvolumegroup": {},
        "kubectl_get_storageclass": {},
        "kubectl_get_csidrivers": {}
    }
    
    results = []
    for tool in get_kubernetes_tools():
        # Get tool name safely
        if hasattr(tool, 'name'):
            tool_name = tool.name
        elif hasattr(tool, '__name__'):
            tool_name = tool.__name__
        else:
            tool_name = str(tool)
            
        args = test_args.get(tool_name, {})
        result = await test_tool(tool, args, config_data)
        results.append(result)
        
        # Print result
        status_color = "green" if result["status"] == "success" else "red"
        console.print(f"[bold]{result['name']}[/bold]: [{status_color}]{result['status']}[/{status_color}]")
        console.print(f"Result: {result.get('result', 'No result')[:500]}")
    
    return results

async def test_diagnostic_tools(config_data=None):
    """Test all diagnostic tools"""
    console.print(Panel("Testing Diagnostic Tools", style="bold blue"))
    
    # Initialize test arguments for each diagnostic tool
    test_args = {
        "smartctl_check": {"node_name": "kind-control-plane", "device_path": "/dev/sda"},
        "fio_performance_test": {"node_name": "kind-control-plane", "device_path": "/dev/sda"},
        "fsck_check": {"node_name": "kind-control-plane", "device_path": "/dev/sda"},
        "xfs_repair_check": {"node_name": "kind-control-plane", "device_path": "/dev/sda"},
        "ssh_execute": {"node_name": "kind-control-plane", "command": "ls -la"},
        "df_command": {"path": "/tmp", "options": "-h"},
        "lsblk_command": {"options": "-f"},
        "mount_command": {"options": "-t xfs"},
        "dmesg_command": {"options": "-T"},
        "journalctl_command": {"options": "-u kubelet"},
        # New disk tools
        "detect_disk_jitter": {"duration_minutes": 1, "check_interval_seconds": 10, "node_name": "kind-control-plane"},
        "run_disk_readonly_test": {"node_name": "kind-control-plane", "device_path": "/dev/sda", "duration_minutes": 1},
        "test_disk_io_performance": {"node_name": "kind-control-plane", "device_path": "/dev/sda", "duration_seconds": 10},
        "check_disk_health": {"node_name": "kind-control-plane", "device_path": "/dev/sda"},
        "analyze_disk_space_usage": {"node_name": "kind-control-plane", "mount_path": "/"},
        "scan_disk_error_logs": {"node_name": "kind-control-plane", "hours_back": 1}
    }
    
    results = []
    for tool in get_diagnostic_tools():
        # Get tool name safely
        if hasattr(tool, 'name'):
            tool_name = tool.name
        elif hasattr(tool, '__name__'):
            tool_name = tool.__name__
        else:
            tool_name = str(tool)
            
        args = test_args.get(tool_name, {})
        result = await test_tool(tool, args, config_data)
        results.append(result)
        
        # Print result
        status_color = "green" if result["status"] == "success" else "red"
        console.print(f"[bold]{result['name']}[/bold]: [{status_color}]{result['status']}[/{status_color}]")
        console.print(f"Result: {result.get('result', 'No result')[:500]}")
    
    return results

async def test_testing_tools(config_data=None):
    """Test all testing tools"""
    console.print(Panel("Testing Testing Tools", style="bold blue"))
    
    # Initialize test arguments for each testing tool
    test_args = {
        "create_test_pod": {"pod_name": "test-pod-1-0", "namespace": "default"},
        "create_test_pvc": {"pvc_name": "www-1-test-pod-1-0", "namespace": "default", "size": "1Gi"},
        "create_test_storage_class": {"sc_name": "test-sc"},
        "run_volume_io_test": {"pod_name": "test-pod-1-0", "namespace": "default", "mount_path": "/log"},
        "validate_volume_mount": {"pod_name": "test-pod-1-0", "namespace": "default", "mount_path": "/log"},
        "test_volume_permissions": {"pod_name": "test-pod-1-0", "namespace": "default", "mount_path": "/log"},
        "run_volume_stress_test": {"pod_name": "test-pod-1-0", "namespace": "default", "mount_path": "/log"},
        "cleanup_test_resources": {"namespace": "default"},
        "list_test_resources": {"namespace": "default"},
        "cleanup_specific_test_pod": {"pod_name": "test-pod-1-0", "namespace": "default"},
        "cleanup_orphaned_pvs": {},
        "force_cleanup_stuck_resources": {"namespace": "default"},
        # Additional volume testing tools
        "verify_volume_mount": {"pod_name": "test-pod-1-0", "namespace": "default", "mount_path": "/log"},
        "test_volume_io_performance": {"pod_name": "test-pod-1-0", "namespace": "default", "mount_path": "/log"},
        "monitor_volume_latency": {"pod_name": "test-pod-1-0", "namespace": "default", "mount_path": "/log", "duration_minutes": 1},
        "check_pod_volume_filesystem": {"pod_name": "test-pod-1-0", "namespace": "default", "mount_path": "/log"},
        "analyze_volume_space_usage": {"pod_name": "test-pod-1-0", "namespace": "default", "mount_path": "/log"},
        "check_volume_data_integrity": {"pod_name": "test-pod-1-0", "namespace": "default", "mount_path": "/log"}
    }
    
    results = []
    for tool in get_testing_tools():
        # Get tool name safely
        if hasattr(tool, 'name'):
            tool_name = tool.name
        elif hasattr(tool, '__name__'):
            tool_name = tool.__name__
        else:
            tool_name = str(tool)
            
        args = test_args.get(tool_name, {})
        result = await test_tool(tool, args, config_data)
        results.append(result)
        
        # Print result
        status_color = "green" if result["status"] == "success" else "red"
        console.print(f"[bold]{result['name']}[/bold]: [{status_color}]{result['status']}[/{status_color}]")
        console.print(f"Result: {result.get('result', 'No result')[:500]}")
    
    return results

async def test_langgraph_components(config_data):
    """Test LangGraph components"""
    console.print(Panel("Testing LangGraph Components", style="bold blue"))
    
    try:
        # Create a minimal test context
        collected_info = {
            "pod_info": {"test-pod-1-0": {"status": "Running"}},
            "pvc_info": {"www-1-test-pod-1-0": {"status": "Bound"}},
            "pv_info": {"test-pv": {"status": "Bound"}},
            "node_info": {"kind-control-plane": {"status": "Ready"}},
            "csi_driver_info": {},
            "system_info": {},
            "knowledge_graph_summary": {},
            "issues": []
        }
        
        # Test Phase 1 graph
        phase1_graph = create_troubleshooting_graph_with_context(
            collected_info=collected_info,
            phase="phase1",
            config_data=config_data
        )
        
        console.print("[bold]Phase 1 Graph Creation[/bold]: [green]success[/green]")
        
        # Test Phase 2 graph
        phase2_graph = create_troubleshooting_graph_with_context(
            collected_info=collected_info,
            phase="phase2",
            config_data=config_data
        )
        
        console.print("[bold]Phase 2 Graph Creation[/bold]: [green]success[/green]")
        
        return {
            "phase1_graph": "success",
            "phase2_graph": "success"
        }
        
    except Exception as e:
        console.print(f"[bold]LangGraph Component Test[/bold]: [red]error[/red] - {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

def generate_summary_report(all_results):
    """Generate a summary report of all test results"""
    console.print(Panel("Test Results Summary", style="bold green"))
    
    # Check if we have any results
    if not all_results:
        console.print("[bold red]No test results available![/bold red]")
        return
    
    # Create a table for the summary
    table = Table(title="Tool Test Results")
    table.add_column("Category", style="cyan")
    table.add_column("Total Tools", style="magenta")
    table.add_column("Success", style="green")
    table.add_column("Failed", style="red")
    table.add_column("Success Rate", style="yellow")
    
    # Add rows for each category
    categories = all_results.keys()
    for category in categories:
        if category == "langgraph":
            continue  # Skip langgraph components from the tool count
        
        # Check if the category has results
        if category not in all_results or not all_results[category]:
            continue
            
        results = all_results[category]
        total = len(results)
        success = sum(1 for r in results if r["status"] == "success")
        failed = total - success
        success_rate = f"{(success/total)*100:.1f}%" if total > 0 else "N/A"
        
        table.add_row(
            category,
            str(total),
            str(success),
            str(failed),
            success_rate
        )
    
    # Add a total row
    all_tools = []
    for category in categories:
        if category != "langgraph":
            all_tools.extend(all_results[category])
    
    total = len(all_tools)
    success = sum(1 for r in all_tools if r["status"] == "success")
    failed = total - success
    success_rate = f"{(success/total)*100:.1f}%" if total > 0 else "N/A"
    
    table.add_row(
        "TOTAL",
        str(total),
        str(success),
        str(failed),
        success_rate,
        style="bold"
    )
    
    console.print(table)
    
    # List failed tools
    if failed > 0:
        console.print(Panel("Failed Tools", style="bold red"))
        for tool in all_tools:
            if tool["status"] == "error":
                console.print(f"[bold]{tool['name']}[/bold]: {tool.get('error', 'Unknown error')}")

async def main():
    """Main function to run all tests"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Test all langgraph tools in the system")
    parser.add_argument("--output", "-o", default="tool_test_results.json", help="Output file path for test results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--category", "-c", help="Test only a specific category (knowledge_graph, kubernetes, diagnostic, testing)")
    args = parser.parse_args()
    
    # Set up output file path
    output_file = args.output
    
    # Configure verbosity
    verbose = args.verbose
    
    console.print(Panel(
        "[bold]LangGraph Tools Test Script[/bold]\n\n"
        "This script tests all langgraph tools in the cluster-storage-troubleshooting system\n"
        "and reports which tools have issues.",
        style="bold green"
    ))
    
    if verbose:
        console.print("[yellow]Verbose mode enabled[/yellow]")
    
    # Load configuration
    config_data = load_config()
    
    # Initialize knowledge graph
    kg = KnowledgeGraph()
    initialize_knowledge_graph(kg)
    
    # Add some test data to the knowledge graph
    pod_id = kg.add_gnode_pod("test-pod-1-0", "default", status="Running")
    node_id = kg.add_gnode_node("kind-control-plane", status="Ready")
    pvc_id = kg.add_gnode_pvc("www-1-test-pod-1-0", "default", status="Bound")
    pv_id = kg.add_gnode_pv("test-pv", status="Bound")
    
    # Add relationships
    kg.add_relationship(pod_id, node_id, "runs_on")
    kg.add_relationship(pod_id, pvc_id, "uses")
    kg.add_relationship(pvc_id, pv_id, "bound_to")
    
    # Add some test issues
    kg.add_issue(pod_id, "pod_crash", "Pod is crashing", severity="medium")
    kg.add_issue(node_id, "disk_pressure", "Node is experiencing disk pressure", severity="high")
    
    # Run tests based on category selection
    all_results = {}
    category = args.category
    
    try:
        # Test LangGraph components (always test these)
        all_results["langgraph"] = await test_langgraph_components(config_data)
        
        # Test specific category or all categories
        if category is None or category == "all":
            console.print("[yellow]Testing all tool categories...[/yellow]")
            # Test Knowledge Graph tools
            #all_results["knowledge_graph"] = await test_knowledge_graph_tools(kg, config_data)
            
            # Test Kubernetes tools
            #all_results["kubernetes"] = await test_kubernetes_tools(config_data)
            
            # Test Diagnostic tools
            #all_results["diagnostic"] = await test_diagnostic_tools(config_data)
            
            # Test Testing tools
            all_results["testing"] = await test_testing_tools(config_data)
        elif category == "knowledge_graph":
            console.print("[yellow]Testing only Knowledge Graph tools...[/yellow]")
            all_results["knowledge_graph"] = await test_knowledge_graph_tools(kg, config_data)
        elif category == "kubernetes":
            console.print("[yellow]Testing only Kubernetes tools...[/yellow]")
            all_results["kubernetes"] = await test_kubernetes_tools(config_data)
        elif category == "diagnostic":
            console.print("[yellow]Testing only Diagnostic tools...[/yellow]")
            all_results["diagnostic"] = await test_diagnostic_tools(config_data)
        elif category == "testing":
            console.print("[yellow]Testing only Testing tools...[/yellow]")
            all_results["testing"] = await test_testing_tools(config_data)
        else:
            console.print(f"[bold red]Unknown category: {category}[/bold red]")
            console.print("[yellow]Available categories: knowledge_graph, kubernetes, diagnostic, testing[/yellow]")
            return
    except Exception as e:
        console.print(f"[bold red]Error during test execution:[/bold red] {str(e)}")
        console.print("[yellow]Continuing with available results...[/yellow]")
    
    # Generate summary report
    generate_summary_report(all_results)
    
    # Save results to file
    try:
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        console.print(Panel(f"Test results saved to {output_file}", style="bold blue"))
    except Exception as e:
        console.print(f"[bold red]Error saving results to file:[/bold red] {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
