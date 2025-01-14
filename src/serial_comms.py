import time
import unicodedata
from PySide6.QtWidgets import QMessageBox
import numpy as np

from typing import Protocol, Tuple, Union
from serial import Serial, SerialException

from threading import Lock
from PySide6.QtCore import QObject, Signal, Slot, Qt

# TODO: Too much stuff in single class/file.
# Separate board serial comms, comms with Qt Gui (signals & slots), and threading
# related functions.
#
# TODO: Do not subclass QThread. Create thread somewhere else and move QObject to it.


"""
    Control codes for controlling the serial output
    and the magnetic calibration values of the Arduino NANO33.

    TODO:   Some are defined as string and some as integers.
            Choose one and stick to it.
"""
SERIAL_HANDSHAKE = "0x05"
SERIAL_DONE = "0x06"

SERIAL_PRINT_NOTHING = 0x10
SERIAL_PRINT_MAG_RAW = 0x11
SERIAL_PRINT_MAG_CALIB = 0x12
SERIAL_PRINT_ACC_RAW = 0x13
SERIAL_PRINT_ACC_CALIB = 0x14
SERIAL_PRINT_GYRO_RAW = 0x15
SERIAL_PRINT_GYRO_CALIB = 0x16
SERIAL_PRINT_AHRS = 0x20

SERIAL_MAG_SET_CALIB = 0x30
SERIAL_MAG_GET_CALIB = 0x31
SERIAL_ACC_SET_CALIB = 0x40
SERIAL_ACC_GET_CALIB = 0x41
SERIAL_GYRO_SET_CALIB = 0x50
SERIAL_GYRO_GET_CALIB = 0x51

SERIAL_RESET_FACTORY_DEFAULTS = 0x60
SERIAL_RESET_KVSTORE = 0x70

SERIAL_BAUDRATE = 57600  # NOTE: Baudrate should not matter with Arduino NANO33
SERIAL_WAIT = 2.0  # seconds
SERIAL_NO_OUTPUT = b""  # serial.readline returns b'' if read timeouts.


class SerialCommsError(Exception):
    pass


class NoDataReceived(Exception):
    pass


class BoardCommunications(Protocol):
    def __enter__(self) -> None:
        self.open()

    def __exit__(self, *args) -> None:
        self.close()

    def open(self) -> None: ...

    def close(self) -> None: ...

    def reset_calibration(self) -> None: ...

    def set_output_mode(self, mode: int) -> None: ...

    def get_magnetometer_calibration(self) -> np.ndarray: ...

    def set_magnetometer_calibration(self, data: np.ndarray) -> None: ...

    def get_accelerometer_calibration(self) -> np.ndarray: ...

    def set_accelerometer_calibration(self, data: np.ndarray) -> None: ...

    def get_gyroscope_calibration(self) -> np.ndarray: ...

    def set_gyroscope_calibration(self, data: np.ndarray) -> None: ...

    def read_row(self) -> np.ndarray: ...


class Board2GUI(QObject):
    """
    Wrapper for passing data from the board to the GUI.

    Low-level comms should be handled by the 'board'-object.
    """

    board: BoardCommunications

    read_sample_size: int
    read_retries: int
    read_wait: float
    stop_reading: bool
    mutex: Lock

    data_row_received = Signal(object)
    data_read_done = Signal()
    debug_signal = Signal(str)

    def __init__(self, board: BoardCommunications, read_sample_size: int = 50) -> None:
        super().__init__()

        self.board = board
        self.read_sample_size = read_sample_size
        self.mutex = Lock()
        self.read_wait = 0.10
        self.read_retries = 3

    @Slot()
    def read_magnetic_calibration_data(self) -> None:
        self.stop_reading = False
        i = 0

        try:
            self.board.open()
            self.board.set_output_mode(SERIAL_PRINT_MAG_RAW)

            while i < self.read_sample_size and not self.stop_reading:
                # TODO: Retry code looks ugly and hard to read.
                for attempt in range(self.read_retries):
                    try:
                        row = self.board.read_row()
                        self.data_row_received.emit(row)
                        i += 1
                        time.sleep(self.read_wait)
                    except NoDataReceived:
                        continue  # Runs the retry-loop again.
                    else:
                        break  # Stop the retry-loop if no error occured.
                else:  # This gets executed only if the for loop is NOT stopped with break.
                    self.debug_signal.emit(
                        f"Reading data failed after {self.read_retries} retries."
                    )

        except AttributeError as e:
            self.debug_signal.emit(f"{e}")

        except SerialCommsError as e:
            self.debug_signal.emit(f"{e}")

        finally:
            self.board.close()
            self.data_read_done.emit()

    @Slot()
    def stop_reading_data(self) -> None:
        with self.mutex:
            self.stop_reading = True


