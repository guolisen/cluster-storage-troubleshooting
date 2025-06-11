"""
Metadata Parsers

Contains methods for parsing metadata from tool outputs.
"""

import logging
from typing import Dict, List, Any
from .base import InformationCollectorBase


class MetadataParsers(InformationCollectorBase):
    """Metadata parsing methods for different entity types"""
    
    def _parse_pod_metadata(self, pod_name: str, namespace: str) -> Dict[str, Any]:
        """Parse pod metadata from tool outputs"""
        metadata = {
            'RestartCount': 0,
            'Phase': 'Unknown',
            'SecurityContext': {},
            'fsGroup': None
        }
        
        pod_output = self.collected_data.get('kubernetes', {}).get('target_pod', '')
        if pod_output:
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
            except Exception as e:
                logging.warning(f"Error parsing pod metadata: {e}")
        
        return metadata
    
    def _parse_pvc_metadata(self, pvc_name: str, namespace: str) -> Dict[str, Any]:
        """Parse PVC metadata from tool outputs"""
        metadata = {
            'AccessModes': '',
            'StorageSize': '',
            'VolumeMode': 'Filesystem',
            'Phase': 'Unknown'
        }
        
        pvcs_output = self.collected_data.get('kubernetes', {}).get('pvcs', '')
        if pvcs_output:
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
            except Exception as e:
                logging.warning(f"Error parsing PVC metadata: {e}")
        
        return metadata
    
    def _parse_pv_metadata(self, pv_name: str) -> Dict[str, Any]:
        """Parse PV metadata from tool outputs"""
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
            except Exception as e:
                logging.warning(f"Error parsing PV metadata: {e}")
        
        return metadata
    
    def _parse_vol_metadata(self, vol_name: str) -> Dict[str, Any]:
        """Parse volume metadata from tool outputs"""
        ''' volume example:
        apiVersion: v1
        items:
        - apiVersion: csi-baremetal.dell.com/v1
        kind: Volume
        metadata:
            creationTimestamp: "2025-05-25T07:10:00Z"
            finalizers:
            - dell.emc.csi/volume-cleanup
            generation: 6
            name: pvc-1466401c-4595-4ae5-add7-4f6273369f9e
            namespace: default
            resourceVersion: "4964995"
            uid: b956f1b6-effa-4709-8901-9f861269d9af
        spec:
            CSIStatus: PUBLISHED
            Health: UNKNOWN
            Id: pvc-1466401c-4595-4ae5-add7-4f6273369f9e
            Location: 4924f8a4-6920-4b3f-9c4b-68141ad258dd
            LocationType: DRIVE
            Mode: FS
            NodeId: 45b1ba07-213f-4979-aa0d-5bfc66d8aeda
            OperationalStatus: MISSING
            Owners:
            - test-pod-1-0
            Size: 3839999606784
            StorageClass: NVME
            Type: xfs
            Usage: IN_USE
        kind: List
        metadata:
        resourceVersion: ""
        '''
        metadata = {
            'CSIStatus': 'UNKNOWN',
            'Health': 'UNKNOWN',
            'Id': '',
            'Location': '',
            'LocationType': 'UNKNOWN',
            'Mode': 'UNKNOWN',
            'NodeId': '',
            'OperationalStatus': 'UNKNOWN',
            'Owners': [],
            'Size': 0,
            'StorageClass': '',
            'Type': '',
            'Usage': 'UNKNOWN'
        }
    
        volumes_output = self.collected_data.get('csi_baremetal', {}).get('volumes', '')
        if volumes_output and vol_name in volumes_output:
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
            except Exception as e:
                logging.warning(f"Error parsing volume metadata for {vol_name}: {e}")
                return metadata
        else:
            logging.warning(f"Volume {vol_name} not found in CSI Baremetal volumes output")

        return metadata

    def _extract_yaml_section(self, yaml_output: str, entity_name: str) -> List[str]:
        """Extract YAML section for a specific entity"""
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
        """Parse comprehensive drive information from CSI Baremetal tool outputs"""
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
            except Exception as e:
                logging.warning(f"Error parsing drive metadata for {drive_uuid}: {e}")
        
        return drive_info
    
    def _parse_volume_metadata(self, volume_name: str, namespace: str = None) -> Dict[str, Any]:
        """Parse CSI Baremetal Volume metadata from tool outputs"""
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
            except Exception as e:
                logging.warning(f"Error parsing volume metadata for {volume_name}: {e}")
        
        return volume_info
    
    def _parse_lvg_metadata(self, lvg_name: str) -> Dict[str, Any]:
        """Parse LVG metadata from CSI Baremetal tool outputs"""
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
            except Exception as e:
                logging.warning(f"Error parsing LVG metadata for {lvg_name}: {e}")
        
        return lvg_info
    
    def _parse_ac_metadata(self, ac_name: str) -> Dict[str, Any]:
        """Parse Available Capacity metadata from CSI Baremetal tool outputs"""
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
            except Exception as e:
                logging.warning(f"Error parsing AC metadata for {ac_name}: {e}")
        
        return ac_info
    
    def _parse_csibmnode_mapping(self) -> Dict[str, str]:
        """Parse CSI Baremetal node mapping to get UUID to hostname mapping"""
        node_mapping = {}  # UUID -> hostname
        
        csibm_nodes_output = self.collected_data.get('csi_baremetal', {}).get('nodes', '')
        if csibm_nodes_output:
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
            except Exception as e:
                logging.warning(f"Error parsing CSI Baremetal node mapping: {e}")
        
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
        """Parse comprehensive node information from tool outputs"""
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
                #node_section = self._extract_yaml_section(nodes_output, node_name)
                node_section = lines = nodes_output.split('\n')
                if node_section:
                    for line in node_section:
                        line = line.strip()
                        node_info['Ready'] = 'True'
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
            except Exception as e:
                logging.warning(f"Error parsing node metadata for {node_name}: {e}")
        
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
