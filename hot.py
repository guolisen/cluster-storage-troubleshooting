#!/usr/bin/python3

import os
import re
import subprocess
import sys
import argparse
import time

verbose = 0

def get_verbose():
    global verbose
    return verbose

def get_device_name_from_args(args_name):
    name = os.path.basename(args_name)
    if not name:
        return None

    # Handle NVMe devices
    match = re.match(r"^(nvme\d+(n|p)\d+)", name)
    if match:
        block_device = match.group(1)  # e.g., nvme2n1 or nvme2p1
        block_path = os.path.join("/sys/block", block_device)
        
        try:
            # Read the symbolic link to get the device path
            device_path = os.readlink(block_path)
            
            # Extract the NVMe controller name (e.g., 'nvme5' from '.../nvme/nvme5/nvme2n1')
            nvme_controller = None
            for part in device_path.split('/'):
                if part.startswith('nvme') and re.match(r'nvme\d+$', part):
                    nvme_controller = part
                    break
            
            if nvme_controller:
                nvme_path = os.path.join("/sys/class/nvme", nvme_controller)
                # Check if the NVMe controller path exists
                if os.path.exists(nvme_path):
                    return nvme_controller
                else:
                    print(f"NVMe controller {nvme_path} does not exist")
            else:
                print(f"Could not find NVMe controller for {block_device}")
        except OSError:
            print(f"Failed to resolve NVMe device path for {block_device}")
        return None

    # Handle SCSI block devices (unchanged)
    match = re.match(r"^(sd[a-z]+)", name)
    if match:
        block_device = match.group(1)  # e.g., sda
        path = os.path.join("/sys/class/block", block_device)
        # Check if the SCSI block device exists
        if os.path.exists(path):
            return block_device
        else:
            print(f"SCSI block device {path} does not exist")
        return None

    return None

'''
def get_nvme_name_from_args(args_nvme_name):
    name = os.path.basename(args_nvme_name)
    if name:
        match = re.match(r"^(nvme[0-9]+)+", name)
        if match:
            path = "/sys/class/nvme/" + match.group(1)
            # check if specified nvme name exists
            if os.path.exists(path):
                return match.group(1)
    return

def get_disk_name_from_args(args_disk_name):
    name = os.path.basename(args_disk_name)
    if name:
        match = re.match(r"^(sd[a-z]+)", name)
        if match:
            path = "/sys/class/block/" + match.group(1)
            # check if specified nvme name exists
            if os.path.exists(path):
                return match.group(1)
    return
'''

def get_nvme_physlot(nvme_device_name):
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    # Validate NVMe device name (e.g., nvme2n1, nvme2p1)
    if not re.match(r'nvme\d+(n|p)\d+', nvme_device_name):
        return None  # Invalid NVMe device name

    # Construct path to the block device in /sys/block
    block_path = os.path.join('/sys/block', nvme_device_name)

    try:
        # Read the symbolic link to get the device path
        device_path = os.readlink(block_path)

        # Extract the NVMe controller name (e.g., 'nvme5' from '.../nvme/nvme5/nvme2n1')
        nvme_controller = None
        for part in device_path.split('/'):
            if part.startswith('nvme') and re.match(r'nvme\d+$', part):
                nvme_controller = part
                break

        if not nvme_controller:
            return None  # Could not find NVMe controller

        # Construct the path to the NVMe controller in /sys/class/nvme
        nvme_path = os.path.join('/sys/class/nvme', nvme_controller)

        # Read the symbolic link to get the PCI bus path
        bus_path = os.readlink(nvme_path)
        # Extract the bus ID (e.g., '0000:65:00.0')
        dirs = bus_path.split('/')
        bus_id = dirs[5]  # Assuming bus ID is at index 5

        # Run lspci to get physical slot information
        output = subprocess.check_output(['lspci', '-s', bus_id, '-vmm'])
        match = re.search(r'PhySlot:\s+(\d+)', output.decode())
        if match:
            return match.group(1)
        else:
            return None  # No physical slot found
    except (OSError, subprocess.CalledProcessError):
        return None  # Handle errors (e.g., path doesn't exist, lspci fails)

def get_nvme_pcibus(nvme_device_name):
    path = os.path.join('/sys/class/nvme', nvme_device_name)
    bus_path = os.readlink(path)
    dirs = bus_path.split('/')
    pcibus = f"{dirs[3]}/{dirs[4]}"
    return pcibus

def run_command(command):
    try:
        subprocess.run(command, shell=True, check=True)
        return 0
    except subprocess.CalledProcessError as e:
        print(f"command: '{command}' returned non-zero exit status {e.returncode}")
        print(f"output: {e.output}")
        print(f"error: {e.stderr}")
        return e.returncode

