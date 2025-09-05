import logging
import datetime
import numpy as np
import scipy

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from PySide6.QtCore import Qt, Slot, Signal, QThread
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtWidgets import (
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


from canvas import MatplotlibCanvas
from models import CalibrationDataModel
from widgets import DeviceSelectWidget, CalibrationWidget
from serial_comms import Board2GUI, Nano33SerialComms, TestSerialComms
from ellipsoid import fitEllipsoidNonRotated, makeEllipsoidXYZ

log = logging.getLogger(__name__)


# TODO: This is becoming a god-class.
class MainWindow(QMainWindow):
    primary_canvas: MatplotlibCanvas
    secondary_canvas: MatplotlibCanvas
    data_model: CalibrationDataModel

    board_comms: Board2GUI
    comms_thread: QThread
    start_data_read = Signal()
    start_calibration_get = Signal(str)
    start_calibration_set = Signal(str, object)
    stop_comms_task = Signal()

    log_widget: QTextEdit
    log_dock: QDockWidget

    data_table_widget: QTableView
    data_table_dock: QDockWidget

    device_select_widget: DeviceSelectWidget
    device_select_dock: QDockWidget

    calibration_widget: CalibrationWidget
    calibration_dock: QDockWidget

    def __init__(self, parent: QWidget | None = None):
        log.info("Creating main window.")

        super().__init__(parent=parent)

        self.build_ui()

        self.data_model = CalibrationDataModel(parent=self)
        self.data_table_widget.setModel(self.data_model)
        self.data_model.rowsInserted.connect(self.data_table_widget.scrollToBottom)

        self.primary_canvas.setModel(self.data_model)
        self.secondary_canvas.setModel(self.data_model)

        self.device_select_widget.data_button.pressed.connect(self.data_read_callback)

        self.start_comms_thread()
        self.device_select_widget.refresh_serial_ports()

    # UI ------------------------
    def build_ui(self) -> None:
        # NOTE: These must be called in this order.
        # E.g. Actions must be created before they can be added to toolbar.
        self.build_canvases()
        self.build_dock_widgets()
        self.build_actions()
        self.build_toolbars()
        self.build_menus()

    def build_dock_widgets(self) -> None:
        log.info("Creating GUI dock widgets")

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

    def build_canvases(self) -> None:
        log.info("Creating plot canvases")

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

    def build_actions(self) -> None:
        log.info("Creating GUI-actions")

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
        self.action_set_calibration.triggered.connect(
            self.action_set_calibration_callback
        )

        self.action_fit_ellipsoid = QAction(QIcon.fromTheme(""), "Fit ellipsoid.", self)
        self.action_fit_ellipsoid.triggered.connect(self.action_fit_ellipsoid_callback)

        self.action_plot_ellipsoid_wireframe = QAction(
            QIcon.fromTheme(""), "Wireframe", self
        )
        self.action_plot_ellipsoid_wireframe.triggered.connect(
            self.action_plot_ellipsoid_wireframe_callback
        )

        self.action_random_data = QAction(text="Add random data")
        self.action_random_data.setShortcut(QKeySequence("Ctrl+D"))
        self.action_random_data.triggered.connect(self.add_random_data)

    def build_toolbars(self) -> None:
        log.info("Creating GUI toolbars")

        self.toolbar_main = QToolBar("main_toolbar")

        self.toolbar_main.addActions(
            [
                self.action_random_data,
                self.action_get_calibration,
                self.action_set_calibration,
                self.action_fit_ellipsoid,
                self.action_plot_ellipsoid_wireframe,
                self.action_quit,
            ]
        )

        self.toolbar_mpl = QToolBar("matplotlib_default_tools")
        self.mpl_default_tools = NavigationToolbar2QT(self.primary_canvas, self)
        self.toolbar_mpl.addWidget(self.mpl_default_tools)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_main)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_mpl)

    def build_menus(self) -> None:
        log.info("Creating GUI menus")

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

    # End of UI -----------------

    # Controller -----------------------
    def start_comms_thread(self) -> None:
        log.info("Starting communication thread")

        self.comms_thread = QThread()
        self.board_comms = Board2GUI()
        self.board_comms.moveToThread(self.comms_thread)

        self.board_comms.data_row_received.connect(self.data_model.append_data)
        self.board_comms.calibration_received.connect(self.calibration_received_handler)
        self.board_comms.to_log.connect(self.gui_logger)
        self.board_comms.error_signal.connect(self.exception2MessageBox)
        self.board_comms.task_done.connect(self.comms_task_done)

        self.start_data_read.connect(self.board_comms.read_magnetic_calibration_data)
        self.start_calibration_get.connect(self.board_comms.get_calibration)
        self.start_calibration_set.connect(self.board_comms.set_calibration)
        self.stop_comms_task.connect(
            self.board_comms.set_stop_flag, Qt.ConnectionType.DirectConnection
        )

        # TODO: Connecting button callbacks here is very pastalicous.
        self.calibration_widget.misc.get_calibration_button.pressed.connect(
            self.button_get_misc_calibration_callback
        )
        self.calibration_widget.misc.set_calibration_button.pressed.connect(
            self.button_set_misc_calibration_callback
        )

        self.comms_thread.start()

    def button_get_misc_calibration_callback(self) -> None:
        if not self.board_comms.task_running:
            self.disable_comms_buttons()

            self.update_current_board()
            self.start_calibration_get.emit("misc")

    def button_set_misc_calibration_callback(self) -> None:
        if not self.board_comms.task_running:
            self.disable_comms_buttons()
            self.update_current_board()

            output_offset = self.calibration_widget.misc.get_offset()
            ahrs_settings = self.calibration_widget.misc.get_ahrs_settings()
            self.start_calibration_set.emit("misc", (output_offset, ahrs_settings))

    def button_get_gyroscope_calibration_callback(self) -> None:
        if not self.board_comms.task_running:
            self.disable_comms_buttons()
            self.update_current_board()
            self.start_calibration_get.emit("gyroscope")

    def button_get_accelerometer_calibration_callback(self) -> None:
        if not self.board_comms.task_running:
            self.disable_comms_buttons()
            self.update_current_board()
            self.start_calibration_get.emit("accelerometer")

    def action_get_calibration_callback(self):
        if not self.board_comms.task_running:
            self.disable_comms_buttons()

            self.action_get_calibration.setEnabled(False)
            self.update_current_board()
            self.start_calibration_get.emit("magnetic")

    def action_set_calibration_callback(self):
        if not self.board_comms.task_running:
            self.disable_comms_buttons()

            self.action_set_calibration.setEnabled(False)
            self.update_current_board()
            soft_iron = self.calibration_widget.magnetic.soft_iron.get()
            hard_iron = self.calibration_widget.magnetic.hard_iron.get()

            self.start_calibration_set.emit("magnetic", (soft_iron, hard_iron))

    def action_plot_ellipsoid_wireframe_callback(self) -> None:
        if True:
            print("plot")
            soft_iron = self.calibration_widget.magnetic.soft_iron.get()
            hard_iron = self.calibration_widget.magnetic.hard_iron.get()

            x, y, z = makeEllipsoidXYZ(*hard_iron, *np.diag(soft_iron), as_mesh=True)
            self.primary_canvas.update_wireframe(x, y, z)
        else:
            print("delete")
            self.primary_canvas.delete_wireframe()

    @Slot(object)  # pyright: ignore
    def calibration_received_handler(self, calibration_id: str, data: tuple) -> None:
        log.info(f"Calibration data received: {calibration_id}, {data}")

        match calibration_id.lower():
            case "magnetometer" | "magnetic":
                soft_iron, hard_iron = data
                self.calibration_widget.magnetic.soft_iron.set(soft_iron)
                self.calibration_widget.magnetic.hard_iron.set(hard_iron)

            case "gyroscope":
                misalignment, sensitivity, offset = data
                self.calibration_widget.gyroscope.misalignment.set(misalignment)
                self.calibration_widget.gyroscope.sensitivity.set(sensitivity)
                self.calibration_widget.gyroscope.offset.set(offset)

            case "accelerometer":
                misalignment, sensitivity, offset = data
                self.calibration_widget.accelerometer.misalignment.set(misalignment)
                self.calibration_widget.accelerometer.sensitivity.set(sensitivity)
                self.calibration_widget.accelerometer.offset.set(offset)

            case "misc":
                output_offset, ahrs_settings = data
                self.calibration_widget.misc.set_offset(output_offset)
                self.calibration_widget.misc.set_ahrs_settings(ahrs_settings)

            case _:
                log.error(f"Wrong calibration id: {id}")
                raise ValueError(f"Wrong calibration id supplied: {id}")

    def data_read_callback(self) -> None:
        log.info("Data read callback triggered")
        self.update_current_board()

        if not self.board_comms.task_running:
            log.info("Starting data read task")
            self.disable_comms_buttons()

            self.start_data_read.emit()
        else:
            log.info("Stopping data read task")
            self.stop_comms_task.emit()

    def action_fit_ellipsoid_callback(self):
        data = self.data_model.get_xyz_data()

        (
            params,
            fopt,
            gopt,
            bopt,
            func_calls,
            grad_calls,
            warnflag,
        ) = fitEllipsoidNonRotated(*data)

        # INFO: Using notation from AN4246 page 7.
        V = np.array(params[:3])
        A = np.diag(params[3:])

        # INFO: Eqn. 20 in AN4246.
        # BUG: Cannot figure out if we are supposed to use the soft_iron or inv_soft_iron in the board-side calibration
        #
        # inv_soft_iron = scipy.linalg.sqrtm(A)
        # soft_iron = np.linalg.inv(inv_soft_iron)
        # breakpoint()
        #

        # INFO: For now we just use the inverse of the ellipsoid fit-matrix parameters.
        # That gives us a calibrated magnetic vector normalised to 1 (???).
        soft_iron = np.linalg.inv(A)

        self.calibration_widget.magnetic.soft_iron.set(soft_iron)
        self.calibration_widget.magnetic.hard_iron.set(V)

        s_params = (
            "Fit parameters",
            f"x0={params[0]:.4f}, y0={params[1]:.4f}, z0={params[2]:.4f}, a={params[3]:.4f}, b={params[4]:.4f}, c={params[5]:.4f}",
        )
        s_fopt = ("Residual", f"{fopt:.4e}")
        s_func = ("Function calls", f"{func_calls}")
        s_grad = ("Gradient calls", f"{grad_calls}")

        self.gui_logger(f"Fit parameters:\t{s_params[1]}")
        self.gui_logger(f"Residual: \t{s_fopt[1]}")
        self.gui_logger(f"Function calls: \t{s_func[1]}")
        self.gui_logger(f"Gradient calls: \t{s_grad[1]}")

    def add_random_data(self) -> None:
        self.data_model.append_data(np.random.randint(0, 50, size=(1, 3)))

    def disable_comms_buttons(self) -> None:
        log.info("Disabling communication buttons")

        self.device_select_widget.data_button.setText("Stop")
        self.action_get_calibration.setDisabled(True)
        self.action_set_calibration.setDisabled(True)

    def restore_comms_buttons(self) -> None:
        log.info("Restoring communication buttons")

        self.device_select_widget.data_button.setText("Start")
        self.action_get_calibration.setEnabled(True)
        self.action_set_calibration.setEnabled(True)

    # End of Controller ----------------

    @Slot()
    def comms_task_done(self) -> None:
        log.info("Communication task done")

        self.restore_comms_buttons()
        self.gui_logger("Board communication done.")

    def update_current_board(self) -> None:
        log.info("Updating current board")

        device = self.device_select_widget.device_selector.currentData()

        if device == "debug":
            self.board = TestSerialComms()
        else:
            self.board = Nano33SerialComms(device)

        self.board.moveToThread(self.comms_thread)
        self.board_comms.set_board(self.board)
        self.board_comms.set_sample_size(self.device_select_widget.data_points.value())

        log.info(
            f"Current board set to: {device}, N={self.board_comms.read_sample_size}"
        )

    def closeEvent(self, event):
        # NOTE: We must stop all running threads we have created before closing the main application.
        # Not doing this gives the occasional segfault.

        log.info("Closing main window and stopping threads.")
        try:
            if self.comms_thread.isRunning():
                self.stop_comms_task.emit()
                self.comms_thread.quit()

                while self.comms_thread.isRunning():
                    pass

        except AttributeError:  # If board_thread does not exist.
            pass

        return super().closeEvent(event)

    @Slot(object)  # pyright: ignore
    def exception2MessageBox(self, e: Exception):
        """
        Show exception error message in a GUI message box.
        """
        QMessageBox.warning(
            self,
            "Error",
            str(e),
            QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.NoButton,
        )

    @Slot(str)  # pyright: ignore
    def gui_logger(self, msg: str):
        """
        Print message to the GUI log widget.
        """
        time = datetime.datetime.now().time()
        self.log_widget.append(f"{time}: {msg}")
