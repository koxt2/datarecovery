# duplicates.py
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
import logging
import os
import traceback
import time
from .preflight import check_tools_exist

logger = logging.getLogger('DataRecovery')


def remove_duplicates_with_rdfind(recovery_dir, controller=None):
    try:
        logger.info("=== Scanning For Duplicates ===")
        logger.info(f"Scanning for duplicates in: {recovery_dir}")

        ok, missing = check_tools_exist(['rdfind'])
        if not ok:
            logger.warning(f"Missing required tools: {', '.join(missing)}; skipping duplicate removal")
            return

        # Allow timeout to be configured via env var (in seconds), default 1800 (30 minutes)
        timeout = int(os.environ.get('DATARECOVERY_RDFIND_TIMEOUT', '1800'))

        cmd = ["rdfind", "-deleteduplicates", "true", recovery_dir]

        logger.info("Running rdfind to remove duplicates...")
        
        # Use Popen so we can check for cancellation
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Poll the process and check for cancellation
        start_time = time.time()
        while process.poll() is None:
            if controller and controller.cancel_requested:
                logger.info("Cancellation requested, terminating rdfind duplicate removal")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("rdfind didn't terminate gracefully, killing it")
                    process.kill()
                    process.wait()
                logger.info("Duplicate removal cancelled")
                return
            
            # Check timeout
            if time.time() - start_time > timeout:
                logger.error(f"rdfind timed out after {timeout} seconds")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                return
                
            time.sleep(1)
        
        # Get the results
        stdout, stderr = process.communicate()
        result_returncode = process.returncode

        if result_returncode == 0:
            logger.info("rdfind completed successfully - duplicates removed")
        else:
            logger.warning(f"rdfind failed with return code {result_returncode}")
            if stderr:
                logger.warning(f"rdfind error: {stderr}")

    except subprocess.TimeoutExpired:
        logger.error(f"rdfind timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"Failed to remove duplicates: {e}")
        logger.debug(traceback.format_exc())
        logger.info("Continuing with recovery process")