def nvme_power_control(physlot, onoff):
    if onoff == "on" :
        # not used yet, need to save physlot to somewhere before the poweroff
        command = f"echo 1 > /sys/bus/pci/slots/{physlot}/power"
    else:
        # poweroff -> pci rescan -> poweroff(fail), need to echo 1 and then echo 0
        # poweroff -> poweron -> poweroff(ok)
        subprocess.run(f"echo 1 > /sys/bus/pci/slots/{physlot}/power", shell=True, stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)
        command = f"echo 0 > /sys/bus/pci/slots/{physlot}/power"
    if get_verbose() > 0:
        print(f"run cmd: {command}")
    return run_command(command)

def nvme_device_delete(nvme_device_name):
    command = f"echo 1 > /sys/class/nvme/{nvme_device_name}/device/remove"
    if get_verbose() > 0:
        print(f"run cmd: {command}")
    return run_command(command)

def scsi_disk_delete(scsi_disk_name):
    command = f"echo 1 > /sys/block/{scsi_disk_name}/device/delete"
    if get_verbose() > 0:
        print(f"run cmd: {command}")
    return run_command(command)

def nvme_device_rescan(pcibus):
    command = f"echo 1 > /sys/devices/{pcibus}/rescan"
    if get_verbose() > 0:
        print(f"run cmd: {command}")
    return run_command(command)

def nvme_device_rescan_all():
    # pci rescan can add back deleted devices and power off devices.
    command = "echo 1 > /sys/bus/pci/rescan"
    if get_verbose() > 0:
        print(f"run cmd: {command}")
    return run_command(command)

def scsi_disk_rescan():
    command = "for scan in `ls /sys/class/scsi_host/host*/scan`; do echo \"- - -\" > $scan;done"
    if get_verbose() > 0:
        print(command)
    return run_command(command)

def device_rescan(args):
    scan_all = False
    if not (args.scsi or args.nvme):
        scan_all = True
    if args.nvme or scan_all:
        if nvme_device_rescan_all() != 0:
            print("nvme rescan failed")
            return
        print("nvme disks rescan done")
    if args.scsi or scan_all:
        if scsi_disk_rescan() != 0:
            print("scsi host rescan failed")
            return
        print("scsi disks rescan done")
    print("success")
    return 

def device_off(args):
    name = get_device_name_from_args(args.disk)
    if not name:
        print(f"invalid disk name: {args.disk}")
        return
    if name.startswith("nvme"):
        # nvme disk poweroff
        if args.poweroff:
            physlot = get_nvme_physlot(name)
            if physlot:
                if nvme_power_control(physlot, "off") != 0:
                    print(f"failed to poweroff {name}")
                    return
                print(f"power off {name} done")
            else :
                print("failed to get nvme physlot")
                return
            if args.time > 0:
                print(f"sleeping({args.time}s)...")
                time.sleep(args.time)
                if nvme_power_control(physlot, "on") != 0:
                    print(f"failed to poweron {name}")
                    return
                print(f"power on {name} done")
            else:
                command1 = f"command1: {os.path.basename(sys.argv[0])} on -a poweron -p {physlot}"
                command2 = f"command2: {os.path.basename(sys.argv[0])} rescan"
                print(f"the physlot of {name} is {physlot}, to power on the disk, please run one of the below commands")
                print(command1)
                print(command2)
        # nvme disk delete
        if args.remove:
            pcibus = get_nvme_pcibus(name)
            if nvme_device_delete(name) != 0:
                print(f"failed to delete {name}")
                return
            print(f"delete {name} done")
            if args.time > 0:
                print(f"sleeping({args.time}s)...")
                time.sleep(args.time)
                if nvme_device_rescan(pcibus) != 0:
                    print(f"failed to rescan for {name}")
                    return
                print(f"rescan {name} done")
            else:
                command1 = f"command1: {os.path.basename(sys.argv[0])} on -a rescan -p {pcibus}"
                command2 = f"command2: {os.path.basename(sys.argv[0])} rescan"
                print(f"the pci bus of {name} is {pcibus}, to rescan the disk, please run one of the below commands")
                print(command1)
                print(command2)
    else :
        # scsi disk
        if args.poweroff:
            print("power off scsi disk is not supported.")
            return
        if args.remove:
            if scsi_disk_delete(name) != 0:
                print(f"failed to delete {name}")
                return
            print(f"delete {name} done")
            if args.time > 0:
                print(f"sleeping({args.time}s)...")
                time.sleep(args.time)
                if scsi_disk_rescan() != 0:
                    print(f"failed to rescan all scsi host")
                    return
                print("rescan all scsi host done")
            else:
                command = f"command: {os.path.basename(sys.argv[0])} rescan"
                print(f"to rescan the disk, please run below command")
                print(command)
    return

