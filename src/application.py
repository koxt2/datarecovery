# application.py
#
# Copyright 2025 koxt2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This programme is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public Licence for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import threading
import subprocess
from gi.repository import Adw, Gtk, GLib

from .log import setup_datarecovery_logging
from .mounted_check import MountedPartitionChecker
from .image import pkexec_ddrescue
from .recover import photorec_recover
from .organise_files import organize_and_cleanup
from .preflight import check_tools_exist

logger = None

class DataRecoveryController:
    
    def __init__(self, window):
        self.window = window
        self.current_thread = None
        self.cancel_requested = False
        self.recovery_dialog = None
        self.current_process = None
    
    def toast(self, message):
        toast = Adw.Toast.new(message)
        self.window.toaster.add_toast(toast)
    
    def set_output_label(self, text):
        GLib.idle_add(self.window.output_label.set_text, text)
    
    def choose_destination(self):
        dialog = Gtk.FileDialog.new()
        dialog.set_modal(True)

        def on_response(dialog, result, user_data):
            try:
                folder = dialog.select_folder_finish(result)
                if folder:
                    self.window.destination_path = folder.get_path()
                    self.window.choose_destination_actionrow.set_title(self.window.destination_path) 
            except Exception as e:
                print(f"Dialog error: {e}")

        dialog.select_folder(self.window, None, on_response, None)

    def start_recovery(self):
        device = getattr(self.window, 'device_path', None)
        dest = getattr(self.window, 'destination_path', None)
        
        if not device or not dest:
            self.toast("Please select both device and destination")
            return
        
        # Reset cancel flag
        self.cancel_requested = False
        
        # Show cancellation dialog
        self.recovery_dialog = Adw.AlertDialog.new("Data Recovery in Progress", None)
        self.recovery_dialog.set_body("Data recovery is starting. This process may take a long time to complete.")
        self.recovery_dialog.add_response("cancel", "Cancel")
        self.recovery_dialog.set_response_appearance("cancel", Adw.ResponseAppearance.DESTRUCTIVE)
        
        def on_cancel_response(dialog_obj, response):
            if response == "cancel":
                self.cancel_requested = True
                
                # Create cancel flag file that the helper will check
                try:
                    if hasattr(self, 'cancel_file_path') and self.cancel_file_path:
                        # Use the secure cancel file path provided by the helper
                        with open(self.cancel_file_path, 'w') as f:
                            f.write('cancel')
                        logger.info(f"Cancellation requested - created cancel flag file: {self.cancel_file_path}")
                    elif self.current_process:
                        # Fallback to old method if cancel file path not available
                        helper_pid = self.current_process.pid
                        cancel_file = f'/tmp/datarecovery_cancel_{helper_pid}'
                        with open(cancel_file, 'w') as f:
                            f.write('cancel')
                        logger.info(f"Cancellation requested - created cancel flag file: {cancel_file}")
                except Exception as e:
                    logger.error(f"Error creating cancel flag: {e}")
                
                # Also try to terminate the process directly
                if self.current_process and self.current_process.poll() is None:
                    try:
                        logger.info("Terminating current recovery process...")
                        self.current_process.terminate()
                        # Give it a moment to see the cancel flag and terminate gracefully
                        try:
                            self.current_process.wait(timeout=15)
                            logger.info("Recovery process terminated successfully")
                        except subprocess.TimeoutExpired:
                            logger.warning("Recovery process didn't terminate gracefully, forcing termination...")
                            self.current_process.kill()
                            self.current_process.wait()
                            logger.info("Recovery process forcefully terminated")
                    except Exception as e:
                        logger.error(f"Error terminating recovery process: {e}")
                
                if self.current_thread and self.current_thread.is_alive():
                    self.set_output_label("Cancelling recovery process...")
                dialog_obj.close()
                self.recovery_dialog = None
        
        self.recovery_dialog.connect("response", on_cancel_response)
        self.recovery_dialog.present(self.window)
        
        user_data_dir = GLib.get_user_data_dir()
        working_dir = os.path.join(user_data_dir, "DataRecovery", "working")
        os.makedirs(working_dir, exist_ok=True)
        global logger
        logger = setup_datarecovery_logging(working_dir)
        
        # Create mount checker and check for mounted partitions
        all_block_devices = self.window.device_dropdown_manager.devices + self.window.device_dropdown_manager.partitions
        mount_checker = MountedPartitionChecker(self.window, all_block_devices, logger)

        def proceed_with_recovery():
            self.current_thread = threading.Thread(target=self._run_recovery_process, args=(device, dest, working_dir), daemon=True)
            self.current_thread.start()

        mount_checker.check_and_handle_mounted_partitions(device, dest, proceed_with_recovery)

    def startup_preflight(self):
        ok, missing = check_tools_exist(['ddrescue', 'photorec', 'rdfind', 'udisksctl'])
        if not ok:
            dialog = Adw.AlertDialog.new("Missing dependencies", None)
            body = "The following required tools are not available on your system:\n\n"
            body += "\n".join([f"\u2022 {m}" for m in missing])
            dialog.set_body(body)
            dialog.add_response("quit", "Quit")
            dialog.set_close_response("Quit")

            def on_response(dialog_obj, response):
                if response == "quit":
                    try:
                        app = self.window.get_application()
                        if app:
                            app.quit()
                    except Exception:
                        pass

            dialog.connect("response", on_response)
            dialog.present(self.window)

    def _run_recovery_process(self, device, dest, working_dir):
        try:
            if self.cancel_requested:
                self.set_output_label("Recovery cancelled")
                return
                
            self.set_output_label("Starting data recovery...")
            logger.info("\nStarting Data Recovery Process...")
            logger.info(f"Source: {device}")
            logger.info(f"Destination path: {dest}")
            logger.info(f"Using working directory: {working_dir}")

            # Check if the source is already an image file
            is_image_file = not device.startswith('/dev/')

            if is_image_file:
                if self.cancel_requested:
                    self.set_output_label("Recovery cancelled")
                    return
                    
                logger.info("Source is an image file - skipping ddrescue phase")
                # Copy the image file to the working directory for photorec
                import shutil
                image_filename = os.path.basename(device)
                working_image_path = os.path.join(working_dir, image_filename)

                if device != working_image_path:  # Don't copy if already in working dir
                    self.set_output_label("Copying image file to working directory...")
                    logger.info(f"Copying {device} to {working_image_path}")
                    try:
                        shutil.copy2(device, working_image_path)
                        logger.info("Image file copied successfully")
                    except Exception as e:
                        self.set_output_label("Failed to copy image file. Aborting recovery process.")
                        logger.error(f"Failed to copy image file: {e}")
                        return
            else:
                if self.cancel_requested:
                    self.set_output_label("Recovery cancelled")
                    return
                    
                # If whole device is selected and scan_partitions_switch is enabled, 
                # make a list of all the partitions on that device for separate imaging
                device_partition_paths = []
                scan_partitions = self.window.scan_partitions_switch.get_active()

                if scan_partitions:
                    for partition in self.window.device_dropdown_manager.partitions:
                        if partition['path'].startswith(device) and partition['path'] != device:
                            device_partition_paths.append(partition['path'])

                    if device_partition_paths:
                        logger.info(f"Will create separate images for {len(device_partition_paths)} partitions: {device_partition_paths}")
                    else:
                        logger.info("No partitions found for separate imaging")
                else:
                    logger.info("Partition imaging disabled - will only image the whole device")

                ########## Imaging ##########
                if self.cancel_requested:
                    self.set_output_label("Recovery cancelled")
                    return
                    
                self.set_output_label("Creating device image...")
                logger.info("\n=== Phase 1: Creating Disk Image ===")
                imaging_success = pkexec_ddrescue(device, working_dir, device_partition_paths, self.window.device_dropdown_manager.partitions, self)
                if not imaging_success:
                    self.set_output_label("Failed to create device image. Aborting recovery process.")
                    logger.error("Failed to create device image. Aborting recovery process.")
                    return

            ########## Recovery ##########
            if self.cancel_requested:
                self.set_output_label("Recovery cancelled")
                return
                
            self.set_output_label("Starting recovery from image...")
            logger.info("\n=== Phase 2: Running File Recovery ===")

            # Get selected options
            save_image = self.window.save_image_switch.get_active()
            enable_logs = self.window.log_switch.get_active()
            keep_corrupted_files = self.window.corrupted_switch.get_active()
            remove_duplicates = self.window.dupes_switch.get_active()
            logger.info(f"Save image files: {save_image}")
            logger.info(f"Enable PhotoRec logs: {enable_logs}")
            logger.info(f"Keep corrupted files: {keep_corrupted_files}")
            logger.info(f"Remove duplicate files: {remove_duplicates}")

            recovery_success = photorec_recover(dest, working_dir=working_dir, 
                                     partitions_data=self.window.device_dropdown_manager.partitions, enable_logs=enable_logs,
                                     keep_corrupted_files=keep_corrupted_files, controller=self)

            if not recovery_success:
                self.set_output_label("Recovery process failed.")
                logger.error("File recovery process failed")
                return

            ########## Organise ##########
            if self.cancel_requested:
                self.set_output_label("Recovery cancelled")
                return
                
            self.set_output_label("Organising recovered files...")
            logger.info("\n=== Phase 3: Organising Files ===")
            organize_and_cleanup(working_dir, dest, save_image, enable_logs, remove_duplicates, device, self)

            if self.cancel_requested:
                self.set_output_label("Recovery cancelled")
                return

            self.set_output_label("File recovery process completed successfully")
            logger.info("File recovery process completed successfully")
            logger.info("\nRecovery process finished.")
        finally:
            GLib.idle_add(self._close_recovery_dialog)

    def _close_recovery_dialog(self):
        """Helper method to close the recovery dialog from the main thread"""
        if self.recovery_dialog:
            self.recovery_dialog.close()
            self.recovery_dialog = None
    
