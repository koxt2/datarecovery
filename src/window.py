# window.py
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

from gi.repository import Adw, Gtk, Gio

from .about import about_dialog
from .device_dropdown import DeviceDropdownManager
from .device_columnview import DeviceColumnViewManager


@Gtk.Template(resource_path='/datarecovery/gtk/window.ui')
class DatarecoveryWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'DatarecoveryWindow'

    toaster                         = Gtk.Template.Child()
    mounted_factory                 = Gtk.Template.Child()
    device_path_factory             = Gtk.Template.Child()
    size_factory                    = Gtk.Template.Child()
    filesystem_factory              = Gtk.Template.Child()
    label_factory                   = Gtk.Template.Child()
    type_factory                    = Gtk.Template.Child()
    select_device_dropdown          = Gtk.Template.Child()
    device_liststore                = Gtk.Template.Child()
    columnview_liststore            = Gtk.Template.Child()
    columnview_model                = Gtk.Template.Child()
    save_image_switch               = Gtk.Template.Child()
    log_switch                      = Gtk.Template.Child()
    scan_partitions_switch          = Gtk.Template.Child()
    corrupted_switch                = Gtk.Template.Child()
    dupes_switch                    = Gtk.Template.Child()
    choose_destination_actionrow    = Gtk.Template.Child()
    search_button                   = Gtk.Template.Child()  
    output_label                    = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.create_action('about', self.on_about_action)
        self.create_action('choose_destination', self.on_choose_destination)
        self.create_action('search', self.on_search_button_clicked)

        self.device_dropdown_manager = DeviceDropdownManager(self)
        self.columnview_manager = DeviceColumnViewManager(self, self.device_dropdown_manager)
        
        # Connect the managers
        self.device_dropdown_manager.columnview_manager = self.columnview_manager
        
    def create_action(self, name, callback, shortcuts=None):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)
    
    def on_about_action(self, *args):
        about_dialog.present(self) 

    def on_choose_destination(self, action, param):
        self.app_controller.choose_destination()

    def on_search_button_clicked(self, action, param):
        self.app_controller.start_recovery()
