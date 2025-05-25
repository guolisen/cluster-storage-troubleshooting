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
        
        # Add all collected drives and nodes (including cluster nodes)
        await self._add_all_drives_and_nodes()
        
        # Add Volume entities based on PVCs
        await self._add_volume_entities()
        
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
                    lvg_id = self.knowledge_graph.add_lvg(current_lvg, Health=health, drive_uuids=current_drives)
                    
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
            lvg_id = f"LVG:{lvg_name}"
            
            # Add LVG→Drive relationships
            for drive_uuid in drive_uuids:
                drive_id = f"Drive:{drive_uuid}"
                if self.knowledge_graph.graph.has_node(drive_id):
                    self.knowledge_graph.add_relationship(lvg_id, drive_id, "contains")
                    logging.debug(f"Added LVG→Drive relationship: {lvg_id} → {drive_id}")
                    
        except Exception as e:
            logging.warning(f"Error finalizing LVG entity {lvg_name}: {e}")
    
    def _process_available_capacity_entities(self, ac_output: str):
        """Process available capacity entities"""
        try:
            lines = ac_output.split('\n')
            current_ac = None
            ac_info = {}
            
            for line in lines:
                if 'name:' in line and 'metadata:' not in line:
                    # Process previous AC if exists
                    if current_ac:
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
            
            # Process last AC
            if current_ac:
                self._finalize_ac_entity(current_ac, ac_info)
                
        except Exception as e:
            logging.warning(f"Error processing Available Capacity entities: {e}")
    
    def _finalize_ac_entity(self, ac_name: str, ac_info: Dict[str, str]):
        """Finalize AC entity with properties"""
        try:
            ac_id = self.knowledge_graph.add_ac(
                ac_name,
                size=ac_info.get('size', ''),
                storage_class=ac_info.get('storage_class', ''),
                location=ac_info.get('location', '')
            )
            
            # Add AC→Node relationship if location is specified
            location = ac_info.get('location')
            if location:
                node_id = f"Node:{location}"
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
        """Process all drives from collected CSI Baremetal data"""
        try:
            drives_output = self.collected_data.get('csi_baremetal', {}).get('drives', '')
            if not drives_output:
                logging.warning("No drives data found in collected CSI Baremetal information")
                return
            
            lines = drives_output.split('\n')
            current_drive = None
            drive_info = {}
            
            for line in lines:
                if 'name:' in line and 'metadata:' not in line:
                    # Process previous drive if exists
                    if current_drive:
                        self._finalize_drive_entity(current_drive, drive_info)
                    
                    current_drive = line.split('name:')[-1].strip()
                    drive_info = {}
                elif current_drive:
                    # Extract drive properties
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
            
            # Process last drive
            if current_drive:
                self._finalize_drive_entity(current_drive, drive_info)
                
            logging.info(f"Processed drives from CSI Baremetal data")
            
        except Exception as e:
            logging.warning(f"Error processing all drives: {e}")
    
    def _finalize_drive_entity(self, drive_uuid: str, drive_info: Dict[str, str]):
        """Finalize drive entity with comprehensive information"""
        try:
            # Add drive to knowledge graph with all collected information
            drive_id = self.knowledge_graph.add_drive(drive_uuid, **drive_info)
            
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
        """Process all cluster nodes from collected Kubernetes data"""
        try:
            nodes_output = self.collected_data.get('kubernetes', {}).get('nodes', '')
            if not nodes_output:
                logging.warning("No nodes data found in collected Kubernetes information")
                return
            
            # Parse YAML-like output for node information
            lines = nodes_output.split('\n')
            current_node = None
            node_info = {}
            
            for line in lines:
                if 'name:' in line and 'metadata:' not in line:
                    # Process previous node if exists
                    if current_node:
                        self._finalize_cluster_node_entity(current_node, node_info)
                    
                    current_node = line.split('name:')[-1].strip()
                    node_info = {}
                elif current_node:
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
            
            # Process last node
            if current_node:
                self._finalize_cluster_node_entity(current_node, node_info)
                
            logging.info(f"Processed cluster nodes from Kubernetes data")
            
        except Exception as e:
            logging.warning(f"Error processing all cluster nodes: {e}")
    
    def _finalize_cluster_node_entity(self, node_name: str, node_info: Dict[str, Any]):
        """Finalize cluster node entity with comprehensive information"""
        try:
            # Add node to knowledge graph with all collected information
            node_id = self.knowledge_graph.add_node(node_name, **node_info)
            
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
                    node_id = f"Node:{node_name}"
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
                    volume_id = self.knowledge_graph.add_volume(
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
    
    async def _add_system_entities(self):
        """Add System entities to the knowledge graph"""
        try:
            logging.info("Adding System entities to knowledge graph...")
            
            # Add kernel system entity
            kernel_id = self.knowledge_graph.add_system_entity(
                "kernel", "logs",
                description="Kernel logs and dmesg output",
                log_sources=["dmesg", "journal"]
            )
            
            # Add kubelet system entity
            kubelet_id = self.knowledge_graph.add_system_entity(
                "kubelet", "service",
                description="Kubelet service for pod and volume management",
                service_status="active"
            )
            
            # Add boot system entity
            boot_id = self.knowledge_graph.add_system_entity(
                "boot", "logs",
                description="Boot-time hardware and storage initialization",
                log_sources=["journal"]
            )
            
            # Add storage services system entity
            storage_services_id = self.knowledge_graph.add_system_entity(
                "storage_services", "service",
                description="Storage-related system services",
                services=["csi-baremetal-node", "csi-baremetal-controller"]
            )
            
            # Add SMART monitoring system entity if SMART data exists
            if self.collected_data.get('smart_data'):
                smart_id = self.knowledge_graph.add_system_entity(
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
    
    async def _add_smart_data_analysis(self):
        """Add SMART data analysis to the knowledge graph"""
        try:
            smart_data = self.collected_data.get('smart_data', {})
            if not smart_data:
                return
                
            logging.info("Analyzing SMART data for drive health issues...")
            
            for drive_uuid, smart_output in smart_data.items():
                drive_id = f"Drive:{drive_uuid}"
                
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
                smart_system_id = "System:smart_monitoring"
                if self.knowledge_graph.graph.has_node(smart_system_id):
                    self.knowledge_graph.add_relationship(
                        smart_system_id, drive_id, "monitors"
                    )
            
            logging.info(f"SMART data analysis completed for {len(smart_data)} drives")
            
        except Exception as e:
            error_msg = f"Error adding SMART data analysis: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
    
    def _parse_smart_data_issues(self, smart_output: str, drive_uuid: str) -> List[Dict]:
        """Parse SMART data output for health issues"""
        issues = []
        
        try:
            lines = smart_output.split('\n')
            
            for line in lines:
                line_lower = line.lower()
                
                # Check for SMART health status
                if 'overall-health self-assessment test result:' in line_lower:
                    if 'passed' not in line_lower:
                        issues.append({
                            'type': 'smart_health_fail',
                            'description': f"SMART health test failed: {line.strip()}",
                            'severity': 'critical'
                        })
                
                # Check for reallocated sectors
                if 'reallocated_sector_ct' in line_lower and 'raw_value' in line_lower:
                    try:
                        raw_value = int(line.split()[-1])
                        if raw_value > 0:
                            issues.append({
                                'type': 'reallocated_sectors',
                                'description': f"Drive has {raw_value} reallocated sectors",
                                'severity': 'high' if raw_value > 10 else 'medium'
                            })
                    except (ValueError, IndexError):
                        pass
                
                # Check for pending sectors
                if 'current_pending_sector' in line_lower:
                    try:
                        raw_value = int(line.split()[-1])
                        if raw_value > 0:
                            issues.append({
                                'type': 'pending_sectors',
                                'description': f"Drive has {raw_value} pending sectors",
                                'severity': 'high'
                            })
                    except (ValueError, IndexError):
                        pass
                
                # Check for temperature issues
                if 'temperature_celsius' in line_lower:
                    try:
                        temp = int(line.split()[-1])
                        if temp > 60:  # High temperature threshold
                            issues.append({
                                'type': 'high_temperature',
                                'description': f"Drive temperature is high: {temp}°C",
                                'severity': 'medium' if temp < 70 else 'high'
                            })
                    except (ValueError, IndexError):
                        pass
        
        except Exception as e:
            logging.warning(f"Error parsing SMART data for drive {drive_uuid}: {e}")
        
        return issues
    
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
                        "System:kernel",
                        "enhanced_log_pattern",
                        f"Enhanced log analysis detected {pattern_type} issues",
                        "medium"
                    )
            
            # Analyze service logs
            for service_name, log_output in service_logs.items():
                if log_output and ('error' in log_output.lower() or 'failed' in log_output.lower()):
                    # Determine system entity based on service
                    if service_name == 'kubelet':
                        entity_id = "System:kubelet"
                    else:
                        entity_id = "System:storage_services"
                    
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
