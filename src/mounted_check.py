# mounted_check.py
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

import subprocess
from gi.repository import Adw, GLib

class MountedPartitionChecker:
    def __init__(self, parent_window, block_devices, logger=None):
        self.parent_window = parent_window
        self.block_devices = block_devices
        self.logger = logger
    
    def check_and_handle_mounted_partitions(self, device_path, dest, success_callback):
        if self.logger:
            self.logger.info(f"Checking for mounted devices/partitions on device: {device_path}")
        
        mounted_partitions = []
        
        for block_device in self.block_devices:
            if ((block_device['path'] == device_path or block_device['path'].startswith(device_path)) and 
                block_device.get('mounted', False) and 
                block_device.get('mount_path')):
                
                mount_path = block_device['mount_path']
                
                critical_mounts = ['/', '/home', '/boot', '/usr', '/var', '/tmp', '/opt']
                if mount_path in critical_mounts:
                    if self.logger:
                        self.logger.error(f"Critical system partition detected: {block_device['path']} mounted at {mount_path}")
                    self.parent_window.app_controller.toast(f"Cannot proceed: Critical system partition {block_device['path']} is mounted at {mount_path}")
                    return False
                
                if self.logger:
                    device_type = "device" if block_device['path'] == device_path else "partition"
                    self.logger.warning(f"Found mounted {device_type}: {block_device['path']} → {mount_path}")
                mounted_partitions.append({
                    'path': block_device['path'],
                    'mount_path': mount_path
                })
        
        if not mounted_partitions:
            if self.logger:
                self.logger.info("No mounted devices/partitions found, proceeding with recovery")
            success_callback()
            return True
        
        if self.logger:
            self.logger.info(f"Found {len(mounted_partitions)} mounted partitions, showing unmount dialog")

        self._show_unmount_dialog(mounted_partitions, device_path, dest, success_callback)
        return False
    
    def _show_unmount_dialog(self, mounted_partitions, device_path, dest, success_callback):
        if self.logger:
            self.logger.info("=== Starting unmount dialog process ===")
            self.logger.info(f"Device: {device_path}")
            self.logger.info(f"Destination: {dest}")
            self.logger.info(f"Number of mounted partitions: {len(mounted_partitions)}")
            self.logger.info("Displaying unmount dialog to user")
            for partition in mounted_partitions:
                self.logger.info(f"  - {partition['path']} mounted at {partition['mount_path']}")
        
        partition_list = "\n".join([f"• {p['path']} → {p['mount_path']}" for p in mounted_partitions])
        
        dialog = Adw.AlertDialog.new("Mounted Partitions Detected", None)
        
        body_text = f"The following partitions are currently mounted:\n\n{partition_list}\n\nUnmounting recommended before creating disk images."
        dialog.set_body(body_text)
        
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("continue", "Continue Anyway")
        dialog.add_response("unmount", "Unmount & Continue")
        
        dialog.set_response_appearance("unmount", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_response_appearance("continue", Adw.ResponseAppearance.DESTRUCTIVE)
        
        dialog.set_default_response("unmount")
        dialog.set_close_response("cancel")
        
        def on_response(dialog, response):
            if self.logger:
                self.logger.info(f"User selected dialog response: {response}")
            
            if response == "unmount":
                success = True
                failed_partitions = []
                for partition in mounted_partitions:
                    if not self._unmount_partition(partition['path']):
                        success = False
                        failed_partitions.append(partition['path'])
                
                if success:
                    if self.logger:
                        self.logger.info("All partitions unmounted successfully, proceeding with recovery")
                    GLib.idle_add(success_callback)
                else:
                    if self.logger:
                        self.logger.error(f"Failed to unmount partitions: {failed_partitions}")
                    self.parent_window.app_controller.toast(f"Failed to unmount: {', '.join(failed_partitions)}")
            elif response == "continue":
                if self.logger:
                    self.logger.warning("User chose to continue with mounted partitions - this may cause data corruption")
                GLib.idle_add(success_callback)
            else:  # cancel
                if self.logger:
                    self.logger.info("User cancelled recovery due to mounted partitions")
        
        dialog.connect("response", on_response)
        dialog.present(self.parent_window)
    
    def _unmount_partition(self, partition_path):
        if self.logger:
            self.logger.info(f"Attempting to unmount partition: {partition_path}")
        try:
            result = subprocess.run(
                ["udisksctl", "unmount", "-b", partition_path],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                if self.logger:
                    self.logger.info(f"Successfully unmounted {partition_path}")
                print(f"Successfully unmounted {partition_path}")
                return True
            else:
                if self.logger:
                    self.logger.error(f"Failed to unmount {partition_path}: {result.stderr}")
                print(f"Failed to unmount {partition_path}: {result.stderr}")
                return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"Exception while unmounting {partition_path}: {e}")
            print(f"Exception unmounting {partition_path}: {e}")
            return False