class TestSerialComms(QObject):
    def reset_calibration(self) -> None: ...

    def set_output_mode(self, mode: int) -> None:
        pass

    def get_magnetometer_calibration(self) -> np.ndarray: ...

    def set_magnetometer_calibration(self, data: np.ndarray) -> None: ...

    def get_accelerometer_calibration(self) -> np.ndarray: ...

    def set_accelerometer_calibration(self, data: np.ndarray) -> None: ...

    def get_gyroscope_calibration(self) -> np.ndarray: ...

    def set_gyroscope_calibration(self, data: np.ndarray) -> None: ...

    def read_row(self) -> np.ndarray:
        time.sleep(0.25)
        row = np.random.randint(0, 60, size=(1, 3))
        return row


class Nano33SerialComms(QObject):
    ser: Serial

    calibration_sample_size: int
    serial_port: str
    serial_baudrate: int
    serial_timeout: float
    handshake_timeout: float

    mutex: Lock = Lock()

    def __init__(
        self,
        port: str,
        baudrate: int = 57600,
        timeout: float = 2.0,
        handshake_timeout: float = 5.0,
    ):
        super().__init__()

        self.serial_port = port
        self.serial_baudrate = baudrate
        self.serial_timeout = timeout
        self.handshake_timeout = handshake_timeout

    def reset_calibration(self) -> None:
        self.send_command(SERIAL_RESET_KVSTORE)

    def set_output_mode(self, mode: int) -> None:
        command_str = self.parse_command_string(mode)

        try:
            self.send_command_string(command_str)
        except SerialException as e:
            raise SerialCommsError(e)

    def get_magnetometer_calibration(self) -> np.ndarray:
        return np.array(self.get_calibration(SERIAL_MAG_GET_CALIB))

    def set_magnetometer_calibration(self, data: np.ndarray) -> None:
        self.set_calibration(SERIAL_MAG_SET_CALIB, data)

    def get_accelerometer_calibration(self) -> np.ndarray:
        return np.array(self.get_calibration(SERIAL_ACC_GET_CALIB))

    def set_accelerometer_calibration(self, data: np.ndarray) -> None:
        self.set_calibration(SERIAL_ACC_SET_CALIB, data)

    def get_gyroscope_calibration(self) -> np.ndarray:
        return np.array(self.get_calibration(SERIAL_GYRO_GET_CALIB))

    def set_gyroscope_calibration(self, data: np.ndarray) -> None:
        self.set_calibration(SERIAL_GYRO_SET_CALIB, data)

    def open(self) -> None:
        try:
            self.ser = Serial(
                self.serial_port,
                timeout=self.serial_timeout,
                baudrate=self.serial_baudrate,
            )
        except SerialException as e:
            raise SerialCommsError(e)

    def close(self) -> None:
        try:
            self.ser.close()
        except AttributeError:
            pass

    def read_row(self) -> np.ndarray:
        # Flush everything so we get the newest measurement value.
        self.ser.reset_input_buffer()

        stop_byte = "\n".encode("ASCII")
        raw = self.ser.read_until(stop_byte).decode("utf8")

        try:
            row = np.array([float(d) for d in raw.split(sep=",")])
        except ValueError as e:  # if no data was received.
            raise NoDataReceived(e)

        return row.reshape(1, 3)

    def send_command(self, command_id: int) -> None:
        with self.mutex:
            try:
                with Serial(
                    self.serial_port,
                    timeout=self.serial_timeout,
                    baudrate=self.serial_baudrate,
                ) as self.ser:
                    command = self.parse_command_string(command_id)
                    self.send_command_string(command)

            except SerialException as err:
                ...

    def wait_for_board_response(self) -> Tuple[bool, str]:
        # TODO: Raise error instead of returning success-state.

        timeout = time.time() + self.handshake_timeout
        while (data := self.ser.readline()) == SERIAL_NO_OUTPUT:
            if time.time() > timeout:
                return False, ""
            else:
                continue

        return True, data.decode("utf8")

    def get_calibration(self, calibration_type: int) -> list[float] | None:
        """
        Get calibration data from the board.

        IN: calibration_type: One of the 'SERIAL_GET_...' constants.
        """
        with self.mutex:
            try:
                with Serial(
                    self.serial_port,
                    timeout=self.serial_timeout,
                    baudrate=self.serial_baudrate,
                ) as self.ser:
                    command = self.parse_command_string(calibration_type)
                    self.send_command_string(command)
                    _, calib_raw = self.wait_for_board_response()
                    return self.parse_calibration_from_board(calib_raw)

            except SerialException as err:
                ...
            finally:
                ...

    def set_calibration(self, calibration_type: int, data: list[float]) -> None:
        """
        Send calibration data to the board.

        IN: calibration_type: One of the 'SERIAL_SET_...' constants.
            data: list of calibration values. Only first three are used [x, y, z].
        """
        with self.mutex:
            try:
                with Serial(
                    self.serial_port,
                    timeout=self.serial_timeout,
                    baudrate=self.serial_baudrate,
                ) as self.ser:
                    command = self.parse_command_string(calibration_type, data)
                    self.send_command_string(command)
                    self.wait_for_board_response()

            except SerialException as err:
                ...
            finally:
                ...
        """
        Get calibration data from the board.

        IN: calibration_type: One of the 'SERIAL_GET_...' constants.
        """
        with self.mutex:
            try:
                with Serial(
                    self.serial_port,
                    timeout=self.serial_timeout,
                    baudrate=self.serial_baudrate,
                ) as self.ser:
                    command = self.parse_command_string(calibration_type)
                    self.send_command_string(command)
                    _, calib_raw = self.wait_for_board_response()
                    return self.parse_calibration_from_board(calib_raw)

            except SerialException as err:
                ...
            finally:
                ...

    def parse_calibration_from_board(self, input: str) -> list[float]:
        """
        Parse values from string of format "Offset: <x>, <y>, <z>; Gain: <x>, <y>, <z>",
        where <x,y,z> are the calibration values.

        IN: The string to be parsed.

        OUT: List of the offset and gain calibration values.
        """

        s = input.replace(":", ";").split(sep=";")
        vals_str = s[1] + "," + s[3]
        return [float(x) for x in vals_str.split(",")]

    def send_command_string(self, command: str) -> bool:
        """
        Send a command to the board.

        NOTE: The serial object 'self.ser' has to be opened before using this function.
        """
        if not self.serial_handshake():
            # self.logStd("Handshake with board failed.\n", self.command_log)
            return False

        # self.logStd("Handshake with board successful.\n", self.command_log)
        # self.logStd("Sending command: " + command + "\n", self.command_log)
        self.ser.write(command.encode("utf8"))
        return True

    def serial_handshake(self) -> bool:
        """
        Wait for the board to return the handshake.

        NOTE: The serial object 'self.ser' has to be opened before using this function.
        """
        self.ser.write(SERIAL_HANDSHAKE.encode("utf8"))

        time_end = time.time() + self.handshake_timeout
        while time.time() < time_end:
            response = self.ser.readline().decode("utf8")
            response = self.remove_control_characters(response)

            if response == SERIAL_HANDSHAKE:
                return True
            else:
                time.sleep(0.50)

        return False

    @staticmethod
    def remove_control_characters(input: str) -> str:
        try:
            return "".join(
                char for char in input if unicodedata.category(char)[0] != "C"
            )
        except TypeError:
            return ""

    @staticmethod
    def parse_command_string(command: int, data: list[Union[int, float]] = []) -> str:
        command_str = "0x{:02x}; ".format(command)
        for item in data:
            command_str += "{}, ".format(item)
        command_str += "; "

        return command_str
