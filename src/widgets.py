import sys
import logging

from typing import Tuple
from collections import OrderedDict

import numpy as np

from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QPushButton,
)

from serial.tools import list_ports
from models import SerialPortsModel


class DeviceSelectWidget(QWidget):
    """
    Widget for selecting device and getting raw data from the device.
    """

    scan_devices_button: QPushButton
    device_selector: QComboBox

    data_points: QSpinBox
    data_label: QLabel
    data_button: QPushButton

    serial_ports_model: SerialPortsModel

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)

        self.scan_devices_button = QPushButton("Scan devices", parent=self)
        self.scan_devices_button.clicked.connect(self.refresh_serial_ports)
        self.device_selector = QComboBox(parent=self)
        self.serial_ports_model = SerialPortsModel(parent=self)
        self.device_selector.setModel(self.serial_ports_model)

        self.data_points = QSpinBox(parent=self)
        self.data_points.setRange(10, 500)
        self.data_points.setSingleStep(10)
        self.data_points.setValue(20)

        self.data_label = QLabel(parent=self, text="Calibration points: ")
        self.data_button = QPushButton("Read data", parent=self)

        self.device_box = QGroupBox(title="", parent=self)
        self.device_layout = QHBoxLayout()
        self.device_layout.addWidget(self.device_selector)
        self.device_layout.addWidget(self.scan_devices_button)
        self.device_box.setLayout(self.device_layout)

        self.data_box = QGroupBox(title="", parent=self)
        self.data_layout = QHBoxLayout()
        self.data_layout.addWidget(self.data_label)
        self.data_layout.addWidget(self.data_points)
        self.data_layout.addWidget(self.data_button)
        self.data_box.setLayout(self.data_layout)

        layout = QVBoxLayout()
        layout.addWidget(self.device_box)
        layout.addWidget(self.data_box)
        self.setLayout(layout)

    def refresh_serial_ports(self) -> None:
        """
        Get a list of the serial ports the OS knows about,
        and add them to the selector.
        """

        last_selected_device = self.device_selector.currentData()
        ports = OrderedDict()

        ports["debug"] = "Dummy data source"

        for port in list_ports.comports():
            ports[port.device] = port.product

            # Try to order the results so that connected devices are at the top of the list.
            if port.product in [None, ""]:
                ports.move_to_end(port.device, last=True)
            else:
                ports.move_to_end(port.device, last=False)

        self.serial_ports_model.set_ports(ports)

        # Try to keep the previous selection, if it still exists.
        try:
            last_selected_index = list(self.serial_ports_model.ports).index(
                last_selected_device
            )
        except ValueError:
            last_selected_index = 0

        self.device_selector.setCurrentIndex(last_selected_index)


