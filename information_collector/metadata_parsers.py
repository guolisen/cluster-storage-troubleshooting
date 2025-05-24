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
            'AccessModes': [],
            'StorageSize': '',
            'VolumeMode': 'Filesystem',
            'Phase': 'Unknown'
        }
        
        pvcs_output = self.collected_data.get('kubernetes', {}).get('pvcs', '')
        if pvcs_output:
            try:
                pvc_section = self._extract_yaml_section(pvcs_output, pvc_name)
                for line in pvc_section:
                    if 'accessModes:' in line:
                        # Parse access modes (simplified)
                        pass
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
                        if 'health:' in line:
                            drive_info['Health'] = line.split('health:')[-1].strip()
                        elif 'status:' in line:
                            drive_info['Status'] = line.split('status:')[-1].strip()
                        elif 'type:' in line:
                            drive_info['Type'] = line.split('type:')[-1].strip()
                        elif 'size:' in line:
                            try:
                                size_str = line.split('size:')[-1].strip()
                                drive_info['Size'] = int(size_str) if size_str.isdigit() else size_str
                            except (ValueError, TypeError):
                                pass
                        elif 'usage:' in line:
                            drive_info['Usage'] = line.split('usage:')[-1].strip()
                        elif 'isSystem:' in line:
                            system_str = line.split('isSystem:')[-1].strip().lower()
                            drive_info['IsSystem'] = system_str in ['true', 'yes', '1']
                        elif 'path:' in line:
                            drive_info['Path'] = line.split('path:')[-1].strip()
                        elif 'serialNumber:' in line:
                            drive_info['SerialNumber'] = line.split('serialNumber:')[-1].strip()
                        elif 'firmware:' in line:
                            drive_info['Firmware'] = line.split('firmware:')[-1].strip()
                        elif 'vid:' in line:
                            drive_info['VID'] = line.split('vid:')[-1].strip()
                        elif 'pid:' in line:
                            drive_info['PID'] = line.split('pid:')[-1].strip()
                        elif 'nodeId:' in line:
                            drive_info['NodeId'] = line.split('nodeId:')[-1].strip()
            except Exception as e:
                logging.warning(f"Error parsing drive metadata for {drive_uuid}: {e}")
        
        return drive_info
    
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
                node_section = self._extract_yaml_section(nodes_output, node_name)
                if node_section:
                    for line in node_section:
                        line = line.strip()
                        if 'Ready' in line and 'status:' in line:
                            node_info['Ready'] = 'True' in line
                        elif 'DiskPressure' in line and 'status:' in line:
                            node_info['DiskPressure'] = 'True' in line
                        elif 'MemoryPressure' in line and 'status:' in line:
                            node_info['MemoryPressure'] = 'True' in line
                        elif 'PIDPressure' in line and 'status:' in line:
                            node_info['PIDPressure'] = 'True' in line
                        elif 'NetworkUnavailable' in line and 'status:' in line:
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
