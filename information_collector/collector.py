"""
Main Information Collector

Combines all components to provide the main ComprehensiveInformationCollector class.
"""

import os
import yaml
import logging
import asyncio
import time
import subprocess
import json
import paramiko
from typing import Dict, List, Any, Optional, Set, Tuple
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from .base import InformationCollectorBase
from .volume_discovery import VolumeDiscovery
from .tool_executors import ToolExecutors
from .knowledge_builder import KnowledgeBuilder


class ComprehensiveInformationCollector(VolumeDiscovery, ToolExecutors, KnowledgeBuilder):
    """Enhanced Volume-Focused Information Collector for Phase 0"""
    
    def __init__(self, config_data: Dict[str, Any]):
        """Initialize the Enhanced Information Collector"""
        super().__init__(config_data)
        logging.info("Enhanced Volume-Focused Information Collector initialized")
    
    async def comprehensive_collect(self, 
                                   target_pod: str = None, 
                                   target_namespace: str = None,
                                   target_volume_path: str = None) -> Dict[str, Any]:
        """
        Perform enhanced volume-focused data collection using LangGraph tools
        
        This is the main entry point for Phase 0: Information-Collection Phase
        Executes diagnostic LangGraph tools according to parameter's volume path and pod
        """
        logging.info("=== PHASE 0: INFORMATION-COLLECTION - Starting volume-focused data collection ===")
        start_time = time.time()
        
        try:
            # Step 1: Discover volume dependency chain
            logging.info("Step 1: Discovering volume dependency chain...")
            volume_chain = {}
            if target_pod and target_namespace:
                volume_chain = self._discover_volume_dependency_chain(target_pod, target_namespace)
            
            # Step 2: Execute volume-focused tools based on discovered chain
            logging.info("Step 2: Executing volume-focused diagnostic tools...")
            
            # Pod discovery tools
            if target_pod and target_namespace:
                await self._execute_pod_discovery_tools(target_pod, target_namespace)
            
            # Volume chain discovery tools
            await self._execute_volume_chain_tools(volume_chain)
            
            # CSI Baremetal discovery tools
            await self._execute_csi_baremetal_tools(volume_chain.get('drives', []))
            
            # Node and system discovery tools
            await self._execute_node_system_tools(volume_chain.get('nodes', []))
            
            # Step 3: Build enhanced Knowledge Graph from tool outputs
            logging.info("Step 3: Building Knowledge Graph from tool outputs...")
            self.knowledge_graph = await self._build_knowledge_graph_from_tools(
                target_pod, target_namespace, target_volume_path, volume_chain
            )
            
            # Step 4: Perform analysis
            logging.info("Step 4: Analyzing Knowledge Graph...")
            analysis = self.knowledge_graph.analyze_issues()
            fix_plan = self.knowledge_graph.generate_fix_plan(analysis)
            
            # Step 5: Create enhanced context summary
            context_summary = self._create_enhanced_context_summary(analysis, fix_plan, volume_chain)
            
            # Final collection summary
            collection_time = time.time() - start_time
            
            result = {
                'collected_data': self.collected_data,
                'knowledge_graph': self.knowledge_graph,
                'context_summary': context_summary,
                'volume_chain': volume_chain,
                'collection_metadata': {
                    'collection_time': collection_time,
                    'target_pod': target_pod,
                    'target_namespace': target_namespace,
                    'target_volume_path': target_volume_path,
                    'tools_executed': len(self.collected_data['tool_outputs']),
                    'total_errors': len(self.collected_data['errors']),
                    'interactive_mode': self.interactive_mode
                }
            }
            
            logging.info(f"=== PHASE 0: INFORMATION-COLLECTION completed in {collection_time:.2f} seconds ===")
            logging.info(f"Executed {len(self.collected_data['tool_outputs'])} tools, discovered {len(volume_chain.get('pvcs', []))} PVCs")
            return result
            
        except Exception as e:
            error_msg = f"Error during volume-focused collection: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
            raise
