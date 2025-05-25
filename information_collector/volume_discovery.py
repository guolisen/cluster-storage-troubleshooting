"""
Volume Dependency Discovery

Handles discovery of volume dependency chains starting from target pods.
"""

import logging
import time
from typing import Dict, List, Any
from .base import InformationCollectorBase

# Import LangGraph tools
from tools import kubectl_get


class VolumeDiscovery(InformationCollectorBase):
    """Volume dependency chain discovery functionality"""
    
    def _discover_volume_dependency_chain(self, target_pod: str, target_namespace: str) -> Dict[str, List[str]]:
        """
        Discover the volume dependency chain starting from target pod
        
        Args:
            target_pod: Target pod name
            target_namespace: Target pod namespace
            
        Returns:
            Dict[str, List[str]]: Volume dependency chain (pod -> pvcs -> pvs -> drives -> nodes)
        """
        chain = {
            'pods': [],
            'pvcs': [],
            'pvs': [],
            'volumes': [],
            'lvg': [],
            'drives': [],
            'nodes': [],
            'storage_classes': []
        }
        
        try:
            # Start with target pod
            if target_pod and target_namespace:
                chain['pods'].append(f"{target_namespace}/{target_pod}")
                
                # Get pod details to find PVCs
                pod_output = self._execute_tool_with_validation(
                    kubectl_get, {
                        'resource_type': 'pod',
                        'resource_name': target_pod,
                        'namespace': target_namespace,
                        'output_format': 'yaml'
                    },
                    'kubectl_get_pod', f'Get details for target pod {target_pod}'
                )
                
                # Parse pod output to find PVCs (simplified parsing)
                if pod_output and not pod_output.startswith("Error:"):
                    # Extract PVC names from pod spec (this is a simplified approach)
                    lines = pod_output.split('\n')
                    for line in lines:
                        if 'claimName:' in line:
                            pvc_name = line.split('claimName:')[-1].strip()
                            if pvc_name:
                                chain['pvcs'].append(f"{target_namespace}/{pvc_name}")
                        if 'nodeName:' in line:
                            node_name = line.split('nodeName:')[-1].strip()
                            if node_name:
                                chain['nodes'].append(f"{node_name}")
               
                # For each PVC, find bound PV
                for pvc_key in chain['pvcs']:
                    pvc_name = pvc_key.split('/')[-1]
                    pvc_output = self._execute_tool_with_validation(
                        kubectl_get, {
                            'resource_type': 'pvc',
                            'resource_name': pvc_name,
                            'namespace': target_namespace,
                            'output_format': 'yaml'
                        },
                        'kubectl_get_pvc', f'Get PVC details for {pvc_name}'
                    )
                    
                    if pvc_output and not pvc_output.startswith("Error:"):
                        # Extract PV name and storage class
                        lines = pvc_output.split('\n')
                        for line in lines:
                            if 'volumeName:' in line:
                                pv_name = line.split('volumeName:')[-1].strip()
                                if pv_name:
                                    chain['pvs'].append(pv_name)
                                    chain['volumes'].append(pv_name)
                            elif 'storageClassName:' in line:
                                sc_name = line.split('storageClassName:')[-1].strip()
                                if sc_name and sc_name not in chain['storage_classes']:
                                    chain['storage_classes'].append(sc_name)
                
                # For each PV, find associated drive and node
                for pv_name in chain['pvs']:
                    pv_output = self._execute_tool_with_validation(
                        kubectl_get, {
                            'resource_type': 'pv',
                            'resource_name': pv_name,
                            'output_format': 'yaml'
                        },
                        'kubectl_get_pv', f'Get PV details for {pv_name}'
                    )

                    vol_output = self._execute_tool_with_validation(
                        kubectl_get, {
                            'resource_type': 'volume',
                            'namespace': target_namespace,
                            'resource_name': pv_name,
                            'output_format': 'yaml'
                        },
                        'kubectl_get_volume', f'Get Volume details for {pv_name}'
                    )
                    
                    if vol_output and not vol_output.startswith("error:") and not vol_output.startswith("Error:"):
                        # Extract drive UUID and node affinity
                        lines = vol_output.split('\n')
                        locType = None
                        for line in lines:
                            if 'LocationType:' in line:
                                locType = line.split('LocationType:')[-1].strip()
                        
                        lvg_name = None
                        if locType and locType == 'DRIVE':
                            for line in lines:
                                if 'Location:' in line:
                                    drive_name = line.split('Location:')[-1].strip()
                                    if drive_name and drive_name not in chain['drives']:
                                        chain['drives'].append(drive_name)
                        elif locType and locType == 'LVG':
                            for line in lines:
                                if 'Location:' in line:
                                    lvg_name = line.split('Location:')[-1].strip()
                                    if lvg_name and lvg_name not in chain['lvg']:
                                        chain['lvg'].append(lvg_name)
                        
                        if lvg_name:
                            lvg_output = self._execute_tool_with_validation(
                                kubectl_get, {
                                    'resource_type': 'lvg',
                                    'namespace': target_namespace,
                                    'resource_name': lvg_name,
                                    'output_format': 'yaml'
                                },
                                'kubectl_get_lvg', f'Get LVG details for {lvg_name}'
                            )
                            if lvg_output and not lvg_output.startswith("Error:"):
                                # Extract drives from LVG
                                lines = lvg_output.split('\n')
                                drivestart = False
                                for line in lines:
                                    if 'Locations:' in line and not drivestart:
                                        drivestart = True
                                    elif drivestart and line.strip() != '':
                                        # - 0fcefbaa-7bc9-49b0-96de-bc8067445497
                                        drive_name = line.strip().lstrip('- ').strip()
                                        if drive_name and drive_name not in chain['drives']:
                                            chain['drives'].append(drive_name)
                                        else:
                                            drivestart = False

        except Exception as e:
            error_msg = f"Error discovering volume dependency chain: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
        
        logging.info(f"Volume dependency chain discovered: {len(chain['pvcs'])} PVCs, {len(chain['pvs'])} PVs, {len(chain['drives'])} drives")
        return chain
