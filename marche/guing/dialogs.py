#  -*- coding: utf-8 -*-
# *****************************************************************************
# Copyright (c) 2015 by the authors, see LICENSE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Module authors:
#   Alexander Lenz <alenz@dev-platypus.org>
#
# *****************************************************************************

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QTreeWidgetItem, QInputDialog, \
    QWidget, QHeaderView, QMessageBox, QApplication, QDialog, QDialogButtonBox

import marche.guing.res  # noqa, pylint: disable=unused-import
from marche.guing.util import loadUi


class AuthDialog(QDialog):
    def __init__(self, parent, title):
        QDialog.__init__(self, parent)
        loadUi(self, 'authdlg.ui')
        self.buttonBox.button(QDialogButtonBox.Ok).setDefault(True)
        self.nameLbl.setText(title)
        self.setWindowTitle(title)
        self.passwdLineEdit.setFocus()

    @property
    def user(self):
        return str(self.userLineEdit.text()).strip()

    @property
    def passwd(self):
        return str(self.passwdLineEdit.text()).strip()

    @property
    def save_creds(self):
        return self.saveBox.isChecked()

