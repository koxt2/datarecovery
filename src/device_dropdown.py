# device_dropdown.py
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

from gi.repository import Gtk

from .block_devices import udisks2_block_devices, UDisks2Monitor

class DeviceDropdownManager:
    # Manages device detection, selection, and monitoring
    def __init__(self, window):
        self.window = window
        self.devices = []
        self.partitions = []
        self.columnview_manager = None
        
        self.populate_device_selector()
        self.udisks_monitor = UDisks2Monitor(callback=self._repopulate_device_selector)
        
        self.window.select_device_dropdown.connect("notify::selected", self.on_device_selected)
    
    def populate_device_selector(self):
        self.devices, self.partitions = udisks2_block_devices()
        self.window.device_liststore.append(Gtk.StringObject.new("Select a device..."))
        self.window.device_liststore.append(Gtk.StringObject.new("Select image file..."))
        
        for device in self.devices:
            self.window.device_liststore.append(Gtk.StringObject.new(self._format_device_label(device)))
        
        self.window.select_device_dropdown.set_selected(0)
    
    def _repopulate_device_selector(self, devices=None, partitions=None):
        if devices is not None and partitions is not None:
            print("Device list updated due to udisks2 changes")
            self.devices = devices
            self.partitions = partitions

        current_selection = self.window.select_device_dropdown.get_selected()
        current_device = None
        image_files = []

        # Collect any image files that were manually added
        for i in range(2, self.window.device_liststore.get_n_items()):  # Skip first two items
            item_text = self.window.device_liststore.get_item(i).get_string()
            # If it's not a device path (doesn't start with /dev), it's likely an image file
            if not item_text.startswith('/dev'):
                image_files.append(item_text)
            elif current_selection == i:
                # Store currently selected device path for restoration
                for device in self.devices:
                    if self._format_device_label(device) == item_text:
                        current_device = device['path']
                        break

        self.window.device_liststore.remove_all()
        self.window.device_liststore.append(Gtk.StringObject.new("Select a device..."))
        self.window.device_liststore.append(Gtk.StringObject.new("Select image file..."))

        # Add devices
        new_selection = 0
        for i, device in enumerate(self.devices):
            self.window.device_liststore.append(Gtk.StringObject.new(self._format_device_label(device)))

            # Restore previous device selection if it still exists
            if current_device and device['path'] == current_device:
                new_selection = i + 2

        # Re-add any image files
        for image_file in image_files:
            self.window.device_liststore.append(Gtk.StringObject.new(image_file))
            # If an image file was selected, restore that selection
            if current_selection >= len(self.devices) + 2:
                # Calculate if this was the selected image file
                image_index = current_selection - len(self.devices) - 2
                if image_index < len(image_files) and image_files[image_index] == image_file:
                    new_selection = self.window.device_liststore.get_n_items() - 1

        self.window.select_device_dropdown.set_selected(new_selection)

        # Update the column view to reflect mount status changes
        if devices is not None and partitions is not None and self.columnview_manager:
            self.columnview_manager.refresh_device_liststore()

    def _format_device_label(self, device):
        label = device['path']
        details = []
        if device.get('model'):
            details.append(str(device['model']))
        if device.get('serial'):
            details.append(str(device['serial']))
        if details:
            label += " (" + " ".join(details) + ")"
        return label
    
    def on_device_selected(self, widget, param):
        selected = self.window.select_device_dropdown.get_selected()
        
        if selected == 1:
            self._handle_image_file_selection()
        elif selected > 1:
            # Check if this is an image file or a device
            item = self.window.device_liststore.get_item(selected)
            if item is None:
                return  # Device list is being updated, ignore this selection
            selected_text = item.get_string()
            
            # If it doesn't start with /dev, it's likely an image file
            if not selected_text.startswith('/dev'):
                self._handle_existing_image_selection(selected_text)
            else:
                self._handle_device_selection(selected)
        else:
            self._handle_no_selection()
    
    def _handle_image_file_selection(self):
        if hasattr(self.window, 'columnview_liststore'):
            self.window.columnview_liststore.remove_all()
        self.window.scan_partitions_switch.set_sensitive(False)
        self.window.scan_partitions_switch.set_active(False)
        
        dialog = Gtk.FileDialog.new()
        dialog.set_modal(True)
        
        def on_file_selected(dialog, result, user_data):
            try:
                file = dialog.open_finish(result)
                if file:
                    self._add_image_to_selector(file.get_path())
                else:
                    # Reset to "Select a device..." if no file was selected
                    self.window.select_device_dropdown.set_selected(0)
            except Exception as e:
                print(f"FileDialog error: {e}")
                # Reset selection if file dialog failed
                self.window.select_device_dropdown.set_selected(0)
        
        dialog.open(self.window, None, on_file_selected, None)
    
    def _handle_existing_image_selection(self, image_path):
        """Handle selection of an existing image file from the dropdown"""
        self.window.scan_partitions_switch.set_sensitive(False)
        self.window.scan_partitions_switch.set_active(False)
        self.window.save_image_switch.set_sensitive(False)
        self.window.save_image_switch.set_active(False)
        
        # Update window state for selected image
        self.window.device_path = image_path
        if self.columnview_manager:
            self.columnview_manager.update_columnview_for_image(image_path)
    
    def _handle_device_selection(self, selected):
        self.window.save_image_switch.set_sensitive(True)
        self.window.scan_partitions_switch.set_sensitive(True)
        
        # Convert to the correct 1-based index for _populate_columnview
        device_index = selected - 1
        if self.columnview_manager:
            self.columnview_manager._populate_columnview(device_index)
            
            # Set the device_path for the selected device
            actual_device_index = selected - 2  # 0-based index into devices array
            if 0 <= actual_device_index < len(self.devices):
                self.window.device_path = self.devices[actual_device_index]['path']
    
    def _handle_no_selection(self):
        if hasattr(self.window, 'columnview_liststore'):
            self.window.columnview_liststore.remove_all()

        self.window.scan_partitions_switch.set_sensitive(False)
        self.window.scan_partitions_switch.set_active(False)
        self.window.save_image_switch.set_sensitive(True)
    
    def _add_image_to_selector(self, path):
        # Check if image is already in the list
        for i in range(self.window.device_liststore.get_n_items()):
            if self.window.device_liststore.get_item(i).get_string() == path:
                self.window.select_device_dropdown.set_selected(i)
                # Update window state for selected image
                self.window.device_path = path
                if self.columnview_manager:
                    self.columnview_manager.update_columnview_for_image(path)
                return

        self.window.device_liststore.append(Gtk.StringObject.new(path))
        self.window.select_device_dropdown.set_selected(self.window.device_liststore.get_n_items() - 1)

        # Update window state for selected image
        self.window.device_path = path
        if self.columnview_manager:
            self.columnview_manager.update_columnview_for_image(path)