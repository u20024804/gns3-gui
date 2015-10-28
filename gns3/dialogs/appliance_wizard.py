#!/usr/bin/env python
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

import os
import sys

from ..qt import QtWidgets, QtCore, QtWidgets, QtGui
from ..ui.appliance_wizard_ui import Ui_ApplianceWizard
from ..image_manager import ImageManager
from ..registry.appliance import Appliance, ApplianceError
from ..registry.registry import Registry
from ..registry.config import Config, ConfigException
from ..registry.image import Image
from ..utils import human_filesize
from ..utils.wait_for_lambda_worker import WaitForLambdaWorker
from ..utils.progress_dialog import ProgressDialog
from ..servers import Servers
from ..gns3_vm import GNS3VM



class ApplianceWizard(QtWidgets.QWizard, Ui_ApplianceWizard):
    def __init__(self, parent, path):
        super().__init__(parent)

        self._path = path
        self.setupUi(self)
        images_directories = list()
        images_directories.append(os.path.join(ImageManager.instance().getDirectory(), "QEMU"))
        images_directories.append(os.path.dirname(self._path))
        download_directory = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DownloadLocation)
        if download_directory != "" and download_directory != os.path.dirname(self._path):
            images_directories.append(download_directory)
        self._registry = Registry(images_directories)

        try:
            self._appliance = Appliance(self._registry, self._path)
        except ApplianceError as e:
            self.close()
            raise e

        self._refreshVersions()

        self.uiApplianceVersionTreeWidget.currentItemChanged.connect(self._applianceVersionCurrentItemChangedSlot)
        self.uiRefreshPushButton.clicked.connect(self._refreshVersions)
        self.uiDownloadPushButton.clicked.connect(self._downloadPushButtonClickedSlot)
        self.uiImportPushButton.clicked.connect(self._importPushButtonClickedSlot)


        self.uiRemoteRadioButton.toggled.connect(self._remoteServerToggledSlot)
        if hasattr(self, "uiVMRadioButton"):
            self.uiVMRadioButton.toggled.connect(self._vmToggledSlot)

        self.uiLocalRadioButton.toggled.connect(self._localToggledSlot)
        if hasattr(self, "uiLoadBalanceCheckBox"):
            self.uiLoadBalanceCheckBox.toggled.connect(self._loadBalanceToggledSlot)

    def initializePage(self, page_id):
        """
        Initialize Wizard pages.

        :param page_id: page identifier
        """
        super().initializePage(page_id)

        if self._appliance["category"] == "guest":
            symbol = ":/symbols/computer.svg"
        else:
            symbol = ":/symbols/{}.svg".format(self._appliance["category"])
        self.page(page_id).setPixmap(QtWidgets.QWizard.LogoPixmap, QtGui.QPixmap(symbol))

        if self.page(page_id) == self.uiInfoWizardPage:
            self.uiInfoWizardPage.setTitle(self._appliance["product_name"])
            self.uiDescriptionLabel.setText(self._appliance["description"])

            infos = (
                ("Category", "category"),
                ("Product", "product_name"),
                ("Vendor", "vendor_name"),
                ("Status", "status"),
                ("Maintainer", "maintainer")
            )

            self.uiInfoTreeWidget.clear()
            for (name, key) in infos:
                self.uiInfoTreeWidget.addTopLevelItem(QtWidgets.QTreeWidgetItem([name + ":", self._appliance[key]]))

        elif self.page(page_id) == self.uiServerWizardPage:
            self.uiRemoteServersComboBox.clear()
            for server in Servers.instance().remoteServers().values():
                self.uiRemoteServersComboBox.addItem(server.url(), server)

            if not GNS3VM.instance().isRunning():
                self.uiVMRadioButton.setEnabled(False)

            # Qemu has issues on OSX and Windows we disallow usage of the local server
            if (sys.platform.startswith("darwin") or sys.platform.startswith("win")):
                self.uiLocalRadioButton.setEnabled(False)

            if GNS3VM.instance().isRunning():
                self.uiVMRadioButton.setChecked(True)
            elif Servers.instance().localServerIsRunning() and (sys.platform.startswith("darwin") or sys.platform.startswith("win")):
                self.uiLocalRadioButton.setChecked(True)
            elif len(Servers.instance().remoteServers().values()) > 0:
                self.uiRemoteRadioButton.setChecked(True)
            else:
                self.uiRemoteRadioButton.setChecked(False)

        elif self.page(page_id) == self.uiFilesWizardPage:
            self._refreshVersions()

        elif self.page(page_id) == self.uiSummaryWizardPage:
            self.uiSummaryTreeWidget.clear()
            for key in self._appliance["qemu"]:
                self.uiSummaryTreeWidget.addTopLevelItem(QtWidgets.QTreeWidgetItem([key.replace('_', ' ') + ":", str(self._appliance["qemu"][key])]))

        elif self.page(page_id) == self.uiUsageWizardPage:
            self.uiUsageTextEdit.setText("You can found the appliance in the category {}. \n\n{}".format(
                self._appliance["category"].replace("_", " "),
                self._appliance.get("usage", ""))
            )

    def _refreshVersions(self):
        """
        Refresh the list of files for different version of the appliance
        """
        self.uiFilesWizardPage.setSubTitle("The following versions are available for " + self._appliance["product_name"] + ".  Check the status of files required to install.")
        self.uiApplianceVersionTreeWidget.clear()

        worker = WaitForLambdaWorker(lambda: self._resfreshDialogWorker())
        progress_dialog = ProgressDialog(worker, "Add appliance", "Scanning directories for images...", None, busy=True, parent=self)
        progress_dialog.show()
        if progress_dialog.exec_():
            for version in self._appliance["versions"]:
                top = QtWidgets.QTreeWidgetItem([version["name"]])

                size = 0
                status = "Available"
                for image in version["images"].values():
                    if image["status"] == "Missing file":
                        status = "Missing files"

                    size += image["filesize"]
                    image_widget = QtWidgets.QTreeWidgetItem(
                        [
                            "",
                            image["filename"],
                            human_filesize(image["filesize"]),
                            image["status"],
                            image["version"]
                        ])
                    # Associated data stored are col 0: version, col 1: image
                    image_widget.setData(0, QtCore.Qt.UserRole, version)
                    image_widget.setData(1, QtCore.Qt.UserRole, image)
                    image_widget.setData(2, QtCore.Qt.UserRole, self._appliance)
                    top.addChild(image_widget)

                font = top.font(0)
                font.setBold(True)
                top.setFont(0, font)

                top.setData(2, QtCore.Qt.DisplayRole, human_filesize(size))
                top.setData(3, QtCore.Qt.DisplayRole, status)
                top.setData(2, QtCore.Qt.UserRole, self._appliance)
                top.setData(0, QtCore.Qt.UserRole, version)
                self.uiApplianceVersionTreeWidget.addTopLevelItem(top)
                top.setExpanded(True)

            self.uiApplianceVersionTreeWidget.setCurrentItem(self.uiApplianceVersionTreeWidget.topLevelItem(0))

    def _resfreshDialogWorker(self):
        """
        Scan local directory in order to found the images on disk
        """
        for version in self._appliance["versions"]:
            for image in version["images"].values():
                if self._registry.search_image_file(image["filename"], image["md5sum"], image["filesize"]):
                    image["status"] = "Available"
                else:
                    image["status"] = "Missing file"

    def _applianceVersionCurrentItemChangedSlot(self, current, previous):
        """
        Called when user select a different item in the list of appliance files
        """
        self.uiDownloadPushButton.hide()
        self.uiImportPushButton.hide()

        if current is None:
            return

        image = current.data(1, QtCore.Qt.UserRole)
        if image is not None:
            if "direct_download_url" in image or "download_url" in image:
                self.uiDownloadPushButton.show()
            self.uiImportPushButton.show()

    def _downloadPushButtonClickedSlot(self):
        """
        Called when user want to download an appliance images.
        He should have selected the file before.
        """
        current = self.uiApplianceVersionTreeWidget.currentItem()
        data = current.data(1, QtCore.Qt.UserRole)
        if data is not None:
            if "direct_download_url" in data:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(data["direct_download_url"]))
            else:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(data["download_url"]))

    def _importPushButtonClickedSlot(self):
        """
        Called when user want to import an appliance images.
        He should have selected the file before.
        """

        current = self.uiApplianceVersionTreeWidget.currentItem()
        disk = current.data(1, QtCore.Qt.UserRole)

        path, _ = QtWidgets.QFileDialog.getOpenFileName()
        if len(path) == 0:
            return

        image = Image(path)
        if image.md5sum != disk["md5sum"]:
            QtWidgets.QMessageBox.warning(self.parent(), "Add appliance", "This is not the correct image file.")
            return

        config = Config()
        worker = WaitForLambdaWorker(lambda: image.copy(os.path.join(config.images_dir, "QEMU"), disk["filename"]), allowed_exceptions=[OSError])
        progress_dialog = ProgressDialog(worker, "Add appliance", "Import the appliance...", None, busy=True, parent=self)
        if not progress_dialog.exec_():
            return
        self._refreshVersions()

    def _install(self, version):
        """
        Install the appliance to GNS3

        :params version: Version name
        """

        try:
            config = Config()
        except OSError as e:
            QtWidgets.QMessageBox.critical(self.parent(), "Add appliance", str(e))
            return False

        appliance_configuration = self._appliance.search_images_for_version(version)

        if self._server.isLocal():
            server_string = "local"
        elif self._server.isGNS3VM():
            server_string = "vm"
        else:
            server_string = self._server.url()

        worker = WaitForLambdaWorker(lambda: config.add_appliance(appliance_configuration, server_string), allowed_exceptions=[ConfigException, OSError])
        progress_dialog = ProgressDialog(worker, "Add appliance", "Install the appliance...", None, busy=True, parent=self)
        progress_dialog.show()
        if not progress_dialog.exec_():
            return False

        worker = WaitForLambdaWorker(lambda: config.save(), allowed_exceptions=[ConfigException, OSError])
        progress_dialog = ProgressDialog(worker, "Add appliance", "Install the appliance...", None, busy=True, parent=self)
        progress_dialog.show()
        if progress_dialog.exec_():
            QtWidgets.QMessageBox.information(self.parent(), "Add appliance", "{} {} installed!".format(self._appliance["name"], version))
            return True

    def validateCurrentPage(self):
        """
        Validates the settings.
        """

        if self.currentPage() == self.uiFilesWizardPage:
            current = self.uiApplianceVersionTreeWidget.currentItem()
            version = current.data(0, QtCore.Qt.UserRole)
            appliance = current.data(2, QtCore.Qt.UserRole)
            if not self._appliance.is_version_installable(version["name"]):
                QtWidgets.QMessageBox.warning(self, "Appliance", "You can't install the appliance version {} you have missing images.".format(version["name"]))
                return False
            name = "{} {}".format(appliance["name"], version["name"])
            reply = QtWidgets.QMessageBox.question(self, "Appliance", "Would you like to install {}?".format(name), QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.No:
                return False

        elif self.currentPage() == self.uiUsageWizardPage:
            current = self.uiApplianceVersionTreeWidget.currentItem()
            version = current.data(0, QtCore.Qt.UserRole)
            return self._install(version["name"])

        elif self.currentPage() == self.uiServerWizardPage:
            if self.uiRemoteRadioButton.isChecked():
                if not Servers.instance().remoteServers():
                    QtWidgets.QMessageBox.critical(self, "Remote server", "There is no remote server registered in your preferences")
                    return False
                self._server = self.uiRemoteServersComboBox.itemData(self.uiRemoteServersComboBox.currentIndex())
            elif hasattr(self, "uiVMRadioButton") and self.uiVMRadioButton.isChecked():
                gns3_vm_server = Servers.instance().vmServer()
                if gns3_vm_server is None:
                    QtWidgets.QMessageBox.critical(self, "GNS3 VM", "The GNS3 VM is not running")
                    return False
                self._server = gns3_vm_server
            else:
                self._server = Servers.instance().localServer()

        return True

    def _vmToggledSlot(self, checked):
        """
        Slot for when the VM radio button is toggled.

        :param checked: either the button is checked or not
        """
        if checked:
            self.uiRemoteServersGroupBox.setEnabled(False)
            self.uiRemoteServersGroupBox.hide()

    def _remoteServerToggledSlot(self, checked):
        """
        Slot for when the remote server radio button is toggled.

        :param checked: either the button is checked or not
        """

        if checked:
            self.uiRemoteServersGroupBox.setEnabled(True)
            self.uiRemoteServersGroupBox.show()

    def _localToggledSlot(self, checked):
        """
        Slot for when the local server radio button is toggled.

        :param checked: either the button is checked or not
        """
        if checked:
            self.uiRemoteServersGroupBox.setEnabled(False)
            self.uiRemoteServersGroupBox.hide()

    def _loadBalanceToggledSlot(self, checked):
        """
        Slot for when the load balance checkbox is toggled.

        :param checked: either the box is checked or not
        """

        if checked:
            self.uiRemoteServersComboBox.setEnabled(False)
        else:
            self.uiRemoteServersComboBox.setEnabled(True)
