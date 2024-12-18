import sys
import logging

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QSizePolicy,
    QSpinBox,
    QSplitter,
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


class CalibrationFormWidget(QWidget):
    def __init__(self, parent: QWidget | None = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.xgain = QLineEdit(parent=parent)
        self.ygain = QLineEdit(parent=parent)
        self.zgain = QLineEdit(parent=parent)

        self.xoffset = QLineEdit(parent=parent)
        self.yoffset = QLineEdit(parent=parent)
        self.zoffset = QLineEdit(parent=parent)

        validator = QDoubleValidator(-999, 999, 2, parent=parent)
        validator.setNotation(QDoubleValidator.StandardNotation)  # pyright: ignore

        for widget in [
            self.xgain,
            self.ygain,
            self.zgain,
            self.xoffset,
            self.yoffset,
            self.zoffset,
        ]:
            widget.setValidator(validator)
            widget.setMaxLength(5)
            widget.setMaximumWidth(40)

        gain_box = QGroupBox(parent=parent, title="Gain")
        gain_layout = QVBoxLayout()
        gain_layout.addWidget(self.xgain)
        gain_layout.addWidget(self.ygain)
        gain_layout.addWidget(self.zgain)
        gain_box.setLayout(gain_layout)

        offset_box = QGroupBox(parent=parent, title="Offset")
        offset_layout = QVBoxLayout()
        offset_layout.addWidget(self.xoffset)
        offset_layout.addWidget(self.yoffset)
        offset_layout.addWidget(self.zoffset)
        offset_box.setLayout(offset_layout)

        box_layout = QHBoxLayout()
        box_layout.addWidget(offset_box)
        box_layout.addWidget(gain_box)

        self.checkbox = QCheckBox(text="Show in plot", parent=parent)

        layout = QVBoxLayout()
        layout.addLayout(box_layout)
        layout.addWidget(self.checkbox)

        self.setLayout(layout)


class MainWindow(QMainWindow):
    primary_canvas: MatplotlibCanvas
    secondary_canvas: MatplotlibCanvas

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)

        self.create_canvases()
        self.create_dock_widgets()

        self.toolbar_mpl = QToolBar("matplotlib_default_tools")
        self.mpl_default_tools = NavigationToolbar2QT(self.primary_canvas, self)
        self.toolbar_mpl.addWidget(self.mpl_default_tools)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_mpl)

        log.debug("Created main window.")

    def create_dock_widgets(self) -> None:
        self.dock_widget_size_policy = QSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )

        self.device_calibration_widget = CalibrationFormWidget(parent=self)
        self.device_calibration_widget.setSizePolicy(self.dock_widget_size_policy)
        # self.device_calibration_widget.setMinimumSize(dock_widget_size)
        self.device_calibration_dock = QDockWidget("calibration_dock", parent=self)
        self.device_calibration_dock.setWidget(self.device_calibration_widget)

        self.fit_calibration_widget = CalibrationFormWidget(parent=self)
        self.fit_calibration_widget.setSizePolicy(self.dock_widget_size_policy)
        # self.fit_calibration_widget.setMinimumSize(dock_widget_size)
        self.fit_calibration_dock = QDockWidget("fit_dock", parent=self)
        self.fit_calibration_dock.setWidget(self.fit_calibration_widget)

        self.device_select_widget = DeviceWidget(parent=self)
        self.device_select_widget.setSizePolicy(self.dock_widget_size_policy)
        self.device_select_dock = QDockWidget("Device", parent=self)
        self.device_select_dock.setWidget(self.device_select_widget)

        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.device_select_dock
        )
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.device_calibration_dock
        )
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.fit_calibration_dock
        )

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
