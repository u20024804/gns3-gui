# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
QEMU module implementation.
"""

from gns3.local_config import LocalConfig
from gns3.local_server_config import LocalServerConfig

from ...controller import Controller
from ..module import Module
from .qemu_vm import QemuVM
from .settings import QEMU_SETTINGS
from .settings import QEMU_VM_SETTINGS

import logging
log = logging.getLogger(__name__)


class Qemu(Module):
    """
    QEMU module.
    """

    def __init__(self):
        super().__init__()
        self._qemu_vms = {}
        self._loadSettings()

    def _loadSettings(self):
        """
        Loads the settings from the persistent settings file.
        """

        self._settings = LocalConfig.instance().loadSectionSettings(self.__class__.__name__, QEMU_SETTINGS)
        self._loadQemuVMs()

    def _saveSettings(self):
        """
        Saves the settings to the persistent settings file.
        """

        # save the settings
        LocalConfig.instance().saveSectionSettings(self.__class__.__name__, self._settings)
        server_settings = {"enable_hardware_acceleration": self._settings["enable_hardware_acceleration"],
                           "require_hardware_acceleration": self._settings["require_hardware_acceleration"]}
        LocalServerConfig.instance().saveSettings(self.__class__.__name__, server_settings)

    def _loadQemuVMs(self):
        """
        Load the QEMU VMs from the persistent settings file.
        """

        self._qemu_vms = {}
        settings = LocalConfig.instance().settings()
        if "vms" in settings.get(self.__class__.__name__, {}):
            for vm in settings[self.__class__.__name__]["vms"]:
                name = vm.get("name")
                server = vm.get("server")
                key = "{server}:{name}".format(server=server, name=name)
                if key in self._qemu_vms or not name or not server:
                    continue
                vm_settings = QEMU_VM_SETTINGS.copy()
                vm_settings.update(vm)
                # for backward compatibility before version 1.4
                if "symbol" not in vm_settings:
                    vm_settings["symbol"] = vm_settings.get("default_symbol", vm_settings["symbol"])
                    vm_settings["symbol"] = vm_settings["symbol"][:-11] + ".svg" if vm_settings["symbol"].endswith("normal.svg") else vm_settings["symbol"]
                self._qemu_vms[key] = vm_settings

    def _saveQemuVMs(self):
        """
        Saves the QEMU VMs to the persistent settings file.
        """

        self._settings["vms"] = list(self._qemu_vms.values())
        self._saveSettings()

    def nodeTemplates(self):
        """
        Returns QEMU VMs settings.

        :returns: QEMU VMs settings (dictionary)
        """

        return self._qemu_vms

    def setNodeTemplates(self, new_qemu_vms):
        """
        Sets QEMU VM settings.

        :param new_qemu_vms: Qemu images settings (dictionary)
        """

        self._qemu_vms = new_qemu_vms.copy()
        self._saveQemuVMs()

    def getQemuBinariesFromServer(self, compute_id, callback, archs=None):
        """
        Gets the QEMU binaries list from a server.

        :param compute_id: server to send the request to
        :param callback: callback for the reply from the server
        :param archs: A list of architectures. Only binaries matching the specified architectures are returned.
        """

        request_body = None
        if archs is not None:
            request_body = {"archs": archs}
        Controller.instance().getCompute("/qemu/binaries", compute_id, callback, body=request_body)

    def getQemuImgBinariesFromServer(self, compute_id, callback):
        """
        Gets the QEMU-img binaries list from a server.

        :param server: server to send the request to
        :param callback: callback for the reply from the server
        """

        Controller.instance().getCompute("/qemu/img-binaries", compute_id, callback)

    def getQemuCapabilitiesFromServer(self, compute_id, callback):
        """
        Gets the capabilities of Qemu at a server.

        :param server: server to send the request to
        :param callback: callback for the reply from the server
        """

        Controller.instance().getCompute("/qemu/capabilities", compute_id, callback)

    def createDiskImage(self, compute_id, callback, options):
        """
        Create a disk image on the remote server

        :param server: server to send the request to
        :param callback: callback for the reply from the server
        :param options: Options for the image creation
        """

        Controller.instance().postCompute("/qemu/img", compute_id, callback, body=options)

    def updateDiskImage(self, compute_id, callback, options):
        """
        Update a disk image on the remote server

        :param server: server to send the request to
        :param callback: callback for the reply from the server
        :param options: Options for the image update
        """

        Controller.instance().putCompute("/qemu/img", compute_id, callback, body=options)

    @staticmethod
    def getNodeClass(node_type, platform=None):
        """
        Returns the class corresponding to node type.

        :param node_type: node type (string)
        :param platform: not used

        :returns: class or None
        """

        if node_type == "qemu":
            return QemuVM
        return None

    @staticmethod
    def classes():
        """
        Returns all the node classes supported by this module.

        :returns: list of classes
        """

        return [QemuVM]

    @staticmethod
    def preferencePages():
        """
        Returns the preference pages for this module.

        :returns: QWidget object list
        """

        from .pages.qemu_preferences_page import QemuPreferencesPage
        from .pages.qemu_vm_preferences_page import QemuVMPreferencesPage
        return [QemuPreferencesPage, QemuVMPreferencesPage]

    @staticmethod
    def configurationPage():
        """
        Returns the configuration page for this module.

        :returns: QWidget object
        """

        from .pages.qemu_vm_configuration_page import QemuVMConfigurationPage
        return QemuVMConfigurationPage

    @staticmethod
    def instance():
        """
        Singleton to return only one instance of QEMU module.

        :returns: instance of Qemu
        """

        if not hasattr(Qemu, "_instance"):
            Qemu._instance = Qemu()
        return Qemu._instance
