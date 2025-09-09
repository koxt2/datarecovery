# organise_files.py
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
import shutil

from .duplicates import remove_duplicates_with_rdfind

def move_image_files_to_destination(working_dir, dest_path, device_path=None):
    try:
        working_dest = os.path.join(dest_path, "WORKING")
        os.makedirs(working_dest, exist_ok=True)
        
        # Determine which files to move based on device type
        if device_path:
            device_name = os.path.basename(device_path)
            is_whole_device = not any(char.isdigit() for char in device_name)
            if is_whole_device:
                target_files = [f"{device_name}.img", f"{device_name}.map"]
            else:
                target_files = None  # Move all files
        else:
            target_files = None
        
        moved_count = cleaned_count = 0
        for filename in os.listdir(working_dir):
            if filename.endswith(('.img', '.map')):
                src_file = os.path.join(working_dir, filename)
                if target_files is None or filename in target_files:
                    shutil.move(src_file, os.path.join(working_dest, filename))
                    moved_count += 1
                else:
                    os.remove(src_file)
                    cleaned_count += 1
        
    except Exception as e:
        pass

def _cleanup_image_files(working_dir):
    try:
        count = 0
        for filename in os.listdir(working_dir):
            if filename.endswith(('.img', '.map')):
                os.remove(os.path.join(working_dir, filename))
                count += 1
    except Exception as e:
        pass

def _handle_log_files(working_path, dest_path, enable_logs):
    current_dir = os.getcwd()
    
    recovery_dir = os.path.join(working_path, "recovered_files")
    
    import logging
    logger = logging.getLogger('DataRecovery')
    logger.info("Looking for logs in:")
    logger.info(f"  Current dir: {current_dir}")
    logger.info(f"  Working path: {working_path}")
    logger.info(f"  Recovery dir: {recovery_dir}")
    
    # Look for log files in multiple locations
    potential_log_locations = [
        (os.path.join(current_dir, "photorec.log"), "recovery_results.log"),
        (os.path.join(working_path, "photorec.log"), "recovery_results.log"),
        (os.path.join(recovery_dir, "photorec.log"), "recovery_results.log"),  # PhotoRec creates logs here
        (os.path.join(current_dir, "results.txt"), "duplicates_results.log"), 
        (os.path.join(working_path, "results.txt"), "duplicates_results.log"),
        (os.path.join(recovery_dir, "results.txt"), "duplicates_results.log"),  # rdfind might create logs here too
        (os.path.join(working_path, "DataRecovery.log"), "DataRecovery.log"),
    ]
    
    logs_dir = os.path.join(dest_path, "WORKING", "logs")
    processed_files = set()  # Track processed files to avoid duplicates
    
    if enable_logs:
        os.makedirs(logs_dir, exist_ok=True)
        for src, dest_name in potential_log_locations:
            if os.path.exists(src) and src not in processed_files:
                dest_path_full = _get_unique_path(logs_dir, dest_name)
                shutil.move(src, dest_path_full)
                processed_files.add(src)
                logger.info(f"Moved log file: {src} -> {dest_path_full}")  
    else:
        for src, _ in potential_log_locations:
            try:
                if os.path.exists(src) and src not in processed_files:
                    os.remove(src)
                    processed_files.add(src)
                    logger.info(f"Removed log file: {src}")
            except Exception:
                pass

def _get_unique_path(directory, filename):
    dest_path = os.path.join(directory, filename)
    counter = 1
    base_name, ext = os.path.splitext(filename)
    while os.path.exists(dest_path):
        new_name = f"{base_name}_{counter}{ext}"
        dest_path = os.path.join(directory, new_name)
        counter += 1
    return dest_path

def organize_files_by_type(working_path, dest_path, enable_logs=False):
    try:
        photorec_dirs = []
        for item in os.listdir(working_path):
            item_path = os.path.join(working_path, item)
            if os.path.isdir(item_path) and item.startswith('recovered_files'):
                photorec_dirs.append(item_path)
        
        if not photorec_dirs:
            return False
        
        # Process files by extension
        processed = 0
        while True:
            current_ext = None
            files_no_ext = []
            
            # Find files to process
            for dir_path in photorec_dirs:
                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        if file in ["report.xml"] or file.endswith("_report.xml"):
                            # Delete XML report files instead of moving them
                            try:
                                os.remove(os.path.join(root, file))
                            except Exception:
                                pass
                            continue
                        
                        if '.' in file and not file.startswith('.'):
                            ext = os.path.splitext(file)[1][1:].lower()
                            if ext and not current_ext:
                                current_ext = ext
                        else:
                            files_no_ext.append(os.path.join(root, file))
            
            # Process files without extensions first
            if files_no_ext and not current_ext:
                processed += _process_files_without_extension(files_no_ext, dest_path)
                continue
            
            # Process files with current extension
            if current_ext:
                processed += _process_files_with_extension(photorec_dirs, current_ext, dest_path)
            else:
                break
        
        _cleanup_empty_dirs(photorec_dirs)
        return processed > 0
        
    except Exception as e:
        return False

def _process_files_without_extension(files, dest_path):
    no_ext_dir = os.path.join(dest_path, "no_file_type")
    corrupted_dir = os.path.join(dest_path, "corrupted")
    os.makedirs(no_ext_dir, exist_ok=True)
    
    processed = 0
    for file_path in files:
        filename = os.path.basename(file_path)
        if filename.lower().startswith('b'):
            os.makedirs(corrupted_dir, exist_ok=True)
            dest = _get_unique_path(corrupted_dir, filename)
        else:
            dest = _get_unique_path(no_ext_dir, filename)
        
        shutil.copy2(file_path, dest)
        os.remove(file_path)
        processed += 1
    
    return processed

def _process_files_with_extension(photorec_dirs, extension, dest_path):
    filetype_dir = os.path.join(dest_path, extension)
    corrupted_dir = os.path.join(dest_path, "corrupted")
    os.makedirs(filetype_dir, exist_ok=True)
    
    processed = 0
    for dir_path in photorec_dirs:
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith(f'.{extension}'):
                    src = os.path.join(root, file)
                    if file.lower().startswith('b'):
                        os.makedirs(corrupted_dir, exist_ok=True)
                        dest = _get_unique_path(corrupted_dir, file)
                    else:
                        dest = _get_unique_path(filetype_dir, file)
                    
                    shutil.copy2(src, dest)
                    os.remove(src)
                    processed += 1
    
    return processed

def _cleanup_empty_dirs(photorec_dirs):
    for dir_path in photorec_dirs:
        for root, dirs, files in os.walk(dir_path, topdown=False):
            for dirname in dirs:
                try:
                    os.rmdir(os.path.join(root, dirname))
                except OSError:
                    pass
        try:
            os.rmdir(dir_path)
        except OSError:
            pass

def organize_and_cleanup(working_dir, dest_path, save_image, enable_logs=False, remove_duplicates=False, device_path=None, controller=None):
    recovery_dir = os.path.join(working_dir or dest_path, "recovered_files")
    
    if save_image:
        move_image_files_to_destination(working_dir or dest_path, dest_path, device_path)
    else:
        _cleanup_image_files(working_dir or dest_path)
    
    if remove_duplicates:
        remove_duplicates_with_rdfind(recovery_dir, controller)
    
    _handle_log_files(working_dir or dest_path, dest_path, enable_logs)
    
    success = organize_files_by_type(working_dir or dest_path, dest_path, enable_logs)

    if success and working_dir:
        try:
            shutil.rmtree(working_dir)
        except Exception:
            pass
    return success