class CalibrationFormWidget(QGroupBox):
    editingFinished = Signal()
    textEdited = Signal(str)
    textChanged = Signal(str)
    checkStateChange = Signal(object)

    def __init__(self, parent: QWidget | None = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        # NOTE: Hard coded, but the raw data is in microteslas
        # and should be in the range of 20-100 uT.
        validator = QDoubleValidator(-999, 999, 2, parent=self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        label_alignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter

        self.offset_label = QLabel(text="Offset", parent=self)
        self.gain_label = QLabel(text="Gain", parent=self)

        self.offset_label.setAlignment(label_alignment)
        self.gain_label.setAlignment(label_alignment)

        self.x_gain = QLineEdit(parent=self)
        self.y_gain = QLineEdit(parent=self)
        self.z_gain = QLineEdit(parent=self)

        self.x_offset = QLineEdit(parent=self)
        self.y_offset = QLineEdit(parent=self)
        self.z_offset = QLineEdit(parent=self)

        self.show_check = QCheckBox("Show in plot", parent=self)
        self.show_check.checkStateChanged.connect(self.checkStateChange.emit)

        for edit in [
            self.x_gain,
            self.y_gain,
            self.z_gain,
            self.x_offset,
            self.y_offset,
            self.z_offset,
        ]:
            edit.setValidator(validator)
            edit.setText("1.0")
            edit.setMaxLength(6)
            edit.setMinimumWidth(40)

            edit.editingFinished.connect(self.editingFinished.emit)
            edit.textChanged.connect(self.textChanged.emit)
            edit.textEdited.connect(self.textEdited.emit)

        layout = QGridLayout()
        layout.addWidget(self.gain_label, 0, 0)
        layout.addWidget(self.offset_label, 0, 1)
        layout.addWidget(self.x_gain, 1, 0)
        layout.addWidget(self.x_offset, 1, 1)
        layout.addWidget(self.y_gain, 2, 0)
        layout.addWidget(self.y_offset, 2, 1)
        layout.addWidget(self.z_gain, 3, 0)
        layout.addWidget(self.z_offset, 3, 1)

        # columnSpan can be used only for layouts, not single widgets.
        check_layout = QHBoxLayout()
        check_layout.addWidget(self.show_check)
        layout.addItem(check_layout, 4, 0, columnSpan=2)
        self.setLayout(layout)

    def get_gain(self) -> np.ndarray:
        try:
            x = float(self.x_gain.text())
            y = float(self.y_gain.text())
            z = float(self.z_gain.text())
            res = np.array([x, y, z])

        except ValueError as e:
            # TODO: Create better messagebox.
            QMessageBox.warning(
                self,
                "Error converting gain values",
                f"{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Cancel,
            )
            res = np.zeros(3)

        print("gain", res)
        return res

    def set_gain(self, gain: np.ndarray) -> None:
        self.x_gain.setText(str(gain[0]))
        self.y_gain.setText(str(gain[1]))
        self.z_gain.setText(str(gain[2]))

    def get_offset(self) -> np.ndarray:
        try:
            x = float(self.x_offset.text())
            y = float(self.y_offset.text())
            z = float(self.z_offset.text())
            res = np.array([x, y, z])

        except ValueError as e:
            # TODO: Create better messagebox.
            QMessageBox.warning(
                self,
                "Error converting offset values",
                f"{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Cancel,
            )
            res = np.zeros(3)

        print("offset", res)
        return res

    def set_offset(self, offset: np.ndarray) -> None:
        self.x_offset.setText(str(offset[0]))
        self.y_offset.setText(str(offset[1]))
        self.z_offset.setText(str(offset[2]))

    def checkState(self) -> Qt.CheckState:
        return self.show_check.checkState()


class CalibrationWidget(QWidget):
    def __init__(self, parent: QWidget | None = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.device_calibration = CalibrationFormWidget(title="Device", parent=self)
        self.fit_calibration = CalibrationFormWidget(title="Fit", parent=self)

        layout = QGridLayout()
        layout.addWidget(self.device_calibration, 0, 0)
        layout.addWidget(self.fit_calibration, 0, 1)
        self.setLayout(layout)

    @Slot(object)  # pyright: ignore
    def set_device_calibration(self, offset: np.ndarray, gain: np.ndarray) -> None:
        self.device_calibration.set_offset(offset)
        self.device_calibration.set_gain(gain)

    def get_device_calibration(self) -> Tuple[np.ndarray, np.ndarray]:
        gain = self.device_calibration.get_gain()
        offset = self.device_calibration.get_offset()

        print("get_device_calibration", gain, offset)
        return offset, gain

    def set_fit_calibration(self, offset: np.ndarray, gain: np.ndarray) -> None:
        self.fit_calibration.set_offset(offset)
        self.fit_calibration.set_gain(gain)

    def get_fit_calibration(self) -> Tuple[np.ndarray, np.ndarray]:
        gain = self.fit_calibration.get_gain()
        offset = self.fit_calibration.get_offset()

        print("get_fit_calibration", gain, offset)
        return offset, gain


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = CalibrationWidget(parent=None)
    widget.show()

    sys.exit(app.exec())
