"""
Tool Executors

Contains methods for executing different categories of diagnostic tools.
"""

import logging
from typing import Dict, List, Any
from .base import InformationCollectorBase

# Import LangGraph tools
from tools import (
    kubectl_get, kubectl_describe, kubectl_logs,
    kubectl_get_drive, kubectl_get_csibmnode, kubectl_get_availablecapacity,
    kubectl_get_logicalvolumegroup, kubectl_get_storageclass,
    df_command, lsblk_command, dmesg_command, journalctl_command
)


class ToolExecutors(InformationCollectorBase):
    """Tool execution methods for different diagnostic categories"""
    
    async def _execute_pod_discovery_tools(self, target_pod: str, target_namespace: str):
        """Execute pod discovery tools"""
        logging.info(f"Executing pod discovery tools for {target_namespace}/{target_pod}")
        
        # Get pod information
        pod_output = self._execute_tool_with_validation(
            kubectl_get, {
                'resource_type': 'pod',
                'resource_name': target_pod,
                'namespace': target_namespace,
                'output_format': 'yaml'
            },
            'kubectl_get_pod', 'Get target pod details'
        )
        self.collected_data['kubernetes']['target_pod'] = pod_output
        
        # Describe pod
        pod_describe = self._execute_tool_with_validation(
            kubectl_describe, {
                'resource_type': 'pod',
                'resource_name': target_pod,
                'namespace': target_namespace
            },
            'kubectl_describe_pod', 'Get detailed pod configuration and events'
        )
        self.collected_data['kubernetes']['target_pod_describe'] = pod_describe
        
        # Get pod logs
        pod_logs = self._execute_tool_with_validation(
            kubectl_logs, {
                'pod_name': target_pod,
                'namespace': target_namespace,
                'tail': 100
            },
            'kubectl_logs', 'Collect pod logs for error analysis'
        )
        self.collected_data['logs']['target_pod_logs'] = pod_logs
    
    async def _execute_volume_chain_tools(self, volume_chain: Dict[str, List[str]]):
        """Execute volume chain discovery tools"""
        logging.info("Executing volume chain discovery tools")
        
        # Get all PVCs
        if volume_chain.get('pvcs'):
            pvcs_output = self._execute_tool_with_validation(
                kubectl_get, {
                    'resource_type': 'pvc',
                    'output_format': 'yaml'
                },
                'kubectl_get_pvcs', 'Get all PVC information'
            )
            self.collected_data['kubernetes']['pvcs'] = pvcs_output
        
        # Get all PVs
        if volume_chain.get('pvs'):
            pvs_output = self._execute_tool_with_validation(
                kubectl_get, {
                    'resource_type': 'pv',
                    'output_format': 'yaml'
                },
                'kubectl_get_pvs', 'Get all PV information'
            )
            self.collected_data['kubernetes']['pvs'] = pvs_output
        
        # Get storage classes
        sc_output = self._execute_tool_with_validation(
            kubectl_get_storageclass, {
                'output_format': 'yaml'
            },
            'kubectl_get_storageclass', 'Get storage class configuration'
        )
        self.collected_data['kubernetes']['storage_classes'] = sc_output
    
    async def _execute_csi_baremetal_tools(self, drives: List[str]):
        """Execute CSI Baremetal discovery tools"""
        logging.info("Executing CSI Baremetal discovery tools")
        
        # Get drives
        drives_output = self._execute_tool_with_validation(
            kubectl_get_drive, {
                'output_format': 'yaml'
            },
            'kubectl_get_drive', 'Get CSI Baremetal drive status and health'
        )
        self.collected_data['csi_baremetal']['drives'] = drives_output
        
        # Get CSI Baremetal nodes
        csibm_nodes_output = self._execute_tool_with_validation(
            kubectl_get_csibmnode, {
                'output_format': 'yaml'
            },
            'kubectl_get_csibmnode', 'Get CSI Baremetal node mapping'
        )
        self.collected_data['csi_baremetal']['nodes'] = csibm_nodes_output
        
        # Get available capacity
        ac_output = self._execute_tool_with_validation(
            kubectl_get_availablecapacity, {
                'output_format': 'yaml'
            },
            'kubectl_get_availablecapacity', 'Get available capacity information'
        )
        self.collected_data['csi_baremetal']['available_capacity'] = ac_output
        
        # Get logical volume groups
        lvg_output = self._execute_tool_with_validation(
            kubectl_get_logicalvolumegroup, {
                'output_format': 'yaml'
            },
            'kubectl_get_logicalvolumegroup', 'Get LVG health and drive associations'
        )
        self.collected_data['csi_baremetal']['lvgs'] = lvg_output
        
        # Get CSI Baremetal volumes
        volumes_output = self._execute_tool_with_validation(
            kubectl_get, {
                'resource_type': 'volume',
                'output_format': 'yaml'
            },
            'kubectl_get_volumes', 'Get CSI Baremetal volume information with location mapping'
        )
        self.collected_data['csi_baremetal']['volumes'] = volumes_output
    
    async def _execute_node_system_tools(self, nodes: List[str]):
        """Execute node and system discovery tools"""
        logging.info("Executing node and system discovery tools")
        
        # Get nodes
        nodes_output = self._execute_tool_with_validation(
            kubectl_get, {
                'resource_type': 'node',
                'output_format': 'yaml'
            },
            'kubectl_get_nodes', 'Get node status and health'
        )
        self.collected_data['kubernetes']['nodes'] = nodes_output
        
        # Get disk usage
        df_output = self._execute_tool_with_validation(
            df_command, {
                'options': '-h'
            },
            'df_command', 'Check disk space usage'
        )
        self.collected_data['system']['disk_usage'] = df_output
        
        # Get block devices
        lsblk_output = self._execute_tool_with_validation(
            lsblk_command, {
                'options': ''
            },
            'lsblk_command', 'List block devices and mount points'
        )
        self.collected_data['system']['block_devices'] = lsblk_output
        
        # Enhanced kernel logs with comprehensive storage keywords
        storage_keywords = "disk|drive|nvme|ssd|hdd|scsi|sata|xfs|ext4|mount|error|fail|i/o|io|sector|slot|bay|controller|csi|volume"
        dmesg_output = self._execute_tool_with_validation(
            dmesg_command, {
                'options': f'| grep -iE "({storage_keywords})" | tail -50'
            },
            'dmesg_command', 'Check kernel logs for comprehensive storage-related issues'
        )
        self.collected_data['system']['kernel_logs'] = dmesg_output
        
        # Get systemd journal logs for storage services
        journal_storage_output = self._execute_tool_with_validation(
            journalctl_command, {
                'options': f'-n 100 --no-pager | grep -iE "({storage_keywords})"'
            },
            'journalctl_storage', 'Collect systemd journal logs for storage-related services'
        )
        self.collected_data['system']['journal_storage_logs'] = journal_storage_output
        
        # Get kubelet service logs for volume issues
        journal_kubelet_output = self._execute_tool_with_validation(
            journalctl_command, {
                'options': '-u kubelet -n 50 --no-pager'
            },
            'journalctl_kubelet', 'Collect kubelet service logs for volume mount issues'
        )
        self.collected_data['system']['journal_kubelet_logs'] = journal_kubelet_output
        
        # Get recent boot logs for hardware detection issues
        journal_boot_output = self._execute_tool_with_validation(
            journalctl_command, {
                'options': f'-b --no-pager | grep -iE "({storage_keywords})" | tail -30'
            },
            'journalctl_boot', 'Collect boot-time logs for hardware and storage initialization'
        )
        self.collected_data['system']['journal_boot_logs'] = journal_boot_output
    
    async def _execute_smart_data_tools(self, drives: List[str]):
        """Execute SMART data collection tools for drive health monitoring"""
        logging.info("Executing SMART data collection tools")
        
        # Get SMART data for all drives
        for drive_uuid in drives:
            # Get drive path from CSI Baremetal drive info
            drive_path = self._get_drive_path_from_uuid(drive_uuid)
            if drive_path:
                smart_output = self._execute_tool_with_validation(
                    self._execute_smartctl_command, {
                        'device_path': drive_path,
                        'options': '-a'
                    },
                    f'smartctl_{drive_uuid}', f'Collect SMART data for drive {drive_uuid}'
                )
                if 'smart_data' not in self.collected_data:
                    self.collected_data['smart_data'] = {}
                self.collected_data['smart_data'][drive_uuid] = smart_output
    
    def _get_drive_path_from_uuid(self, drive_uuid: str) -> str:
        """Extract drive path from CSI Baremetal drive information"""
        drives_output = self.collected_data.get('csi_baremetal', {}).get('drives', '')
        if drives_output and drive_uuid in drives_output:
            lines = drives_output.split('\n')
            in_drive_section = False
            for line in lines:
                if f'name: {drive_uuid}' in line:
                    in_drive_section = True
                elif in_drive_section and 'path:' in line:
                    return line.split('path:')[-1].strip()
                elif in_drive_section and line.strip() and 'name:' in line and drive_uuid not in line:
                    break
        return None
    
    def _execute_smartctl_command(self, device_path: str, options: str = '-a') -> str:
        """Execute smartctl command to get SMART data"""
        try:
            import subprocess
            cmd = ['smartctl', options, device_path]
            result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.stdout
        except Exception as e:
            return f"Error executing smartctl: {str(e)}"
    
    async def _execute_enhanced_log_analysis_tools(self):
        """Execute enhanced log analysis tools for comprehensive storage issue detection"""
        logging.info("Executing enhanced log analysis tools")
        
        # Enhanced dmesg analysis with more specific patterns
        enhanced_dmesg_patterns = [
            "nvme.*error",
            "ssd.*fail",
            "disk.*timeout",
            "scsi.*error",
            "ata.*error",
            "bad.*sector",
            "i/o.*error",
            "filesystem.*error",
            "mount.*fail",
            "csi.*error"
        ]
        
        for pattern in enhanced_dmesg_patterns:
            dmesg_output = self._execute_tool_with_validation(
                dmesg_command, {
                    'options': f'| grep -iE "{pattern}" | tail -20'
                },
                f'dmesg_{pattern.replace(".*", "_")}', f'Check kernel logs for {pattern} issues'
            )
            if 'enhanced_logs' not in self.collected_data:
                self.collected_data['enhanced_logs'] = {}
            self.collected_data['enhanced_logs'][f'dmesg_{pattern}'] = dmesg_output
        
        # Enhanced journal analysis for CSI and storage services
        csi_services = ['csi-baremetal-node', 'csi-baremetal-controller', 'kubelet']
        for service in csi_services:
            journal_output = self._execute_tool_with_validation(
                journalctl_command, {
                    'options': f'-u {service} -n 50 --no-pager'
                },
                f'journalctl_{service}', f'Collect {service} service logs for CSI issues'
            )
            if 'service_logs' not in self.collected_data:
                self.collected_data['service_logs'] = {}
            self.collected_data['service_logs'][service] = journal_output
