#!/usr/bin/env python3
"""
Mock system data for testing and demonstration purposes
"""

from typing import Dict, Any, List

# Mock system information
MOCK_SYSTEM_INFO = {
    "kernel": {
        "version": "5.15.0-1.el9",
        "arch": "x86_64",
        "modules": [
            {"name": "xfs", "version": "5.15.0", "status": "loaded"},
            {"name": "dm_thin_pool", "version": "5.15.0", "status": "loaded"},
            {"name": "dm_persistent_data", "version": "5.15.0", "status": "loaded"},
            {"name": "dm_bio_prison", "version": "5.15.0", "status": "loaded"},
            {"name": "dm_mod", "version": "5.15.0", "status": "loaded"}
        ],
        "parameters": {
            "fs.file-max": "9223372036854775807",
            "fs.inotify.max_user_watches": "1048576",
            "vm.max_map_count": "262144"
        }
    },
    "os": {
        "name": "CentOS Stream",
        "version": "9",
        "id": "centos",
        "id_like": "rhel fedora",
        "pretty_name": "CentOS Stream 9"
    },
    "hardware": {
        "cpu": {
            "model": "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
            "cores": 8,
            "threads": 16
        },
        "memory": {
            "total": "32GB",
            "free": "12GB",
            "used": "20GB",
            "swap_total": "8GB",
            "swap_free": "8GB"
        },
        "disks": [
            {
                "device": "/dev/sda",
                "size": "100GB",
                "type": "HDD",
                "model": "HGST HUS726020ALA610",
                "serial": "ABC123DEF456",
                "smart_status": "WARN",
                "smart_attributes": [
                    {
                        "id": 5,
                        "name": "Reallocated_Sector_Ct",
                        "value": 100,
                        "worst": 100,
                        "threshold": 10,
                        "status": "OK"
                    },
                    {
                        "id": 187,
                        "name": "Reported_Uncorrect",
                        "value": 95,
                        "worst": 95,
                        "threshold": 0,
                        "status": "WARN"
                    },
                    {
                        "id": 197,
                        "name": "Current_Pending_Sector",
                        "value": 98,
                        "worst": 98,
                        "threshold": 0,
                        "status": "WARN"
                    },
                    {
                        "id": 198,
                        "name": "Offline_Uncorrectable",
                        "value": 100,
                        "worst": 100,
                        "threshold": 0,
                        "status": "OK"
                    }
                ],
                "partitions": [
                    {
                        "name": "/dev/sda1",
                        "size": "1GB",
                        "type": "EFI System",
                        "mountpoint": "/boot/efi"
                    },
                    {
                        "name": "/dev/sda2",
                        "size": "99GB",
                        "type": "Linux LVM",
                        "mountpoint": None
                    }
                ]
            }
        ],
        "filesystems": [
            {
                "device": "/dev/mapper/vg0-root",
                "mountpoint": "/",
                "type": "xfs",
                "size": "50GB",
                "used": "30GB",
                "available": "20GB",
                "use_percent": 60
            },
            {
                "device": "/dev/mapper/vg0-var",
                "mountpoint": "/var",
                "type": "xfs",
                "size": "20GB",
                "used": "10GB",
                "available": "10GB",
                "use_percent": 50
            },
            {
                "device": "/dev/mapper/vg0-home",
                "mountpoint": "/home",
                "type": "xfs",
                "size": "10GB",
                "used": "2GB",
                "available": "8GB",
                "use_percent": 20
            },
            {
                "device": "/dev/sda1",
                "mountpoint": "/boot/efi",
                "type": "vfat",
                "size": "1GB",
                "used": "0.2GB",
                "available": "0.8GB",
                "use_percent": 20
            }
        ]
    },
    "network": {
        "interfaces": [
            {
                "name": "eth0",
                "mac": "00:11:22:33:44:55",
                "ip": "192.168.1.10",
                "netmask": "255.255.255.0",
                "gateway": "192.168.1.1",
                "status": "up",
                "speed": "1000Mb/s",
                "mtu": 1500
            }
        ],
        "hostname": "worker-1",
        "dns_servers": ["8.8.8.8", "8.8.4.4"],
        "routes": [
            {
                "destination": "0.0.0.0/0",
                "gateway": "192.168.1.1",
                "interface": "eth0"
            },
            {
                "destination": "192.168.1.0/24",
                "gateway": "0.0.0.0",
                "interface": "eth0"
            }
        ]
    },
    "processes": {
        "total": 234,
        "running": 2,
        "sleeping": 232,
        "stopped": 0,
        "zombie": 0,
        "top": [
            {
                "pid": 1,
                "user": "root",
                "command": "/usr/lib/systemd/systemd --system --deserialize 35",
                "cpu_percent": 0.0,
                "memory_percent": 0.1
            },
            {
                "pid": 1234,
                "user": "root",
                "command": "/usr/bin/kubelet --config=/var/lib/kubelet/config.yaml",
                "cpu_percent": 2.5,
                "memory_percent": 3.2
            },
            {
                "pid": 2345,
                "user": "root",
                "command": "/usr/bin/containerd",
                "cpu_percent": 1.8,
                "memory_percent": 2.5
            }
        ]
    },
    "logs": {
        "kernel": [
            {
                "timestamp": "2025-06-16T04:28:00Z",
                "level": "err",
                "message": "XFS (dm-3): Metadata corruption detected at xfs_inode_buf_verify+0x89/0x1c0 [xfs], xfs_inode block 0x1234"
            },
            {
                "timestamp": "2025-06-16T04:28:01Z",
                "level": "err",
                "message": "XFS (dm-3): Unmount and run xfs_repair"
            },
            {
                "timestamp": "2025-06-16T04:28:02Z",
                "level": "err",
                "message": "XFS (dm-3): First 64 bytes of corrupted metadata buffer:"
            },
            {
                "timestamp": "2025-06-16T04:28:10Z",
                "level": "err",
                "message": "Buffer I/O error on dev dm-3, logical block 1234, async page read"
            }
        ],
        "system": [
            {
                "timestamp": "2025-06-16T04:29:00Z",
                "service": "kubelet",
                "level": "error",
                "message": "Error syncing pod default/test-pod: I/O error on volume mount"
            },
            {
                "timestamp": "2025-06-16T04:29:05Z",
                "service": "containerd",
                "level": "error",
                "message": "Container test-container exited with error: I/O error on volume"
            }
        ]
    },
    "volume_diagnostics": {
        "mount_info": {
            "device": "/dev/mapper/volume-123-456",
            "mountpoint": "/var/lib/kubelet/pods/pod-123-456/volumes/kubernetes.io~csi/test-pv/mount",
            "type": "xfs",
            "options": "rw,relatime,attr2,inode64,logbufs=8,logbsize=32k,noquota"
        },
        "xfs_info": {
            "block_size": 4096,
            "data_blocks": 2621440,
            "imaxpct": 25,
            "log_blocks": 2560,
            "naming": "version 2",
            "uuid": "12345678-abcd-1234-efgh-123456789abc"
        },
        "xfs_repair_check": {
            "status": "error",
            "errors_found": [
                "Inode 1234 has corrupt core.mode",
                "Inode 5678 has corrupt core.size",
                "Filesystem has corrupt metadata"
            ],
            "repair_recommended": True
        },
        "io_stats": {
            "read_ops": 12345,
            "write_ops": 23456,
            "read_bytes": 123456789,
            "write_bytes": 234567890,
            "read_time_ms": 45678,
            "write_time_ms": 56789,
            "io_time_ms": 78901,
            "io_in_progress": 0,
            "errors": 123
        }
    }
}

# Function to get mock system data
def get_mock_system_data() -> Dict[str, Any]:
    """
    Get mock system data for testing and demonstration
    
    Returns:
        Dict[str, Any]: Mock system data
    """
    return MOCK_SYSTEM_INFO