def device_on(args):
    if args.action == "poweron":
        path = f"/sys/bus/pci/slots/{args.param}"
        if not os.path.exists(path):
            print(f"invalid physlot {args.param}")
            return
        if nvme_power_control(args.param, "on") != 0:
            print(f"failed to power on physlot {args.param}")
            return
        print(f"power on physlot {args.param} done")
    if args.action == "rescan":
        path = f"/sys/devices/{args.param}"
        if not os.path.exists(path):
            print(f"invalid pci bus {args.param}")
            return
        if nvme_device_rescan(args.param) != 0:
            print(f"failed to rescan pci bus {args.param}")
            return
        print(f"rescan pci bus {args.param} done")
    return

def get_my_node_uuid():
    command = "kubectl get node -o=custom-columns=Name:'{metadata.name}',Uuid:'{metadata.labels.nodes\\.csi\-baremetal\\.dell\\.com/uuid}'|grep -i $HOSTNAME"
    result = subprocess.check_output(command, shell=True)
    node_name, node_uuid = result.decode().split('\n')[0].split()
    if get_verbose() > 0:
        print(command)
        print(result.decode())
    return node_uuid, node_name
    
def print_node_drive_list(node_uuid):
    command = f"kubectl get drive -o=custom-columns=NAME:.metadata.name,TYPE:.spec.Type,PATH:.spec.Path,NODE:.spec.NodeId,SYSTEM:.spec.IsSystem|grep -E \"{node_uuid}|^NAME\""
    if get_verbose() > 0:
        print(command)
    result = subprocess.check_output(command, shell=True)
    print(result.decode())

def list_drives(args):
    node_uuid, node_name = get_my_node_uuid()
    if node_uuid:
        print_node_drive_list(node_uuid)
    else:
        print("failed to get current node uuid")

def add_arguments(in_parser):
    subparsers = in_parser.add_subparsers(title='hotplug_type', dest='sub_parser')

    # command offline
    off_parser = subparsers.add_parser('off', description='make the specified disk offline', help='make the specified disk offline')
    off_mutually_exclusive_group = off_parser.add_mutually_exclusive_group(required=True)
    off_mutually_exclusive_group.add_argument('-p','--poweroff', action='store_true', help='poweroff nvme disk(only support nvme disk)')
    off_mutually_exclusive_group.add_argument('-r','--remove', action='store_true', help='remove disk(any type)')
    off_parser.add_argument('-d', '--disk', help='disk device name', required=True)
    off_parser.add_argument('-t', '--time', help='disks will be added back after specified seconds', type=int, default=0)
    off_parser.add_argument('-v', '--verbose', help='show what commands were executed', action='count', default=0)
    off_parser.set_defaults(func=device_off)

    # command online
    on_parser = subparsers.add_parser('on', description='make nvme disk online by scan pci bus or power on physlot(only support nvme disk)', help='make nvme disk online(nvme only)')
    '''
    on_mutually_exclusive_group = on_parser.add_mutually_exclusive_group(required=True)
    on_mutually_exclusive_group.add_argument('-p', '--pci', help='scan nvme on pci bus address')
    on_mutually_exclusive_group.add_argument('-s', '--slot', help='power on nvme on pci physlot')
    '''
    on_parser.add_argument('-a', '--action', choices=['poweron', 'rescan'], required=True, help='power on physlot or scan pci bus')
    on_parser.add_argument('-p', '--param', required=True, help='action param, slot or bus determined by action')
    on_parser.add_argument('-v', '--verbose', help='show what commands were executed', action='count', default=0)
    on_parser.set_defaults(func=device_on)

    # command rescan
    rescan_parser = subparsers.add_parser('rescan', description='add back all deleted/power off nvme or/and scsi disks by rescan pci bus/scsi host', help='add back all nvme or/and scsi disks')
    rescan_parser.add_argument('-s', '--scsi', help='add back all scsi disks', action='store_true')
    rescan_parser.add_argument('-n', '--nvme', help='add back all nvme disks', action='store_true')
    rescan_parser.add_argument('-v', '--verbose', help='show what commands were executed', action='count', default=0)
    rescan_parser.set_defaults(func=device_rescan)

    # command list
    list_parser = subparsers.add_parser('list', description='list all drives on current node', help='list all drives on current node')
    list_parser.add_argument('-v', '--verbose', help='show what commands were executed', action='count', default=0)
    list_parser.set_defaults(func=list_drives)

def main():
    parser = argparse.ArgumentParser(description='nvme hotplug error injection tool')
    add_arguments(parser)
    args = parser.parse_args()
    global verbose
    verbose = args.verbose

    args.func(args)


if __name__ == "__main__":
    main()
