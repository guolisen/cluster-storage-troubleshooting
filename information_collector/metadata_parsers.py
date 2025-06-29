"""
Metadata Parsers

Contains methods for parsing metadata from tool outputs.
"""

import yaml
import logging
from typing import Dict, List, Any
from .base import InformationCollectorBase


class MetadataParsers(InformationCollectorBase):
    """Metadata parsing methods for different entity types"""
    
    def _parse_pod_metadata(self, pod_name: str, namespace: str) -> Dict[str, Any]:
        """Parse pod metadata from tool outputs using yaml package"""
        metadata = {
            'RestartCount': 0,
            'Phase': 'Unknown',
            'SecurityContext': {},
            'fsGroup': None
        }
        
        pod_output = self.collected_data.get('kubernetes', {}).get('target_pod', '')
        if pod_output:
            try:
                # Parse the YAML output
                pod_data = yaml.safe_load(pod_output)
                
                if pod_data:
                    # Extract pod phase
                    metadata['Phase'] = pod_data.get('status', {}).get('phase', 'Unknown')
                    
                    # Extract restart count from the first container status
                    container_statuses = pod_data.get('status', {}).get('containerStatuses', [])
                    if container_statuses and len(container_statuses) > 0:
                        metadata['RestartCount'] = container_statuses[0].get('restartCount', 0)
                    
                    # Extract security context and fsGroup
                    security_context = pod_data.get('spec', {}).get('securityContext', {})
                    metadata['SecurityContext'] = security_context
                    metadata['fsGroup'] = security_context.get('fsGroup')
                    
            except Exception as e:
                logging.warning(f"Error parsing pod metadata with yaml package: {e}")
                # Fallback to the old method in case of parsing errors
                try:
                    lines = pod_output.split('\n')
                    for line in lines:
                        if 'restartCount:' in line:
                            try:
                                count = int(line.split('restartCount:')[-1].strip())
                                metadata['RestartCount'] = count
                            except (ValueError, TypeError):
                                pass
                        elif 'phase:' in line:
                            metadata['Phase'] = line.split('phase:')[-1].strip()
                        elif 'fsGroup:' in line:
                            try:
                                group = int(line.split('fsGroup:')[-1].strip())
                                metadata['fsGroup'] = group
                            except (ValueError, TypeError):
                                pass
                except Exception as fallback_error:
                    logging.warning(f"Fallback parsing also failed for pod metadata: {fallback_error}")
        
        return metadata
    
    def _parse_pvc_metadata(self, pvc_name: str, namespace: str) -> Dict[str, Any]:
        """Parse PVC metadata from tool outputs using yaml package"""
        metadata = {
            'AccessModes': '',
            'StorageSize': '',
            'VolumeMode': 'Filesystem',
            'Phase': 'Unknown'
        }
        
        pvcs_output = self.collected_data.get('kubernetes', {}).get('pvcs', '')
        if pvcs_output:
            try:
                # Parse the YAML output
                pvc_data = yaml.safe_load(pvcs_output)
                
                # Find the PVC with matching name
                target_pvc = None
                if isinstance(pvc_data, dict) and 'items' in pvc_data and isinstance(pvc_data['items'], list):
                    # List of PVCs case
                    for pvc in pvc_data['items']:
                        if pvc.get('metadata', {}).get('name') == pvc_name:
                            target_pvc = pvc
                            break
                elif isinstance(pvc_data, dict) and pvc_data.get('metadata', {}).get('name') == pvc_name:
                    # Single PVC case
                    target_pvc = pvc_data
                elif isinstance(pvc_data, list):
                    # Direct list of PVCs
                    for pvc in pvc_data:
                        if pvc.get('metadata', {}).get('name') == pvc_name:
                            target_pvc = pvc
                            break
                
                if target_pvc:
                    # Extract PVC phase
                    metadata['Phase'] = target_pvc.get('status', {}).get('phase', 'Unknown')
                    
                    # Extract access modes
                    access_modes = target_pvc.get('status', {}).get('accessModes', [])
                    if access_modes and isinstance(access_modes, list) and len(access_modes) > 0:
                        metadata['AccessModes'] = access_modes[0]
                    
                    # Extract volume mode
                    metadata['VolumeMode'] = target_pvc.get('spec', {}).get('volumeMode', 'Filesystem')
                    
                    # Extract storage size
                    resources = target_pvc.get('spec', {}).get('resources', {})
                    metadata['StorageSize'] = resources.get('requests', {}).get('storage', '')
                    
            except Exception as e:
                logging.warning(f"Error parsing PVC metadata with yaml package: {e}")
                # Fallback to the old method in case of parsing errors
                try:
                    pvc_section = self._extract_yaml_section(pvcs_output, pvc_name)
                    access_mode_start = False
                    for line in pvc_section:
                        if access_mode_start:
                            # If we are in access modes section, get the next line
                            if '- ' in line:
                                access_mode = line.split(' ')[-1].strip()
                                metadata['AccessModes'] = access_mode
                                access_mode_start = False
                        elif 'accessModes:' in line:
                            # example: 
                            #  status:
                            #     accessModes:
                            #     - ReadWriteOnce
                            # the access mode in the next line write code to get the access mode
                            access_mode_start = True
                        elif 'storage:' in line and 'requests:' in pvcs_output:
                            metadata['StorageSize'] = line.split('storage:')[-1].strip()
                        elif 'phase:' in line:
                            metadata['Phase'] = line.split('phase:')[-1].strip()
                except Exception as fallback_error:
                    logging.warning(f"Fallback parsing also failed for PVC metadata: {fallback_error}")
        
        return metadata
    
    def _parse_pv_metadata(self, pv_name: str) -> Dict[str, Any]:
        """Parse PV metadata from tool outputs using yaml package"""
        metadata = {
            'Phase': 'Unknown',
            'ReclaimPolicy': 'Unknown',
            'AccessModes': [],
            'Capacity': '',
            'diskPath': '',
            'nodeAffinity': ''
        }
        
        pvs_output = self.collected_data.get('kubernetes', {}).get('pvs', '')
        if pvs_output:
            try:
                # Parse the YAML output
                pv_data = yaml.safe_load(pvs_output)
                
                # Find the PV with matching name
                target_pv = None
                if isinstance(pv_data, dict) and 'items' in pv_data and isinstance(pv_data['items'], list):
                    # List of PVs case
                    for pv in pv_data['items']:
                        if pv.get('metadata', {}).get('name') == pv_name:
                            target_pv = pv
                            break
                elif isinstance(pv_data, dict) and pv_data.get('metadata', {}).get('name') == pv_name:
                    # Single PV case
                    target_pv = pv_data
                elif isinstance(pv_data, list):
                    # Direct list of PVs
                    for pv in pv_data:
                        if pv.get('metadata', {}).get('name') == pv_name:
                            target_pv = pv
                            break
                
                if target_pv:
                    # Extract PV phase
                    metadata['Phase'] = target_pv.get('status', {}).get('phase', 'Unknown')
                    
                    # Extract reclaim policy
                    metadata['ReclaimPolicy'] = target_pv.get('spec', {}).get('persistentVolumeReclaimPolicy', 'Unknown')
                    
                    # Extract access modes
                    metadata['AccessModes'] = target_pv.get('spec', {}).get('accessModes', [])
                    
                    # Extract capacity
                    metadata['Capacity'] = target_pv.get('spec', {}).get('capacity', {}).get('storage', '')
                    
                    # Extract disk path (if available)
                    if 'local' in target_pv.get('spec', {}):
                        metadata['diskPath'] = target_pv.get('spec', {}).get('local', {}).get('path', '')
                    elif 'hostPath' in target_pv.get('spec', {}):
                        metadata['diskPath'] = target_pv.get('spec', {}).get('hostPath', {}).get('path', '')
                    
                    # Extract node affinity
                    node_selector = target_pv.get('spec', {}).get('nodeAffinity', {}).get('required', {}).get('nodeSelectorTerms', [])
                    if node_selector and len(node_selector) > 0:
                        expressions = node_selector[0].get('matchExpressions', [])
                        for expr in expressions:
                            if expr.get('key') == 'kubernetes.io/hostname' and expr.get('operator') == 'In':
                                values = expr.get('values', [])
                                if values and len(values) > 0:
                                    metadata['nodeAffinity'] = values[0]
                                    break
            except Exception as e:
                logging.warning(f"Error parsing PV metadata with yaml package: {e}")
                # Fallback to the old method in case of parsing errors
                try:
                    pv_section = self._extract_yaml_section(pvs_output, pv_name)
                    for line in pv_section:
                        if 'phase:' in line:
                            metadata['Phase'] = line.split('phase:')[-1].strip()
                        elif 'persistentVolumeReclaimPolicy:' in line:
                            metadata['ReclaimPolicy'] = line.split('persistentVolumeReclaimPolicy:')[-1].strip()
                        elif 'storage:' in line and 'capacity:' in pvs_output:
                            metadata['Capacity'] = line.split('storage:')[-1].strip()
                        elif 'path:' in line:
                            metadata['diskPath'] = line.split('path:')[-1].strip()
                        elif 'kubernetes.io/hostname:' in line:
                            metadata['nodeAffinity'] = line.split('kubernetes.io/hostname:')[-1].strip()
                except Exception as fallback_error:
                    logging.warning(f"Fallback parsing also failed for PV metadata: {fallback_error}")
        
        return metadata
    
    def _parse_vol_metadata(self, vol_name: str) -> Dict[str, Any]:
        """Parse volume metadata from tool outputs using yaml package"""
        metadata = {
            'CSIStatus': 'CSI may not support Volume',
            'Health': 'CSI may not support Volume',
            'Id': '',
            'Location': '',
            'LocationType': 'CSI may not support Volume',
            'Mode': 'CSI may not support Volume',
            'NodeId': '',
            'OperationalStatus': 'CSI may not support Volume',
            'Owners': [],
            'Size': 0,
            'StorageClass': '',
            'Type': '',
            'Usage': 'CSI may not support Volume'
        }
    
        volumes_output = self.collected_data.get('csi_baremetal', {}).get('volumes', '')
        if volumes_output and vol_name in volumes_output:
            try:
                # Parse the YAML output
                volumes_data = yaml.safe_load(volumes_output)
                
                # Find the volume with matching name
                target_volume = None
                if isinstance(volumes_data, dict) and 'items' in volumes_data and isinstance(volumes_data['items'], list):
                    # List of volumes case
                    for volume in volumes_data['items']:
                        if volume.get('metadata', {}).get('name') == vol_name:
                            target_volume = volume
                            break
                elif isinstance(volumes_data, dict) and volumes_data.get('metadata', {}).get('name') == vol_name:
                    # Single volume case
                    target_volume = volumes_data
                elif isinstance(volumes_data, list):
                    # Direct list of volumes
                    for volume in volumes_data:
                        if volume.get('metadata', {}).get('name') == vol_name:
                            target_volume = volume
                            break
                
                if target_volume:
                    # Extract volume spec properties
                    spec = target_volume.get('spec', {})
                    metadata['CSIStatus'] = spec.get('CSIStatus', 'CSI may not support Volume')
                    metadata['Health'] = spec.get('Health', 'CSI may not support Volume')
                    metadata['Id'] = spec.get('Id', '')
                    metadata['Location'] = spec.get('Location', '')
                    metadata['LocationType'] = spec.get('LocationType', 'CSI may not support Volume')
                    metadata['Mode'] = spec.get('Mode', 'CSI may not support Volume')
                    metadata['NodeId'] = spec.get('NodeId', '')
                    metadata['OperationalStatus'] = spec.get('OperationalStatus', 'CSI may not support Volume')
                    metadata['Owners'] = spec.get('Owners', [])
                    metadata['Size'] = spec.get('Size', 0)
                    metadata['StorageClass'] = spec.get('StorageClass', '')
                    metadata['Type'] = spec.get('Type', '')
                    metadata['Usage'] = spec.get('Usage', 'CSI may not support Volume')
                else:
                    logging.warning(f"Volume {vol_name} not found in parsed YAML data")
                    
            except Exception as e:
                logging.warning(f"Error parsing volume metadata for {vol_name} with yaml package: {e}")
                # Fallback to the old method in case of parsing errors
                try:
                    vol_section = self._extract_yaml_section(volumes_output, vol_name)
                    for line in vol_section:
                        if 'CSIStatus:' in line:
                            metadata['CSIStatus'] = line.split('CSIStatus:')[-1].strip()
                        elif 'Health:' in line:
                            metadata['Health'] = line.split('Health:')[-1].strip()
                        elif 'Id:' in line:
                            metadata['Id'] = line.split('Id:')[-1].strip()
                        elif 'Location:' in line:
                            metadata['Location'] = line.split('Location:')[-1].strip()
                        elif 'LocationType:' in line:
                            metadata['LocationType'] = line.split('LocationType:')[-1].strip()
                        elif 'Mode:' in line:
                            metadata['Mode'] = line.split('Mode:')[-1].strip()
                        elif 'NodeId:' in line:
                            metadata['NodeId'] = line.split('NodeId:')[-1].strip()
                        elif 'OperationalStatus:' in line:
                            metadata['OperationalStatus'] = line.split('OperationalStatus:')[-1].strip()
                        elif 'Owners:' in line:
                            owners = line.split('Owners:')[-1].strip()
                            if owners.startswith('- '):
                                metadata['Owners'] = [owner.strip() for owner in owners.split('\n') if owner.strip()]
                            else:   
                                metadata['Owners'] = [owners.strip()]
                        elif 'Size:' in line:
                            try:
                                size_str = line.split('Size:')[-1].strip()
                                metadata['Size'] = int(size_str) if size_str.isdigit() else size_str
                            except (ValueError, TypeError):
                                pass
                        elif 'StorageClass:' in line:
                            metadata['StorageClass'] = line.split('StorageClass:')[-1].strip()
                        elif 'Type:' in line:
                            metadata['Type'] = line.split('Type:')[-1].strip()
                        elif 'Usage:' in line:
                            metadata['Usage'] = line.split('Usage:')[-1].strip()
                except Exception as fallback_error:
                    logging.warning(f"Fallback parsing also failed for volume metadata: {fallback_error}")
        else:
            logging.warning(f"Volume {vol_name} not found in CSI Baremetal volumes output")

        return metadata

    def _extract_yaml_section(self, yaml_output: str, entity_name: str) -> List[str]:
        """
        Extract YAML section for a specific entity using yaml package
        
        Args:
            yaml_output: YAML string to parse
            entity_name: Name of the entity to extract
            
        Returns:
            List of lines from the extracted section (for backward compatibility)
        """
        try:
            # Parse the YAML output
            yaml_data = yaml.safe_load(yaml_output)
            
            # Handle different YAML structures
            if yaml_data is None:
                return []
                
            # Case 1: List of items (most common Kubernetes output format)
            if isinstance(yaml_data, dict) and 'items' in yaml_data and isinstance(yaml_data['items'], list):
                for item in yaml_data['items']:
                    if item.get('metadata', {}).get('name') == entity_name:
                        # Convert back to YAML string for backward compatibility
                        entity_yaml = yaml.dump(item, default_flow_style=False)
                        return entity_yaml.split('\n')
            
            # Case 2: Single item
            elif isinstance(yaml_data, dict) and yaml_data.get('metadata', {}).get('name') == entity_name:
                entity_yaml = yaml.dump(yaml_data, default_flow_style=False)
                return entity_yaml.split('\n')
            
            # Case 3: Direct list of items
            elif isinstance(yaml_data, list):
                for item in yaml_data:
                    if isinstance(item, dict) and item.get('metadata', {}).get('name') == entity_name:
                        entity_yaml = yaml.dump(item, default_flow_style=False)
                        return entity_yaml.split('\n')
            
            # Fallback to the old method if we couldn't find the entity
            logging.warning(f"Entity {entity_name} not found in YAML using structured parsing, falling back to line-by-line method")
            lines = yaml_output.split('\n')
            section_lines = []
            in_section = False
            indent_level = 0
            
            for line in lines:
                if f'name: {entity_name}' in line:
                    in_section = True
                    indent_level = len(line) - len(line.lstrip())
                    section_lines.append(line)
                elif in_section:
                    current_indent = len(line) - len(line.lstrip())
                    if line.strip() and current_indent <= indent_level and 'name:' in line:
                        # New entity started
                        break
                    section_lines.append(line)
            
            return section_lines
            
        except Exception as e:
            logging.warning(f"Error parsing YAML for entity {entity_name}: {e}")
            # Fallback to the old method in case of parsing errors
            lines = yaml_output.split('\n')
            section_lines = []
            in_section = False
            indent_level = 0
            
            for line in lines:
                if f'name: {entity_name}' in line:
                    in_section = True
                    indent_level = len(line) - len(line.lstrip())
                    section_lines.append(line)
                elif in_section:
                    current_indent = len(line) - len(line.lstrip())
                    if line.strip() and current_indent <= indent_level and 'name:' in line:
                        # New entity started
                        break
                    section_lines.append(line)
            
            return section_lines
    
    def _parse_comprehensive_drive_info(self, drive_uuid: str) -> Dict[str, Any]:
        """Parse comprehensive drive information from CSI Baremetal tool outputs using yaml package"""
        drive_info = {
            'Health': 'UNKNOWN',
            'Status': 'UNKNOWN',
            'Type': 'UNKNOWN',
            'Size': 0,
            'Usage': 'UNKNOWN',
            'IsSystem': False,
            'Path': '',
            'SerialNumber': '',
            'Firmware': '',
            'VID': '',
            'PID': '',
            'NodeId': ''
        }
        
        drives_output = self.collected_data.get('csi_baremetal', {}).get('drives', '')
        if drives_output and drive_uuid in drives_output:
            try:
                # Parse the YAML output
                drives_data = yaml.safe_load(drives_output)
                
                # Find the drive with matching UUID
                target_drive = None
                if isinstance(drives_data, dict) and 'items' in drives_data and isinstance(drives_data['items'], list):
                    # List of drives case
                    for drive in drives_data['items']:
                        if drive.get('metadata', {}).get('name') == drive_uuid:
                            target_drive = drive
                            break
                elif isinstance(drives_data, dict) and drives_data.get('metadata', {}).get('name') == drive_uuid:
                    # Single drive case
                    target_drive = drives_data
                elif isinstance(drives_data, list):
                    # Direct list of drives
                    for drive in drives_data:
                        if drive.get('metadata', {}).get('name') == drive_uuid:
                            target_drive = drive
                            break
                
                if target_drive:
                    # Extract drive spec properties
                    spec = target_drive.get('spec', {})
                    drive_info['Health'] = spec.get('Health', 'UNKNOWN')
                    drive_info['Status'] = spec.get('Status', 'UNKNOWN')
                    drive_info['Type'] = spec.get('Type', 'UNKNOWN')
                    drive_info['Size'] = spec.get('Size', 0)
                    drive_info['Usage'] = spec.get('Usage', 'UNKNOWN')
                    drive_info['IsSystem'] = spec.get('IsSystem', False)
                    drive_info['Path'] = spec.get('Path', '')
                    drive_info['SerialNumber'] = spec.get('SerialNumber', '')
                    drive_info['Firmware'] = spec.get('Firmware', '')
                    drive_info['VID'] = spec.get('VID', '')
                    drive_info['PID'] = spec.get('PID', '')
                    drive_info['NodeId'] = spec.get('NodeId', '')
                else:
                    logging.warning(f"Drive {drive_uuid} not found in parsed YAML data")
                    
            except Exception as e:
                logging.warning(f"Error parsing drive metadata for {drive_uuid} with yaml package: {e}")
                # Fallback to the old method in case of parsing errors
                try:
                    drive_section = self._extract_yaml_section(drives_output, drive_uuid)
                    if drive_section:
                        for line in drive_section:
                            line = line.strip()
                            if 'Health:' in line:
                                drive_info['Health'] = line.split('Health:')[-1].strip()
                            elif 'Status:' in line:
                                drive_info['Status'] = line.split('Status:')[-1].strip()
                            elif 'Type:' in line:
                                drive_info['Type'] = line.split('Type:')[-1].strip()
                            elif 'Size:' in line:
                                try:
                                    size_str = line.split('Size:')[-1].strip()
                                    drive_info['Size'] = int(size_str) if size_str.isdigit() else size_str
                                except (ValueError, TypeError):
                                    pass
                            elif 'Usage:' in line:
                                drive_info['Usage'] = line.split('Usage:')[-1].strip()
                            elif 'IsSystem:' in line:
                                system_str = line.split('IsSystem:')[-1].strip().lower()
                                drive_info['IsSystem'] = system_str in ['true', 'yes', '1']
                            elif 'Path:' in line:
                                drive_info['Path'] = line.split('Path:')[-1].strip()
                            elif 'SerialNumber:' in line:
                                drive_info['SerialNumber'] = line.split('SerialNumber:')[-1].strip()
                            elif 'Firmware:' in line:
                                drive_info['Firmware'] = line.split('Firmware:')[-1].strip()
                            elif 'VID:' in line:
                                drive_info['VID'] = line.split('VID:')[-1].strip()
                            elif 'PID:' in line:
                                drive_info['PID'] = line.split('PID:')[-1].strip()
                            elif 'NodeId:' in line:
                                drive_info['NodeId'] = line.split('NodeId:')[-1].strip()
                except Exception as fallback_error:
                    logging.warning(f"Fallback parsing also failed for drive metadata: {fallback_error}")
        
        return drive_info
    
    def _parse_volume_metadata(self, volume_name: str, namespace: str = None) -> Dict[str, Any]:
        """Parse CSI Baremetal Volume metadata from tool outputs using yaml package"""
        volume_info = {
            'Health': 'UNKNOWN',
            'LocationType': 'UNKNOWN',
            'Size': 0,
            'StorageClass': '',
            'Location': '',  # This is the key field - Drive UUID or LVG name
            'Usage': 'UNKNOWN',
            'Mode': 'UNKNOWN',
            'Type': 'UNKNOWN',
            'NodeId': ''
        }
        
        volumes_output = self.collected_data.get('csi_baremetal', {}).get('volumes', '')
        if volumes_output and volume_name in volumes_output:
            try:
                # Parse the YAML output
                volumes_data = yaml.safe_load(volumes_output)
                
                # Find the volume with matching name
                target_volume = None
                if isinstance(volumes_data, dict) and 'items' in volumes_data and isinstance(volumes_data['items'], list):
                    # List of volumes case
                    for volume in volumes_data['items']:
                        if volume.get('metadata', {}).get('name') == volume_name:
                            target_volume = volume
                            break
                elif isinstance(volumes_data, dict) and volumes_data.get('metadata', {}).get('name') == volume_name:
                    # Single volume case
                    target_volume = volumes_data
                elif isinstance(volumes_data, list):
                    # Direct list of volumes
                    for volume in volumes_data:
                        if volume.get('metadata', {}).get('name') == volume_name:
                            target_volume = volume
                            break
                
                if target_volume:
                    # Extract volume spec properties
                    spec = target_volume.get('spec', {})
                    volume_info['Health'] = spec.get('health', 'UNKNOWN')
                    volume_info['LocationType'] = spec.get('locationType', 'UNKNOWN')
                    volume_info['Size'] = spec.get('size', 0)
                    volume_info['StorageClass'] = spec.get('storageClass', '')
                    volume_info['Location'] = spec.get('location', '')
                    volume_info['Usage'] = spec.get('usage', 'UNKNOWN')
                    volume_info['Mode'] = spec.get('mode', 'UNKNOWN')
                    volume_info['Type'] = spec.get('type', 'UNKNOWN')
                    volume_info['NodeId'] = spec.get('nodeId', '')
                else:
                    logging.warning(f"Volume {volume_name} not found in parsed YAML data")
                    
            except Exception as e:
                logging.warning(f"Error parsing volume metadata for {volume_name} with yaml package: {e}")
                # Fallback to the old method in case of parsing errors
                try:
                    volume_section = self._extract_yaml_section(volumes_output, volume_name)
                    if volume_section:
                        for line in volume_section:
                            line = line.strip()
                            if 'health:' in line:
                                volume_info['Health'] = line.split('health:')[-1].strip()
                            elif 'locationType:' in line:
                                volume_info['LocationType'] = line.split('locationType:')[-1].strip()
                            elif 'size:' in line:
                                try:
                                    size_str = line.split('size:')[-1].strip()
                                    volume_info['Size'] = int(size_str) if size_str.isdigit() else size_str
                                except (ValueError, TypeError):
                                    pass
                            elif 'storageClass:' in line:
                                volume_info['StorageClass'] = line.split('storageClass:')[-1].strip()
                            elif 'location:' in line:
                                volume_info['Location'] = line.split('location:')[-1].strip()
                            elif 'usage:' in line:
                                volume_info['Usage'] = line.split('usage:')[-1].strip()
                            elif 'mode:' in line:
                                volume_info['Mode'] = line.split('mode:')[-1].strip()
                            elif 'type:' in line:
                                volume_info['Type'] = line.split('type:')[-1].strip()
                            elif 'nodeId:' in line:
                                volume_info['NodeId'] = line.split('nodeId:')[-1].strip()
                except Exception as fallback_error:
                    logging.warning(f"Fallback parsing also failed for volume metadata: {fallback_error}")
        
        return volume_info
    
    def _parse_lvg_metadata(self, lvg_name: str) -> Dict[str, Any]:
        """Parse LVG metadata from CSI Baremetal tool outputs using yaml package"""
        lvg_info = {
            'Health': 'UNKNOWN',
            'Size': 0,
            'VolumeGroup': '',
            'Node': '',
            'Locations': []  # Array of Drive UUIDs
        }
        
        lvgs_output = self.collected_data.get('csi_baremetal', {}).get('lvgs', '')
        if lvgs_output and lvg_name in lvgs_output:
            try:
                # Parse the YAML output
                lvgs_data = yaml.safe_load(lvgs_output)
                
                # Find the LVG with matching name
                target_lvg = None
                if isinstance(lvgs_data, dict) and 'items' in lvgs_data and isinstance(lvgs_data['items'], list):
                    # List of LVGs case
                    for lvg in lvgs_data['items']:
                        if lvg.get('metadata', {}).get('name') == lvg_name:
                            target_lvg = lvg
                            break
                elif isinstance(lvgs_data, dict) and lvgs_data.get('metadata', {}).get('name') == lvg_name:
                    # Single LVG case
                    target_lvg = lvgs_data
                elif isinstance(lvgs_data, list):
                    # Direct list of LVGs
                    for lvg in lvgs_data:
                        if lvg.get('metadata', {}).get('name') == lvg_name:
                            target_lvg = lvg
                            break
                
                if target_lvg:
                    # Extract LVG spec properties
                    spec = target_lvg.get('spec', {})
                    lvg_info['Health'] = spec.get('health', 'UNKNOWN')
                    lvg_info['Size'] = spec.get('size', 0)
                    lvg_info['VolumeGroup'] = spec.get('volumeGroup', '')
                    lvg_info['Node'] = spec.get('node', '')
                    lvg_info['Locations'] = spec.get('locations', [])
                else:
                    logging.warning(f"LVG {lvg_name} not found in parsed YAML data")
                    
            except Exception as e:
                logging.warning(f"Error parsing LVG metadata for {lvg_name} with yaml package: {e}")
                # Fallback to the old method in case of parsing errors
                try:
                    lvg_section = self._extract_yaml_section(lvgs_output, lvg_name)
                    if lvg_section:
                        in_locations_array = False
                        for line in lvg_section:
                            line = line.strip()
                            if 'health:' in line:
                                lvg_info['Health'] = line.split('health:')[-1].strip()
                            elif 'size:' in line:
                                try:
                                    size_str = line.split('size:')[-1].strip()
                                    lvg_info['Size'] = int(size_str) if size_str.isdigit() else size_str
                                except (ValueError, TypeError):
                                    pass
                            elif 'volumeGroup:' in line:
                                lvg_info['VolumeGroup'] = line.split('volumeGroup:')[-1].strip()
                            elif 'node:' in line:
                                lvg_info['Node'] = line.split('node:')[-1].strip()
                            elif 'locations:' in line:
                                in_locations_array = True
                            elif in_locations_array and line.startswith('- '):
                                # Extract drive UUID from array item
                                drive_uuid = line[2:].strip()
                                if drive_uuid:
                                    lvg_info['Locations'].append(drive_uuid)
                            elif in_locations_array and not line.startswith('- ') and not line.startswith(' '):
                                # End of locations array
                                in_locations_array = False
                except Exception as fallback_error:
                    logging.warning(f"Fallback parsing also failed for LVG metadata: {fallback_error}")
        
        return lvg_info
    
    def _parse_ac_metadata(self, ac_name: str) -> Dict[str, Any]:
        """Parse Available Capacity metadata from CSI Baremetal tool outputs using yaml package"""
        ac_info = {
            'Size': 0,
            'StorageClass': '',
            'Location': '',  # Drive UUID or LVG name
            'Node': '',
            'NodeId': ''
        }
        
        ac_output = self.collected_data.get('csi_baremetal', {}).get('available_capacity', '')
        if ac_output and ac_name in ac_output:
            try:
                # Parse the YAML output
                ac_data = yaml.safe_load(ac_output)
                
                # Find the AC with matching name
                target_ac = None
                if isinstance(ac_data, dict) and 'items' in ac_data and isinstance(ac_data['items'], list):
                    # List of ACs case
                    for ac in ac_data['items']:
                        if ac.get('metadata', {}).get('name') == ac_name:
                            target_ac = ac
                            break
                elif isinstance(ac_data, dict) and ac_data.get('metadata', {}).get('name') == ac_name:
                    # Single AC case
                    target_ac = ac_data
                elif isinstance(ac_data, list):
                    # Direct list of ACs
                    for ac in ac_data:
                        if ac.get('metadata', {}).get('name') == ac_name:
                            target_ac = ac
                            break
                
                if target_ac:
                    # Extract AC spec properties
                    spec = target_ac.get('spec', {})
                    ac_info['Size'] = spec.get('size', 0)
                    ac_info['StorageClass'] = spec.get('storageClass', '')
                    ac_info['Location'] = spec.get('location', '')
                    ac_info['Node'] = spec.get('node', '')
                    ac_info['NodeId'] = spec.get('nodeId', '')
                else:
                    logging.warning(f"AC {ac_name} not found in parsed YAML data")
                    
            except Exception as e:
                logging.warning(f"Error parsing AC metadata for {ac_name} with yaml package: {e}")
                # Fallback to the old method in case of parsing errors
                try:
                    ac_section = self._extract_yaml_section(ac_output, ac_name)
                    if ac_section:
                        for line in ac_section:
                            line = line.strip()
                            if 'size:' in line:
                                try:
                                    size_str = line.split('size:')[-1].strip()
                                    ac_info['Size'] = int(size_str) if size_str.isdigit() else size_str
                                except (ValueError, TypeError):
                                    pass
                            elif 'storageClass:' in line:
                                ac_info['StorageClass'] = line.split('storageClass:')[-1].strip()
                            elif 'location:' in line:
                                ac_info['Location'] = line.split('location:')[-1].strip()
                            elif 'node:' in line:
                                ac_info['Node'] = line.split('node:')[-1].strip()
                            elif 'nodeId:' in line:
                                ac_info['NodeId'] = line.split('nodeId:')[-1].strip()
                except Exception as fallback_error:
                    logging.warning(f"Fallback parsing also failed for AC metadata: {fallback_error}")
        
        return ac_info
    
    def _parse_csibmnode_mapping(self) -> Dict[str, str]:
        """Parse CSI Baremetal node mapping to get UUID to hostname mapping using yaml package"""
        node_mapping = {}  # UUID -> hostname
        
        csibm_nodes_output = self.collected_data.get('csi_baremetal', {}).get('nodes', '')
        if csibm_nodes_output:
            try:
                # Parse the YAML output
                nodes_data = yaml.safe_load(csibm_nodes_output)
                
                # Process CSI Baremetal node data
                if nodes_data:
                    # Handle different YAML structures
                    node_items = []
                    if isinstance(nodes_data, dict) and 'items' in nodes_data and isinstance(nodes_data['items'], list):
                        # List of nodes case
                        node_items = nodes_data['items']
                    elif isinstance(nodes_data, list):
                        # Direct list of nodes
                        node_items = nodes_data
                    
                    # Extract UUID to hostname mapping
                    for node in node_items:
                        if isinstance(node, dict):
                            node_uuid = node.get('metadata', {}).get('name', '')
                            # Check if it's a UUID format (typically long string with hyphens)
                            if len(node_uuid) > 30:
                                hostname = node.get('spec', {}).get('hostname', '')
                                if hostname:
                                    node_mapping[node_uuid] = hostname
                    
            except Exception as e:
                logging.warning(f"Error parsing CSI Baremetal node mapping with yaml package: {e}")
                # Fallback to the old method in case of parsing errors
                try:
                    lines = csibm_nodes_output.split('\n')
                    current_uuid = None
                    current_hostname = None
                    
                    for line in lines:
                        line = line.strip()
                        if 'name:' in line and len(line.split('name:')[-1].strip()) > 30:  # UUID format
                            current_uuid = line.split('name:')[-1].strip()
                        elif 'hostname:' in line:
                            current_hostname = line.split('hostname:')[-1].strip()
                            if current_uuid and current_hostname:
                                node_mapping[current_uuid] = current_hostname
                                current_uuid = None
                                current_hostname = None
                except Exception as fallback_error:
                    logging.warning(f"Fallback parsing also failed for CSI Baremetal node mapping: {fallback_error}")
        
        return node_mapping
    
    def _parse_smart_data(self, drive_uuid: str) -> Dict[str, Any]:
        """Parse SMART data for drive health analysis"""
        smart_info = {
            'PowerOnHours': 0,
            'PowerCycleCount': 0,
            'ReallocatedSectorCount': 0,
            'CurrentPendingSectorCount': 0,
            'UncorrectableErrorCount': 0,
            'Temperature': 0,
            'OverallHealth': 'UNKNOWN',
            'SmartStatus': 'UNKNOWN'
        }
        
        smart_data = self.collected_data.get('smart_data', {}).get(drive_uuid, '')
        if smart_data:
            try:
                lines = smart_data.split('\n')
                for line in lines:
                    line = line.strip()
                    line_lower = line.lower()
                    
                    # Overall SMART status
                    if 'smart overall-health self-assessment test result:' in line_lower:
                        smart_info['SmartStatus'] = line.split(':')[-1].strip()
                        smart_info['OverallHealth'] = 'GOOD' if 'passed' in line_lower else 'BAD'
                    
                    # Power on hours
                    elif 'power_on_hours' in line_lower or '9 power_on_hours' in line_lower:
                        parts = line.split()
                        if len(parts) >= 10:
                            try:
                                smart_info['PowerOnHours'] = int(parts[9])
                            except (ValueError, IndexError):
                                pass
                    
                    # Power cycle count
                    elif 'power_cycle_count' in line_lower or '12 power_cycle_count' in line_lower:
                        parts = line.split()
                        if len(parts) >= 10:
                            try:
                                smart_info['PowerCycleCount'] = int(parts[9])
                            except (ValueError, IndexError):
                                pass
                    
                    # Reallocated sector count
                    elif 'reallocated_sector_ct' in line_lower or '5 reallocated_sector_ct' in line_lower:
                        parts = line.split()
                        if len(parts) >= 10:
                            try:
                                smart_info['ReallocatedSectorCount'] = int(parts[9])
                            except (ValueError, IndexError):
                                pass
                    
                    # Current pending sector count
                    elif 'current_pending_sector' in line_lower or '197 current_pending_sector' in line_lower:
                        parts = line.split()
                        if len(parts) >= 10:
                            try:
                                smart_info['CurrentPendingSectorCount'] = int(parts[9])
                            except (ValueError, IndexError):
                                pass
                    
                    # Uncorrectable error count
                    elif 'offline_uncorrectable' in line_lower or '198 offline_uncorrectable' in line_lower:
                        parts = line.split()
                        if len(parts) >= 10:
                            try:
                                smart_info['UncorrectableErrorCount'] = int(parts[9])
                            except (ValueError, IndexError):
                                pass
                    
                    # Temperature
                    elif 'temperature_celsius' in line_lower or '194 temperature_celsius' in line_lower:
                        parts = line.split()
                        if len(parts) >= 10:
                            try:
                                smart_info['Temperature'] = int(parts[9])
                            except (ValueError, IndexError):
                                pass
            except Exception as e:
                logging.warning(f"Error parsing SMART data for {drive_uuid}: {e}")
        
        return smart_info
    
    def _parse_comprehensive_node_info(self, node_name: str) -> Dict[str, Any]:
        """
        Parse comprehensive node information from tool outputs using YAML parser
        
        Args:
            node_name: Name of the node to parse information for
            
        Returns:
            Dictionary containing parsed node information
        """
        node_info = {
            'Ready': False,
            'DiskPressure': False,
            'MemoryPressure': False,
            'PIDPressure': False,
            'NetworkUnavailable': False,
            'KubeletVersion': '',
            'ContainerRuntimeVersion': '',
            'KernelVersion': '',
            'OSImage': '',
            'Architecture': '',
            'Capacity': {},
            'Allocatable': {}
        }
        
        nodes_output = self.collected_data.get('kubernetes', {}).get('nodes', '')
        if nodes_output and node_name in nodes_output:
            try:
                # Parse the YAML output
                nodes_data = yaml.safe_load(nodes_output)
                
                # Find the node with matching name
                target_node = None
                if isinstance(nodes_data, dict) and 'items' in nodes_data and isinstance(nodes_data['items'], list):
                    # List of nodes case
                    for node in nodes_data['items']:
                        if node.get('metadata', {}).get('name') == node_name:
                            target_node = node
                            break
                elif isinstance(nodes_data, list):
                    # Direct list of nodes
                    for node in nodes_data:
                        if node.get('metadata', {}).get('name') == node_name:
                            target_node = node
                            break
                
                if not target_node:
                    logging.warning(f"Node {node_name} not found in the provided YAML output")
                    return node_info
                
                # Extract status information
                status = target_node.get('status', {})
                
                # Extract conditions
                conditions = status.get('conditions', [])
                for condition in conditions:
                    condition_type = condition.get('type', '')
                    condition_status = condition.get('status', '').lower() == 'true'
                    
                    if condition_type == 'Ready':
                        node_info['Ready'] = condition_status
                    elif condition_type == 'DiskPressure':
                        node_info['DiskPressure'] = condition_status
                    elif condition_type == 'MemoryPressure':
                        node_info['MemoryPressure'] = condition_status
                    elif condition_type == 'PIDPressure':
                        node_info['PIDPressure'] = condition_status
                    elif condition_type == 'NetworkUnavailable':
                        node_info['NetworkUnavailable'] = condition_status
                
                # Extract node info
                node_info_data = target_node.get('status', {}).get('nodeInfo', {})
                node_info['KubeletVersion'] = node_info_data.get('kubeletVersion', '')
                node_info['ContainerRuntimeVersion'] = node_info_data.get('containerRuntimeVersion', '')
                node_info['KernelVersion'] = node_info_data.get('kernelVersion', '')
                node_info['OSImage'] = node_info_data.get('osImage', '')
                node_info['Architecture'] = node_info_data.get('architecture', '')
                
                # Extract capacity and allocatable resources
                node_info['Capacity'] = status.get('capacity', {})
                node_info['Allocatable'] = status.get('allocatable', {})
                
            except Exception as e:
                logging.warning(f"Error parsing node metadata for {node_name} using YAML parser: {e}")
                # Fallback to the old method in case of parsing errors
                try:
                    node_section = nodes_output.split('\n')
                    for line in node_section:
                        line = line.strip()
                        if 'ready' in line and 'status:' in line:
                            node_info['Ready'] = 'True' in line
                        elif 'diskPressure' in line and 'status:' in line:
                            node_info['DiskPressure'] = 'True' in line
                        elif 'memoryPressure' in line and 'status:' in line:
                            node_info['MemoryPressure'] = 'True' in line
                        elif 'PIDPressure' in line and 'status:' in line:
                            node_info['PIDPressure'] = 'True' in line
                        elif 'networkUnavailable' in line and 'status:' in line:
                            node_info['NetworkUnavailable'] = 'True' in line
                        elif 'kubeletVersion:' in line:
                            node_info['KubeletVersion'] = line.split('kubeletVersion:')[-1].strip()
                        elif 'containerRuntimeVersion:' in line:
                            node_info['ContainerRuntimeVersion'] = line.split('containerRuntimeVersion:')[-1].strip()
                        elif 'kernelVersion:' in line:
                            node_info['KernelVersion'] = line.split('kernelVersion:')[-1].strip()
                        elif 'osImage:' in line:
                            node_info['OSImage'] = line.split('osImage:')[-1].strip()
                        elif 'architecture:' in line:
                            node_info['Architecture'] = line.split('architecture:')[-1].strip()
                except Exception as fallback_error:
                    logging.warning(f"Fallback parsing also failed for node {node_name}: {fallback_error}")
        
        return node_info
    
    def _parse_dmesg_issues(self) -> List[Dict[str, Any]]:
        """Parse dmesg logs to identify storage-related issues"""
        issues = []
        dmesg_output = self.collected_data.get('system', {}).get('kernel_logs', '')
        
        if not dmesg_output:
            return issues
        
        try:
            lines = dmesg_output.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Parse timestamp and message
                issue = self._extract_dmesg_issue(line)
                if issue:
                    issues.append(issue)
        
        except Exception as e:
            logging.warning(f"Error parsing dmesg issues: {e}")
        
        return issues
    
    def _extract_dmesg_issue(self, line: str) -> Dict[str, Any]:
        """Extract issue information from a dmesg log line"""
        issue = None
        line_lower = line.lower()
        
        # Disk/Drive hardware errors
        if any(keyword in line_lower for keyword in ['disk error', 'drive error', 'bad sector', 'i/o error']):
            severity = 'critical' if 'bad sector' in line_lower else 'high'
            issue = {
                'type': 'disk_hardware_error',
                'severity': severity,
                'description': f"Hardware disk error detected: {line}",
                'raw_log': line,
                'source': 'dmesg'
            }
        
        # NVMe/SSD specific issues
        elif any(keyword in line_lower for keyword in ['nvme', 'ssd']) and any(error in line_lower for error in ['error', 'fail', 'timeout']):
            issue = {
                'type': 'nvme_ssd_error',
                'severity': 'high',
                'description': f"NVMe/SSD error detected: {line}",
                'raw_log': line,
                'source': 'dmesg'
            }
        
        # Filesystem errors
        elif any(keyword in line_lower for keyword in ['xfs', 'ext4']) and any(error in line_lower for error in ['error', 'corrupt', 'fail']):
            issue = {
                'type': 'filesystem_error',
                'severity': 'high',
                'description': f"Filesystem error detected: {line}",
                'raw_log': line,
                'source': 'dmesg'
            }
        
        # I/O timeout issues
        elif 'timeout' in line_lower and any(keyword in line_lower for keyword in ['i/o', 'io', 'disk', 'drive']):
            issue = {
                'type': 'io_timeout',
                'severity': 'medium',
                'description': f"I/O timeout detected: {line}",
                'raw_log': line,
                'source': 'dmesg'
            }
        
        # Controller/SCSI/SATA issues
        elif any(keyword in line_lower for keyword in ['controller', 'scsi', 'sata']) and any(error in line_lower for error in ['error', 'fail', 'reset']):
            issue = {
                'type': 'controller_error',
                'severity': 'high',
                'description': f"Storage controller error detected: {line}",
                'raw_log': line,
                'source': 'dmesg'
            }
        
        return issue
    
    def _parse_journal_issues(self) -> List[Dict[str, Any]]:
        """Parse systemd journal logs to identify storage and service issues"""
        issues = []
        
        # Parse different journal log types
        storage_logs = self.collected_data.get('system', {}).get('journal_storage_logs', '')
        kubelet_logs = self.collected_data.get('system', {}).get('journal_kubelet_logs', '')
        boot_logs = self.collected_data.get('system', {}).get('journal_boot_logs', '')
        
        # Parse storage-related journal logs
        if storage_logs:
            issues.extend(self._extract_journal_storage_issues(storage_logs))
        
        # Parse kubelet service logs
        if kubelet_logs:
            issues.extend(self._extract_journal_kubelet_issues(kubelet_logs))
        
        # Parse boot-time hardware detection issues
        if boot_logs:
            issues.extend(self._extract_journal_boot_issues(boot_logs))
        
        return issues
    
    def _extract_journal_storage_issues(self, logs: str) -> List[Dict[str, Any]]:
        """Extract storage-related issues from journal logs"""
        issues = []
        
        try:
            lines = logs.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                line_lower = line.lower()
                
                # Storage service failures
                if any(keyword in line_lower for keyword in ['failed', 'error', 'timeout']) and any(service in line_lower for service in ['mount', 'umount', 'filesystem']):
                    issues.append({
                        'type': 'storage_service_error',
                        'severity': 'high',
                        'description': f"Storage service error: {line}",
                        'raw_log': line,
                        'source': 'journal_storage'
                    })
                
                # Disk/drive detection issues
                elif any(keyword in line_lower for keyword in ['disk', 'drive', 'nvme', 'ssd']) and 'detected' in line_lower:
                    issues.append({
                        'type': 'hardware_detection',
                        'severity': 'low',
                        'description': f"Hardware detection event: {line}",
                        'raw_log': line,
                        'source': 'journal_storage'
                    })
        
        except Exception as e:
            logging.warning(f"Error parsing journal storage issues: {e}")
        
        return issues
    
    def _extract_journal_kubelet_issues(self, logs: str) -> List[Dict[str, Any]]:
        """Extract kubelet volume-related issues from journal logs"""
        issues = []
        
        try:
            lines = logs.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                line_lower = line.lower()
                
                # Volume mount/attach failures
                if any(keyword in line_lower for keyword in ['volume', 'mount', 'attach']) and any(error in line_lower for error in ['failed', 'error', 'timeout']):
                    issues.append({
                        'type': 'kubelet_volume_error',
                        'severity': 'high',
                        'description': f"Kubelet volume error: {line}",
                        'raw_log': line,
                        'source': 'journal_kubelet'
                    })
                
                # CSI driver issues
                elif 'csi' in line_lower and any(error in line_lower for error in ['failed', 'error', 'timeout']):
                    issues.append({
                        'type': 'csi_driver_error',
                        'severity': 'high',
                        'description': f"CSI driver error: {line}",
                        'raw_log': line,
                        'source': 'journal_kubelet'
                    })
        
        except Exception as e:
            logging.warning(f"Error parsing journal kubelet issues: {e}")
        
        return issues
    
    def _extract_journal_boot_issues(self, logs: str) -> List[Dict[str, Any]]:
        """Extract boot-time hardware and storage initialization issues"""
        issues = []
        
        try:
            lines = logs.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                line_lower = line.lower()
                
                # Hardware initialization failures
                if any(keyword in line_lower for keyword in ['failed to initialize', 'hardware error', 'device not found']):
                    issues.append({
                        'type': 'boot_hardware_error',
                        'severity': 'critical',
                        'description': f"Boot-time hardware error: {line}",
                        'raw_log': line,
                        'source': 'journal_boot'
                    })
                
                # Drive/controller detection issues
                elif any(keyword in line_lower for keyword in ['drive', 'controller', 'nvme', 'ssd']) and any(issue in line_lower for issue in ['not found', 'failed', 'error']):
                    issues.append({
                        'type': 'boot_storage_detection',
                        'severity': 'high',
                        'description': f"Boot-time storage detection issue: {line}",
                        'raw_log': line,
                        'source': 'journal_boot'
                    })
        
        except Exception as e:
            logging.warning(f"Error parsing journal boot issues: {e}")
        
        return issues
