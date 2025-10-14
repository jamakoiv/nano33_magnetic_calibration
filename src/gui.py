import logging
import datetime
import numpy as np

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from PySide6.QtCore import Qt, Slot, Signal, QThread
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QTableView,
    QToolBar,
    QDockWidget,
    QWidget,
    QTextEdit,
)


from canvas import MatplotlibCanvas
from models import CalibrationDataModel, CalibrationDataDelegate
from widgets import DeviceSelectWidget, CalibrationWidget, FitWidget
from orientation_window import OrientationWindow
from serial_comms import Board2GUI, Nano33SerialComms, TestSerialComms
from ellipsoid import makeEllipsoidXYZ

log = logging.getLogger(__name__)


# TODO: This is becoming a god-class.
class MainWindow(QMainWindow):
    start_data_read = Signal()
    start_calibration_get = Signal(str)
    start_calibration_set = Signal(str, object)
    stop_comms_task = Signal()

    def __init__(self, parent: QWidget | None = None):
        log.info("Creating main window.")

        super().__init__(parent=parent)

        # NOTE: These must be called in this order.
        # E.g. Actions must be created before they can be added to toolbar.
        self.primary_canvas = MatplotlibCanvas(5, 5, 96, projection="3d")
        self.setCentralWidget(self.primary_canvas)
        self.build_dock_widgets()
        self.build_actions()
        self.build_toolbars()
        self.build_menus()

        self.data_model = CalibrationDataModel(parent=self)
        self.data_table_widget.setModel(self.data_model)
        self.data_model.rowsInserted.connect(self.data_table_widget.scrollToBottom)

        self.primary_canvas.setModel(self.data_model)

        self.device_select_widget.data_button.pressed.connect(self.data_read_callback)

        self.start_comms_thread()
        self.device_select_widget.refresh_serial_ports()

    # UI ------------------------
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
        # self.calibration_dock.setFeatures(
        #     QDockWidget.DockWidgetFeature.DockWidgetVerticalTitleBar
        # )
        self.calibration_widget.magnetic.send_to_board_action.triggered.connect(
            self.set_magnetic_calibration_callback
        )
        self.calibration_widget.accelerometer.send_to_board_action.triggered.connect(
            self.set_accelerometer_calibration_callback
        )
        self.calibration_widget.gyroscope.send_to_board_action.triggered.connect(
            self.set_gyroscope_calibration_callback
        )
        self.calibration_widget.misc.send_to_board_action.triggered.connect(
            self.set_misc_settings_callback
        )

        self.orientation_window = OrientationWindow()
        self.orientation_widget = QWidget.createWindowContainer(
            self.orientation_window, parent=self
        )
        # self.orientation_widget.setSizePolicy(default_size_policy)
        self.orientation_dock = QDockWidget("&Board Orientation", parent=self)
        self.orientation_dock.setWidget(self.orientation_widget)
        self.orientation_dock.visibilityChanged.connect(
            self.orientation_window.setUpdateTimerRunning
        )

        self.data_table_widget = QTableView(parent=self)
        self.data_table_dock = QDockWidget("Data &table", parent=self)
        self.data_table_dock.setWidget(self.data_table_widget)
        self.data_table_widget.horizontalHeader().setDefaultSectionSize(85)
        self.data_table_delegate = CalibrationDataDelegate()
        self.data_table_widget.setItemDelegate(self.data_table_delegate)
        # self.data_table_dock.setFeatures(
        #     QDockWidget.DockWidgetFeature.DockWidgetVerticalTitleBar
        # )

        self.log_widget = QTextEdit(parent=self)
        self.log_dock = QDockWidget("&Log", parent=self)
        self.log_dock.setWidget(self.log_widget)

        # self.addDockWidget(
        #     Qt.DockWidgetArea.LeftDockWidgetArea, self.device_select_dock
        # )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.calibration_dock)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.data_table_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self.orientation_dock
        )

    def build_actions(self) -> None:
        log.info("Creating GUI-actions")

        self.action_quit = QAction(QIcon.fromTheme("application-exit"), "&Exit", self)
        self.action_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self.action_quit.triggered.connect(self.close)

    def build_toolbars(self) -> None:
        log.info("Creating GUI toolbars")

        self.toolbar_device = QToolBar("device_toolbar")
        self.device_select_widget = DeviceSelectWidget(parent=self)
        self.device_select_widget.device_selector.currentIndexChanged.connect(
            self.update_current_board
        )
        self.device_select_widget.data_points.valueChanged.connect(
            self.update_current_board
        )
        self.device_select_widget.get_calibration_action.triggered.connect(
            self.action_get_calibration_callback
        )
        self.toolbar_device.addWidget(self.device_select_widget)

        self.toolbar_fit = QToolBar("main_toolbar")
        self.fit_widget = FitWidget(parent=self)
        self.fit_widget.button_fit_ellipsoid.pressed.connect(
            self.action_fit_ellipsoid_callback
        )
        self.toolbar_fit.addWidget(self.fit_widget)

        self.toolbar_mpl = QToolBar("matplotlib_default_tools")
        self.mpl_default_tools = NavigationToolbar2QT(self.primary_canvas, self)
        self.toolbar_mpl.addWidget(self.mpl_default_tools)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_device)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_fit)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar_mpl)

    def build_menus(self) -> None:
        log.info("Creating GUI menus")

        self.menu_file = self.menuBar().addMenu("&File")
        self.menu_file.addAction(self.action_quit)

        self.menu_view = self.menuBar().addMenu("&View")

        self.menu_view.addActions(
            [
                # self.device_select_dock.toggleViewAction(),
                self.calibration_dock.toggleViewAction(),
                self.orientation_dock.toggleViewAction(),
                self.menu_view.addSeparator(),
                self.data_table_dock.toggleViewAction(),
                self.log_dock.toggleViewAction(),
            ]
        )

    # End of UI -----------------

    # Controller -----------------------

    def set_magnetic_calibration_callback(self) -> None:
        data = (
            self.calibration_widget.magnetic.soft_iron.get(),
            self.calibration_widget.magnetic.hard_iron.get(),
        )
        log.info(f"Magnetic calibration data to send: {data}")

        self.start_calibration_set.emit("magnetic", data)

    def set_accelerometer_calibration_callback(self) -> None:
        data = (
            self.calibration_widget.accelerometer.misalignment.get(),
            self.calibration_widget.accelerometer.sensitivity.get(),
            self.calibration_widget.accelerometer.offset.get(),
        )
        log.info(f"Accelerometer calibration data to send: {data}")

        self.start_calibration_set.emit("accelerometer", data)

    def set_gyroscope_calibration_callback(self) -> None:
        data = (
            self.calibration_widget.gyroscope.misalignment.get(),
            self.calibration_widget.gyroscope.sensitivity.get(),
            self.calibration_widget.gyroscope.offset.get(),
        )
        log.info(f"Gyroscope calibration data to send: {data}")

        self.start_calibration_set.emit("gyroscope", data)

    def set_misc_settings_callback(self) -> None:
        data = (
            self.calibration_widget.misc.output_offset.get(),
            self.calibration_widget.misc.filter_time_constant.get(),
            self.calibration_widget.misc.get_ahrs_settings(),
        )
        log.info(f"Offset and AHRS settings to send: {data}")

        self.start_calibration_set.emit("misc", data)

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

        self.start_data_read.connect(self.board_comms.read_raw_data)
        self.start_calibration_get.connect(self.board_comms.get_calibration)
        self.start_calibration_set.connect(self.board_comms.set_calibration)
        self.stop_comms_task.connect(
            self.board_comms.set_stop_flag, Qt.ConnectionType.DirectConnection
        )

        self.comms_thread.start()

    def set_calibration_callback_template(self, id: str, data: tuple) -> None:
        log.info(f"Set calibration callback triggered: {id}, {data}")
        if not self.board_comms.task_running:
            self.disable_comms_buttons()
            self.start_calibration_set.emit(id, data)

    def action_get_calibration_callback(self):
        if not self.board_comms.task_running:
            self.disable_comms_buttons()

            self.device_select_widget.get_calibration_action.setEnabled(False)
            self.start_calibration_get.emit("magnetic")
            self.start_calibration_get.emit("gyroscope")
            self.start_calibration_get.emit("accelerometer")
            self.start_calibration_get.emit("misc")

    def action_plot_ellipsoid_wireframe_callback(self) -> None:
        soft_iron = self.calibration_widget.magnetic.soft_iron.get()
        hard_iron = self.calibration_widget.magnetic.hard_iron.get()

        x, y, z = makeEllipsoidXYZ(*hard_iron, *np.diag(soft_iron), as_mesh=True)
        self.primary_canvas.update_wireframe(x, y, z)

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
                output_offset, filter_constant, ahrs_settings = data
                self.calibration_widget.misc.output_offset.set(output_offset)
                self.calibration_widget.misc.filter_time_constant.set(filter_constant)
                self.calibration_widget.misc.set_ahrs_settings(ahrs_settings)

            case _:
                log.error(f"Wrong calibration id: {id}")
                raise ValueError(f"Wrong calibration id supplied: {id}")

    def data_read_callback(self) -> None:
        log.info("Data read callback triggered")

        if not self.board_comms.task_running:
            log.info("Starting data read task")
            self.disable_comms_buttons()

            self.start_data_read.emit()
        else:
            log.info("Stopping data read task")
            self.stop_comms_task.emit()

    def action_fit_ellipsoid_callback(self):
        data = self.data_model.get_xyz_data()
        soft_iron, offset, semi_axes, rotation = self.fit_widget.fit_function(*data)

        self.gui_logger(f"soft-iron matrix: {soft_iron}")
        self.gui_logger(f"offset vector: {offset}")
        self.gui_logger(f"semi-axes: {semi_axes}")
        self.gui_logger(f"rotation matrix: {rotation}")

        self.calibration_widget.magnetic.soft_iron.set(soft_iron)
        self.calibration_widget.magnetic.hard_iron.set(offset)

    def disable_comms_buttons(self) -> None:
        log.info("Disabling communication buttons")

        self.device_select_widget.data_button.setText("Stop")
        self.device_select_widget.get_calibration_action.setDisabled(True)

    def restore_comms_buttons(self) -> None:
        log.info("Restoring communication buttons")

        self.device_select_widget.data_button.setText("Start")
        self.device_select_widget.get_calibration_action.setEnabled(True)

    # End of Controller ----------------

    @Slot()
    def comms_task_done(self) -> None:
        log.info("Communication task done")

        self.restore_comms_buttons()
        self.data_table_widget.resizeColumnsToContents()
        self.gui_logger("Board communication done.")

    def update_current_board(self) -> None:
        log.info("Updating current board")

        device, name = self.device_select_widget.device_selector.currentData()

        if device == "debug":
            self.board = TestSerialComms()
        else:
            self.board = Nano33SerialComms(device)

        self.board.moveToThread(self.comms_thread)
        self.board_comms.set_board(self.board)
        self.board_comms.set_sample_size(self.device_select_widget.data_points.value())

        joy_id, joy_name, _ = self.orientation_window.joystick.guess_joystick_id(name)
        self.orientation_window.setJoystick(joy_id)

        log.info(
            f"Current board set to: {device}, N={self.board_comms.read_sample_size}; Joystick ID: {joy_id}, {joy_name}"
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

        f_csv = "data.csv"
        log.info(f"Exporting table to csv: {f_csv}")
        np.savetxt(f_csv, self.data_model._data, fmt="%f", delimiter=",")

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
