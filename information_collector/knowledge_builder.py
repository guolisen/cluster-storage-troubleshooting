"""
Knowledge Graph Builder

Contains methods for building enhanced Knowledge Graph from tool outputs.
"""

import logging
from typing import Dict, List, Any
from .base import InformationCollectorBase
from .metadata_parsers import MetadataParsers


class KnowledgeBuilder(MetadataParsers):
    """Knowledge Graph construction from tool outputs with rich CSI metadata"""
    
    async def _build_knowledge_graph_from_tools(self, 
                                               target_pod: str = None, 
                                               target_namespace: str = None,
                                               target_volume_path: str = None,
                                               volume_chain: Dict[str, List[str]] = None) -> 'KnowledgeGraph':
        """Build enhanced Knowledge Graph from tool outputs with rich CSI metadata"""
        logging.info("Building Knowledge Graph from tool outputs with CSI metadata...")
        
        # Reset Knowledge Graph
        self.knowledge_graph = self.knowledge_graph.__class__()
        
        # Process target pod first if specified
        if target_pod and target_namespace:
            # Extract pod metadata
            pod_metadata = self._parse_pod_metadata(target_pod, target_namespace)
            pod_id = self.knowledge_graph.add_pod(
                target_pod, target_namespace,
                volume_path=target_volume_path or '',
                is_target=True,
                **pod_metadata
            )
            
            # Add pod logs as issues if they contain errors
            pod_logs = self.collected_data.get('logs', {}).get('target_pod_logs', '')
            if pod_logs and ('error' in pod_logs.lower() or 'failed' in pod_logs.lower()):
                self.knowledge_graph.add_issue(
                    pod_id,
                    "pod_error",
                    "Pod logs contain error messages",
                    "medium"
                )
        
        # Process volume chain entities with enhanced metadata
        if volume_chain:
            # Add PVCs with metadata
            for pvc_key in volume_chain.get('pvcs', []):
                namespace, name = pvc_key.split('/', 1)
                pvc_metadata = self._parse_pvc_metadata(name, namespace)
                pvc_id = self.knowledge_graph.add_pvc(name, namespace, **pvc_metadata)
                
                # Link to target pod if it exists
                if target_pod and target_namespace:
                    pod_id = f"Pod:{target_namespace}/{target_pod}"
                    self.knowledge_graph.add_relationship(pod_id, pvc_id, "uses")
            
            # Add PVs with metadata
            for pv_name in volume_chain.get('pvs', []):
                pv_metadata = self._parse_pv_metadata(pv_name)
                pv_id = self.knowledge_graph.add_pv(pv_name, **pv_metadata)
                
                # Link to PVCs
                for pvc_key in volume_chain.get('pvcs', []):
                    pvc_id = f"PVC:{pvc_key}"
                    self.knowledge_graph.add_relationship(pvc_id, pv_id, "bound_to")
            
            # Add drives with comprehensive CSI metadata
            for drive_uuid in volume_chain.get('drives', []):
                drive_info = self._parse_comprehensive_drive_info(drive_uuid)
                drive_id = self.knowledge_graph.add_drive(drive_uuid, **drive_info)
                
                # Add issues for unhealthy drives
                if drive_info.get('Health') in ['SUSPECT', 'BAD']:
                    self.knowledge_graph.add_issue(
                        drive_id,
                        "disk_health",
                        f"Drive health issue: {drive_info.get('Health')}",
                        "critical" if drive_info.get('Health') == 'BAD' else "high"
                    )
                
                # Add issues for system drives under high usage
                if drive_info.get('IsSystem') and drive_info.get('Usage') == 'IN_USE':
                    self.knowledge_graph.add_issue(
                        drive_id,
                        "system_drive_usage",
                        "System drive is in heavy use",
                        "medium"
                    )
                
                # Link to PVs
                for pv_name in volume_chain.get('pvs', []):
                    pv_id = f"PV:{pv_name}"
                    self.knowledge_graph.add_relationship(pv_id, drive_id, "maps_to")
            
            # Add nodes with enhanced metadata
            for node_name in volume_chain.get('nodes', []):
                node_info = self._parse_comprehensive_node_info(node_name)
                node_id = self.knowledge_graph.add_node(node_name, **node_info)
                
                # Add issues for unhealthy nodes
                if not node_info.get('Ready') or node_info.get('DiskPressure'):
                    self.knowledge_graph.add_issue(
                        node_id,
                        "node_health",
                        f"Node issues: Ready={node_info.get('Ready')}, DiskPressure={node_info.get('DiskPressure')}",
                        "high" if not node_info.get('Ready') else "medium"
                    )
                
                # Link drives to nodes
                for drive_uuid in volume_chain.get('drives', []):
                    drive_id = f"Drive:{drive_uuid}"
                    self.knowledge_graph.add_relationship(drive_id, node_id, "located_on")
        
        # Add CSI Baremetal specific entities
        await self._add_csi_baremetal_entities()
        
        # Add log-based issues to knowledge graph
        await self._add_log_based_issues()
        
        # Log final summary
        summary = self.knowledge_graph.get_summary()
        logging.info(f"Enhanced Knowledge Graph built: {summary['total_nodes']} nodes, "
                    f"{summary['total_edges']} edges, {summary['total_issues']} issues")
        
        return self.knowledge_graph
    
    async def _add_csi_baremetal_entities(self):
        """Add CSI Baremetal specific entities to knowledge graph"""
        try:
            # Add logical volume groups
            lvg_output = self.collected_data.get('csi_baremetal', {}).get('lvgs', '')
            if lvg_output:
                self._process_lvg_entities(lvg_output)
            
            # Add available capacity entities
            ac_output = self.collected_data.get('csi_baremetal', {}).get('available_capacity', '')
            if ac_output:
                self._process_available_capacity_entities(ac_output)
            
            # Add CSI Baremetal node entities
            csibm_nodes_output = self.collected_data.get('csi_baremetal', {}).get('nodes', '')
            if csibm_nodes_output:
                self._process_csibm_node_entities(csibm_nodes_output)
        
        except Exception as e:
            error_msg = f"Error adding CSI Baremetal entities: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
    
    def _process_lvg_entities(self, lvg_output: str):
        """Process logical volume group entities"""
        try:
            lines = lvg_output.split('\n')
            current_lvg = None
            
            for line in lines:
                if 'name:' in line and 'metadata:' not in line:
                    current_lvg = line.split('name:')[-1].strip()
                elif current_lvg and 'health:' in line:
                    health = line.split('health:')[-1].strip()
                    
                    # Add LVG to knowledge graph
                    lvg_id = f"LVG:{current_lvg}"
                    
                    # Add issues for unhealthy LVGs
                    if health not in ['GOOD', 'HEALTHY']:
                        self.knowledge_graph.add_issue(
                            lvg_id,
                            "lvg_health",
                            f"LVG health issue: {health}",
                            "high"
                        )
        except Exception as e:
            logging.warning(f"Error processing LVG entities: {e}")
    
    def _process_available_capacity_entities(self, ac_output: str):
        """Process available capacity entities"""
        try:
            lines = ac_output.split('\n')
            
            for line in lines:
                if 'name:' in line and 'metadata:' not in line:
                    ac_name = line.split('name:')[-1].strip()
                    ac_id = f"AC:{ac_name}"
                    # Available capacity entities are informational
                    
        except Exception as e:
            logging.warning(f"Error processing Available Capacity entities: {e}")
    
    def _process_csibm_node_entities(self, csibm_nodes_output: str):
        """Process CSI Baremetal node entities"""
        try:
            lines = csibm_nodes_output.split('\n')
            
            for line in lines:
                if 'name:' in line and 'metadata:' not in line:
                    csibm_node_name = line.split('name:')[-1].strip()
                    csibm_node_id = f"CSIBMNode:{csibm_node_name}"
                    # CSI Baremetal nodes provide additional node context
                    
        except Exception as e:
            logging.warning(f"Error processing CSI Baremetal node entities: {e}")
    
    async def _add_log_based_issues(self):
        """Add log-based issues to the knowledge graph"""
        try:
            logging.info("Analyzing logs for storage-related issues...")
            
            # Parse dmesg issues
            dmesg_issues = self._parse_dmesg_issues()
            for issue in dmesg_issues:
                # Add system-level issues to a general system entity
                system_id = "System:kernel"
                self.knowledge_graph.add_issue(
                    system_id,
                    issue['type'],
                    issue['description'],
                    issue['severity']
                )
            
            # Parse journal log issues
            journal_issues = self._parse_journal_issues()
            for issue in journal_issues:
                # Determine entity based on issue source
                if issue['source'] == 'journal_kubelet':
                    entity_id = "System:kubelet"
                elif issue['source'] == 'journal_boot':
                    entity_id = "System:boot"
                else:
                    entity_id = "System:storage_services"
                
                self.knowledge_graph.add_issue(
                    entity_id,
                    issue['type'],
                    issue['description'],
                    issue['severity']
                )
            
            total_log_issues = len(dmesg_issues) + len(journal_issues)
            logging.info(f"Added {total_log_issues} log-based issues to knowledge graph "
                        f"({len(dmesg_issues)} from dmesg, {len(journal_issues)} from journal)")
            
            # Store log analysis summary
            self.collected_data['log_analysis'] = {
                'dmesg_issues': dmesg_issues,
                'journal_issues': journal_issues,
                'total_issues': total_log_issues
            }
            
        except Exception as e:
            error_msg = f"Error adding log-based issues: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
