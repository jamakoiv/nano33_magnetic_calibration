import sys
import logging
import numpy as np

from typing import Tuple
from collections import OrderedDict
from serial.tools import list_ports
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QPushButton,
)

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


class CalibrationVectorWidget(QWidget):
    """
    Widget for displaying and entering a XYZ-vector.
    """

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

        self.x_edit = QLineEdit(parent=self)
        self.y_edit = QLineEdit(parent=self)
        self.z_edit = QLineEdit(parent=self)

        for edit in [
            self.x_edit,
            self.y_edit,
            self.z_edit,
        ]:
            edit.setValidator(validator)
            edit.setText("1.0")
            edit.setMaxLength(6)
            edit.setMinimumWidth(40)

            edit.editingFinished.connect(self.editingFinished.emit)
            edit.textChanged.connect(self.textChanged.emit)
            edit.textEdited.connect(self.textEdited.emit)

        layout = QVBoxLayout()
        layout.addWidget(self.x_edit)
        layout.addWidget(self.y_edit)
        layout.addWidget(self.z_edit)
        self.setLayout(layout)

    def get(self) -> np.ndarray:
        x = float(self.x_edit.text())
        y = float(self.y_edit.text())
        z = float(self.z_edit.text())
        res = np.array([x, y, z])

        return res

    def set(self, gain: np.ndarray) -> None:
        self.x_edit.setText(str(gain[0]))
        self.y_edit.setText(str(gain[1]))
        self.z_edit.setText(str(gain[2]))

        # NOTE: Emit signal manually so we only have to connect editingChanged,
        # rather than all the possible QLineEdit signals.
        self.editingFinished.emit()


class CalibrationMatrixWidget(QWidget):
    """
    Widget for displaying and entering a 3x3-matrix.
    """

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

        self.xx_edit = QLineEdit(parent=self)
        self.xy_edit = QLineEdit(parent=self)
        self.xz_edit = QLineEdit(parent=self)

        self.yx_edit = QLineEdit(parent=self)
        self.yy_edit = QLineEdit(parent=self)
        self.yz_edit = QLineEdit(parent=self)

        self.zx_edit = QLineEdit(parent=self)
        self.zy_edit = QLineEdit(parent=self)
        self.zz_edit = QLineEdit(parent=self)

        for edit in [
            self.xx_edit,
            self.xy_edit,
            self.xz_edit,
            self.yx_edit,
            self.yy_edit,
            self.yz_edit,
            self.zx_edit,
            self.zy_edit,
            self.zz_edit,
        ]:
            edit.setValidator(validator)
            edit.setText("1.0")
            edit.setMaxLength(6)
            edit.setMinimumWidth(40)

            edit.editingFinished.connect(self.editingFinished.emit)
            edit.textChanged.connect(self.textChanged.emit)
            edit.textEdited.connect(self.textEdited.emit)

        layout = QVBoxLayout()
        layout.addWidget(self.xx_edit)
        layout.addWidget(self.xy_edit)
        layout.addWidget(self.xz_edit)
        layout.addWidget(self.yx_edit)
        layout.addWidget(self.yy_edit)
        layout.addWidget(self.yz_edit)
        layout.addWidget(self.zx_edit)
        layout.addWidget(self.zy_edit)
        layout.addWidget(self.zz_edit)
        self.setLayout(layout)

    def get(self) -> np.ndarray:
        xx = float(self.xx_edit.text())
        xy = float(self.xy_edit.text())
        xz = float(self.xz_edit.text())
        yx = float(self.yx_edit.text())
        yy = float(self.yy_edit.text())
        yz = float(self.yz_edit.text())
        zx = float(self.zx_edit.text())
        zy = float(self.zy_edit.text())
        zz = float(self.zz_edit.text())
        res = np.array([xx, xy, xz, yx, yy, yz, zx, zy, zz]).reshape(3, 3)

        return res

    def set(self, values: np.ndarray) -> None:
        if values.shape == (3, 3):
            values = values.flatten()
        elif values.shape == (9,):
            pass
        else:
            # TODO: Create error if input shape is garbage.
            pass

        self.xx_edit.setText(str(values[0]))
        self.xy_edit.setText(str(values[1]))
        self.xz_edit.setText(str(values[2]))
        self.yx_edit.setText(str(values[3]))
        self.yy_edit.setText(str(values[4]))
        self.yz_edit.setText(str(values[5]))
        self.zx_edit.setText(str(values[6]))
        self.zy_edit.setText(str(values[7]))
        self.zz_edit.setText(str(values[8]))

        # NOTE: Emit signal manually so we only have to connect editingChanged,
        # rather than all the possible QLineEdit signals.
        self.editingFinished.emit()

    ...


class CalibrationFormWidget(QWidget):
    """
    Widget for displaying and entering magnetometer, gyroscope, and accelerometer gain and offset values.
    """

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
        self.x_gain.setText(str(gain[0]))
        self.y_gain.setText(str(gain[1]))
        self.z_gain.setText(str(gain[2]))

        # NOTE: Emit signal manually so we only have to connect editingChanged,
        # rather than all the possible QLineEdit signals.
        self.editingFinished.emit()

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
        self.x_offset.setText(str(offset[0]))
        self.y_offset.setText(str(offset[1]))
        self.z_offset.setText(str(offset[2]))

        self.editingFinished.emit()


