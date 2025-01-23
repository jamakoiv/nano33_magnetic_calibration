import sys
import logging
import datetime

import numpy as np

from PySide6.QtCore import Qt, Slot, Signal, QThread, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon
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

from canvas import MatplotlibCanvas
from models import CalibrationDataModel
from widgets import DeviceSelectWidget, CalibrationWidget
from serial_comms import Board2GUI, Nano33SerialComms, TestSerialComms


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

        self.build_ui()

        self.data_model = CalibrationDataModel(parent=self)
        self.data_table_widget.setModel(self.data_model)

        self.primary_canvas.setModel(self.data_model)
        self.secondary_canvas.setModel(self.data_model)

        self.device_select_widget.data_button.pressed.connect(self.data_read_callback)

        log.debug("Created main window.")

        self.device_select_widget.refresh_serial_ports()

    def build_ui(self) -> None:
        # NOTE: These must be called in this order.
        # E.g. Actions must be created before they can be added to toolbar.
        self.build_canvases()
        self.build_dock_widgets()
        self.build_actions()
        self.build_toolbars()
        self.build_menus()

    def build_dock_widgets(self) -> None:
        default_size_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        self.calibration_widget = CalibrationWidget(parent=self)
        self.calibration_widget.setSizePolicy(default_size_policy)
        self.calibration_dock = QDockWidget("&Calibration values", parent=self)
        self.calibration_dock.setWidget(self.calibration_widget)
        self.calibration_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetVerticalTitleBar
        )

        self.device_select_widget = DeviceSelectWidget(parent=self)
        self.device_select_widget.setSizePolicy(default_size_policy)
        self.device_select_dock = QDockWidget("&Device select", parent=self)
        self.device_select_dock.setWidget(self.device_select_widget)
        self.device_select_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetVerticalTitleBar
        )

        self.data_table_widget = QTableView(parent=self)
        self.data_table_dock = QDockWidget("Data &table", parent=self)
        self.data_table_dock.setWidget(self.data_table_widget)
        self.data_table_widget.horizontalHeader().setDefaultSectionSize(60)
        self.data_table_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetVerticalTitleBar
        )

        self.log_widget = QTextEdit(parent=self)
        self.log_dock = QDockWidget("&Log", parent=self)
        self.log_dock.setWidget(self.log_widget)

        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.device_select_dock
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.calibration_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.data_table_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)

        log.debug("Created dock widgets.")

    def build_canvases(self) -> None:
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

    def build_actions(self) -> None:
        self.action_quit = QAction(QIcon.fromTheme("application-exit"), "&Exit", self)
        self.action_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self.action_quit.triggered.connect(self.close)

        self.action_get_calibration = QAction(
            QIcon.fromTheme("go-first"),
            "Get calibration from currently selected device.",
            self,
        )
        self.action_get_calibration.triggered.connect(
            self.action_get_calibration_callback
        )
        self.action_set_calibration = QAction(
            QIcon.fromTheme("go-last"),
            "Send calibration to currently selected device.",
            self,
        )

        self.action_random_data = QAction(text="Add random data")
        self.action_random_data.setShortcut(QKeySequence("Ctrl+D"))
        self.action_random_data.triggered.connect(self.add_random_data)

    def build_toolbars(self) -> None:
        self.toolbar_main = QToolBar("main_toolbar")

        self.toolbar_main.addActions(
            [
                self.action_random_data,
                self.action_get_calibration,
                self.action_set_calibration,
                self.action_quit,
            ]
        )

        self.toolbar_mpl = QToolBar("matplotlib_default_tools")
        self.mpl_default_tools = NavigationToolbar2QT(self.primary_canvas, self)
        self.toolbar_mpl.addWidget(self.mpl_default_tools)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_main)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_mpl)

    def build_menus(self) -> None:
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

    def action_get_calibration_callback(self):
        device = self.device_select_widget.device_selector.currentData()
        if device == "debug":
            board = TestSerialComms()
        else:
            board = Nano33SerialComms(device)

        self.board_comms = Board2GUI(
            board=board, read_sample_size=self.device_select_widget.data_points.value()
        )

        calib = self.board_comms.board.get_magnetometer_calibration()
        offset, gain = calib[:3], calib[3:]

        self.calibration_widget.set_device_calibration(calib)

        self.logger(
            f" <-- Received magnetic calibration. Offset: {offset}, Gain: {gain}"
        )

    def add_random_data(self):
        self.data_model.append_data(np.random.randint(0, 50, size=(1, 3)))

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

        device = self.device_select_widget.device_selector.currentData()
        if device == "debug":
            board = TestSerialComms()
        else:
            board = Nano33SerialComms(device)

        self.board_comms = Board2GUI(
            board=board, read_sample_size=self.device_select_widget.data_points.value()
        )
        self.board_comms.data_row_received.connect(self.data_model.append_data)
        self.board_comms.log_signal.connect(self.logger)
        self.board_comms.debug_signal.connect(self.debug_printer)
        self.board_comms.error_signal.connect(self.exception2MessageBox)
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
                    pass

        except AttributeError:  # If board_thread does not exist.
            pass

        return super().closeEvent(event)

    @Slot(str)  # pyright: ignore
    def debug_printer(self, d: str):
        print(d)

    @Slot(object)  # pyright: ignore
    def exception2MessageBox(self, e: Exception):
        QMessageBox.warning(
            self,
            "Error",
            str(e),
            QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.NoButton,
        )

    @Slot(str)  # pyright: ignore
    def logger(self, msg: str):
        time = datetime.datetime.now().time()
        self.log_widget.append(f"{time}: {msg}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
