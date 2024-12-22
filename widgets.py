import sys
import logging

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
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QPushButton,
)


class DeviceSelectWidget(QWidget):
    """
    Widget for selecting device and getting raw data from the device.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)

        self.button = QPushButton(parent=self, text="Scan devices")
        self.selector = QComboBox(parent=self)

        self.data_points = QSpinBox(parent=self)
        self.data_label = QLabel(parent=self, text="Calibration points")
        self.data_button = QPushButton(parent=self, text="Read data")

        self.device_box = QGroupBox(title="Device select", parent=self)
        self.device_layout = QHBoxLayout()
        self.device_layout.addWidget(self.selector)
        self.device_layout.addWidget(self.button)
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = CalibrationWidget(parent=None)
    widget.show()

    sys.exit(app.exec())
