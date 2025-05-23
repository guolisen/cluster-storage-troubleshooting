#!/usr/bin/env python3
"""
Comprehensive Kubernetes Volume Troubleshooting Mode

This script orchestrates the comprehensive troubleshooting process:
1. Collects all issues across K8s, Linux, and Storage layers
2. Builds a knowledge graph of issue relationships
3. Identifies root causes using both the graph and LLM analysis
4. Provides a comprehensive fix plan
"""

import os
import sys
import yaml
import json
import asyncio
import logging
import argparse
from typing import Dict, List, Any, Optional, Tuple

from issue_collector import collect_issues
from knowledge_graph import create_knowledge_graph
from troubleshoot import init_chat_model, load_config

class ComprehensiveTroubleshooter:
    """Orchestrates comprehensive troubleshooting with issue collection and knowledge graph"""
    
    def __init__(self, config_data: Dict[str, Any]):
        """
        Initialize the troubleshooter
        
        Args:
            config_data: Configuration data from config.yaml
        """
        self.config_data = config_data
        self.model = init_chat_model(
            self.config_data['llm']['model'],
            api_key=self.config_data['llm']['api_key'],
            base_url=self.config_data['llm']['api_endpoint'],
            temperature=self.config_data['llm']['temperature'],
            max_tokens=self.config_data['llm']['max_tokens']
        )
        self.llm_system_prompt = self._create_system_prompt()
    
    def _create_system_prompt(self) -> str:
        """
        Create the system prompt for the LLM
        
        Returns:
            str: System prompt
        """
        return """You are an AI assistant powering a comprehensive Kubernetes volume troubleshooting system. You are operating in COMPREHENSIVE ANALYSIS MODE.

In this mode:
1. You have been provided with a COMPLETE COLLECTION of all issues detected across:
   - Kubernetes layer (pods, PVCs, PVs, CSI driver)
   - Linux operating system layer (kernel, filesystem, IO)
   - Storage hardware layer (disks, controllers)

2. You have also been provided with a KNOWLEDGE GRAPH that models the relationships between these issues.
   This graph includes:
   - Issues as nodes
   - Causal relationships as directed edges
   - Identified root causes with confidence scores
   - Automated fix plans

3. Your task is to:
   - Review ALL collected issues holistically
   - Analyze the relationships in the knowledge graph
   - Consider the automated root cause analysis
   - Provide your own expert assessment
   - Create a comprehensive fix plan that addresses ALL issues from their root causes
   - Prioritize fixes based on impact and dependencies

4. Return your analysis as a structured JSON with:
   - primary_root_cause: The primary underlying cause
   - contributing_factors: Secondary issues that contributed to the problem (array)
   - all_issues_summary: Brief summary of all detected issues across layers
   - fix_plan: Detailed, ordered steps to resolve all issues from root cause
   - fix_verification: How to verify the fixes worked

Focus on providing a COMPREHENSIVE analysis that explains all observed symptoms and provides a clear path to resolution.
Your analysis should consider all three layers (Kubernetes, Linux, and Storage) and their interactions.
"""
    
    async def collect_and_analyze(self, pod_name: str, namespace: str, volume_path: str) -> Dict[str, Any]:
        """
        Collect all issues and perform comprehensive analysis
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            
        Returns:
            Dict[str, Any]: Comprehensive analysis results
        """
        logging.info(f"Starting comprehensive analysis for pod {namespace}/{pod_name}, volume {volume_path}")
        
        # Step 1: Collect all issues
        issues = await collect_issues(self.config_data, pod_name, namespace, volume_path)
        logging.info(f"Collected {len(issues)} issues across all layers")
        
        # Step 2: Build knowledge graph
        graph = create_knowledge_graph(issues)
        graph_data = json.loads(graph.to_json())
        logging.info(f"Built knowledge graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges")
        
        # Step 3: Get initial root cause from knowledge graph
        primary_root_cause = graph.identify_primary_root_cause()
        logging.info(f"Primary root cause identified by graph: {primary_root_cause['root_cause']}")
        
        # Step 4: Use LLM for comprehensive analysis
        llm_analysis = await self._perform_llm_analysis(pod_name, namespace, volume_path, issues, graph_data)
        logging.info("Completed LLM analysis")
        
        # Step 5: Combine graph and LLM analysis
        comprehensive_result = self._create_comprehensive_report(
            pod_name, namespace, volume_path,
            issues, graph_data, primary_root_cause, llm_analysis
        )
        
        return comprehensive_result
    
    async def _perform_llm_analysis(
        self, pod_name: str, namespace: str, volume_path: str, 
        issues: List[Dict[str, Any]], graph_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to perform comprehensive analysis
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            issues: List of collected issues
            graph_data: Knowledge graph data
            
        Returns:
            Dict[str, Any]: LLM analysis results
        """
        prompt = f"""
Perform a comprehensive analysis of the volume I/O error for pod {pod_name} in namespace {namespace} at volume path {volume_path}.

ISSUES:
{json.dumps(issues, indent=2)}

KNOWLEDGE GRAPH ANALYSIS:
{json.dumps(graph_data, indent=2)}

Based on the provided issues and knowledge graph, provide your comprehensive analysis of the root cause(s) and fix plan.
Return your analysis as a structured JSON with:
- primary_root_cause: The primary underlying cause
- contributing_factors: Secondary issues that contributed to the problem (array)
- all_issues_summary: Brief summary of all detected issues across layers
- fix_plan: Detailed, ordered steps to resolve all issues from root cause
- fix_verification: How to verify the fixes worked
"""
        
        messages = [
            {"role": "system", "content": self.llm_system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        response = self.model.invoke(messages)
        response_content = response.content
        
        # Extract JSON from response
        try:
            # Find JSON in the response (handle potential text before/after)
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_content[json_start:json_end]
                analysis = json.loads(json_str)
                return analysis
            else:
                logging.error("Failed to find JSON in LLM response")
                return {
                    "primary_root_cause": "Error: Failed to parse LLM response",
                    "contributing_factors": [],
                    "all_issues_summary": "Error in LLM analysis",
                    "fix_plan": "Please review the collected issues manually",
                    "fix_verification": "N/A due to analysis error"
                }
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse LLM response as JSON: {e}")
            return {
                "primary_root_cause": "Error: Failed to parse LLM response",
                "contributing_factors": [],
                "all_issues_summary": "Error in LLM analysis",
                "fix_plan": "Please review the collected issues manually",
                "fix_verification": "N/A due to analysis error"
            }
    
    def _create_comprehensive_report(
        self, pod_name: str, namespace: str, volume_path: str,
        issues: List[Dict[str, Any]], graph_data: Dict[str, Any],
        primary_root_cause: Dict[str, Any], llm_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a comprehensive report combining graph and LLM analysis
        
        Args:
            pod_name: Name of the pod with the error
            namespace: Namespace of the pod
            volume_path: Path of the volume with I/O error
            issues: List of collected issues
            graph_data: Knowledge graph data
            primary_root_cause: Primary root cause from knowledge graph
            llm_analysis: LLM analysis results
            
        Returns:
            Dict[str, Any]: Comprehensive report
        """
        # Count issues by layer and severity
        layer_counts = {"kubernetes": 0, "linux": 0, "storage": 0}
        severity_counts = {"critical": 0, "warning": 0, "info": 0}
        
        for issue in issues:
            layer = issue.get("layer", "unknown")
            severity = issue.get("severity", "unknown")
            
            if layer in layer_counts:
                layer_counts[layer] += 1
            
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        # Combine analysis results
        report = {
            "metadata": {
                "pod_name": pod_name,
                "namespace": namespace,
                "volume_path": volume_path,
                "timestamp": asyncio.get_event_loop().time(),
                "issue_counts": {
                    "total": len(issues),
                    "by_layer": layer_counts,
                    "by_severity": severity_counts
                }
            },
            "issues": issues,
            "knowledge_graph": {
                "node_count": len(graph_data.get("nodes", {})),
                "edge_count": len(graph_data.get("edges", [])),
                "root_causes": graph_data.get("root_causes", [])
            },
            "graph_analysis": {
                "primary_root_cause": primary_root_cause.get("root_cause"),
                "confidence": primary_root_cause.get("confidence"),
                "fix_plan": primary_root_cause.get("fix_plan")
            },
            "llm_analysis": llm_analysis,
            "composite_analysis": {
                "primary_root_cause": llm_analysis.get("primary_root_cause") or primary_root_cause.get("root_cause"),
                "contributing_factors": llm_analysis.get("contributing_factors", []),
                "all_issues_summary": llm_analysis.get("all_issues_summary", "Summary not available"),
                "fix_plan": llm_analysis.get("fix_plan") or primary_root_cause.get("fix_plan"),
                "fix_verification": llm_analysis.get("fix_verification", "Verification steps not available")
            }
        }
        
        return report


async def run_comprehensive_mode(pod_name: str, namespace: str, volume_path: str) -> Dict[str, Any]:
    """
    Convenience function to run comprehensive troubleshooting
    
    Args:
        pod_name: Name of the pod with the error
        namespace: Namespace of the pod
        volume_path: Path of the volume with I/O error
        
    Returns:
        Dict[str, Any]: Comprehensive analysis results
    """
    # Load configuration
    config_data = load_config()
    
    # Create troubleshooter
    troubleshooter = ComprehensiveTroubleshooter(config_data)
    
    # Collect and analyze
    return await troubleshooter.collect_and_analyze(pod_name, namespace, volume_path)


def format_report_for_display(report: Dict[str, Any]) -> str:
    """
    Format the comprehensive report for display
    
    Args:
        report: Comprehensive report
        
    Returns:
        str: Formatted report text
    """
    metadata = report.get("metadata", {})
    composite = report.get("composite_analysis", {})
    
    formatted = f"""
===== COMPREHENSIVE VOLUME I/O ERROR ANALYSIS =====

POD: {metadata.get('pod_name')} in namespace {metadata.get('namespace')}
VOLUME PATH: {metadata.get('volume_path')}

ISSUE COUNTS:
- Total: {metadata.get('issue_counts', {}).get('total', 0)}
- Kubernetes layer: {metadata.get('issue_counts', {}).get('by_layer', {}).get('kubernetes', 0)}
- Linux layer: {metadata.get('issue_counts', {}).get('by_layer', {}).get('linux', 0)}
- Storage layer: {metadata.get('issue_counts', {}).get('by_layer', {}).get('storage', 0)}
- Critical issues: {metadata.get('issue_counts', {}).get('by_severity', {}).get('critical', 0)}

PRIMARY ROOT CAUSE:
{composite.get('primary_root_cause', 'Unknown')}

CONTRIBUTING FACTORS:
{chr(10).join('- ' + factor for factor in composite.get('contributing_factors', ['None identified']))}

SUMMARY OF ALL ISSUES:
{composite.get('all_issues_summary', 'Summary not available')}

FIX PLAN:
{composite.get('fix_plan', 'Fix plan not available')}

VERIFICATION:
{composite.get('fix_verification', 'Verification steps not available')}

===== END OF REPORT =====
"""
    return formatted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run comprehensive Kubernetes volume troubleshooting")
    parser.add_argument("pod_name", help="Name of the pod with the error")
    parser.add_argument("namespace", help="Namespace of the pod")
    parser.add_argument("volume_path", help="Path of the volume with I/O error")
    parser.add_argument("--output", "-o", choices=["text", "json"], default="text",
                        help="Output format (text or json)")
    parser.add_argument("--output-file", "-f", help="Output file path (optional)")
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("troubleshoot.log"),
            logging.StreamHandler()
        ]
    )
    
    try:
        # Run comprehensive mode
        report = asyncio.run(run_comprehensive_mode(args.pod_name, args.namespace, args.volume_path))
        
        # Output report
        if args.output == "json":
            output = json.dumps(report, indent=2)
        else:
            output = format_report_for_display(report)
        
        # Write to file or stdout
        if args.output_file:
            with open(args.output_file, "w") as f:
                f.write(output)
            print(f"Report written to {args.output_file}")
        else:
            print(output)
        
        sys.exit(0)
    except Exception as e:
        logging.error(f"Error in comprehensive mode: {str(e)}")
        print(f"Error: {str(e)}")
        sys.exit(1)
