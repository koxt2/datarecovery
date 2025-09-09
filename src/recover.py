# recover.py
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
import subprocess
import traceback
import logging
import shutil
import time

logger = logging.getLogger('DataRecovery')

def photorec_recover(dest_path, working_dir=None, partitions_data=None, enable_logs=False, keep_corrupted_files=False, controller=None):
    try:
        logger.info("\nInitializing PhotoRec recovery...")
        recovery_dir = os.path.join(working_dir or dest_path, "recovered_files")
        os.makedirs(recovery_dir, exist_ok=True)
        logger.info(f"Recovery directory: {recovery_dir}")
        
        image_files = _find_image_files(working_dir or dest_path)
        
        if not image_files:
            logger.error("No image files found to scan")
            return False
        
        logger.info(f"Found {len(image_files)} image files to scan")
        
        for image_file in image_files:
            _scan_image_file(image_file, recovery_dir, partitions_data, enable_logs, keep_corrupted_files, controller)
        
        logger.info("\nPhotoRec recovery completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"PhotoRec recovery failed with error: {e}")
        traceback.print_exc()
        return False

def run_photorec_on_source(source_file, output_dir, description="source", enable_logs=False, keep_corrupted_files=False, filesystem_type=None, controller=None):
    try:
        logger.info(f"Scanning {description}: {os.path.basename(source_file)}")

        options_string = "options"

        if filesystem_type and filesystem_type.startswith('ext'):
            options_string += ",mode_ext2"

        if keep_corrupted_files:
            options_string += ",keep_corrupted_file"

        options_string += ",search"

        cmd = ["photorec"]

        if enable_logs:
            cmd.append("/log")

        cmd.extend(["/d", output_dir, "/cmd", source_file, options_string])

        logger.info(f"Command: {' '.join(cmd)}")

        outdir = os.path.dirname(output_dir) or output_dir

        cwd = outdir if os.path.exists(outdir) else os.getcwd()
        logger.info(f"Running PhotoRec with cwd={cwd}")
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
        
        # Poll the process and check for cancellation
        while process.poll() is None:
            if controller and controller.cancel_requested:
                logger.info(f"Cancellation requested, terminating PhotoRec scan of {description}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"PhotoRec scan of {description} didn't terminate gracefully, killing it")
                    process.kill()
                    process.wait()
                logger.info(f"PhotoRec scan of {description} cancelled")
                return False
            time.sleep(1)
        
        # Get the results
        stdout, stderr = process.communicate()
        result_returncode = process.returncode

        if stderr:
            logger.warning(f"\nPhotoRec errors for {description}:")
            logger.warning(stderr)

        if result_returncode == 0:
            logger.info(f"PhotoRec scan of {description} completed successfully")
            return True
        else:
            logger.error(f"PhotoRec scan of {description} failed with error code {result_returncode}")
            return False
    except Exception as e:
        logger.error(f"PhotoRec scan of {description} failed with error: {e}")
        logger.debug(traceback.format_exc())
        return False

def _find_image_files(working_dir):
    image_files = []
    if not working_dir or not os.path.isdir(working_dir):
        logger.info(f"No working directory available to search for images: {working_dir}")
        return image_files

    try:
        for filename in os.listdir(working_dir):
            if filename.endswith('.img'):
                full_path = os.path.join(working_dir, filename)
                image_files.append(full_path)
                logger.info(f"Found image file: {filename}")
        image_files.sort()
    except Exception as e:
        logger.error(f"Failed to list image files in {working_dir}: {e}")

    return image_files

def _scan_image_file(image_file, recovery_dir, partitions_data=None, enable_logs=False, keep_corrupted_files=False, controller=None):
    filename = os.path.basename(image_file)
    name_without_ext = os.path.splitext(filename)[0]
    
    logger.info(f"\n=== Scanning {filename} ===")
    
    output_dir = os.path.join(recovery_dir, name_without_ext)
    os.makedirs(output_dir, exist_ok=True)
    
    filesystem_type = _get_filesystem_type_for_image(filename, partitions_data)
    
    success = run_photorec_on_source(image_file, output_dir, filename, enable_logs, keep_corrupted_files, filesystem_type, controller)
    if not success:
        logger.warning(f"Scan of {filename} failed, continuing...")
        
    return success

def _get_filesystem_type_for_image(filename, partitions_data):
    if not partitions_data:
        logger.info("No partitions_data provided for filesystem detection")
        return None
    
    # For partition images (e.g., sdb1.img), try to find matching partition
    if any(char.isdigit() for char in filename):
        device_name = filename.replace('.img', '')  # sdb1.img -> sdb1
        device_path = f"/dev/{device_name}"  # sdb1 -> /dev/sdb1
        
        logger.info(f"Looking for filesystem type of partition: {device_path}")
        
        # Look for matching partition in the data
        for partition in partitions_data:
            if partition.get('path') == device_path:
                filesystem_type = partition.get('id_type', '')
                logger.info(f"Found filesystem type: {filesystem_type} for {device_name}")
                return filesystem_type
        
        logger.info(f"No filesystem data found for {device_name}")
        return None
    
    # For whole device images, return None (let PhotoRec auto-detect)
    logger.info(f"Whole device image detected ({filename}), no specific filesystem type")
    return None


