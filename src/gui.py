import sys
import logging
import queue
from typing import Callable

import numpy as np

from PySide6.QtCore import Qt, Slot, Signal, QThread, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QTableView,
    QToolBar,
    QDockWidget,
    QWidget,
    QTextEdit,
)

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from numpy.random import sample

from canvas import MatplotlibCanvas
from models import CalibrationDataModel
from widgets import DeviceSelectWidget, CalibrationWidget
from serial_comms import Board2GUI, Nano33SerialComms, SerialCommsError, TestSerialComms


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    primary_canvas: MatplotlibCanvas
    secondary_canvas: MatplotlibCanvas
    data_model: CalibrationDataModel

    board_comms: Board2GUI
    board_comms_timer: QTimer
    stop_board_thread = Signal()

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

        self.device_select_widget.data_button.pressed.connect(self.data_read_callback)

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
        # self.calibration_dock.setFeatures(
        #     QDockWidget.DockWidgetFeature.DockWidgetVerticalTitleBar
        # )

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
        self.data_model.append_data(np.random.randint(0, 50, size=(1, 3)))

    @Slot()
    def data_read_callback(self):
        try:
            if self.board_thread.isRunning():
                print("Sending stop signal.")
                self.stop_board_thread.emit()
            else:
                self.start_board_thread()

        except AttributeError:  # if self.board_thread does not exist.
            self.start_board_thread()

    def start_board_thread(self) -> None:
        # NOTE: could probably just replace the thread with a QTimer since the
        # data acquisition is pretty fast and light.
        #

        board = Nano33SerialComms(
            self.device_select_widget.device_selector.currentData()
        )

        # board = TestSerialComms()
        self.board_comms = Board2GUI(
            board=board, read_sample_size=self.device_select_widget.data_points.value()
        )
        self.board_comms.data_row_received.connect(self.data_model.append_data)
        self.board_comms.debug_signal.connect(self.debug_printer)
        self.board_comms.data_read_done.connect(self.board_thread_cleanup)

        self.board_thread = QThread()
        board.moveToThread(self.board_thread)
        self.board_comms.moveToThread(self.board_thread)

        self.device_select_widget.data_button.setText("Stop")

        # DirectConnection causes the target function to execute in current thread,
        # so we are modifying the data owned by object in another thread.
        # In this case it is safe since the target function only toggle a boolean flag
        self.stop_board_thread.connect(
            self.board_comms.stop_reading_data, Qt.ConnectionType.DirectConnection
        )

        self.board_thread.run = self.board_comms.read_magnetic_calibration_data
        self.board_thread.start()

    @Slot()
    def board_thread_cleanup(self):
        print("data read cleanup function")

        self.board_thread.quit()
        self.device_select_widget.data_button.setText("Start")

    def closeEvent(self, event):
        try:
            if self.board_thread.isRunning():
                self.stop_board_thread.emit()
                self.board_thread.quit()

                while self.board_thread.isRunning():
                    # Wait for thread to stop.
                    pass

        except AttributeError:
            pass

        return super().closeEvent(event)

    @Slot(str)  # pyright: ignore
    def debug_printer(self, d: str):
        print(d)
        QMessageBox.information(self, "Debug message", f"{d}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
