# preflight.py
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
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger('DataRecovery')


def check_tools_exist(tools: List[str]) -> Tuple[bool, List[str]]:
    # return (True, []) if all tools available, otherwise (False, missing_list)
    missing = []
    for t in tools:
        if not shutil.which(t):
            missing.append(t)
    return (len(missing) == 0, missing)


def ensure_dest_writable(path: str) -> Tuple[bool, Optional[str]]:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        return False, f"Failed to create destination path {path}: {e}"

    if not os.access(path, os.W_OK):
        return False, f"Destination path is not writable: {path}"

    return True, None


def check_free_space(path: str, min_bytes: int = 1 << 30) -> Tuple[bool, int]:
    try:
        st = os.statvfs(path)
        free_bytes = st.f_bavail * st.f_frsize
        return (free_bytes >= min_bytes, free_bytes)
    except Exception:
        logger.debug("Unable to determine free space for %s", path)
        return (True, 0)


def validate_partition_paths(paths: List[str]) -> Tuple[List[str], List[str]]:
    valid = []
    skipped = []
    for p in paths:
        if p.startswith('/dev/'):
            valid.append(p)
        elif os.path.exists(p):
            valid.append(p)
        else:
            skipped.append(p)
    return valid, skipped
