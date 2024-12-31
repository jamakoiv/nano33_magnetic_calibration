import sys
import logging

from collections import OrderedDict
import numpy as np

from PySide6.QtCore import Qt
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

        self.scan_devices_button = QPushButton(parent=self, text="Scan devices")
        self.scan_devices_button.clicked.connect(self.refresh_serial_ports)
        self.device_selector = QComboBox(parent=self)
        self.serial_ports_model = SerialPortsModel(parent=self)
        self.device_selector.setModel(self.serial_ports_model)

        self.data_points = QSpinBox(parent=self)
        self.data_points.setRange(10, 500)
        self.data_points.setSingleStep(10)
        self.data_points.setValue(50)

        self.data_label = QLabel(parent=self, text="Calibration points")
        self.data_button = QPushButton(parent=self, text="Read data")

        self.device_box = QGroupBox(title="Device select", parent=self)
        self.device_layout = QHBoxLayout()
        self.device_layout.addWidget(self.device_selector)
        self.device_layout.addWidget(self.scan_devices_button)
        self.device_box.setLayout(self.device_layout)

        self.data_box = QGroupBox(title="Raw calibration data", parent=self)
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
        except ValueError as e:
            last_selected_index = 0

        self.device_selector.setCurrentIndex(last_selected_index)


class CalibrationFormWidget(QGroupBox):
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

        self.show_check = QCheckBox(text="Show in plot", parent=self)

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

        return res

    def set_gain(self, gain: np.ndarray) -> None:
        self.x_gain.setText(gain[0])
        self.y_gain.setText(gain[1])
        self.z_gain.setText(gain[2])

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

        return res

    def set_offset(self, offset: np.ndarray) -> None:
        self.x_offset.setText(offset[0])
        self.y_offset.setText(offset[1])
        self.z_offset.setText(offset[2])


class CalibrationWidget(QWidget):
    def __init__(self, parent: QWidget | None = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.device_calibration = CalibrationFormWidget(title="Device", parent=self)
        self.fit_calibration = CalibrationFormWidget(title="Fit", parent=self)

        self.send_to_device_button = QPushButton(text="Read from device", parent=self)
        self.read_from_device_button = QPushButton(text="Send to device", parent=self)

        layout = QGridLayout()
        layout.addWidget(self.device_calibration, 0, 0)
        layout.addWidget(self.fit_calibration, 0, 1)
        layout.addWidget(self.read_from_device_button, 1, 0)
        layout.addWidget(self.send_to_device_button, 1, 1)
        self.setLayout(layout)

        self.send_to_device_button.pressed.connect(self.get_fit_calibration)

    def set_device_calibration(self, calibration: np.ndarray) -> None:
        self.device_calibration.set_gain(calibration[0:3])
        self.device_calibration.set_offset(calibration[3:6])

    def get_device_calibration(self) -> np.ndarray:
        gain = self.device_calibration.get_gain()
        offset = self.device_calibration.get_offset()

        return np.concat((gain, offset), axis=0)

    def set_fit_calibration(self, calibration: np.ndarray) -> None:
        self.fit_calibration.set_gain(calibration[0:3])
        self.fit_calibration.set_offset(calibration[3:6])

    def get_fit_calibration(self) -> np.ndarray:
        gain = self.device_calibration.get_gain()
        offset = self.device_calibration.get_offset()

        QMessageBox.information(self, "Jotain", f"{gain}, {offset}")

        return np.concat((gain, offset), axis=0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = CalibrationWidget(parent=None)
    widget.show()

    sys.exit(app.exec())
