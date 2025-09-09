# log.py
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

import logging
import os

class WorkingDirectoryFileHandler(logging.FileHandler):
    def __init__(self, working_dir):
        log_path = os.path.join(working_dir, "DataRecovery.log")
        super().__init__(log_path, mode='a', encoding='utf-8')


def setup_datarecovery_logging(working_dir):
    logger = logging.getLogger('DataRecovery')
    logger.setLevel(logging.INFO)

    logger.handlers = []

    file_handler = WorkingDirectoryFileHandler(working_dir)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger
