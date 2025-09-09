# block_devices.py
#
# Copyright 2025 koxt2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# SPDX-License-Identifier: GPL-2.0-or-later

import re

import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

def udisks2_block_devices():
    devices, partitions = [], []
    
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        manager = Gio.DBusObjectManagerClient.new_sync(
            bus, Gio.DBusObjectManagerClientFlags.NONE,
            'org.freedesktop.UDisks2', '/org/freedesktop/UDisks2', None, None, None)
        
        for obj in manager.get_objects():
            block = obj.get_interface('org.freedesktop.UDisks2.Block')
            if not block:
                continue
            
            path = _get_device_path(block)
            model, serial = _get_drive_info(manager, block)
            
            # Get mount status and path
            filesystem = obj.get_interface('org.freedesktop.UDisks2.Filesystem')
            mount_points = []
            if filesystem:
                mount_points = filesystem.get_cached_property('MountPoints').unpack()
            is_mounted = bool(mount_points and len(mount_points) > 0)
            mount_path = None
            if is_mounted and mount_points[0]:
                # Mount points come as list of byte values, convert to string
                if isinstance(mount_points[0], list):
                    mount_path = bytes(mount_points[0]).decode('utf-8').rstrip('\x00')
                elif isinstance(mount_points[0], (bytes, bytearray)):
                    mount_path = mount_points[0].decode('utf-8').rstrip('\x00')
                else:
                    mount_path = str(mount_points[0]).rstrip('\x00')

            info = {
                'path': path,
                'model': model,
                'serial': serial,
                'size': block.get_cached_property('Size').unpack(),
                'id_type': block.get_cached_property('IdType').unpack(),
                'label': block.get_cached_property('IdLabel').unpack(),
                'partition_type': _get_partition_type(obj, block),
                'mounted': is_mounted,
                'mount_path': mount_path,
            }
            
            if _is_device(path):
                devices.append(info)
            elif _is_partition(path):
                partitions.append(info)
                
    except Exception as e:
        print(f"Failed to list block devices via UDisks2: {e}")
    
    return devices, partitions

def _get_device_path(block_interface):
    device = block_interface.get_cached_property('Device').unpack()
    if isinstance(device, (bytes, bytearray)):
        return device.decode('utf-8').rstrip('\x00')
    elif isinstance(device, list):
        return bytes(device).decode('utf-8').rstrip('\x00')
    else:
        return str(device)

def _get_drive_info(manager, block_interface):
    #Get model and serial from drive interface if available
    drive_path = block_interface.get_cached_property('Drive').unpack()
    if not drive_path:
        return None, None
    
    drive_obj = manager.get_object(drive_path)
    if not drive_obj:
        return None, None
    
    drive = drive_obj.get_interface('org.freedesktop.UDisks2.Drive')
    if not drive:
        return None, None
    
    model = drive.get_cached_property('Model').unpack()
    serial = drive.get_cached_property('Serial').unpack()
    return model, serial

def _get_partition_type(obj, block_interface):
    partition = obj.get_interface('org.freedesktop.UDisks2.Partition')
    if not partition:
        return None
    
    # Try to get partition type GUID first (for GPT)
    partition_type = partition.get_cached_property('Type')
    if partition_type:
        return partition_type.unpack()
    
    # For MBR partitions, get the type ID
    type_id = partition.get_cached_property('TypeID')
    if type_id:
        return f"0x{type_id.unpack():02x}"
    
    return None

def _is_device(path):
    # Check to see if it a device
    patterns = [
        re.compile(r'^/dev/sd[a-z]$'),
        re.compile(r'^/dev/nvme\d+n\d+$'),
        re.compile(r'^/dev/mmcblk\d+$')
    ]
    return any(p.match(path) for p in patterns)

def _is_partition(path):
    # Check to see if it a partition
    patterns = [
        re.compile(r'^/dev/sd[a-z][0-9]+$'),
        re.compile(r'^/dev/nvme\d+n\d+p\d+$'),
        re.compile(r'^/dev/mmcblk\d+p\d+$')
    ]
    return any(p.match(path) for p in patterns)


class UDisks2Monitor:
    # Monitor for changes to block devices... un/mount, device added/removed etc

    def __init__(self, callback=None):
        self.callback = callback
        self.manager = None
        self.bus = None
        self._setup_monitor()
    
    def _setup_monitor(self):
        # Set up the udisks2 object manager and connect signals
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self.manager = Gio.DBusObjectManagerClient.new_sync(
                self.bus, Gio.DBusObjectManagerClientFlags.NONE,
                'org.freedesktop.UDisks2', '/org/freedesktop/UDisks2', None, None, None)
            
            # Connect to object added/removed signals
            self.manager.connect('object-added', self._on_object_changed)
            self.manager.connect('object-removed', self._on_object_changed)
            
            # Connect to interface property changes (for mount/unmount events)
            self.manager.connect('interface-proxy-properties-changed', self._on_properties_changed)
            
            print("UDisks2 monitor initialized successfully")
            
        except Exception as e:
            print(f"Failed to initialize UDisks2 monitor: {e}")
    
    def _on_object_changed(self, manager, obj):
        object_path = obj.get_object_path()
        
        # Only care about block devices, not jobs or other objects
        if not object_path.startswith('/org/freedesktop/UDisks2/block_devices/'):
            return
            
        print(f"UDisks2: Device added/removed: {object_path}")
        self._notify_change()
    
    def _on_properties_changed(self, manager, interface_proxy, changed_properties, invalidated_properties, *args):
        object_path = interface_proxy.get_object_path()
        
        # Only care about block devices, not jobs or other objects
        if not object_path.startswith('/org/freedesktop/UDisks2/block_devices/'):
            return
            
        print(f"UDisks2: Properties changed on {object_path}")
        self._notify_change()
    
    def _notify_change(self):
        # Refresh device list and notify callback
        if self.callback:
            try:
                devices, partitions = udisks2_block_devices()
                GLib.idle_add(self.callback, devices, partitions)
            except Exception as e:
                print(f"Error refreshing device list: {e}")
    
    def stop(self):
        # Stop monitoring
        if self.manager:
            self.manager = None
        if self.bus:
            self.bus = None
        print("UDisks2 monitor stopped")

