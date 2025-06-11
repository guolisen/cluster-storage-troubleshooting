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
        
        # Load historical experience data
        await self._load_historical_experience()
        
        # Process target pod first if specified
        if target_pod and target_namespace:
            # Extract pod metadata
            pod_metadata = self._parse_pod_metadata(target_pod, target_namespace)
            pod_id = self.knowledge_graph.add_gnode_pod(
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
                pvc_id = self.knowledge_graph.add_gnode_pvc(name, namespace, **pvc_metadata)
                
                if pvc_metadata['AccessModes'] not in ['ReadWriteOnce', 'ReadWriteMany']:
                    self.knowledge_graph.add_issue(
                        pvc_id,
                        "pvc_access_mode",
                        f"PVC access mode issue: {pvc_metadata['AccessModes']}",
                        "Critical" if pvc_metadata['AccessModes'] == 'ReadOnlyMany' else "high"
                    )

                # Link to target pod if it exists
                if target_pod and target_namespace:
                    pod_id = f"gnode:Pod:{target_namespace}/{target_pod}"
                    self.knowledge_graph.add_relationship(pod_id, pvc_id, "uses")
            
            # Add PVs with metadata
            for pv_name in volume_chain.get('pvs', []):
                pv_metadata = self._parse_pv_metadata(pv_name)
                pv_id = self.knowledge_graph.add_gnode_pv(pv_name, **pv_metadata)
                
                # Link to PVCs
                for pvc_key in volume_chain.get('pvcs', []):
                    pvc_id = f"gnode:PVC:{pvc_key}"
                    self.knowledge_graph.add_relationship(pvc_id, pv_id, "bound_to")

            # Add PVs with metadata
            volume_chain_id = None
            for vol_name in volume_chain.get('volumes', []):
                vol_metadata = self._parse_vol_metadata(vol_name)
                volume_chain_id = self.knowledge_graph.add_gnode_volume(vol_name, target_namespace, **vol_metadata)
                
                if vol_metadata.get('Health') not in ['GOOD']:
                    self.knowledge_graph.add_issue(
                        volume_chain_id,
                        "volume_health",
                        f"Volume health issue: {vol_metadata.get('Health')}",
                        "critical"
                    )

                if vol_metadata.get('CSIStatus') in ['FAILED']:
                    self.knowledge_graph.add_issue(
                        volume_chain_id,
                        "volume_health",
                        f"Volume CSIStatus issue: {vol_metadata.get('CSIStatus')}",
                        "critical"
                    )

                if vol_metadata.get('OperationalStatus') not in ['OPERATIVE']:
                    self.knowledge_graph.add_issue(
                        volume_chain_id,
                        "volume_health",
                        f"Volume OperationalStatus issue: {vol_metadata.get('OperationalStatus')}",
                        "critical"
                    )

                self.knowledge_graph.add_relationship(pvc_id, volume_chain_id, "bound_to")

            # Add drives with comprehensive CSI metadata
            drive_id = None
            for drive_uuid in volume_chain.get('drives', []):
                drive_info = self._parse_comprehensive_drive_info(drive_uuid)
                drive_id = self.knowledge_graph.add_gnode_drive(drive_uuid, **drive_info)

                # Link drives to volume chains
                if volume_chain_id:
                    self.knowledge_graph.add_relationship(volume_chain_id, drive_id, "bound_to")

                # Add issues for unhealthy drives
                if drive_info.get('Health') not in ['GOOD']:
                    self.knowledge_graph.add_issue(
                        drive_id,
                        "disk_health",
                        f"Drive health issue: {drive_info.get('Health')}",
                        "critical" if drive_info.get('Health') == 'BAD' else "high"
                    )

                if drive_info.get('Usage') not in ['IN_USE']:
                    self.knowledge_graph.add_issue(
                        drive_id,
                        "disk_health",
                        f"Drive usage issue: {drive_info.get('Usage')}",
                        "critical"
                    )

                if drive_info.get('Status') not in ['ONLINE']:
                    self.knowledge_graph.add_issue(
                        drive_id,
                        "disk_health",
                        f"Drive status issue: {drive_info.get('Status')}",
                        "critical"
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
                    pv_id = f"gnode:PV:{pv_name}"
                    self.knowledge_graph.add_relationship(pv_id, drive_id, "maps_to")
            
            # Add nodes with enhanced metadata
            for node_name in volume_chain.get('nodes', []):
                node_info = self._parse_comprehensive_node_info(node_name)
                node_id = self.knowledge_graph.add_gnode_node(node_name, **node_info)
                
                # Add issues for unhealthy nodes
                if not node_info.get('Ready') or node_info.get('DiskPressure'):
                    self.knowledge_graph.add_issue(
                        node_id,
                        "node_health",
                        f"Node issues: Ready={node_info.get('Ready')}, DiskPressure={node_info.get('DiskPressure')}",
                        "high" if not node_info.get('Ready') else "medium"
                    )
                
                # Link drives to nodes
                if drive_id:
                    self.knowledge_graph.add_relationship(drive_id, node_id, "located_on")
                    self.knowledge_graph.add_relationship(node_id, drive_id, "related_to")
        
                # Link to target pod if it exists
                if target_pod and target_namespace:
                    pod_id = f"gnode:Pod:{target_namespace}/{target_pod}"
                    self.knowledge_graph.add_relationship(pod_id, node_id, "located_on")
                    self.knowledge_graph.add_relationship(node_id, pod_id, "related_to")
                
        # Add CSI Baremetal specific entities
        await self._add_csi_baremetal_entities()
        
        # Add all collected drives and nodes (including cluster nodes)
        await self._add_all_drives_and_nodes()
        
        # Add Volume entities based on PVCs
        await self._add_volume_entities()
        
        # Create enhanced CSI relationships
        await self._create_enhanced_csi_relationships()
        
        # Add System entities (logs, SMART data)
        await self._add_system_entities()
        
        # Add log-based issues to knowledge graph
        await self._add_log_based_issues()
        
        # Add SMART data analysis
        await self._add_smart_data_analysis()
        
        # Add enhanced log analysis
        await self._add_enhanced_log_analysis()
        
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
            current_drives = []
            
            for line in lines:
                if 'name:' in line and 'metadata:' not in line:
                    # Process previous LVG if exists
                    if current_lvg:
                        self._finalize_lvg_entity(current_lvg, current_drives)
                    
                    current_lvg = line.split('name:')[-1].strip()
                    current_drives = []
                elif current_lvg and 'health:' in line:
                    health = line.split('health:')[-1].strip()
                    
                    # Add LVG to knowledge graph
                    lvg_id = self.knowledge_graph.add_gnode_lvg(current_lvg, Health=health, drive_uuids=current_drives)
                    
                    # Add issues for unhealthy LVGs
                    if health not in ['GOOD', 'HEALTHY']:
                        self.knowledge_graph.add_issue(
                            lvg_id,
                            "lvg_health",
                            f"LVG health issue: {health}",
                            "high"
                        )
                elif current_lvg and 'drive:' in line:
                    # Extract drive UUID from LVG
                    drive_uuid = line.split('drive:')[-1].strip()
                    if drive_uuid:
                        current_drives.append(drive_uuid)
            
            # Process last LVG
            if current_lvg:
                self._finalize_lvg_entity(current_lvg, current_drives)
                
        except Exception as e:
            logging.warning(f"Error processing LVG entities: {e}")
    
    def _finalize_lvg_entity(self, lvg_name: str, drive_uuids: List[str]):
        """Finalize LVG entity with drive relationships"""
        try:
            lvg_id = f"gnode:LVG:{lvg_name}"
            
            # Add LVG→Drive relationships
            for drive_uuid in drive_uuids:
                drive_id = f"gnode:Drive:{drive_uuid}"
                if self.knowledge_graph.graph.has_node(drive_id):
                    self.knowledge_graph.add_relationship(lvg_id, drive_id, "contains")
                    logging.debug(f"Added LVG→Drive relationship: {lvg_id} → {drive_id}")
                    
        except Exception as e:
            logging.warning(f"Error finalizing LVG entity {lvg_name}: {e}")
    
    def _process_available_capacity_entities(self, ac_output: str):
        """Process only relevant available capacity entities"""
        try:
            # Get relevant drive UUIDs to filter ACs
            relevant_drives = self._get_relevant_drive_uuids()
            
            lines = ac_output.split('\n')
            current_ac = None
            ac_info = {}
            
            for line in lines:
                if 'name:' in line and 'metadata:' not in line:
                    # Process previous AC if exists and relevant
                    if current_ac and self._is_ac_relevant(current_ac, ac_info, relevant_drives):
                        self._finalize_ac_entity(current_ac, ac_info)
                    
                    current_ac = line.split('name:')[-1].strip()
                    ac_info = {}
                elif current_ac:
                    # Extract AC properties
                    if 'size:' in line:
                        ac_info['size'] = line.split('size:')[-1].strip()
                    elif 'storageClass:' in line:
                        ac_info['storage_class'] = line.split('storageClass:')[-1].strip()
                    elif 'location:' in line:
                        ac_info['location'] = line.split('location:')[-1].strip()
            
            # Process last AC if relevant
            if current_ac and self._is_ac_relevant(current_ac, ac_info, relevant_drives):
                self._finalize_ac_entity(current_ac, ac_info)
                
        except Exception as e:
            logging.warning(f"Error processing Available Capacity entities: {e}")
    
    def _is_ac_relevant(self, ac_name: str, ac_info: Dict[str, str], relevant_drives: set) -> bool:
        """Check if AC is relevant to the current volume troubleshooting"""
        try:
            # AC is relevant if its location matches a relevant drive
            location = ac_info.get('location', '')
            if location in relevant_drives:
                return True
            
            # Also include ACs that might be on the same nodes as relevant drives
            # This is a more conservative approach to ensure we don't miss related capacity
            return False
            
        except Exception as e:
            logging.warning(f"Error checking AC relevance for {ac_name}: {e}")
            return False
    
    def _finalize_ac_entity(self, ac_name: str, ac_info: Dict[str, str]):
        """Finalize AC entity with properties"""
        try:
            ac_id = self.knowledge_graph.add_gnode_ac(
                ac_name,
                size=ac_info.get('size', ''),
                storage_class=ac_info.get('storage_class', ''),
                location=ac_info.get('location', '')
            )
            
            # Add AC→Node relationship if location is specified
            location = ac_info.get('location')
            if location:
                node_id = f"gnode:Node:{location}"
                if self.knowledge_graph.graph.has_node(node_id):
                    self.knowledge_graph.add_relationship(ac_id, node_id, "available_on")
                    logging.debug(f"Added AC→Node relationship: {ac_id} → {node_id}")
                    
        except Exception as e:
            logging.warning(f"Error finalizing AC entity {ac_name}: {e}")
    
    def _process_csibm_node_entities(self, csibm_nodes_output: str):
        """Process CSI Baremetal node entities"""
        try:
            lines = csibm_nodes_output.split('\n')
            
            for line in lines:
                if 'name:' in line and 'metadata:' not in line:
                    csibm_node_name = line.split('name:')[-1].strip()
                    # CSI Baremetal nodes provide additional node context
                    # These will be linked to regular nodes in _add_all_drives_and_nodes
                    
        except Exception as e:
            logging.warning(f"Error processing CSI Baremetal node entities: {e}")
    
    async def _add_all_drives_and_nodes(self):
        """Add all collected drives and cluster nodes to the knowledge graph"""
        try:
            logging.info("Adding all collected drives and cluster nodes to knowledge graph...")
            
            # Process all drives from CSI Baremetal data
            await self._process_all_drives()
            
            # Process all cluster nodes
            await self._process_all_cluster_nodes()
            
            # Create drive→node relationships
            await self._create_drive_node_relationships()
            
            # Create PV→drive relationships
            await self._create_pv_drive_relationships()
            
        except Exception as e:
            error_msg = f"Error adding all drives and nodes: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
    
    async def _process_all_drives(self):
        """Process only relevant drives from collected CSI Baremetal data"""
        try:
            drives_output = self.collected_data.get('csi_baremetal', {}).get('drives', '')
            if not drives_output:
                logging.warning("No drives data found in collected CSI Baremetal information")
                return
            
            # Get relevant drive UUIDs from volume locations and LVGs
            relevant_drives = self._get_relevant_drive_uuids()
            
            lines = drives_output.split('\n')
            current_drive = None
            drive_info = {}
            
            for line in lines:
                if 'name:' in line and 'metadata:' not in line:
                    # Process previous drive if exists and relevant
                    if current_drive and current_drive in relevant_drives:
                        self._finalize_drive_entity(current_drive, drive_info)
                    
                    current_drive = line.split('name:')[-1].strip()
                    drive_info = {}
                elif current_drive and current_drive in relevant_drives:
                    # Extract drive properties only for relevant drives
                    if 'health:' in line:
                        drive_info['Health'] = line.split('health:')[-1].strip()
                    elif 'status:' in line:
                        drive_info['Status'] = line.split('status:')[-1].strip()
                    elif 'path:' in line:
                        drive_info['Path'] = line.split('path:')[-1].strip()
                    elif 'usage:' in line:
                        drive_info['Usage'] = line.split('usage:')[-1].strip()
                    elif 'size:' in line:
                        drive_info['Size'] = line.split('size:')[-1].strip()
                    elif 'type:' in line:
                        drive_info['Type'] = line.split('type:')[-1].strip()
                    elif 'node:' in line:
                        drive_info['NodeName'] = line.split('node:')[-1].strip()
                    elif 'serialNumber:' in line:
                        drive_info['SerialNumber'] = line.split('serialNumber:')[-1].strip()
            
            # Process last drive if relevant
            if current_drive and current_drive in relevant_drives:
                self._finalize_drive_entity(current_drive, drive_info)
                
            logging.info(f"Processed {len(relevant_drives)} relevant drives from CSI Baremetal data")
            
        except Exception as e:
            logging.warning(f"Error processing relevant drives: {e}")
    
    def _get_relevant_drive_uuids(self) -> set:
        """Get relevant drive UUIDs from volume locations and LVGs"""
        relevant_drives = set()
        
        try:
            # Get drive UUIDs from CSI Volume locations
            volumes_output = self.collected_data.get('csi_baremetal', {}).get('volumes', '')
            if volumes_output:
                volume_locations = self._parse_volume_locations(volumes_output)
                for location in volume_locations.values():
                    if self._is_drive_uuid(location):
                        relevant_drives.add(location)
            
            # Get drive UUIDs from LVG locations
            lvg_output = self.collected_data.get('csi_baremetal', {}).get('lvgs', '')
            if lvg_output:
                lvg_drives = self._parse_lvg_drive_locations(lvg_output)
                relevant_drives.update(lvg_drives)
            
            # Also include drives from volume chain if available
            volume_chain_drives = getattr(self, '_volume_chain_drives', set())
            relevant_drives.update(volume_chain_drives)
            
            logging.info(f"Found {len(relevant_drives)} relevant drive UUIDs")
            return relevant_drives
            
        except Exception as e:
            logging.warning(f"Error getting relevant drive UUIDs: {e}")
            return set()
    
    def _parse_lvg_drive_locations(self, lvg_output: str) -> set:
        """Parse LVG output to extract drive UUIDs from LOCATIONS property"""
        drive_uuids = set()
        
        try:
            lines = lvg_output.split('\n')
            current_lvg = None
            
            for line in lines:
                line = line.strip()
                if 'name:' in line and 'metadata:' not in line:
                    current_lvg = line.split('name:')[-1].strip()
                elif current_lvg and 'locations:' in line.lower():
                    # Extract drive UUIDs from locations array
                    locations_str = line.split('locations:')[-1].strip()
                    # Handle array format like ["uuid1", "uuid2"]
                    if '[' in locations_str and ']' in locations_str:
                        locations_str = locations_str.strip('[]')
                        for location in locations_str.split(','):
                            location = location.strip().strip('"\'')
                            if self._is_drive_uuid(location):
                                drive_uuids.add(location)
                    current_lvg = None  # Reset for next LVG
            
        except Exception as e:
            logging.warning(f"Error parsing LVG drive locations: {e}")
        
        return drive_uuids
    
    def _finalize_drive_entity(self, drive_uuid: str, drive_info: Dict[str, str]):
        """Finalize drive entity with comprehensive information"""
        try:
            # Add drive to knowledge graph with all collected information
            drive_id = self.knowledge_graph.add_gnode_drive(drive_uuid, **drive_info)
            
            # Add issues for unhealthy drives
            health = drive_info.get('Health', 'UNKNOWN')
            if health in ['SUSPECT', 'BAD', 'FAILED']:
                severity = "critical" if health in ['BAD', 'FAILED'] else "high"
                self.knowledge_graph.add_issue(
                    drive_id,
                    "disk_health",
                    f"Drive health issue: {health}",
                    severity
                )
            
            # Add issues for drives with high usage
            usage = drive_info.get('Usage', 'UNKNOWN')
            if usage == 'IN_USE' and drive_info.get('Type') == 'SYSTEM':
                self.knowledge_graph.add_issue(
                    drive_id,
                    "system_drive_usage",
                    "System drive is in heavy use",
                    "medium"
                )
            
            logging.debug(f"Added Drive entity: {drive_id} with health {health}")
            
        except Exception as e:
            logging.warning(f"Error finalizing drive entity {drive_uuid}: {e}")
    
    async def _process_all_cluster_nodes(self):
        """Process only actual cluster nodes from kubectl get node output"""
        try:
            nodes_output = self.collected_data.get('kubernetes', {}).get('nodes', '')
            if not nodes_output:
                logging.warning("No nodes data found in collected Kubernetes information")
                return
            
            # Get actual cluster node names from kubectl get node output
            cluster_nodes = self._parse_cluster_node_names(nodes_output)
            
            # Process only these cluster nodes
            for node_name in cluster_nodes:
                node_info = self._parse_node_info_from_output(node_name, nodes_output)
                self._finalize_cluster_node_entity(node_name, node_info)
                
            logging.info(f"Processed {len(cluster_nodes)} actual cluster nodes from Kubernetes data")
            
        except Exception as e:
            logging.warning(f"Error processing cluster nodes: {e}")
    
    def _parse_cluster_node_names(self, nodes_output: str) -> List[str]:
        """Parse actual cluster node names from kubectl get node output"""
        cluster_nodes = []
        
        try:
            lines = nodes_output.split('\n')
            
            for line in lines:
                line = line.strip()
                # Look for node names that match cluster naming pattern
                if 'name:' in line and 'metadata:' not in line:
                    node_name = line.split('name:')[-1].strip()
                    # Filter out non-cluster nodes (CSI nodes, PV nodes, etc.)
                    if self._is_cluster_node(node_name):
                        cluster_nodes.append(node_name)
            
        except Exception as e:
            logging.warning(f"Error parsing cluster node names: {e}")
        
        return cluster_nodes
    
    def _is_cluster_node(self, node_name: str) -> bool:
        """Check if node name represents an actual cluster node"""
        # Filter out CSI-specific nodes, PV nodes, and other non-cluster entities
        exclude_patterns = [
            'csi/',
            'driver.',
            'pvc-',
            'kubernetes.io/',
            '-' * 8,  # UUID-like patterns
        ]
        
        for pattern in exclude_patterns:
            if pattern in node_name:
                return False
        
        # Cluster nodes typically have domain-like names
        return '.' in node_name or node_name.endswith('.local') or len(node_name.split('.')) > 1
    
    def _parse_node_info_from_output(self, node_name: str, nodes_output: str) -> Dict[str, Any]:
        """Parse node information for a specific node from the output"""
        node_info = {}
        
        try:
            lines = nodes_output.split('\n')
            in_node_section = False
            
            for line in lines:
                if f'name: {node_name}' in line:
                    in_node_section = True
                    continue
                elif in_node_section and 'name:' in line and node_name not in line:
                    # Reached next node section
                    break
                elif in_node_section:
                    # Extract node properties
                    if 'ready:' in line.lower():
                        ready_value = line.split(':')[-1].strip().lower()
                        node_info['Ready'] = ready_value in ['true', 'ready']
                    elif 'diskpressure:' in line.lower():
                        pressure_value = line.split(':')[-1].strip().lower()
                        node_info['DiskPressure'] = pressure_value in ['true', 'yes']
                    elif 'memorypressure:' in line.lower():
                        pressure_value = line.split(':')[-1].strip().lower()
                        node_info['MemoryPressure'] = pressure_value in ['true', 'yes']
                    elif 'pidpressure:' in line.lower():
                        pressure_value = line.split(':')[-1].strip().lower()
                        node_info['PIDPressure'] = pressure_value in ['true', 'yes']
                    elif 'architecture:' in line.lower():
                        node_info['Architecture'] = line.split(':')[-1].strip()
                    elif 'kernel:' in line.lower():
                        node_info['KernelVersion'] = line.split(':')[-1].strip()
                    elif 'os:' in line.lower():
                        node_info['OperatingSystem'] = line.split(':')[-1].strip()
                    elif 'role:' in line.lower():
                        node_info['Role'] = line.split(':')[-1].strip()
            
        except Exception as e:
            logging.warning(f"Error parsing node info for {node_name}: {e}")
        
        return node_info
    
    def _finalize_cluster_node_entity(self, node_name: str, node_info: Dict[str, Any]):
        """Finalize cluster node entity with comprehensive information"""
        try:
            # Add node to knowledge graph with all collected information
            node_id = self.knowledge_graph.add_gnode_node(node_name, **node_info)
            
            # Add issues for unhealthy nodes
            ready = node_info.get('Ready', True)
            disk_pressure = node_info.get('DiskPressure', False)
            memory_pressure = node_info.get('MemoryPressure', False)
            
            if not ready:
                self.knowledge_graph.add_issue(
                    node_id,
                    "node_not_ready",
                    f"Node {node_name} is not ready",
                    "critical"
                )
            
            if disk_pressure:
                self.knowledge_graph.add_issue(
                    node_id,
                    "disk_pressure",
                    f"Node {node_name} is experiencing disk pressure",
                    "high"
                )
            
            if memory_pressure:
                self.knowledge_graph.add_issue(
                    node_id,
                    "memory_pressure",
                    f"Node {node_name} is experiencing memory pressure",
                    "medium"
                )
            
            logging.debug(f"Added Node entity: {node_id} with Ready={ready}, DiskPressure={disk_pressure}")
            
        except Exception as e:
            logging.warning(f"Error finalizing cluster node entity {node_name}: {e}")
    
    async def _create_drive_node_relationships(self):
        """Create Drive→Node relationships based on collected data"""
        try:
            # Get all drive nodes
            drive_nodes = self.knowledge_graph.find_nodes_by_type('Drive')
            
            for drive_id in drive_nodes:
                drive_attrs = self.knowledge_graph.graph.nodes[drive_id]
                node_name = drive_attrs.get('NodeName')
                
                if node_name:
                    node_id = f"gnode:Node:{node_name}"
                    if self.knowledge_graph.graph.has_node(node_id):
                        self.knowledge_graph.add_relationship(drive_id, node_id, "located_on")
                        logging.debug(f"Added Drive→Node relationship: {drive_id} → {node_id}")
            
        except Exception as e:
            logging.warning(f"Error creating drive→node relationships: {e}")
    
    async def _create_pv_drive_relationships(self):
        """Create PV→Drive relationships based on collected data"""
        try:
            # Get all PV nodes
            pv_nodes = self.knowledge_graph.find_nodes_by_type('PV')
            
            for pv_id in pv_nodes:
                pv_attrs = self.knowledge_graph.graph.nodes[pv_id]
                disk_path = pv_attrs.get('diskPath')
                
                if disk_path:
                    # Find drive with matching path
                    drive_nodes = self.knowledge_graph.find_nodes_by_type('Drive')
                    for drive_id in drive_nodes:
                        drive_attrs = self.knowledge_graph.graph.nodes[drive_id]
                        drive_path = drive_attrs.get('Path')
                        
                        if drive_path and drive_path == disk_path:
                            self.knowledge_graph.add_relationship(pv_id, drive_id, "maps_to")
                            logging.debug(f"Added PV→Drive relationship: {pv_id} → {drive_id}")
                            break
            
        except Exception as e:
            logging.warning(f"Error creating PV→drive relationships: {e}")
    
    async def _add_volume_entities(self):
        """Add Volume entities to the knowledge graph based on PVC relationships"""
        try:
            logging.info("Adding Volume entities to knowledge graph based on PVCs...")
            
            # Process volumes only for existing PVCs in the knowledge graph
            self._process_volumes_from_pvcs()
                
        except Exception as e:
            error_msg = f"Error adding Volume entities: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
    
    def _process_volumes_from_pvcs(self):
        """Process Volume entities based on existing PVCs in the knowledge graph"""
        try:
            # Get all PVC nodes from the knowledge graph
            pvc_nodes = self.knowledge_graph.find_nodes_by_type('PVC')
            
            for pvc_id in pvc_nodes:
                pvc_attrs = self.knowledge_graph.graph.nodes[pvc_id]
                pvc_name = pvc_attrs.get('name')
                pvc_namespace = pvc_attrs.get('namespace')
                
                if not pvc_name or not pvc_namespace:
                    continue
                
                # Extract volume information from PVC properties and related PV
                volume_info = self._extract_volume_info_from_pvc(pvc_id, pvc_attrs)
                
                if volume_info:
                    # Create volume entity
                    volume_id = self.knowledge_graph.add_gnode_volume(
                        volume_info['name'],
                        volume_info['namespace'],
                        **volume_info['attributes']
                    )
                    
                    # Add PVC→Volume edge
                    self.knowledge_graph.add_relationship(pvc_id, volume_id, "bound_to")
                    
                    # Add Volume→Storage relationships based on storage type
                    self._add_volume_storage_relationships(volume_id, volume_info)
                    
                    logging.debug(f"Added Volume {volume_id} for PVC {pvc_id}")
                    
        except Exception as e:
            logging.warning(f"Error processing volumes from PVCs: {e}")
    
    def _extract_volume_info_from_pvc(self, pvc_id: str, pvc_attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract volume information from PVC and its bound PV"""
        try:
            # Find the PV bound to this PVC
            bound_pvs = self.knowledge_graph.find_connected_nodes(pvc_id, "bound_to")
            
            if not bound_pvs:
                # No bound PV, create volume from PVC info only
                volume_name = f"vol-{pvc_attrs.get('name', 'unknown')}"
                return {
                    'name': volume_name,
                    'namespace': pvc_attrs.get('namespace', 'default'),
                    'attributes': {
                        'Health': 'UNKNOWN',
                        'LocationType': 'PVC_ONLY',
                        'size': pvc_attrs.get('StorageSize', ''),
                        'storage_class': pvc_attrs.get('storageClass', ''),
                        'location': '',
                        'Usage': pvc_attrs.get('Phase', 'UNKNOWN'),
                        'source_pvc': pvc_id
                    }
                }
            
            # Get PV information
            pv_id = bound_pvs[0]
            pv_attrs = self.knowledge_graph.graph.nodes[pv_id]
            
            # Determine volume name from PV or generate one
            volume_name = pv_attrs.get('volumeName', f"vol-{pv_attrs.get('name', 'unknown')}")
            
            # Determine storage type and health
            health = self._determine_volume_health(pv_id, pv_attrs)
            location_type = self._determine_location_type(pv_id, pv_attrs)
            usage = self._determine_volume_usage(pv_id, pv_attrs)
            
            return {
                'name': volume_name,
                'namespace': pvc_attrs.get('namespace', 'default'),
                'attributes': {
                    'Health': health,
                    'LocationType': location_type,
                    'size': pv_attrs.get('Capacity', pvc_attrs.get('StorageSize', '')),
                    'storage_class': pv_attrs.get('storageClass', ''),
                    'location': pv_attrs.get('nodeAffinity', ''),
                    'Usage': usage,
                    'source_pvc': pvc_id,
                    'source_pv': pv_id
                }
            }
            
        except Exception as e:
            logging.warning(f"Error extracting volume info from PVC {pvc_id}: {e}")
            return None
    
    def _determine_volume_health(self, pv_id: str, pv_attrs: Dict[str, Any]) -> str:
        """Determine volume health based on PV and connected storage"""
        try:
            # Check PV phase
            pv_phase = pv_attrs.get('Phase', 'Unknown')
            if pv_phase != 'Bound':
                return 'SUSPECT'
            
            # Check connected drives health
            connected_drives = self.knowledge_graph.find_connected_nodes(pv_id, "maps_to")
            for drive_id in connected_drives:
                drive_attrs = self.knowledge_graph.graph.nodes[drive_id]
                drive_health = drive_attrs.get('Health', 'UNKNOWN')
                if drive_health in ['SUSPECT', 'BAD']:
                    return drive_health
            
            # Check connected LVGs health
            for drive_id in connected_drives:
                # Find LVGs that contain this drive
                for lvg_id in self.knowledge_graph.find_nodes_by_type('LVG'):
                    lvg_drives = self.knowledge_graph.find_connected_nodes(lvg_id, "contains")
                    if drive_id in lvg_drives:
                        lvg_attrs = self.knowledge_graph.graph.nodes[lvg_id]
                        lvg_health = lvg_attrs.get('Health', 'UNKNOWN')
                        if lvg_health not in ['GOOD', 'HEALTHY']:
                            return 'SUSPECT'
            
            return 'GOOD'
            
        except Exception as e:
            logging.warning(f"Error determining volume health for PV {pv_id}: {e}")
            return 'UNKNOWN'
    
    def _determine_location_type(self, pv_id: str, pv_attrs: Dict[str, Any]) -> str:
        """Determine volume location type (LVG or DRIVE)"""
        try:
            # Check if PV maps to drives that are part of LVGs
            connected_drives = self.knowledge_graph.find_connected_nodes(pv_id, "maps_to")
            
            for drive_id in connected_drives:
                # Check if this drive is contained in any LVG
                for lvg_id in self.knowledge_graph.find_nodes_by_type('LVG'):
                    lvg_drives = self.knowledge_graph.find_connected_nodes(lvg_id, "contains")
                    if drive_id in lvg_drives:
                        return 'LVG'
            
            # If no LVG found, it's direct drive usage
            if connected_drives:
                return 'DRIVE'
            
            return 'UNKNOWN'
            
        except Exception as e:
            logging.warning(f"Error determining location type for PV {pv_id}: {e}")
            return 'UNKNOWN'
    
    def _determine_volume_usage(self, pv_id: str, pv_attrs: Dict[str, Any]) -> str:
        """Determine volume usage status"""
        try:
            pv_phase = pv_attrs.get('Phase', 'Unknown')
            
            if pv_phase == 'Bound':
                return 'IN_USE'
            elif pv_phase == 'Available':
                return 'AVAILABLE'
            elif pv_phase == 'Released':
                return 'RELEASED'
            elif pv_phase == 'Failed':
                return 'FAILED'
            else:
                return 'UNKNOWN'
                
        except Exception as e:
            logging.warning(f"Error determining volume usage for PV {pv_id}: {e}")
            return 'UNKNOWN'
    
    def _add_volume_storage_relationships(self, volume_id: str, volume_info: Dict[str, Any]):
        """Add Volume→Storage relationships based on storage type"""
        try:
            location_type = volume_info['attributes'].get('LocationType', 'UNKNOWN')
            source_pv = volume_info['attributes'].get('source_pv')
            
            if not source_pv:
                return
            
            # Get drives connected to the PV
            connected_drives = self.knowledge_graph.find_connected_nodes(source_pv, "maps_to")
            
            if location_type == 'LVG':
                # Find LVG that contains the drives
                for drive_id in connected_drives:
                    for lvg_id in self.knowledge_graph.find_nodes_by_type('LVG'):
                        lvg_drives = self.knowledge_graph.find_connected_nodes(lvg_id, "contains")
                        if drive_id in lvg_drives:
                            # Add Volume→LVG relationship
                            self.knowledge_graph.add_relationship(volume_id, lvg_id, "bound_to")
                            logging.debug(f"Added Volume→LVG relationship: {volume_id} → {lvg_id}")
                            break
            
            elif location_type == 'DRIVE':
                # Add direct Volume→Drive relationships
                for drive_id in connected_drives:
                    self.knowledge_graph.add_relationship(volume_id, drive_id, "bound_to")
                    logging.debug(f"Added Volume→Drive relationship: {volume_id} → {drive_id}")
            
        except Exception as e:
            logging.warning(f"Error adding volume storage relationships for {volume_id}: {e}")
    
    async def _create_enhanced_csi_relationships(self):
        """Create enhanced CSI relationships based on Volume location mapping"""
        try:
            logging.info("Creating enhanced CSI relationships...")
            
            # Create Volume → Drive/LVG relationships based on CSI Volume data
            await self._create_volume_drive_relationships()
            
            logging.info("Enhanced CSI relationships created successfully")
            
        except Exception as e:
            error_msg = f"Error creating enhanced CSI relationships: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
    
    async def _create_volume_drive_relationships(self):
        """Create Volume → Drive/LVG relationships based on CSI Volume location data"""
        try:
            volumes_output = self.collected_data.get('csi_baremetal', {}).get('volumes', '')
            if not volumes_output:
                logging.warning("No CSI Volume data found for relationship creation")
                return
            
            # Parse CSI Volume data to extract location information
            volume_locations = self._parse_volume_locations(volumes_output)
            
            # Get all Volume nodes from knowledge graph
            volume_nodes = self.knowledge_graph.find_nodes_by_type('Volume')
            
            for volume_id in volume_nodes:
                volume_attrs = self.knowledge_graph.graph.nodes[volume_id]
                volume_name = volume_attrs.get('name')
                
                if not volume_name:
                    continue
                
                # Find location for this volume
                location = volume_locations.get(volume_name)
                if not location:
                    # Try to get location from volume attributes if not found in parsed data
                    location = volume_attrs.get('location')
                
                if not location:
                    logging.debug(f"No location found for volume {volume_name}")
                    continue
                
                # Enhanced logic: Determine if location is Drive UUID or LVG UUID
                if self._is_drive_uuid(location):
                    # Direct Volume → Drive relationship
                    drive_id = f"gnode:Drive:{location}"
                    if self.knowledge_graph.graph.has_node(drive_id):
                        self.knowledge_graph.add_relationship(volume_id, drive_id, "bound_to")
                        logging.debug(f"Added Volume→Drive relationship: {volume_id} → {drive_id}")
                    else:
                        logging.warning(f"Drive {location} not found for volume {volume_name}")
                else:
                    # Volume → LVG relationship (location is LVG UUID)
                    lvg_id = f"gnode:LVG:{location}"
                    if self.knowledge_graph.graph.has_node(lvg_id):
                        self.knowledge_graph.add_relationship(volume_id, lvg_id, "bound_to")
                        logging.debug(f"Added Volume→LVG relationship: {volume_id} → {lvg_id}")
                        
                        # Also create Volume → Drive relationships through LVG
                        await self._create_volume_to_drive_via_lvg(volume_id, lvg_id)
                    else:
                        logging.warning(f"LVG {location} not found for volume {volume_name}")
            
        except Exception as e:
            logging.warning(f"Error creating volume→drive relationships: {e}")
    
    def _parse_volume_locations(self, volumes_output: str) -> Dict[str, str]:
        """Parse CSI Volume output to extract volume name → location mapping"""
        volume_locations = {}
        
        try:
            lines = volumes_output.split('\n')
            current_volume = None
            
            for line in lines:
                line = line.strip()
                if 'name:' in line and 'metadata:' not in line:
                    current_volume = line.split('name:')[-1].strip()
                elif current_volume and 'location:' in line:
                    location = line.split('location:')[-1].strip()
                    if location:
                        volume_locations[current_volume] = location
                        current_volume = None  # Reset for next volume
            
        except Exception as e:
            logging.warning(f"Error parsing volume locations: {e}")
        
        return volume_locations
    
    def _is_drive_uuid(self, location: str) -> bool:
        """Check if location string is a Drive UUID format"""
        # Drive UUIDs are typically 36 characters with hyphens (UUID format)
        # e.g., "2a96dfec-47db-449d-9789-0d81660c2c4d"
        return len(location) == 36 and location.count('-') == 4
    
    async def _create_volume_to_drive_via_lvg(self, volume_id: str, lvg_id: str):
        """Create Volume → Drive relationships through LVG"""
        try:
            # Get drives contained in the LVG
            lvg_drives = self.knowledge_graph.find_connected_nodes(lvg_id, "contains")
            
            for drive_id in lvg_drives:
                # Add Volume → Drive relationship through LVG
                self.knowledge_graph.add_relationship(volume_id, drive_id, "bound_to")
                logging.debug(f"Added Volume→Drive (via LVG) relationship: {volume_id} → {drive_id}")
                
        except Exception as e:
            logging.warning(f"Error creating volume→drive relationships via LVG {lvg_id}: {e}")
    
    async def _add_system_entities(self):
        """Add System entities to the knowledge graph"""
        try:
            logging.info("Adding System entities to knowledge graph...")
            
            # Add kernel system entity
            kernel_id = self.knowledge_graph.add_gnode_system_entity(
                "kernel", "logs",
                description="Kernel logs and dmesg output",
                log_sources=["dmesg", "journal"]
            )
            
            # Add kubelet system entity
            kubelet_id = self.knowledge_graph.add_gnode_system_entity(
                "kubelet", "service",
                description="Kubelet service for pod and volume management",
                service_status="active"
            )
            
            # Add boot system entity
            boot_id = self.knowledge_graph.add_gnode_system_entity(
                "boot", "logs",
                description="Boot-time hardware and storage initialization",
                log_sources=["journal"]
            )
            
            # Add storage services system entity
            storage_services_id = self.knowledge_graph.add_gnode_system_entity(
                "storage_services", "service",
                description="Storage-related system services",
                services=["csi-baremetal-node", "csi-baremetal-controller"]
            )
            
            # Add SMART monitoring system entity if SMART data exists
            if self.collected_data.get('smart_data'):
                smart_id = self.knowledge_graph.add_gnode_system_entity(
                    "smart_monitoring", "hardware",
                    description="SMART drive health monitoring",
                    monitored_drives=list(self.collected_data['smart_data'].keys())
                )
                
        except Exception as e:
            error_msg = f"Error adding System entities: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
    
    async def _add_log_based_issues(self):
        """Add log-based issues to the knowledge graph"""
        try:
            logging.info("Analyzing logs for storage-related issues...")
            
            # Parse dmesg issues
            dmesg_issues = self._parse_dmesg_issues()
            for issue in dmesg_issues:
                # Add system-level issues to a general system entity
                system_id = "gnode:System:kernel"
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
                    entity_id = "gnode:System:kubelet"
                elif issue['source'] == 'journal_boot':
                    entity_id = "gnode:System:boot"
                else:
                    entity_id = "gnode:System:storage_services"
                
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
    
    async def _add_smart_data_analysis(self):
        """Add SMART data analysis to the knowledge graph"""
        try:
            smart_data = self.collected_data.get('smart_data', {})
            if not smart_data:
                return
                
            logging.info("Analyzing SMART data for drive health issues...")
            
            for drive_uuid, smart_output in smart_data.items():
                drive_id = f"gnode:Drive:{drive_uuid}"
                
                # Parse SMART data for health indicators
                smart_issues = self._parse_smart_data_issues(smart_output, drive_uuid)
                
                for issue in smart_issues:
                    self.knowledge_graph.add_issue(
                        drive_id,
                        issue['type'],
                        issue['description'],
                        issue['severity']
                    )
                
                # Add relationship between drive and SMART monitoring system
                smart_system_id = "gnode:System:smart_monitoring"
                if self.knowledge_graph.graph.has_node(smart_system_id):
                    self.knowledge_graph.add_relationship(
                        smart_system_id, drive_id, "monitors"
                    )
            
            logging.info(f"SMART data analysis completed for {len(smart_data)} drives")
            
        except Exception as e:
            error_msg = f"Error adding SMART data analysis: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
    
    async def _add_enhanced_log_analysis(self):
        """Add enhanced log analysis to the knowledge graph"""
        try:
            enhanced_logs = self.collected_data.get('enhanced_logs', {})
            service_logs = self.collected_data.get('service_logs', {})
            
            if not enhanced_logs and not service_logs:
                return
                
            logging.info("Analyzing enhanced logs for storage issues...")
            
            # Analyze enhanced dmesg patterns
            for pattern_key, log_output in enhanced_logs.items():
                if log_output and log_output.strip():
                    # Extract pattern type from key
                    pattern_type = pattern_key.replace('dmesg_', '').replace('_', ' ')
                    
                    # Add issue to kernel system entity
                    self.knowledge_graph.add_issue(
                        "gnode:System:kernel",
                        "enhanced_log_pattern",
                        f"Enhanced log analysis detected {pattern_type} issues",
                        "medium"
                    )
            
            # Analyze service logs
            for service_name, log_output in service_logs.items():
                if log_output and ('error' in log_output.lower() or 'failed' in log_output.lower()):
                    # Determine system entity based on service
                    if service_name == 'kubelet':
                        entity_id = "gnode:System:kubelet"
                    else:
                        entity_id = "gnode:System:storage_services"
                    
                    self.knowledge_graph.add_issue(
                        entity_id,
                        "service_error",
                        f"Service {service_name} logs contain error messages",
                        "medium"
                    )
            
            logging.info("Enhanced log analysis completed")
            
        except Exception as e:
            error_msg = f"Error adding enhanced log analysis: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
    
    async def _load_historical_experience(self):
        """
        Load historical experience data from the configured file path
        and add it to the knowledge graph
        """
        import os
        import json
        
        try:
            # Get file path from configuration or use default if not configured
            historical_experience_file = self.config.get('historical_experience', {}).get('file_path', "historical_experience.json")
            logging.info(f"Loading historical experience data from {historical_experience_file}")
            
            if not os.path.exists(historical_experience_file):
                error_msg = f"Historical experience file {historical_experience_file} not found"
                logging.warning(error_msg)
                self.collected_data['errors'].append(error_msg)
                return
            
            try:
                with open(historical_experience_file, 'r') as f:
                    historical_experiences = json.load(f)
            except json.JSONDecodeError as e:
                error_msg = f"Error parsing historical experience file: {str(e)}"
                logging.error(error_msg)
                self.collected_data['errors'].append(error_msg)
                return
            except Exception as e:
                error_msg = f"Error reading historical experience file: {str(e)}"
                logging.error(error_msg)
                self.collected_data['errors'].append(error_msg)
                return
            
            if not isinstance(historical_experiences, list):
                error_msg = f"Historical experience data should be a list of objects"
                logging.error(error_msg)
                self.collected_data['errors'].append(error_msg)
                return
            
            # Add each historical experience to the knowledge graph
            for idx, experience in enumerate(historical_experiences):
                # Validate required fields
                required_fields = ['phenomenon', 'root_cause', 'localization_method', 'resolution_method']
                missing_fields = [field for field in required_fields if field not in experience]
                
                if missing_fields:
                    error_msg = f"Historical experience entry {idx} is missing required fields: {missing_fields}"
                    logging.warning(error_msg)
                    self.collected_data['errors'].append(error_msg)
                    continue
                
                # Add historical experience node to the knowledge graph
                experience_id = f"hist_{idx+1}"
                he_id = self.knowledge_graph.add_gnode_historical_experience(
                    experience_id=experience_id,
                    phenomenon=experience['phenomenon'],
                    root_cause=experience['root_cause'],
                    localization_method=experience['localization_method'],
                    resolution_method=experience['resolution_method']
                )
                
                # Link historical experience to related system components based on phenomenon
                self._link_historical_experience_to_components(he_id, experience)
            
            logging.info(f"Successfully loaded {len(historical_experiences)} historical experiences")
            
        except Exception as e:
            error_msg = f"Error loading historical experience data: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
    
    def _link_historical_experience_to_components(self, he_id: str, experience: Dict[str, str]):
        """
        Link historical experience node to related system components based on phenomenon
        
        Args:
            he_id: Historical experience node ID
            experience: Historical experience data
        """
        try:
            phenomenon = experience['phenomenon'].lower()
            
            # Link to logs if phenomenon mentions logs
            if 'logs' in phenomenon:
                log_nodes = self.knowledge_graph.find_nodes_by_type('System')
                for log_id in log_nodes:
                    node_attrs = self.knowledge_graph.graph.nodes[log_id]
                    if node_attrs.get('subtype') == 'logs':
                        self.knowledge_graph.add_relationship(he_id, log_id, "related_to")
                        logging.debug(f"Added relationship: {he_id} -> {log_id}")
            
            # Link to drives if phenomenon mentions volume/disk/drive
            if any(term in phenomenon for term in ['volume', 'disk', 'drive']):
                drive_nodes = self.knowledge_graph.find_nodes_by_type('Drive')
                for drive_id in drive_nodes:
                    self.knowledge_graph.add_relationship(he_id, drive_id, "related_to")
                    logging.debug(f"Added relationship: {he_id} -> {drive_id}")
            
            # Link to PVCs if phenomenon mentions PVC
            if 'pvc' in phenomenon:
                pvc_nodes = self.knowledge_graph.find_nodes_by_type('PVC')
                for pvc_id in pvc_nodes:
                    self.knowledge_graph.add_relationship(he_id, pvc_id, "related_to")
                    logging.debug(f"Added relationship: {he_id} -> {pvc_id}")
            
            # Link to pods if phenomenon mentions pod
            if 'pod' in phenomenon:
                pod_nodes = self.knowledge_graph.find_nodes_by_type('Pod')
                for pod_id in pod_nodes:
                    self.knowledge_graph.add_relationship(he_id, pod_id, "related_to")
                    logging.debug(f"Added relationship: {he_id} -> {pod_id}")
                    
        except Exception as e:
            logging.warning(f"Error linking historical experience {he_id} to components: {str(e)}")
