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
    df_command, lsblk_command, dmesg_command
)


class ToolExecutors(InformationCollectorBase):
    """Tool execution methods for different diagnostic categories"""
    
    async def _execute_pod_discovery_tools(self, target_pod: str, target_namespace: str):
        """Execute pod discovery tools"""
        logging.info(f"Executing pod discovery tools for {target_namespace}/{target_pod}")
        
        # Get pod information
        pod_output = self._execute_tool_with_validation(
            kubectl_get, ['pod', target_pod, target_namespace, 'yaml'],
            'kubectl_get_pod', 'Get target pod details'
        )
        self.collected_data['kubernetes']['target_pod'] = pod_output
        
        # Describe pod
        pod_describe = self._execute_tool_with_validation(
            kubectl_describe, ['pod', target_pod, target_namespace],
            'kubectl_describe_pod', 'Get detailed pod configuration and events'
        )
        self.collected_data['kubernetes']['target_pod_describe'] = pod_describe
        
        # Get pod logs
        pod_logs = self._execute_tool_with_validation(
            kubectl_logs, [target_pod, target_namespace, None, 100],
            'kubectl_logs', 'Collect pod logs for error analysis'
        )
        self.collected_data['logs']['target_pod_logs'] = pod_logs
    
    async def _execute_volume_chain_tools(self, volume_chain: Dict[str, List[str]]):
        """Execute volume chain discovery tools"""
        logging.info("Executing volume chain discovery tools")
        
        # Get all PVCs
        if volume_chain.get('pvcs'):
            pvcs_output = self._execute_tool_with_validation(
                kubectl_get, ['pvc', None, None, 'yaml'],
                'kubectl_get_pvcs', 'Get all PVC information'
            )
            self.collected_data['kubernetes']['pvcs'] = pvcs_output
        
        # Get all PVs
        if volume_chain.get('pvs'):
            pvs_output = self._execute_tool_with_validation(
                kubectl_get, ['pv', None, None, 'yaml'],
                'kubectl_get_pvs', 'Get all PV information'
            )
            self.collected_data['kubernetes']['pvs'] = pvs_output
        
        # Get storage classes
        sc_output = self._execute_tool_with_validation(
            kubectl_get_storageclass, [None, 'yaml'],
            'kubectl_get_storageclass', 'Get storage class configuration'
        )
        self.collected_data['kubernetes']['storage_classes'] = sc_output
    
    async def _execute_csi_baremetal_tools(self, drives: List[str]):
        """Execute CSI Baremetal discovery tools"""
        logging.info("Executing CSI Baremetal discovery tools")
        
        # Get drives
        drives_output = self._execute_tool_with_validation(
            kubectl_get_drive, [None, 'yaml'],
            'kubectl_get_drive', 'Get CSI Baremetal drive status and health'
        )
        self.collected_data['csi_baremetal']['drives'] = drives_output
        
        # Get CSI Baremetal nodes
        csibm_nodes_output = self._execute_tool_with_validation(
            kubectl_get_csibmnode, [None, 'yaml'],
            'kubectl_get_csibmnode', 'Get CSI Baremetal node mapping'
        )
        self.collected_data['csi_baremetal']['nodes'] = csibm_nodes_output
        
        # Get available capacity
        ac_output = self._execute_tool_with_validation(
            kubectl_get_availablecapacity, [None, 'yaml'],
            'kubectl_get_availablecapacity', 'Get available capacity information'
        )
        self.collected_data['csi_baremetal']['available_capacity'] = ac_output
        
        # Get logical volume groups
        lvg_output = self._execute_tool_with_validation(
            kubectl_get_logicalvolumegroup, [None, 'yaml'],
            'kubectl_get_logicalvolumegroup', 'Get LVG health and drive associations'
        )
        self.collected_data['csi_baremetal']['lvgs'] = lvg_output
    
    async def _execute_node_system_tools(self, nodes: List[str]):
        """Execute node and system discovery tools"""
        logging.info("Executing node and system discovery tools")
        
        # Get nodes
        nodes_output = self._execute_tool_with_validation(
            kubectl_get, ['node', None, None, 'yaml'],
            'kubectl_get_nodes', 'Get node status and health'
        )
        self.collected_data['kubernetes']['nodes'] = nodes_output
        
        # Get disk usage
        df_output = self._execute_tool_with_validation(
            df_command, [None, '-h'],
            'df_command', 'Check disk space usage'
        )
        self.collected_data['system']['disk_usage'] = df_output
        
        # Get block devices
        lsblk_output = self._execute_tool_with_validation(
            lsblk_command, [''],
            'lsblk_command', 'List block devices and mount points'
        )
        self.collected_data['system']['block_devices'] = lsblk_output
        
        # Get kernel logs
        dmesg_output = self._execute_tool_with_validation(
            dmesg_command, ['| grep -i "error\\|disk\\|io" | tail -20'],
            'dmesg_command', 'Check kernel logs for storage errors'
        )
        self.collected_data['system']['kernel_logs'] = dmesg_output
