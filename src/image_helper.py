# image_helper.py
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
import tempfile
import logging
from gi.repository import GLib

logger = logging.getLogger('DataRecovery')


class DDRescueHelper:
    """Manages ddrescue execution through a secure helper script via pkexec"""
    
    def __init__(self, device_path, dest_path, partition_paths, owner_uid, owner_gid):
        self.device_path = device_path
        self.dest_path = dest_path
        self.partition_paths = partition_paths or []
        self.owner_uid = owner_uid
        self.owner_gid = owner_gid
        
        # Temporary file paths
        self.helper_path = None
        self.cancel_file_path = None
        self.helper_fd = None
        
        # Cache directory for secure temp files
        self.cache_dir = os.path.join(GLib.get_user_cache_dir(), 'datarecovery')
        os.makedirs(self.cache_dir, exist_ok=True, mode=0o700)
    
    def create_helper_script(self):
        """Generate the Python helper script for ddrescue execution"""
        helper_template = '''#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import signal
import time
import tempfile

current_process = None
cancel_file = None  # Will be set to secure location in main()

def check_cancel():
    """Check if cancellation was requested"""
    return os.path.exists(cancel_file.format(pid=os.getpid()))

def signal_handler(signum, frame):
    global current_process
    print(f'Received signal {signum}, terminating...', file=sys.stderr)
    if current_process and current_process.poll() is None:
        print('Terminating ddrescue process...', file=sys.stderr)
        current_process.terminate()
        try:
            current_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print('Force killing ddrescue process...', file=sys.stderr)
            current_process.kill()
            current_process.wait()
    sys.exit(1)

def run(cmd):
    global current_process
    print('RUN:', ' '.join(cmd))
    
    # Check for cancellation before starting
    if check_cancel():
        print('Cancellation requested before ddrescue execution, stopping', file=sys.stderr)
        sys.exit(1)
    
    current_process = subprocess.Popen(cmd)
    
    # Poll the process and check for cancellation
    while current_process.poll() is None:
        time.sleep(1)
        if check_cancel():
            print('Cancellation requested during ddrescue execution, terminating...', file=sys.stderr)
            current_process.terminate()
            try:
                current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print('Force killing ddrescue process...', file=sys.stderr)
                current_process.kill()
                current_process.wait()
            print('ddrescue imaging cancelled', file=sys.stderr)
            sys.exit(1)
    
    returncode = current_process.returncode
    current_process = None
    
    if returncode != 0:
        print('Command failed:', ' '.join(cmd), file=sys.stderr)
        sys.exit(returncode)

def main():
    global cancel_file, pid_file_path
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create secure cancel file in user's runtime directory
    runtime_dir = os.environ.get('XDG_RUNTIME_DIR', '/tmp')
    cancel_fd, cancel_file = tempfile.mkstemp(
        dir=runtime_dir,
        prefix='datarecovery_cancel_',
        suffix='.flag'
    )
    os.fchmod(cancel_fd, 0o600)  # Set secure permissions
    os.close(cancel_fd)  # We just need the filename, close the descriptor
    os.remove(cancel_file)  # Remove the file, we'll create it when cancellation is requested
    
    # Write our PID to a secure file so the parent can signal us
    pid_file_path = None
    try:
        # Create PID file with secure permissions in user's runtime directory
        runtime_dir = os.environ.get('XDG_RUNTIME_DIR', '/tmp')
        pid_file_fd, pid_file_path = tempfile.mkstemp(
            dir=runtime_dir,
            prefix='datarecovery_helper_',
            suffix='.pid'
        )
        os.fchmod(pid_file_fd, 0o600)  # Set secure permissions
        with os.fdopen(pid_file_fd, 'w') as f:
            f.write(str(os.getpid()))
            f.flush()
            os.fsync(f.fileno())
    except:
        pass  # Continue even if we can't write PID file
    
    p = argparse.ArgumentParser()
    p.add_argument('--device', required=True)
    p.add_argument('--dest', required=True)
    p.add_argument('--partitions', nargs='*', default=[]) 
    p.add_argument('--owner-uid', type=int, required=True)
    p.add_argument('--owner-gid', type=int, required=True)
    p.add_argument('--cancel-file', required=True)
    args = p.parse_args()
    
    # Use the cancel file path provided by parent
    cancel_file = args.cancel_file

    dd = 'ddrescue'
    dev = args.device
    dest = args.dest
    img = os.path.join(dest, os.path.basename(dev) + '.img')
    mapf = os.path.join(dest, os.path.basename(dev) + '.map')

    stages = [
        [dd, '--force', '--no-scrape', '--verbose', dev, img, mapf],
        [dd, '--force', '--idirect', '--retry-passes=3', '--no-scrape', '--verbose', dev, img, mapf],
        [dd, '--force', '--idirect', '--retry-passes=3', '--reverse', '--verbose', dev, img, mapf],
        [dd, '--force', '--idirect', '--retry-passes=3', '--verbose', dev, img, mapf],
    ]

    try:
        for cmd in stages:
            if check_cancel():
                print('Cancellation requested before ddrescue stage, stopping', file=sys.stderr)
                sys.exit(1)
                
            run(cmd)
            try:
                os.chown(img, args.owner_uid, args.owner_gid)
                os.chown(mapf, args.owner_uid, args.owner_gid)
            except Exception as e:
                print('chown failed:', e, file=sys.stderr)

        # Partition imaging
        for ppath in args.partitions:
            if check_cancel():
                print('Cancellation requested before partition imaging, stopping', file=sys.stderr)
                sys.exit(1)
                
            pimg = os.path.join(dest, os.path.basename(ppath) + '.img')
            pmap = os.path.join(dest, os.path.basename(ppath) + '.map')
            run([dd, '--force', '--verbose', ppath, pimg, pmap])
            try:
                os.chown(pimg, args.owner_uid, args.owner_gid)
                os.chown(pmap, args.owner_uid, args.owner_gid)
            except Exception:
                pass
    finally:
        # Clean up files
        try:
            if pid_file_path and os.path.exists(pid_file_path):
                os.remove(pid_file_path)
            if os.path.exists(cancel_file):
                os.remove(cancel_file)
        except:
            pass

if __name__ == '__main__':
    main()
'''
        return helper_template
    
    def create_secure_temp_files(self):
        """Create secure temporary files for the helper script and cancellation"""
        try:
            # Create helper script file
            self.helper_fd, self.helper_path = tempfile.mkstemp(
                dir=self.cache_dir, 
                prefix='ddrescue_helper_', 
                suffix='.py'
            )
            
            # Set secure permissions immediately after creation
            os.fchmod(self.helper_fd, 0o600)
            
            # Write the helper script
            with os.fdopen(self.helper_fd, 'w') as tf:
                tf.write(self.create_helper_script())
                tf.flush()
                os.fsync(tf.fileno())  # Ensure data is written to disk
            self.helper_fd = None  # File descriptor is closed by fdopen context manager

            # Make executable by owner only
            os.chmod(self.helper_path, 0o700)

            # Create secure cancel file for communication with helper
            runtime_dir = os.environ.get('XDG_RUNTIME_DIR', self.cache_dir)
            cancel_fd, self.cancel_file_path = tempfile.mkstemp(
                dir=runtime_dir,
                prefix='datarecovery_cancel_',
                suffix='.flag'
            )
            os.fchmod(cancel_fd, 0o600)  # Set secure permissions
            os.close(cancel_fd)  # We just need the filename
            os.remove(self.cancel_file_path)  # Remove the file initially
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create secure temp files: {e}")
            self.cleanup()
            return False
    
    def run_with_pkexec(self, controller=None):
        """Execute the helper script via pkexec"""
        if not self.create_secure_temp_files():
            return False
            
        try:
            # Build command arguments
            cmd = [
                "pkexec", "/usr/bin/python3", self.helper_path, 
                '--device', self.device_path, 
                '--dest', self.dest_path,
                '--owner-uid', str(self.owner_uid), 
                '--owner-gid', str(self.owner_gid), 
                '--cancel-file', self.cancel_file_path
            ]
            
            # Add partitions
            for p in self.partition_paths:
                cmd.extend(['--partitions', p])

            logger.info('Running ddrescue helper via pkexec')
            
            # Use Popen so we can store process reference for cancellation
            process = subprocess.Popen(cmd)
            if controller:
                controller.current_process = process
                controller.cancel_file_path = self.cancel_file_path  # Store for cancellation
                
            # Wait for completion
            result_code = process.wait()
            
            if controller:
                controller.current_process = None  # Clear reference when done
                
            if result_code == 0:
                logger.info('ddrescue helper completed successfully')
                return True
            else:
                logger.error('ddrescue helper failed with code %s', result_code)
                return False
                
        except Exception as e:
            logger.error('Failed to run ddrescue helper: %s', e)
            return False
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up temporary files and resources"""
        # Clean up file descriptor if still open
        if self.helper_fd is not None:
            try:
                os.close(self.helper_fd)
            except Exception:
                pass
            self.helper_fd = None
        
        # Clean up temporary helper script
        if self.helper_path and os.path.exists(self.helper_path):
            try:
                # Securely remove the file
                os.chmod(self.helper_path, 0o600)  # Ensure we can delete it
                os.remove(self.helper_path)
                logger.debug(f"Cleaned up helper script: {self.helper_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up helper script: {e}")
            self.helper_path = None
        
        # Clean up cancel file
        if self.cancel_file_path and os.path.exists(self.cancel_file_path):
            try:
                os.remove(self.cancel_file_path)
                logger.debug(f"Cleaned up cancel file: {self.cancel_file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up cancel file: {e}")
            self.cancel_file_path = None
