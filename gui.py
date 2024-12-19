import sys
import logging
import numpy as np

from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import QAction, QDoubleValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableView,
    QToolBar,
    QDockWidget,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QPushButton,
)

from matplotlib.axes import Axes
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.figure import Figure

from data_table import CalibrationDataModel


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


class MatplotlibCanvas(FigureCanvasQTAgg):
    """
    Canvas for drawing matplotlib-plots.
    """

    fig: Figure
    axes: Axes

    def __init__(
        self, parent=None, width=5, height=4, dpi=100, *args, **kwargs
    ) -> None:
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)


class DeviceWidget(QWidget):
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

        validator = QDoubleValidator(-999, 999, 2, parent=parent)
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

        self.device_calibration = CalibrationFormWidget(title="Device", parent=parent)
        self.fit_calibration = CalibrationFormWidget(title="Fit", parent=parent)

        self.send_to_device_button = QPushButton(text="Read from device", parent=parent)
        self.read_from_device_button = QPushButton(text="Send to device", parent=parent)

        layout = QGridLayout()
        layout.addWidget(self.device_calibration, 0, 0)
        layout.addWidget(self.fit_calibration, 0, 1)
        layout.addWidget(self.read_from_device_button, 1, 0)
        layout.addWidget(self.send_to_device_button, 1, 1)

        self.setLayout(layout)


class MainWindow(QMainWindow):
    primary_canvas: MatplotlibCanvas
    secondary_canvas: MatplotlibCanvas

    data_table_widget: QTableView

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)

        self.create_canvases()
        self.create_dock_widgets()

        self.data_model = CalibrationDataModel(parent=self)
        self.data_table_widget.setModel(self.data_model)

        self.toolbar_main = QToolBar("main_toolbar")
        self.action_quit = QAction(text="Exit")
        self.action_quit.triggered.connect(self.close)
        self.action_random_data = QAction(text="Add random data")
        self.action_random_data.triggered.connect(self.add_random_data)

        self.toolbar_main.addActions([self.action_random_data, self.action_quit])

        self.toolbar_mpl = QToolBar("matplotlib_default_tools")
        self.mpl_default_tools = NavigationToolbar2QT(self.primary_canvas, self)
        self.toolbar_mpl.addWidget(self.mpl_default_tools)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_main)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_mpl)

        log.debug("Created main window.")

    def create_dock_widgets(self) -> None:
        default_size_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        self.calibration_widget = CalibrationWidget(parent=self)
        self.calibration_widget.setSizePolicy(default_size_policy)
        self.calibration_dock = QDockWidget("calibration_dock", parent=self)
        self.calibration_dock.setWidget(self.calibration_widget)

        self.device_select_widget = DeviceWidget(parent=self)
        self.device_select_widget.setSizePolicy(default_size_policy)
        self.device_select_dock = QDockWidget("Device", parent=self)
        self.device_select_dock.setWidget(self.device_select_widget)

        self.data_table_widget = QTableView(parent=self)
        self.data_table_dock = QDockWidget("Data", parent=self)
        self.data_table_dock.setWidget(self.data_table_widget)

        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.device_select_dock
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.calibration_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.data_table_dock)

        log.debug("Created dock widgets.")

    def create_canvases(self) -> None:
        """
        Create
        """
        self.primary_canvas = MatplotlibCanvas(parent=self)
        self.primary_canvas.ax = self.primary_canvas.fig.add_subplot(
            111, projection="3d"
        )
        self.primary_canvas.ax.set_aspect("equal")

        self.secondary_canvas = MatplotlibCanvas(parent=self)
        self.secondary_canvas.x_ax = self.secondary_canvas.fig.add_subplot(131)
        self.secondary_canvas.y_ax = self.secondary_canvas.fig.add_subplot(132)
        self.secondary_canvas.z_ax = self.secondary_canvas.fig.add_subplot(133)
        self.secondary_canvas.x_ax.set_aspect("equal")
        self.secondary_canvas.y_ax.set_aspect("equal")
        self.secondary_canvas.z_ax.set_aspect("equal")

        splitter = QSplitter(Qt.Orientation.Vertical, parent=self)
        splitter.addWidget(self.primary_canvas)
        splitter.addWidget(self.secondary_canvas)

        size = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter.setSizePolicy(size)

        # Main canvas should get 2/3 of the main window
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        log.debug("Created canvases.")

    @Slot()
    def add_random_data(self):
        self.data_model.append_data(np.random.randint(0, 50, size=(1, 4)))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
