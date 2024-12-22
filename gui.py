import sys
import logging
from typing import Callable
import numpy as np

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QTableView,
    QToolBar,
    QDockWidget,
    QWidget,
    QTextEdit,
)

from matplotlib.axes import Axes
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.figure import Figure

from mpl_toolkits.mplot3d.art3d import Line3D
from mpl_toolkits.mplot3d.axes3d import Axes3D
from matplotlib.lines import Line2D

from data_table import CalibrationDataModel
from widgets import DeviceSelectWidget, CalibrationFormWidget, CalibrationWidget


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


class MatplotlibCanvas(FigureCanvasQTAgg):
    """
    Canvas for drawing matplotlib-plots.
    """

    # NOTE: We should probably inherit QAbstractItemView as well since we
    # are basically implementing a Qt view. However both QAbstractItemView
    # and FigureCanvasQTAgg have paintEvent which conflict when inheriting both.

    plot: Callable
    update_plot: Callable

    fig: Figure
    axes: dict[str, Axes | Axes3D]
    plot_ref: dict[str, Line2D | Line3D]
    model: CalibrationDataModel

    def __init__(
        self,
        width: int = 5,
        height: int = 4,
        dpi: int = 100,
        projection: str = "3d",
    ) -> None:
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)

        self.axes = {}
        self.plot_ref = {}

        match projection:
            case "3d":
                self.plot = self.plot_3d
                self.update_plot = self.update_3d
            case "2d":
                self.plot = self.plot_2d
                self.update_plot = self.update_2d

    def setModel(self, model: CalibrationDataModel) -> None:
        self.model = model

        self.model.rowsInserted.connect(self.update_plot)
        self.model.rowsRemoved.connect(self.update_plot)
        self.model.modelReset.connect(self.update_plot)

        self.plot()

    def plot_3d(self) -> None:
        self.axes["3d"] = self.fig.add_subplot(111, projection="3d")

        self.axes["3d"].set_aspect("equal")
        self.axes["3d"].set_box_aspect((75, 75, 75))  # pyright: ignore
        self.fig.tight_layout()

        # Draw helper axes at origo.
        c = 60  # Scale
        self.axes["3d"].plot3D([-1 * c, 1 * c], [0, 0], [0, 0], "k:")  # pyright: ignore
        self.axes["3d"].plot3D([0, 0], [-1 * c, 1 * c], [0, 0], "k:")  # pyright: ignore
        self.axes["3d"].plot3D([0, 0], [0, 0], [-1 * c, 1 * c], "k:")  # pyright: ignore

        x, y, z = self.model.get_xyz_data()
        plot_ref_list = self.axes["3d"].plot3D(x, y, z, "rx")  # pyright: ignore

        self.plot_ref["3d"] = plot_ref_list[-1]

    def update_3d(self):
        x, y, z = self.model.get_xyz_data()
        self.plot_ref["3d"].set_data_3d(x, y, z)  # pyright: ignore

        self.draw()

    def plot_2d(self) -> None:
        for i, axis in enumerate(["x", "y", "z"]):
            ax = self.fig.add_subplot(1, 3, i + 1)
            ax.set_aspect("equal")

            self.axes[axis] = ax

    def update_2d(self): ...


class MainWindow(QMainWindow):
    primary_canvas: MatplotlibCanvas
    secondary_canvas: MatplotlibCanvas

    log_widget: QTextEdit
    log_dock: QDockWidget

    data_table_widget: QTableView
    data_table_dock: QDockWidget

    device_select_widget: DeviceSelectWidget
    device_select_dock: QDockWidget

    calibration_widget: CalibrationWidget
    calibration_dock: QDockWidget

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)

        self.create_canvases()
        self.create_dock_widgets()

        self.data_model = CalibrationDataModel(parent=self)
        self.data_table_widget.setModel(self.data_model)

        self.primary_canvas.setModel(self.data_model)
        self.secondary_canvas.setModel(self.data_model)

        self.toolbar_main = QToolBar("main_toolbar")
        self.action_quit = QAction(text="&Exit")
        self.action_quit.triggered.connect(self.close)
        self.action_random_data = QAction(text="Add random data")
        self.action_random_data.triggered.connect(self.add_random_data)

        self.toolbar_main.addActions([self.action_random_data, self.action_quit])

        self.toolbar_mpl = QToolBar("matplotlib_default_tools")
        self.mpl_default_tools = NavigationToolbar2QT(self.primary_canvas, self)
        self.toolbar_mpl.addWidget(self.mpl_default_tools)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_main)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_mpl)

        self.menu_file = self.menuBar().addMenu("&File")
        self.menu_file.addAction(self.action_quit)

        self.menu_view = self.menuBar().addMenu("&View")

        self.menu_view.addActions(
            [
                self.device_select_dock.toggleViewAction(),
                self.calibration_dock.toggleViewAction(),
                self.menu_view.addSeparator(),
                self.data_table_dock.toggleViewAction(),
                self.log_dock.toggleViewAction(),
            ]
        )

        log.debug("Created main window.")

    def create_dock_widgets(self) -> None:
        default_size_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        self.calibration_widget = CalibrationWidget(parent=self)
        self.calibration_widget.setSizePolicy(default_size_policy)
        self.calibration_dock = QDockWidget("&Calibration", parent=self)
        self.calibration_dock.setWidget(self.calibration_widget)

        self.device_select_widget = DeviceSelectWidget(parent=self)
        self.device_select_widget.setSizePolicy(default_size_policy)
        self.device_select_dock = QDockWidget("&Device select", parent=self)
        self.device_select_dock.setWidget(self.device_select_widget)

        self.data_table_widget = QTableView(parent=self)
        self.data_table_dock = QDockWidget("Data &table", parent=self)
        self.data_table_dock.setWidget(self.data_table_widget)
        self.data_table_widget.horizontalHeader().setDefaultSectionSize(60)

        self.log_widget = QTextEdit(parent=self)
        self.log_dock = QDockWidget("&Log", parent=self)
        self.log_dock.setWidget(self.log_widget)

        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.device_select_dock
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.calibration_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.data_table_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.log_dock)

        log.debug("Created dock widgets.")

    def create_canvases(self) -> None:
        """
        Create
        """
        self.primary_canvas = MatplotlibCanvas(5, 5, 96, projection="3d")
        self.secondary_canvas = MatplotlibCanvas(5, 5, 96, projection="2d")

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
