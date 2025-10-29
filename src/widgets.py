import sys
import logging
from PySide6 import QtWidgets
import numpy as np

from collections import OrderedDict
from serial.tools import list_ports
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDoubleValidator, QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QToolButton,
)

from models import SerialPortsModel
import fit_functions
from orientation_window import OrientationWindow

log = logging.getLogger(__name__)


class DeviceSelectWidget(QWidget):
    """
    Widget for selecting device and getting raw data from the device.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)

        self.scan_devices_button = QToolButton(parent=self)
        self.scan_devices_action = QAction(
            QIcon.fromTheme("view-refresh"), "Scan", self
        )
        self.scan_devices_action.setToolTip("Refresh device list")
        self.scan_devices_action.triggered.connect(self.refresh_serial_ports)
        self.scan_devices_button.setDefaultAction(self.scan_devices_action)

        self.get_calibration_button = QToolButton(parent=self)
        self.get_calibration_action = QAction(QIcon.fromTheme("go-first"), "Get", self)
        self.get_calibration_action.setToolTip(
            "Get current calibration values from device"
        )
        self.get_calibration_button.setDefaultAction(self.get_calibration_action)

        # self.data_label = QLabel(parent=self, text="N: ")
        self.data_button = QToolButton(parent=self)
        self.data_button_action = QAction(
            QIcon.fromTheme("media-playback-start"), "Get data", self
        )
        self.data_button_action.setToolTip("Get raw data from the device")
        self.data_button.setDefaultAction(self.data_button_action)

        self.device_selector = QComboBox(parent=self)
        self.device_selector.setToolTip("Selected serial device")
        self.serial_ports_model = SerialPortsModel(parent=self)
        self.device_selector.setModel(self.serial_ports_model)

        self.data_points = QSpinBox(parent=self)
        self.data_points.setToolTip("Number of data points to get")
        self.data_points.setRange(10, 500)
        self.data_points.setSingleStep(10)
        self.data_points.setValue(20)

        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.Shape.VLine)

        layout = QHBoxLayout()
        layout.addWidget(self.device_selector)
        layout.addWidget(self.scan_devices_button)
        layout.addWidget(self.separator)
        layout.addWidget(self.data_points)
        layout.addWidget(self.data_button)
        layout.addWidget(self.get_calibration_button)
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


class FitWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.fit_function = fit_functions.fit_sphere

        self.select_function = QComboBox(parent=self)
        self.select_function.setToolTip("Select function to fit to the data")
        self.select_function.addItems(list(fit_functions.register.keys()))
        self.select_function.currentIndexChanged.connect(self.set_fit_function)

        self.action_fit_ellipsoid = QAction(QIcon.fromTheme(""), "&Fit", self)
        self.action_fit_ellipsoid.setToolTip(
            "Fit the selected function to current data"
        )
        self.button_fit_ellipsoid = QToolButton(parent=self)
        self.button_fit_ellipsoid.setDefaultAction(self.action_fit_ellipsoid)

        layout = QHBoxLayout()
        layout.addWidget(self.select_function)
        layout.addWidget(self.button_fit_ellipsoid)
        self.setLayout(layout)

    def set_fit_function(self):
        function_name = self.select_function.currentText()
        log.info(f"Function selector combobox changed, currentText: {function_name}")
        self.fit_function = fit_functions.register[function_name]


class CalibrationVectorWidget(QWidget):
    """
    Widget for displaying and entering a XYZ-vector.
    """

    editingFinished = Signal()
    textEdited = Signal(str)
    textChanged = Signal(str)
    checkStateChange = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        labels: list = ["X", "Y", "Z"],
        *args,
        **kwargs,
    ):
        super().__init__(parent=parent, *args, **kwargs)

        # NOTE: Hard coded, but the raw data is in microteslas
        # and should be in the range of 20-100 uT.
        self.validator = QDoubleValidator(-999, 999, 5, parent=self)
        self.validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        self.x_edit = QLineEdit(parent=self)
        self.y_edit = QLineEdit(parent=self)
        self.z_edit = QLineEdit(parent=self)
        self.x_label = QLabel(parent=self, text=f"{labels[0]}: ")
        self.y_label = QLabel(parent=self, text=f"{labels[1]}: ")
        self.z_label = QLabel(parent=self, text=f"{labels[2]}: ")

        for edit in [
            self.x_edit,
            self.y_edit,
            self.z_edit,
        ]:
            edit.setValidator(self.validator)
            edit.setText("1.0")
            edit.setMaxLength(6)
            edit.setMinimumWidth(40)

            edit.editingFinished.connect(self.editingFinished.emit)
            edit.textChanged.connect(self.textChanged.emit)
            edit.textEdited.connect(self.textEdited.emit)

        layout = QFormLayout()
        layout.addRow(self.x_label, self.x_edit)
        layout.addRow(self.y_label, self.y_edit)
        layout.addRow(self.z_label, self.z_edit)
        self.setLayout(layout)

    def get(self) -> np.ndarray:
        x = float(self.x_edit.text())
        y = float(self.y_edit.text())
        z = float(self.z_edit.text())
        res = np.array([x, y, z])

        return res

    def set(self, gain: np.ndarray) -> None:
        gain = np.clip(gain, self.validator.bottom(), self.validator.top())

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
        self.validator = QDoubleValidator(-999, 999, 5, parent=self)
        self.validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        self.xx_edit = QLineEdit(parent=self)
        self.xy_edit = QLineEdit(parent=self)
        self.xz_edit = QLineEdit(parent=self)

        self.yx_edit = QLineEdit(parent=self)
        self.yy_edit = QLineEdit(parent=self)
        self.yz_edit = QLineEdit(parent=self)

        self.zx_edit = QLineEdit(parent=self)
        self.zy_edit = QLineEdit(parent=self)
        self.zz_edit = QLineEdit(parent=self)

        self.x_column_label = QLabel(parent=self, text="X")
        self.y_column_label = QLabel(parent=self, text="Y")
        self.z_column_label = QLabel(parent=self, text="Z")

        self.x_row_label = QLabel(parent=self, text="X")
        self.y_row_label = QLabel(parent=self, text="Y")
        self.z_row_label = QLabel(parent=self, text="Z")

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
            edit.setValidator(self.validator)
            edit.setText("1.0")
            edit.setMaxLength(6)
            edit.setMinimumWidth(40)

            edit.editingFinished.connect(self.editingFinished.emit)
            edit.textChanged.connect(self.textChanged.emit)
            edit.textEdited.connect(self.textEdited.emit)

        layout = QGridLayout()
        layout.addWidget(self.x_row_label, 1, 0)
        layout.addWidget(self.y_row_label, 2, 0)
        layout.addWidget(self.z_row_label, 3, 0)

        layout.addWidget(self.x_column_label, 0, 1)
        layout.addWidget(self.y_column_label, 0, 2)
        layout.addWidget(self.z_column_label, 0, 3)

        layout.addWidget(self.xx_edit, 1, 1)
        layout.addWidget(self.xy_edit, 1, 2)
        layout.addWidget(self.xz_edit, 1, 3)
        layout.addWidget(self.yx_edit, 2, 1)
        layout.addWidget(self.yy_edit, 2, 2)
        layout.addWidget(self.yz_edit, 2, 3)
        layout.addWidget(self.zx_edit, 3, 1)
        layout.addWidget(self.zy_edit, 3, 2)
        layout.addWidget(self.zz_edit, 3, 3)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
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

        values = np.clip(values, self.validator.bottom(), self.validator.top())

        self.xx_edit.setText(str(values[0]))
        self.xy_edit.setText(str(values[1]))
        self.xz_edit.setText(str(values[2]))
        self.yx_edit.setText(str(values[3]))
        self.yy_edit.setText(str(values[4]))
        self.yz_edit.setText(str(values[5]))
        self.zx_edit.setText(str(values[6]))
        self.zy_edit.setText(str(values[7]))
        self.zz_edit.setText(str(values[8]))

        # NOTE: Emit signal manually so we only have to connect editingFinished,
        # rather than all the possible QLineEdit signals.
        self.editingFinished.emit()


class MagneticCalibrationWidget(QWidget):
    """
    Widget for displaying and entering one matrix and one vector.
    """

    editingFinished = Signal()
    textEdited = Signal(str)
    textChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.soft_iron = CalibrationMatrixWidget(parent=self)
        self.soft_iron_box = QGroupBox(title="Soft-iron matrix", parent=self)

        self.hard_iron = CalibrationVectorWidget(parent=self)
        self.hard_iron_box = QGroupBox(title="Hard-iron offset", parent=self)

        self.send_to_board_button = QToolButton(parent=self)
        self.send_to_board_action = QAction(QIcon.fromTheme("go-last"), "Set", self)
        self.send_to_board_action.setToolTip("Send current calibration to board")
        self.send_to_board_button.setDefaultAction(self.send_to_board_action)

        for box, widget in (
            (self.soft_iron_box, self.soft_iron),
            (self.hard_iron_box, self.hard_iron),
        ):
            widget.editingFinished.connect(self.editingFinished.emit)
            layout = QVBoxLayout()
            layout.addWidget(widget)
            box.setLayout(layout)

        button_layout = QVBoxLayout()
        button_layout.addWidget(self.send_to_board_button)

        layout = QHBoxLayout()
        layout.addWidget(self.soft_iron_box, stretch=3)
        layout.addWidget(self.hard_iron_box, stretch=2)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.soft_iron.set(np.eye(3))
        self.hard_iron.set(np.zeros(3))


class InertialCalibrationWidget(QWidget):
    """
    Widget for displaying and entering one matrix and two vectors.
    """

    editingFinished = Signal()
    textEdited = Signal(str)
    textChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.misalignment_box = QGroupBox(title="Misalignment matrix", parent=self)
        self.misalignment = CalibrationMatrixWidget(parent=self)

        self.sensitivity_box = QGroupBox(title="Sensitivity", parent=self)
        self.sensitivity = CalibrationVectorWidget(parent=self)

        self.offset_box = QGroupBox(title="Offset", parent=self)
        self.offset = CalibrationVectorWidget(parent=self)

        self.send_to_board_button = QToolButton(parent=self)
        self.send_to_board_action = QAction(QIcon.fromTheme("go-last"), "Set", self)
        self.send_to_board_action.setToolTip("Send current calibration to board")
        self.send_to_board_button.setDefaultAction(self.send_to_board_action)

        for box, widget in (
            (self.misalignment_box, self.misalignment),
            (self.sensitivity_box, self.sensitivity),
            (self.offset_box, self.offset),
        ):
            widget.editingFinished.connect(self.editingFinished.emit)
            layout = QVBoxLayout()
            layout.addWidget(widget)
            box.setLayout(layout)

        button_layout = QVBoxLayout()
        button_layout.addWidget(self.send_to_board_button)

        layout = QHBoxLayout()
        layout.addWidget(self.misalignment_box, stretch=3)
        layout.addWidget(self.sensitivity_box, stretch=2)
        layout.addWidget(self.offset_box, stretch=2)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.misalignment.set(np.eye(3))
        self.sensitivity.set(np.ones(3))
        self.offset.set(np.zeros(3))


class CalibrationMiscWidget(QWidget):
    """
    Calibration widget for displaying and setting output offsets and AHRS settings.
    """

    editingFinished = Signal()

    def __init__(self, parent: QWidget | None = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.output_offset = CalibrationVectorWidget(
            parent=self, labels=["Yaw", "Pitch", "Roll"]
        )
        self.output_offset_box = QGroupBox(title="Output offset", parent=self)
        self.output_offset.editingFinished.connect(self.editingFinished.emit)
        self.output_offset_box_layout = QVBoxLayout()
        self.output_offset_box_layout.addWidget(self.output_offset)
        self.output_offset_box.setLayout(self.output_offset_box_layout)

        self.filter_time_constant = CalibrationVectorWidget(
            parent=self, labels=["Gyroscope", "Accelerometer", "Magnetometer"]
        )
        self.filter_box = QGroupBox(title="Filter time constant", parent=self)
        self.filter_time_constant.editingFinished.connect(self.editingFinished)
        self.filter_box_layout = QVBoxLayout()
        self.filter_box_layout.addWidget(self.filter_time_constant)
        self.filter_box.setLayout(self.filter_box_layout)

        self.ahrs_box = QGroupBox(title="AHRS settings", parent=self)

        self.ahrs_validator = QDoubleValidator(0, 9999, 2, parent=self)
        self.ahrs_validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        self.ahrs_gain = QLineEdit(parent=self)
        self.ahrs_acc_reject = QLineEdit(parent=self)
        self.ahrs_mag_reject = QLineEdit(parent=self)
        self.ahrs_reject_timeout = QLineEdit(parent=self)
        self.ahrs_magnetometer_check = QCheckBox("Use magnetometer", parent=self)
        self.ahrs_magnetometer_check.setChecked(True)

        for edit in [
            self.ahrs_gain,
            self.ahrs_acc_reject,
            self.ahrs_mag_reject,
            self.ahrs_reject_timeout,
        ]:
            edit.setValidator(self.ahrs_validator)
            edit.setMaxLength(6)
            edit.setMinimumWidth(40)

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
        self.ahrs_box_layout.addWidget(self.ahrs_magnetometer_check, 4, 0, 1, 2)
        self.ahrs_box.setLayout(self.ahrs_box_layout)

        self.send_to_board_button = QToolButton(parent=self)
        self.send_to_board_action = QAction(QIcon.fromTheme("go-last"), "Set", self)
        self.send_to_board_action.setToolTip("Send current calibration to board")
        self.send_to_board_button.setDefaultAction(self.send_to_board_action)

        button_layout = QVBoxLayout()
        button_layout.addWidget(self.send_to_board_button)

        layout = QHBoxLayout()
        layout.addWidget(self.output_offset_box)
        layout.addWidget(self.filter_box)
        layout.addWidget(self.ahrs_box)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.output_offset.set(np.zeros(3))
        self.set_ahrs_settings(np.array([0.50, 10.0, 10.0, 500, True]))

    def get_ahrs_settings(self) -> np.ndarray:
        return np.array(
            [
                float(self.ahrs_gain.text()),
                float(self.ahrs_acc_reject.text()),
                float(self.ahrs_mag_reject.text()),
                float(self.ahrs_reject_timeout.text()),
                self.ahrs_magnetometer_check.isChecked(),
            ]
        )

    def set_ahrs_settings(self, settings: np.ndarray) -> None:
        settings = np.clip(
            settings, self.ahrs_validator.bottom(), self.ahrs_validator.top()
        )

        self.ahrs_gain.setText(str(settings[0]))
        self.ahrs_acc_reject.setText(str(settings[1]))
        self.ahrs_mag_reject.setText(str(settings[2]))
        self.ahrs_reject_timeout.setText(str(settings[3]))
        self.ahrs_magnetometer_check.setChecked(bool(settings[4]))


class CalibrationWidget(QWidget):
    def __init__(self, parent: QWidget | None = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.tabs = QTabWidget(parent=self)

        self.magnetic = MagneticCalibrationWidget(parent=self.tabs)
        self.gyroscope = InertialCalibrationWidget(parent=self.tabs)
        self.accelerometer = InertialCalibrationWidget(parent=self.tabs)
        self.misc = CalibrationMiscWidget(parent=self.tabs)

        self.tabs.addTab(self.magnetic, "Mag")
        self.icon_magnetic = QIcon()
        self.icon_magnetic.addFile("src/assets/compass.svg")
        self.tabs.setTabIcon(0, self.icon_magnetic)

        self.tabs.addTab(self.gyroscope, "Gyro")
        self.icon_gyro = QIcon()
        self.icon_gyro.addFile("src/assets/gyroscope.svg")
        self.tabs.setTabIcon(1, self.icon_gyro)

        self.tabs.addTab(self.accelerometer, "Acc")
        self.icon_acc = QIcon()
        self.icon_acc.addFile("src/assets/accelerometer.svg")
        self.tabs.setTabIcon(2, self.icon_acc)

        self.tabs.addTab(self.misc, "Misc")
        self.icon_misc = QIcon()
        self.icon_misc.addFile("src/assets/settings.svg")
        self.tabs.setTabIcon(3, self.icon_misc)

        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        self.setLayout(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OrientationWindow()
    widget = QtWidgets.QWidget.createWindowContainer(window, None)
    widget.show()

    sys.exit(app.exec())
