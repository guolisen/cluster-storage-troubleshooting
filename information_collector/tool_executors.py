"""
Tool Executors

Contains methods for executing different categories of diagnostic tools.
"""

import string
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
    
    async def _execute_volume_chain_tools(self, volume_chain: Dict[str, List[str]], target_volume_path: str = 'default'):
        """Execute volume chain discovery tools"""
        logging.info("Executing volume chain discovery tools")

        if volume_chain.get('pods', []):
            pod_namespace, pod_name = volume_chain.get('pods', [])[0].split('/', 1)
            pods_output = self._execute_tool_with_validation(
                kubectl_get, {
                    'resource_type': 'pod',
                    'resource_name': pod_name,
                    'namespace': pod_namespace,
                    'output_format': 'yaml'
                },
                'kubectl_get_pods', 'Get all PVC information'
            )
            self.collected_data['kubernetes']['pods'] = pods_output

        # Get all PVCs
        if volume_chain.get('pvcs', []):
            pvc_namespace, pvc_name = volume_chain.get('pvcs', [])[0].split('/', 1)
            pvcs_output = self._execute_tool_with_validation(
                kubectl_get, {
                    'resource_type': 'pvc',
                    'resource_name': pvc_name,
                    'namespace': pvc_namespace,
                    'output_format': 'yaml'
                },
                'kubectl_get_pvcs', 'Get all PVC information'
            )
            self.collected_data['kubernetes']['pvcs'] = pvcs_output
        
        # Get all PVs
        if volume_chain.get('pvs', []):
            pvs_output = self._execute_tool_with_validation(
                kubectl_get, {
                    'resource_type': 'pv',
                    'resource_name': volume_chain.get('pvs', [])[0],
                    'namespace': target_volume_path,
                    'output_format': 'yaml'
                },
                'kubectl_get_pvs', 'Get all PV information'
            )
            self.collected_data['kubernetes']['pvs'] = pvs_output
        
        if volume_chain.get('volumes', []):
            vol_output = self._execute_tool_with_validation(
                kubectl_get, {
                    'resource_type': 'volume',
                    'resource_name': volume_chain.get('volumes', [])[0],
                    'namespace': target_volume_path,
                    'output_format': 'yaml'
                },
                'kubectl_get_volume', 'Get all volume information'
            )
            self.collected_data['kubernetes']['volumes'] = vol_output

        if volume_chain.get('lvg', []):
            lvg_output = self._execute_tool_with_validation(
                kubectl_get, {
                    'resource_type': 'lvg',
                    'resource_name': volume_chain.get('lvg', [])[0],
                    'namespace': target_volume_path,
                    'output_format': 'yaml'
                },
                'kubectl_get_volume', 'Get all volume information'
            )
            self.collected_data['kubernetes']['lvg'] = lvg_output

        if volume_chain.get('drives', []):
            drv_output = self._execute_tool_with_validation(
                kubectl_get, {
                    'resource_type': 'drive',
                    'resource_name': volume_chain.get('drives', [])[0],
                    'output_format': 'yaml'
                },
                'kubectl_get_drive', 'Get all drive information'
            )
            self.collected_data['kubernetes']['drives'] = drv_output

        if volume_chain.get('nodes', []):
            drv_output = self._execute_tool_with_validation(
                kubectl_get, {
                    'resource_type': 'node',
                    'resource_name': volume_chain.get('nodes', [])[0],
                    'output_format': 'yaml'
                },
                'kubectl_get_node', 'Get all node information'
            )
            self.collected_data['kubernetes']['nodes'] = drv_output

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
        
        # Execute system commands on each node in the list
        for node_name in nodes:
            logging.info(f"Executing system tools on node: {node_name}")
            node_key = node_name.replace('.', '_').replace('-', '_')
            
            # Initialize node-specific data structure if not exists
            if 'system' not in self.collected_data:
                self.collected_data['system'] = {}
            if node_key not in self.collected_data['system']:
                self.collected_data['system'][node_key] = {}
            
            # Get disk usage
            df_output = self._execute_tool_with_validation(
                df_command, {
                    'node_name': node_name,
                    'options': '-h'
                },
                f'df_command_{node_key}', f'Check disk space usage on {node_name}'
            )
            self.collected_data['system'][node_key]['disk_usage'] = df_output
            
            # Get block devices
            lsblk_output = self._execute_tool_with_validation(
                lsblk_command, {
                    'node_name': node_name,
                    'options': ''
                },
                f'lsblk_command_{node_key}', f'List block devices and mount points on {node_name}'
            )
            self.collected_data['system'][node_key]['block_devices'] = lsblk_output
            
            # Enhanced kernel logs with comprehensive storage keywords
            storage_keywords = "disk|drive|nvme|ssd|hdd|scsi|sata|xfs|ext4|mount|error|fail|i/o|io|sector|slot|bay|controller|csi|volume"
            dmesg_output = self._execute_tool_with_validation(
                dmesg_command, {
                    'node_name': node_name,
                    'options': f'| grep -iE "({storage_keywords})" | tail -50'
                },
                f'dmesg_command_{node_key}', f'Check kernel logs for storage-related issues on {node_name}'
            )
            self.collected_data['system'][node_key]['kernel_logs'] = dmesg_output
            
            # Get systemd journal logs for storage services
            journal_storage_output = self._execute_tool_with_validation(
                journalctl_command, {
                    'node_name': node_name,
                    'options': f'-n 100 --no-pager | grep -iE "({storage_keywords})"'
                },
                f'journalctl_storage_{node_key}', f'Collect storage-related journal logs on {node_name}'
            )
            self.collected_data['system'][node_key]['journal_storage_logs'] = journal_storage_output
            
            # Get kubelet service logs for volume issues
            journal_kubelet_output = self._execute_tool_with_validation(
                journalctl_command, {
                    'node_name': node_name,
                    'options': '-u kubelet -n 50 --no-pager'
                },
                f'journalctl_kubelet_{node_key}', f'Collect kubelet logs on {node_name}'
            )
            self.collected_data['system'][node_key]['journal_kubelet_logs'] = journal_kubelet_output
            
            # Get recent boot logs for hardware detection issues
            journal_boot_output = self._execute_tool_with_validation(
                journalctl_command, {
                    'node_name': node_name,
                    'options': f'-b --no-pager | grep -iE "({storage_keywords})" | tail -30'
                },
                f'journalctl_boot_{node_key}', f'Collect boot-time logs on {node_name}'
            )
            self.collected_data['system'][node_key]['journal_boot_logs'] = journal_boot_output
    
    async def _execute_smart_data_tools(self, drives: List[str]):
        """Execute SMART data collection tools for drive health monitoring"""
        logging.info("Executing SMART data collection tools")
        
        # Get SMART data for all drives
        for drive_uuid in drives:
            # Get drive path and node info from CSI Baremetal drive info
            drive_info = self._get_drive_info_from_uuid(drive_uuid)
            if drive_info and drive_info.get('path'):
                node_name = drive_info.get('node')
                drive_path = drive_info.get('path')
                
                smart_output = self._execute_tool_with_validation(
                    self._execute_smartctl_command, {
                        'device_path': drive_path,
                        'options': '-a',
                        'node_name': node_name
                    },
                    f'smartctl_{drive_uuid}', f'Collect SMART data for drive {drive_uuid} on node {node_name}'
                )
                if 'smart_data' not in self.collected_data:
                    self.collected_data['smart_data'] = {}
                self.collected_data['smart_data'][drive_uuid] = smart_output
    
    def _get_drive_info_from_uuid(self, drive_uuid: str) -> Dict[str, str]:
        """Extract drive information from CSI Baremetal drive information
        
        Args:
            drive_uuid: Drive UUID to look up
            
        Returns:
            Dict with drive info including path and node
        """
        drive_info = {'path': None, 'node': None, 'serial': None}
        drives_output = self.collected_data.get('csi_baremetal', {}).get('drives', '')
        
        if drives_output and drive_uuid in drives_output:
            lines = drives_output.split('\n')
            in_drive_section = False
            
            for line in lines:
                if f'name: {drive_uuid}' in line:
                    in_drive_section = True
                elif in_drive_section:
                    # Extract path information
                    if 'path:' in line:
                        drive_info['path'] = line.split('path:')[-1].strip()
                    # Extract node information
                    elif 'node:' in line:
                        drive_info['node'] = line.split('node:')[-1].strip()
                    # Extract serial information
                    elif 'serial:' in line:
                        drive_info['serial'] = line.split('serial:')[-1].strip()
                    # Break if we've moved to another drive section
                    elif line.strip() and 'name:' in line and drive_uuid not in line:
                        break
        
        return drive_info
    
    def _get_drive_path_from_uuid(self, drive_uuid: str) -> str:
        """Extract drive path from CSI Baremetal drive information (legacy support)"""
        drive_info = self._get_drive_info_from_uuid(drive_uuid)
        return drive_info.get('path')
    
    def _execute_smartctl_command(self, device_path: str, options: str = '-a', node_name: str = None) -> str:
        """Execute smartctl command to get SMART data
        
        Args:
            device_path: Path to the device
            options: Command options
            node_name: Node hostname or IP (if None, runs locally)
            
        Returns:
            str: Command output
        """
        try:
            cmd_str = f"smartctl {options} {device_path}"
            
            # If node_name is provided, use SSH to execute on the remote node
            if node_name:
                from tools.diagnostics.hardware import ssh_execute
                return ssh_execute.invoke({"node_name": node_name, "command": cmd_str})
            else:
                # Fall back to local execution
                import subprocess
                cmd = ['smartctl', options, device_path]
                result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                return result.stdout
        except Exception as e:
            return f"Error executing smartctl: {str(e)}"
    
    async def _execute_enhanced_log_analysis_tools(self, nodes: List[str]):
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
        
        # Execute enhanced log analysis on each node
        for node_name in nodes:
            logging.info(f"Executing enhanced log analysis on node: {node_name}")
            node_key = node_name.replace('.', '_').replace('-', '_')
            
            # Initialize node-specific data structure if not exists
            if 'enhanced_logs' not in self.collected_data:
                self.collected_data['enhanced_logs'] = {}
            if node_key not in self.collected_data['enhanced_logs']:
                self.collected_data['enhanced_logs'][node_key] = {}
            
            # Process each dmesg pattern
            for pattern in enhanced_dmesg_patterns:
                pattern_key = pattern.replace(".*", "_")
                dmesg_output = self._execute_tool_with_validation(
                    dmesg_command, {
                        'node_name': node_name,
                        'options': f'| grep -iE "{pattern}" | tail -20'
                    },
                    f'dmesg_{pattern_key}_{node_key}', f'Check kernel logs for {pattern} issues on {node_name}'
                )
                self.collected_data['enhanced_logs'][node_key][f'dmesg_{pattern_key}'] = dmesg_output
            
            # Enhanced journal analysis for CSI and storage services
            csi_services = ['csi-baremetal-node', 'csi-baremetal-controller', 'kubelet']
            
            # Initialize service_logs if not exists
            if 'service_logs' not in self.collected_data:
                self.collected_data['service_logs'] = {}
            if node_key not in self.collected_data['service_logs']:
                self.collected_data['service_logs'][node_key] = {}
            
            for service in csi_services:
                journal_output = self._execute_tool_with_validation(
                    journalctl_command, {
                        'node_name': node_name,
                        'options': f'-u {service} -n 50 --no-pager'
                    },
                    f'journalctl_{service}_{node_key}', f'Collect {service} service logs on {node_name}'
                )
                self.collected_data['service_logs'][node_key][service] = journal_output
