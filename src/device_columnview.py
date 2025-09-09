# device_columnview.py
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

import os
from gi.repository import GObject, Gtk

from .partition_guids import PARTITION_TYPE_GUIDS

class PartitionRow(GObject.Object):
    __gtype_name__ = 'PartitionRow'

    def __init__(self, mounted = False, path='', size='', filesystem='', label='', type='', mount_path=None):
        super().__init__()
        self._mounted = mounted
        self._path = path
        self._size = size
        self._filesystem = filesystem
        self._label = label
        self._type = type
        self._mount_path = mount_path

    @GObject.Property(type=bool, default=False)
    def mounted(self):
        return self._mounted

    @GObject.Property(type=str)
    def path(self):
        return self._path

    @GObject.Property(type=str)
    def size(self):
        return self._size

    @GObject.Property(type=str)
    def filesystem(self):
        return self._filesystem

    @GObject.Property(type=str)
    def label(self):
        return self._label

    @GObject.Property(type=str)
    def type(self):
        return self._type

    @GObject.Property(type=str)
    def mount_path(self):
        return self._mount_path

class DeviceColumnViewManager:
    def __init__(self, window, device_dropdown_manager):
        self.window = window
        self.device_dropdown_manager = device_dropdown_manager
        self.setup_factories()

        self.window.columnview_model.connect('notify::selected', self.on_row_selected)

    def setup_factories(self):
        self.window.mounted_factory.connect("setup", self._mounted_factory_setup)
        self.window.mounted_factory.connect("bind", self._mounted_factory_bind('mounted'))
        self.window.device_path_factory.connect("setup", self._label_factory_setup)
        self.window.device_path_factory.connect("bind", self._label_factory_bind('path'))
        self.window.size_factory.connect("setup", self._label_factory_setup)
        self.window.size_factory.connect("bind", self._label_factory_bind('size'))
        self.window.filesystem_factory.connect("setup", self._label_factory_setup)
        self.window.filesystem_factory.connect("bind", self._label_factory_bind('filesystem'))
        self.window.label_factory.connect("setup", self._label_factory_setup)
        self.window.label_factory.connect("bind", self._label_factory_bind('label'))
        self.window.type_factory.connect("setup", self._label_factory_setup)
        self.window.type_factory.connect("bind", self._label_factory_bind('type'))
    
    def _label_factory_setup(self, factory, item):
        label = Gtk.Label()
        label.set_halign(Gtk.Align.START)
        item.set_child(label)

    def _label_factory_bind(self, prop):
        def bind_func(factory, item):
            label = item.get_child()
            row = item.get_item()
            label.set_label(getattr(row, prop, ''))
        return bind_func
    
    def _mounted_factory_setup(self, factory, item):
        check = Gtk.CheckButton()
        check.set_sensitive(False)  # Read-only
        check.set_halign(Gtk.Align.CENTER)
        item.set_child(check)

    def _mounted_factory_bind(self, prop):
        def bind_func(factory, item):
            check = item.get_child()
            row = item.get_item()
            # The mounted property is expected to be a bool
            check.set_active(bool(getattr(row, prop, False)))
            # Set mount path as tooltip
            mount_path = getattr(row, 'mount_path', None)
            if mount_path:
                check.set_tooltip_text(mount_path)
            else:
                check.set_tooltip_text(None)
        return bind_func
   
    def _format_size(self, size_bytes):
        if not size_bytes:
            return "0 MB"
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > 1000:
            return f"{size_mb/1024:.2f} GB"
        else:
            return f"{size_mb:.2f} MB"
    
    def _populate_columnview(self, idx):
        self.window.columnview_liststore.remove_all()
        
        if idx <= 0 or idx > len(self.device_dropdown_manager.devices):
            return
            
        device = self.device_dropdown_manager.devices[idx - 1] # Get the list of devices from device manager but skip the placeholder 'select a device'
        
        # Find partitions for this device
        matching_parts = [
            p for p in self.device_dropdown_manager.partitions
            if p['path'].startswith(device['path']) and p['path'] != device['path']
        ]
        
        # Always show the whole device as a row
        size_str = self._format_size(device.get('size', 0))
        part_type_name = 'WHOLE DEVICE'
        row = PartitionRow(
            mounted=device.get('mounted', False),
            path=device['path'],
            size=size_str,
            filesystem=device.get('id_type', ''),
            label=device.get('label', ''),
            type=part_type_name,
            mount_path=device.get('mount_path')
        )
        self.window.columnview_liststore.append(row)
        
        # Then show all partitions (if any)
        for p in matching_parts:
            size_str = self._format_size(p.get('size', 0))
            part_type_guid = p.get('partition_type', '')
            part_type_name = PARTITION_TYPE_GUIDS.get(part_type_guid.lower(), part_type_guid) if part_type_guid else ''
            row = PartitionRow(
                mounted=p.get('mounted', False),
                path=p.get('path', ''),
                size=size_str,
                filesystem=p.get('id_type', ''),
                label=p.get('label', ''),
                type=part_type_name,
                mount_path=p.get('mount_path')
            )
            self.window.columnview_liststore.append(row)
        
        # Disable scan partitions switch if there are no partitions
        if not matching_parts:
            self.window.scan_partitions_switch.set_sensitive(False)
            self.window.scan_partitions_switch.set_active(False)

    def on_row_selected(self, selection, param):
        selected_index = self.window.columnview_model.get_selected()
        if selected_index != -1:
            item = self.window.columnview_liststore.get_item(selected_index)
            if item is not None:
                self.window.device_path = item.path
                self.window.filesystem = item.filesystem
                
                # Enable scan_partitions_switch only if a whole device is selected AND has partitions
                is_whole_device = (item.type == 'WHOLE DEVICE')
                if is_whole_device:
                    # Check if this device has any partitions
                    matching_parts = [
                        p for p in self.device_dropdown_manager.partitions
                        if p['path'].startswith(item.path) and p['path'] != item.path
                    ]
                    has_partitions = len(matching_parts) > 0
                    self.window.scan_partitions_switch.set_sensitive(has_partitions)
                    if not has_partitions:
                        self.window.scan_partitions_switch.set_active(False)
                else:
                    self.window.scan_partitions_switch.set_sensitive(False)
                    self.window.scan_partitions_switch.set_active(False)
    
    def refresh_device_liststore(self):
        # Refresh the columnview with updated device/partition data
        current_selection = self.window.select_device_dropdown.get_selected()
        
        # If a device is selected, refresh only the mount status instead of clearing everything
        if current_selection > 1:  # Skip "Select a device..." and "Select image file..."
            self._refresh_mount_status()
        elif current_selection > 0:
            self._populate_columnview(current_selection)
    
    def _refresh_mount_status(self):
        # Update only the mounted status of existing entries without clearing the list
        current_selected_index = self.window.columnview_model.get_selected()
        current_selected_item = None
        if current_selected_index != -1:
            current_selected_item = self.window.columnview_liststore.get_item(current_selected_index)
        
        n_items = self.window.columnview_liststore.get_n_items()
        
        for i in range(n_items):
            row = self.window.columnview_liststore.get_item(i)
            if row:
                device_path = row.path                
                is_mounted = False
                mount_path = None
                
                for partition in self.device_dropdown_manager.partitions:
                    if partition['path'] == device_path:
                        is_mounted = partition.get('mounted', False)
                        mount_path = partition.get('mount_path')
                        break
                
                # Update the row's mounted status
                row.mounted = is_mounted
                row.mount_path = mount_path
        
        # reselect the current selection
        if current_selected_item is not None:
            for i in range(n_items):
                item = self.window.columnview_liststore.get_item(i)
                if item and item.path == current_selected_item.path:
                    self.window.columnview_model.set_selected(i)
                    break

    def update_columnview_for_image(self, image_path):
        self.window.columnview_liststore.remove_all()
        size_str = self._format_size(os.path.getsize(image_path) if os.path.exists(image_path) else 0)
        row = PartitionRow(
            mounted=False,
            path=image_path,
            size=size_str,
            filesystem='',
            label=os.path.basename(image_path),
            type='IMAGE FILE'
        )
        self.window.columnview_liststore.append(row)
        
        self.window.save_image_switch.set_sensitive(False)
        self.window.save_image_switch.set_active(False)