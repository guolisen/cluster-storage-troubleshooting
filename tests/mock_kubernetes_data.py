#!/usr/bin/env python3
"""
Mock Kubernetes data for testing and demonstration purposes
"""

from typing import Dict, Any

# Mock Kubernetes data
MOCK_KUBERNETES_DATA = {
    "pods": {
        "default/test-pod": {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "test-pod",
                "namespace": "default",
                "uid": "pod-123-456",
                "labels": {
                    "app": "test-app"
                },
                "annotations": {
                    "kubernetes.io/created-by": "test-user"
                }
            },
            "spec": {
                "containers": [
                    {
                        "name": "test-container",
                        "image": "nginx:latest",
                        "ports": [
                            {
                                "containerPort": 80,
                                "protocol": "TCP"
                            }
                        ],
                        "volumeMounts": [
                            {
                                "name": "test-volume",
                                "mountPath": "/data"
                            }
                        ],
                        "resources": {
                            "limits": {
                                "cpu": "500m",
                                "memory": "512Mi"
                            },
                            "requests": {
                                "cpu": "250m",
                                "memory": "256Mi"
                            }
                        }
                    }
                ],
                "volumes": [
                    {
                        "name": "test-volume",
                        "persistentVolumeClaim": {
                            "claimName": "test-pvc"
                        }
                    }
                ],
                "nodeName": "worker-1"
            },
            "status": {
                "phase": "Running",
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "lastProbeTime": None,
                        "lastTransitionTime": "2025-06-16T04:00:00Z",
                        "reason": "ContainersReady",
                        "message": "All containers are ready"
                    }
                ],
                "containerStatuses": [
                    {
                        "name": "test-container",
                        "state": {
                            "running": {
                                "startedAt": "2025-06-16T04:00:00Z"
                            }
                        },
                        "lastState": {
                            "terminated": {
                                "exitCode": 1,
                                "reason": "Error",
                                "message": "I/O error on volume",
                                "startedAt": "2025-06-16T03:50:00Z",
                                "finishedAt": "2025-06-16T03:55:00Z"
                            }
                        },
                        "ready": True,
                        "restartCount": 1,
                        "image": "nginx:latest",
                        "imageID": "docker-pullable://nginx@sha256:abcdef123456",
                        "containerID": "containerd://container-123-456"
                    }
                ],
                "qosClass": "Burstable"
            }
        }
    },
    "pvcs": {
        "default/test-pvc": {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": "test-pvc",
                "namespace": "default",
                "uid": "pvc-123-456",
                "annotations": {
                    "pv.kubernetes.io/bind-completed": "yes",
                    "pv.kubernetes.io/bound-by-controller": "yes",
                    "volume.beta.kubernetes.io/storage-provisioner": "csi-baremetal"
                }
            },
            "spec": {
                "accessModes": [
                    "ReadWriteOnce"
                ],
                "resources": {
                    "requests": {
                        "storage": "10Gi"
                    }
                },
                "volumeName": "test-pv",
                "storageClassName": "csi-baremetal-sc",
                "volumeMode": "Filesystem"
            },
            "status": {
                "phase": "Bound",
                "accessModes": [
                    "ReadWriteOnce"
                ],
                "capacity": {
                    "storage": "10Gi"
                }
            }
        }
    },
    "pvs": {
        "test-pv": {
            "apiVersion": "v1",
            "kind": "PersistentVolume",
            "metadata": {
                "name": "test-pv",
                "uid": "pv-123-456",
                "annotations": {
                    "pv.kubernetes.io/provisioned-by": "csi-baremetal"
                }
            },
            "spec": {
                "capacity": {
                    "storage": "10Gi"
                },
                "accessModes": [
                    "ReadWriteOnce"
                ],
                "persistentVolumeReclaimPolicy": "Delete",
                "storageClassName": "csi-baremetal-sc",
                "csi": {
                    "driver": "csi-baremetal",
                    "volumeHandle": "volume-123-456",
                    "fsType": "xfs",
                    "volumeAttributes": {
                        "storage": "HDD",
                        "node": "worker-1"
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
                                        "values": [
                                            "worker-1"
                                        ]
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
        }
    },
    "nodes": {
        "worker-1": {
            "apiVersion": "v1",
            "kind": "Node",
            "metadata": {
                "name": "worker-1",
                "uid": "node-123-456",
                "labels": {
                    "beta.kubernetes.io/arch": "amd64",
                    "beta.kubernetes.io/os": "linux",
                    "kubernetes.io/arch": "amd64",
                    "kubernetes.io/hostname": "worker-1",
                    "kubernetes.io/os": "linux",
                    "node-role.kubernetes.io/worker": ""
                }
            },
            "spec": {
                "podCIDR": "10.244.1.0/24",
                "taints": []
            },
            "status": {
                "capacity": {
                    "cpu": "8",
                    "ephemeral-storage": "102834Mi",
                    "hugepages-1Gi": "0",
                    "hugepages-2Mi": "0",
                    "memory": "32Gi",
                    "pods": "110"
                },
                "allocatable": {
                    "cpu": "7800m",
                    "ephemeral-storage": "94822323329",
                    "hugepages-1Gi": "0",
                    "hugepages-2Mi": "0",
                    "memory": "31Gi",
                    "pods": "110"
                },
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "lastHeartbeatTime": "2025-06-16T04:30:00Z",
                        "lastTransitionTime": "2025-06-16T00:00:00Z",
                        "reason": "KubeletReady",
                        "message": "kubelet is posting ready status"
                    },
                    {
                        "type": "DiskPressure",
                        "status": "False",
                        "lastHeartbeatTime": "2025-06-16T04:30:00Z",
                        "lastTransitionTime": "2025-06-16T00:00:00Z",
                        "reason": "KubeletHasSufficientDisk",
                        "message": "kubelet has sufficient disk space available"
                    },
                    {
                        "type": "MemoryPressure",
                        "status": "False",
                        "lastHeartbeatTime": "2025-06-16T04:30:00Z",
                        "lastTransitionTime": "2025-06-16T00:00:00Z",
                        "reason": "KubeletHasSufficientMemory",
                        "message": "kubelet has sufficient memory available"
                    },
                    {
                        "type": "PIDPressure",
                        "status": "False",
                        "lastHeartbeatTime": "2025-06-16T04:30:00Z",
                        "lastTransitionTime": "2025-06-16T00:00:00Z",
                        "reason": "KubeletHasSufficientPID",
                        "message": "kubelet has sufficient PID available"
                    },
                    {
                        "type": "NetworkUnavailable",
                        "status": "False",
                        "lastHeartbeatTime": "2025-06-16T04:30:00Z",
                        "lastTransitionTime": "2025-06-16T00:00:00Z",
                        "reason": "RouteCreated",
                        "message": "RouteController created a route"
                    }
                ],
                "addresses": [
                    {
                        "type": "InternalIP",
                        "address": "192.168.1.10"
                    },
                    {
                        "type": "Hostname",
                        "address": "worker-1"
                    }
                ],
                "nodeInfo": {
                    "machineID": "abc123def456",
                    "systemUUID": "abc123def456",
                    "bootID": "abc123def456",
                    "kernelVersion": "5.15.0-1.el9",
                    "osImage": "CentOS Stream 9",
                    "containerRuntimeVersion": "containerd://1.6.0",
                    "kubeletVersion": "v1.26.0",
                    "kubeProxyVersion": "v1.26.0",
                    "operatingSystem": "linux",
                    "architecture": "amd64"
                }
            }
        }
    },
    "storage_classes": {
        "csi-baremetal-sc": {
            "apiVersion": "storage.k8s.io/v1",
            "kind": "StorageClass",
            "metadata": {
                "name": "csi-baremetal-sc",
                "annotations": {
                    "storageclass.kubernetes.io/is-default-class": "true"
                }
            },
            "provisioner": "csi-baremetal",
            "parameters": {
                "storageType": "HDD",
                "fsType": "xfs"
            },
            "reclaimPolicy": "Delete",
            "volumeBindingMode": "WaitForFirstConsumer",
            "allowVolumeExpansion": True
        }
    },
    "csi_driver": {
        "name": "csi-baremetal",
        "version": "1.0.0",
        "nodeID": "worker-1",
        "topology": {
            "segments": {
                "topology.csi-baremetal/node": "worker-1"
            }
        },
        "volumes": {
            "volume-123-456": {
                "id": "volume-123-456",
                "name": "volume-123-456",
                "capacity": "10Gi",
                "status": "published",
                "published_node": "worker-1",
                "storage_type": "HDD",
                "fs_type": "xfs",
                "health": "warning",
                "drive_uuid": "drive-abc-123",
                "error_log": [
                    {
                        "timestamp": "2025-06-16T04:28:00Z",
                        "error": "I/O error detected",
                        "details": "Error accessing filesystem metadata"
                    }
                ]
            }
        },
        "drives": {
            "drive-abc-123": {
                "uuid": "drive-abc-123",
                "serial": "ABC123DEF456",
                "size": "100Gi",
                "node": "worker-1",
                "type": "HDD",
                "path": "/dev/sda",
                "status": "online",
                "health": "warning",
                "error_log": [
                    {
                        "timestamp": "2025-06-16T04:28:00Z",
                        "error": "Multiple read failures detected",
                        "details": "5 uncorrectable errors reported by SMART"
                    }
                ]
            }
        }
    }
}

# Function to get mock Kubernetes data
def get_mock_kubernetes_data() -> Dict[str, Any]:
    """
    Get mock Kubernetes data for testing and demonstration
    
    Returns:
        Dict[str, Any]: Mock Kubernetes data
    """
    return MOCK_KUBERNETES_DATA