class CalibrationMiscWidget(QWidget):
    """
    Calibration widget for displaying and setting output offsets and AHRS settings.
    """

    def __init__(self, parent: QWidget | None = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.output_offset_box = QGroupBox(title="Output offset", parent=self)

        self.yaw_offset = QLineEdit(parent=self)
        self.pitch_offset = QLineEdit(parent=self)
        self.roll_offset = QLineEdit(parent=self)
        self.yaw_label = QLabel(text="Yaw:", parent=self)
        self.pitch_label = QLabel(text="Pitch:", parent=self)
        self.roll_label = QLabel(text="Roll:", parent=self)

        self.offset_box_layout = QGridLayout()
        self.offset_box_layout.addWidget(self.yaw_label, 0, 0)
        self.offset_box_layout.addWidget(self.yaw_offset, 0, 1)
        self.offset_box_layout.addWidget(self.pitch_label, 1, 0)
        self.offset_box_layout.addWidget(self.pitch_offset, 1, 1)
        self.offset_box_layout.addWidget(self.roll_label, 2, 0)
        self.offset_box_layout.addWidget(self.roll_offset, 2, 1)
        self.output_offset_box.setLayout(self.offset_box_layout)

        self.ahrs_box = QGroupBox(title="AHRS settings", parent=self)

        self.ahrs_gain = QLineEdit(parent=self)
        self.ahrs_acc_reject = QLineEdit(parent=self)
        self.ahrs_mag_reject = QLineEdit(parent=self)
        self.ahrs_reject_timeout = QLineEdit(parent=self)
        self.ahrs_gain_label = QLabel(text="Gain:", parent=self)
        self.ahrs_acc_reject_label = QLabel(text="Acceleration rejection:", parent=self)
        self.ahrs_mag_reject_label = QLabel(text="Magnetic rejection:", parent=self)
        self.ahrs_reject_timeout_label = QLabel(text="Rejection timeout:", parent=self)

        self.ahrs_box_layout = QGridLayout()
        self.ahrs_box_layout.addWidget(self.ahrs_gain_label, 0, 0)
        self.ahrs_box_layout.addWidget(self.ahrs_gain, 0, 1)
        self.ahrs_box_layout.addWidget(self.ahrs_acc_reject_label, 1, 0)
        self.ahrs_box_layout.addWidget(self.ahrs_acc_reject, 1, 1)
        self.ahrs_box_layout.addWidget(self.ahrs_mag_reject_label, 2, 0)
        self.ahrs_box_layout.addWidget(self.ahrs_mag_reject, 2, 1)
        self.ahrs_box_layout.addWidget(self.ahrs_reject_timeout_label, 3, 0)
        self.ahrs_box_layout.addWidget(self.ahrs_reject_timeout, 3, 1)
        self.ahrs_box.setLayout(self.ahrs_box_layout)

        layout = QHBoxLayout()
        layout.addWidget(self.output_offset_box)
        layout.addWidget(self.ahrs_box)
        self.setLayout(layout)


class MagneticCalibrationWidget(QWidget):
    """
    Widget for displaying and entering one matrix and one vector.
    """

    pass


class InertialCalibrationWidget(QWidget):
    """
    Widget for displaying and entering one matrix and two vectors.
    """

    pass


class CalibrationWidget(QWidget):
    def __init__(self, parent: QWidget | None = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.tabs = QTabWidget(parent=self)

        self.mag_calibration = CalibrationFormWidget(parent=self.tabs)
        self.gyro_calibration = CalibrationFormWidget(parent=self.tabs)
        self.acc_calibration = CalibrationFormWidget(parent=self.tabs)
        self.misc = CalibrationMiscWidget(parent=self.tabs)

        self.tabs.addTab(self.mag_calibration, "Mag")
        self.tabs.addTab(self.gyro_calibration, "Gyro")
        self.tabs.addTab(self.acc_calibration, "Acc")
        self.tabs.addTab(self.misc, "Misc")

        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        self.setLayout(layout)

    @Slot(object)  # pyright: ignore
    def set_mag_calibration(self, offset: np.ndarray, gain: np.ndarray) -> None:
        self.mag_calibration.set_offset(offset)
        self.mag_calibration.set_gain(gain)

    @Slot(object)  # pyright: ignore
    def set_gyro_calibration(self, offset: np.ndarray, gain: np.ndarray) -> None:
        self.gyro_calibration.set_offset(offset)
        self.gyro_calibration.set_gain(gain)

    @Slot(object)  # pyright: ignore
    def set_acc_calibration(self, offset: np.ndarray, gain: np.ndarray) -> None:
        self.acc_calibration.set_offset(offset)
        self.acc_calibration.set_gain(gain)

    def get_mag_calibration(self) -> Tuple[np.ndarray, np.ndarray]:
        gain = self.mag_calibration.get_gain()
        offset = self.mag_calibration.get_offset()

        return offset, gain

    def get_gyro_calibration(self) -> Tuple[np.ndarray, np.ndarray]:
        gain = self.gyro_calibration.get_gain()
        offset = self.gyro_calibration.get_offset()

        return offset, gain

    def get_acc_calibration(self) -> Tuple[np.ndarray, np.ndarray]:
        gain = self.acc_calibration.get_gain()
        offset = self.acc_calibration.get_offset()

        return offset, gain


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = CalibrationWidget(parent=None)
    widget.show()

    sys.exit(app.exec())
