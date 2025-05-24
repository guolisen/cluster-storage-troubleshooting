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
                    
                    if pv_output and not pv_output.startswith("Error:"):
                        # Extract drive UUID and node affinity
                        lines = pv_output.split('\n')
                        for line in lines:
                            if 'kubernetes.io/hostname:' in line:
                                node_name = line.split('kubernetes.io/hostname:')[-1].strip()
                                if node_name and node_name not in chain['nodes']:
                                    chain['nodes'].append(node_name)
                            elif 'baremetal-csi' in line and 'uuid' in line.lower():
                                # Extract drive UUID (simplified)
                                for part in line.split():
                                    if len(part) > 10 and '-' in part:  # UUID-like pattern
                                        if part not in chain['drives']:
                                            chain['drives'].append(part)
        except Exception as e:
            error_msg = f"Error discovering volume dependency chain: {str(e)}"
            logging.error(error_msg)
            self.collected_data['errors'].append(error_msg)
        
        logging.info(f"Volume dependency chain discovered: {len(chain['pvcs'])} PVCs, {len(chain['pvs'])} PVs, {len(chain['drives'])} drives")
        return chain
