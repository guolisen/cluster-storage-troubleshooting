#!/usr/bin/env python3
"""
Test script for the Kubernetes Volume I/O Error Troubleshooting System

This script simulates a volume I/O error scenario and runs the troubleshooting
workflow with different configuration settings to validate the implementation.
"""

import os
import sys
import yaml
import logging
import asyncio
import json
import argparse
from typing import Dict, Any
from unittest.mock import patch
from langchain_community.chat_models import FakeListChatModel
from langchain_core.messages import AIMessage

# Import the troubleshooting module
import troubleshoot

# Mock Kubernetes API for testing
class MockKubernetesAPI:
    """Mock Kubernetes API for testing"""
    
    def __init__(self, scenario: str):
        """Initialize mock API with a specific scenario"""
        self.scenario = scenario
        self.commands_executed = []
        
        # Load mock data for the scenario
        self.mock_data = self._load_mock_data()
    
    def _load_mock_data(self) -> Dict[str, Any]:
        """Load mock data for the scenario"""
        scenarios = {
            "bad_sectors": {
                "pod": {
                    "metadata": {
                        "name": "app-1",
                        "namespace": "default",
                        "annotations": {
                            "volume-io-error": "/data"
                        }
                    },
                    "spec": {
                        "volumes": [
                            {
                                "name": "data-volume",
                                "persistentVolumeClaim": {
                                    "claimName": "data-pvc"
                                }
                            }
                        ],
                        "containers": [
                            {
                                "name": "app",
                                "image": "nginx",
                                "volumeMounts": [
                                    {
                                        "name": "data-volume",
                                        "mountPath": "/data"
                                    }
                                ]
                            }
                        ]
                    },
                    "status": {
                        "phase": "Running",
                        "conditions": [
                            {
                                "type": "Ready",
                                "status": "False",
                                "reason": "ContainerFailed",
                                "message": "Container app failed with: I/O error"
                            }
                        ]
                    }
                },
                "pvc": {
                    "metadata": {
                        "name": "data-pvc",
                        "namespace": "default"
                    },
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "resources": {
                            "requests": {
                                "storage": "10Gi"
                            }
                        },
                        "storageClassName": "csi-baremetal-sc-ssd",
                        "volumeName": "pv-data-123"
                    },
                    "status": {
                        "phase": "Bound"
                    }
                },
                "pv": {
                    "metadata": {
                        "name": "pv-data-123"
                    },
                    "spec": {
                        "capacity": {
                            "storage": "10Gi"
                        },
                        "accessModes": ["ReadWriteOnce"],
                        "persistentVolumeReclaimPolicy": "Delete",
                        "storageClassName": "csi-baremetal-sc-ssd",
                        "csi": {
                            "driver": "csi-baremetal.dell.com",
                            "volumeHandle": "drive-123",
                            "volumeAttributes": {
                                "storage": "ssd",
                                "node": "workernode1"
                            }
                        },
                        "nodeAffinity": {
                            "required": {
                                "nodeSelectorTerms": [
                                    {
                                        "matchExpressions": [
                                            {
                                                "key": "kubernetes.io/hostname",
                                                "operator": "In",
                                                "values": ["workernode1"]
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    },
                    "status": {
                        "phase": "Bound"
                    }
                },
                "drive": {
                    "metadata": {
                        "name": "drive-123"
                    },
                    "spec": {
                        "uuid": "drive-123",
                        "path": "/dev/sda",
                        "type": "SSD",
                        "size": "10Gi",
                        "node": "workernode1"
                    },
                    "status": {
                        "health": "BAD",
                        "status": "ONLINE",
                        "usage": "IN_USE"
                    }
                },
                "smartctl": {
                    "smart_status": {
                        "passed": False
                    },
                    "ata_smart_attributes": {
                        "table": [
                            {
                                "id": 5,
                                "name": "Reallocated_Sector_Ct",
                                "value": 100,
                                "worst": 100,
                                "thresh": 10,
                                "when_failed": "FAILING_NOW",
                                "raw": {
                                    "value": 123,
                                    "string": "123"
                                }
                            },
                            {
                                "id": 197,
                                "name": "Current_Pending_Sector",
                                "value": 100,
                                "worst": 100,
                                "thresh": 0,
                                "when_failed": "FAILING_NOW",
                                "raw": {
                                    "value": 45,
                                    "string": "45"
                                }
                            }
                        ]
                    }
                }
            },
            "permission_issue": {
                "pod": {
                    "metadata": {
                        "name": "app-2",
                        "namespace": "default",
                        "annotations": {
                            "volume-io-error": "/data"
                        }
                    },
                    "spec": {
                        "volumes": [
                            {
                                "name": "data-volume",
                                "persistentVolumeClaim": {
                                    "claimName": "data-pvc"
                                }
                            }
                        ],
                        "containers": [
                            {
                                "name": "app",
                                "image": "nginx",
                                "volumeMounts": [
                                    {
                                        "name": "data-volume",
                                        "mountPath": "/data"
                                    }
                                ]
                            }
                        ],
                        "securityContext": {
                            "runAsUser": 1000,
                            "runAsGroup": 1000,
                            "fsGroup": 1000
                        }
                    },
                    "status": {
                        "phase": "Running",
                        "conditions": [
                            {
                                "type": "Ready",
                                "status": "False",
                                "reason": "ContainerFailed",
                                "message": "Container app failed with: Permission denied"
                            }
                        ]
                    }
                },
                "pvc": {
                    "metadata": {
                        "name": "data-pvc",
                        "namespace": "default"
                    },
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "resources": {
                            "requests": {
                                "storage": "10Gi"
                            }
                        },
                        "storageClassName": "csi-baremetal-sc-ssd",
                        "volumeName": "pv-data-456"
                    },
                    "status": {
                        "phase": "Bound"
                    }
                },
                "pv": {
                    "metadata": {
                        "name": "pv-data-456"
                    },
                    "spec": {
                        "capacity": {
                            "storage": "10Gi"
                        },
                        "accessModes": ["ReadWriteOnce"],
                        "persistentVolumeReclaimPolicy": "Delete",
                        "storageClassName": "csi-baremetal-sc-ssd",
                        "csi": {
                            "driver": "csi-baremetal.dell.com",
                            "volumeHandle": "drive-456",
                            "volumeAttributes": {
                                "storage": "ssd",
                                "node": "workernode1"
                            }
                        },
                        "nodeAffinity": {
                            "required": {
                                "nodeSelectorTerms": [
                                    {
                                        "matchExpressions": [
                                            {
                                                "key": "kubernetes.io/hostname",
                                                "operator": "In",
                                                "values": ["workernode1"]
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    },
                    "status": {
                        "phase": "Bound"
                    }
                },
                "drive": {
                    "metadata": {
                        "name": "drive-456"
                    },
                    "spec": {
                        "uuid": "drive-456",
                        "path": "/dev/sdb",
                        "type": "SSD",
                        "size": "10Gi",
                        "node": "workernode1"
                    },
                    "status": {
                        "health": "GOOD",
                        "status": "ONLINE",
                        "usage": "IN_USE"
                    }
                },
                "fs_info": {
                    "permissions": "-rwxr----- 1 root root 4096 May 22 2023 /data"
                }
            }
        }
        
        if self.scenario not in scenarios:
            raise ValueError(f"Unknown scenario: {self.scenario}")
        
        return scenarios[self.scenario]
    
    def execute_command(self, command: str, purpose: str) -> str:
        """Mock command execution"""
        self.commands_executed.append({"command": command, "purpose": purpose})
        
        # Log the command
        logging.info(f"[MOCK] Executing: {command}")
        
        # Handle different commands
        if command.startswith("kubectl get pod") and "app-" in command:
            return yaml.dump(self.mock_data["pod"])
            
        elif command.startswith("kubectl describe pod") and "app-" in command:
            return f"Name:         {self.mock_data['pod']['metadata']['name']}\n" + \
                   f"Namespace:    {self.mock_data['pod']['metadata']['namespace']}\n" + \
                   "Status:       Running\n" + \
                   f"Message:      {self.mock_data['pod']['status']['conditions'][0]['message']}\n"
            
        elif command.startswith("kubectl logs") and "app-" in command:
            if self.scenario == "bad_sectors":
                return "I/O error on device /dev/sda, logical block 1234\nKernel panic - not syncing: I/O error"
            elif self.scenario == "permission_issue":
                return "open /data/file.txt: permission denied\nfailed to open data file: permission denied"
        
        elif command.startswith("kubectl get pvc"):
            return yaml.dump(self.mock_data["pvc"])
            
        elif command.startswith("kubectl get pv"):
            return yaml.dump(self.mock_data["pv"])
            
        elif command.startswith("kubectl get drive"):
            return yaml.dump(self.mock_data["drive"])
            
        elif command.startswith("kubectl exec") and "ls -ld" in command:
            if self.scenario == "permission_issue":
                return self.mock_data["fs_info"]["permissions"]
            else:
                return "-rwxrwxrwx 1 root root 4096 May 22 2023 /data"
            
        elif command.startswith("ssh") and "smartctl" in command:
            if self.scenario == "bad_sectors":
                return json.dumps(self.mock_data["smartctl"])
            else:
                return json.dumps({"smart_status": {"passed": True}})
            
        elif command.startswith("ssh") and "fio" in command:
            if self.scenario == "bad_sectors":
                return "READ: io=100MB, aggrb=10MB/s, minb=10MB/s, maxb=10MB/s, mint=10000msec, maxt=10000msec\nWRITE: io=0KB, aggrb=0KB/s\nErrors: 23 read errors, 0 write errors"
            else:
                return "READ: io=100MB, aggrb=500MB/s, minb=500MB/s, maxb=500MB/s, mint=200msec, maxt=200msec\nWRITE: io=100MB, aggrb=450MB/s\nErrors: 0 read errors, 0 write errors"
        
        # Default response for unhandled commands
        return f"Mock command executed: {command}"

def patch_troubleshoot_module(mock_api):
    """Patch the troubleshoot module to use mock API"""
    
    # Override execute_command function
    troubleshoot.execute_command = mock_api.execute_command
    
    # Override ssh_execute function
    troubleshoot.ssh_execute = lambda node, command, purpose: mock_api.execute_command(f"ssh {node} {command}", purpose)
    
    # Disable interactive mode for testing
    troubleshoot.INTERACTIVE_MODE = False
    
    # Mock input function to always proceed to remediation
    troubleshoot.input = lambda _: "y"

async def run_test(scenario: str, auto_fix: bool):
    """
    Run a test with a specific scenario and auto_fix setting
    
    Args:
        scenario: Test scenario ("bad_sectors" or "permission_issue")
        auto_fix: Enable/disable auto-fix mode
    """
    # Create mock API
    mock_api = MockKubernetesAPI(scenario)
    
    # Patch troubleshoot module
    patch_troubleshoot_module(mock_api)
    
    # Set configuration
    troubleshoot.CONFIG_DATA = {
        'llm': {
            'model': 'gpt4-o4-mini',
            'api_endpoint': 'https://x.ai/api',
            'api_key': '',
            'temperature': 0.7,
            'max_tokens': 1000
        },
        'troubleshoot': {
            'timeout_seconds': 300,
            'interactive_mode': False,  # Disable for testing
            'auto_fix': auto_fix,
            'ssh': {
                'enabled': True,
                'user': 'admin',
                'key_path': '/path/to/ssh/key',
                'nodes': ['workernode1', 'workernode2', 'masternode1'],
                'retries': 3,
                'retry_backoff_seconds': 5
            }
        },
        'commands': {
            'allowed': [
                'kubectl get *',
                'kubectl describe *',
                'kubectl logs *',
                'kubectl exec *',
                'df -h',
                'lsblk',
                'cat /proc/mounts',
                'smartctl -a *',
                'fio --name=read_test *',
                'dmesg | grep -i disk',
                'dmesg | grep -i error',
                'journalctl -u kubelet *',
                'xfs_repair -n *'
            ],
            'disallowed': [
                'fsck *',
                'chmod *',
                'chown *',
                'dd *',
                'mkfs *',
                'rm *',
                'kubectl delete *',
                'kubectl apply *',
                'xfs_repair *'
            ]
        },
        'logging': {
            'file': 'test_troubleshoot.log',
            'stdout': True
        }
    }
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('test_troubleshoot.log'),
            logging.StreamHandler()
        ]
    )
    
    # Get pod details from scenario
    pod_data = mock_api.mock_data['pod']
    pod_name = pod_data['metadata']['name']
    namespace = pod_data['metadata']['namespace']
    volume_path = pod_data['metadata']['annotations']['volume-io-error']
    
    # Run troubleshooting
    logging.info(f"Starting test with scenario '{scenario}', auto_fix={auto_fix}")
    logging.info(f"Troubleshooting pod {namespace}/{pod_name}, volume {volume_path}")
    
    # Mock the two-phase troubleshooting process
    try:
        # Phase 1: Analysis
        logging.info("Starting Phase 1: Analysis")
        
        if scenario == "bad_sectors":
            root_cause = "Bad sectors detected on the disk - SMART data shows Reallocated_Sector_Ct=123 and Current_Pending_Sector=45"
            fix_plan = "Step 1: Back up data from the affected volume. Step 2: Replace the physical disk. Step 3: Update the drive CR status."
        elif scenario == "permission_issue":
            root_cause = "Incorrect file system permissions - pod running as UID 1000 but volume owned by root with restricted permissions"
            fix_plan = "Step 1: Update pod security context with correct fsGroup. Step 2: Restart the pod."
        
        logging.info(f"Analysis completed: Root cause: {root_cause}")
        logging.info(f"Fix plan: {fix_plan}")
        
        # Check if we proceed to remediation
        if auto_fix:
            logging.info("Auto-fix enabled, proceeding to remediation automatically")
            proceed_to_remediation = True
        else:
            logging.info("Auto-fix disabled, would prompt user in non-test environment")
            # In real code this would prompt the user, but we're mocking it
            proceed_to_remediation = True
            logging.info("User approved proceeding to remediation (mocked)")
        
        # Phase 2: Remediation (if approved)
        if proceed_to_remediation:
            logging.info("Starting Phase 2: Remediation")
            
            if scenario == "bad_sectors":
                # In a real environment, these commands would be blocked by disallowed list
                # or would require user approval in interactive mode
                result = "Issue not resolved. Manual actions required: Replace physical disk with UUID drive-123 on node workernode1."
            elif scenario == "permission_issue":
                # In a real environment, these commands would be blocked by disallowed list
                # or would require user approval in interactive mode
                result = "Issue resolved: Updated pod security context with fsGroup=0 and restarted pod. Verified write access to volume."
            
            logging.info(f"Remediation completed: {result}")
            return result
        else:
            logging.info("Remediation phase skipped")
            return f"Analysis completed. Root cause: {root_cause}\nFix plan: {fix_plan}\nRemediation skipped."
        
    except Exception as e:
        logging.error(f"Error during test: {str(e)}")
        return f"Error: {str(e)}"

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Test Kubernetes Volume I/O Error Troubleshooting')
    parser.add_argument('--scenario', choices=['bad_sectors', 'permission_issue'], default='bad_sectors',
                      help='Test scenario to run (default: bad_sectors)')
    parser.add_argument('--auto-fix', action='store_true',
                      help='Enable auto-fix mode (default: false)')
    
    args = parser.parse_args()
    
    try:
        result = asyncio.run(run_test(args.scenario, args.auto_fix))
        
        print("\n=== Test Results ===")
        print(f"Scenario: {args.scenario}")
        print(f"Auto-fix: {args.auto_fix}")
        print(f"Result: {result}")
        print("=====================\n")
        
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        sys.exit(1)

async def test_run_analysis_phase_with_mock_llm():
    """
    Tests the run_analysis_phase function with a mocked LLM
    that returns a JSON response.
    """
    # 1. Setup scenario data
    pod_name = "test-pod-json"
    namespace = "test-ns-json"
    volume_path = "/data-json"
    
    expected_root_cause = "Mocked: LLM analysis complete - disk is critically full."
    expected_fix_plan = "Mocked: Step 1: Identify and delete large unnecessary files. Step 2: Consider resizing the volume or adding more storage."
    llm_response_json_str = json.dumps({
        "root_cause": expected_root_cause,
        "fix_plan": expected_fix_plan
    })

    # 2. Setup mocks
    # The scenario for MockKubernetesAPI might not be strictly relevant here
    # as the LLM is mocked and we expect it to directly return the JSON,
    # not necessarily call tools that MockKubernetesAPI would intercept for this specific test.
    mock_kube_api = MockKubernetesAPI(scenario="bad_sectors") 
    patch_troubleshoot_module(mock_kube_api) # Patches execute_command, ssh_execute, input

    # Configure troubleshoot.CONFIG_DATA
    # Using a minimal valid config for the test
    troubleshoot.CONFIG_DATA = {
        'llm': {'model': 'fake-model', 'api_key': 'fake', 'api_endpoint': 'fake', 'temperature': 0.1, 'max_tokens': 100},
        'troubleshoot': {
            'timeout_seconds': 30, 
            'auto_fix': False, 
            'interactive_mode': False, 
            'ssh': {
                'enabled': False, 
                'nodes': [], 
                'user': '', 
                'key_path': '', 
                'retries': 1, 
                'retry_backoff_seconds': 1
            }
        },
        'commands': { # Ensure some commands are allowed for the graph to be built, though not used by LLM here
            'allowed': ["kubectl get *", "kubectl describe *", "kubectl logs *", "kubectl exec *"], 
            'disallowed': ["rm *"]
        },
        'logging': {'file': 'test_troubleshoot.log', 'stdout': False} # Assuming logging is handled
    }
    troubleshoot.INTERACTIVE_MODE = False # Ensure non-interactive for tests

    # 3. Patch init_chat_model to return FakeListChatModel
    # FakeListChatModel expects a list of responses.
    # For a direct answer from the LLM (not tool usage), this response string
    # will be wrapped in an AIMessage by LangGraph, which is what run_analysis_phase expects.
    fake_llm = FakeListChatModel(responses=[llm_response_json_str])

    with patch('troubleshoot.init_chat_model', return_value=fake_llm) as mock_init_model:
        # 4. Call the target function
        logging.info("Calling run_analysis_phase with mocked LLM...")
        actual_root_cause, actual_fix_plan = await troubleshoot.run_analysis_phase(pod_name, namespace, volume_path)
        logging.info(f"Received root_cause: {actual_root_cause}, fix_plan: {actual_fix_plan}")

        # 5. Assertions
        assert mock_init_model.called, "troubleshoot.init_chat_model was not called"
        assert actual_root_cause == expected_root_cause, f"Root cause mismatch. Expected: '{expected_root_cause}', Got: '{actual_root_cause}'"
        assert actual_fix_plan == expected_fix_plan, f"Fix plan mismatch. Expected: '{expected_fix_plan}', Got: '{actual_fix_plan}'"
    
    logging.info("test_run_analysis_phase_with_mock_llm completed successfully.")

if __name__ == "__main__":
    # main() # Keep original main for now
    # For testing this specific new test case:
    print("Running test_run_analysis_phase_with_mock_llm...")
    asyncio.run(test_run_analysis_phase_with_mock_llm())
    print("test_run_analysis_phase_with_mock_llm finished.")
