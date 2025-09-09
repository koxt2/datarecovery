# image.py
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
import logging
from .preflight import validate_partition_paths
from .image_helper import DDRescueHelper

logger = logging.getLogger('DataRecovery')

def pkexec_ddrescue(device_path, dest_path, partition_paths=None, partitions_data=None, controller=None):
    logger.info("Attempting device access with ddrescue and pkexec...")
    try:
        ddrescue_path = "ddrescue"

        device_name = os.path.basename(device_path)  # sdb from /dev/sdb
        image_file = os.path.join(dest_path, f"{device_name}.img")
        map_file = os.path.join(dest_path, f"{device_name}.map")

        # Determine the user's uid/gid to chown created files back
        owner_uid = os.getuid()
        owner_gid = os.getgid()

        validated_parts, skipped = validate_partition_paths(partition_paths or [])
        for p in skipped:
            logger.warning(f"Partition/image path not valid, skipping: {p}")

        return _create_and_run_helper(device_path, dest_path, validated_parts, owner_uid, owner_gid, controller)
    except Exception as e:
        logger.error(f"pkexec with ddrescue failed: {e}")
        return False

def _create_and_run_helper(device_path, dest_path, partition_paths, owner_uid, owner_gid, controller=None):
    """Create and run ddrescue helper using the DDRescueHelper class"""
    helper = DDRescueHelper(device_path, dest_path, partition_paths, owner_uid, owner_gid)
    return helper.run_with_pkexec(controller)

