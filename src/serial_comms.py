from enum import Enum
import time
import unicodedata
import struct
import numpy as np

from typing import Iterable, Protocol
from serial import Serial, SerialException

from threading import Lock
from PySide6.QtCore import QObject, Signal, Slot, Qt

from .ellipsoid import makeEllipsoidXYZ


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


class BoardCommsError(Exception):
    pass


class NoDataReceived(Exception):
    pass


class RetryLimitReached(Exception):
    pass


class BoardCommunications(Protocol):
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


class CalibrationType(Enum):
    magnetometer = 0
    gyroscope = 1
    accelerometer = 2


class Board2GUI(QObject):
    """
    Wrapper for passing data from the board to the GUI.

    Low-level comms should be handled by the 'board'-object.
    """

    board: BoardCommunications

    read_sample_size: int
    read_retries: int
    read_wait: float
    stop: bool
    mutex: Lock

    task_running: bool
    task_done = Signal()

    data_row_received = Signal(object)
    calibration_received = Signal(object)
    debug_signal = Signal(str)
    error_signal = Signal(object)
    to_log = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self.mutex = Lock()
        self.task_running = False
        self.read_wait = 0.10
        self.read_retries = 5

    def set_board(self, board: BoardCommunications) -> None:
        with self.mutex:
            self.board = board

    def set_sample_size(self, N: int) -> None:
        with self.mutex:
            self.read_sample_size = int(N)

    @Slot()
    def read_magnetic_calibration_data(self) -> None:
        with self.mutex:
            self.task_running = True
            self.stop = False
            i = 0

        try:
            self.to_log.emit("Start reading raw magnetometer data from board.")

            self.board.open()
            self.board.set_output_mode(SERIAL_PRINT_MAG_RAW)

            while i < self.read_sample_size and not self.stop:
                # TODO: Retry code looks ugly and hard to read.
                for attempt in range(self.read_retries):
                    try:
                        row = self.board.read_row()
                        self.data_row_received.emit(row)
                        self.to_log.emit("Received data: {}".format(row))
                        i += 1
                        time.sleep(self.read_wait)
                    except NoDataReceived:
                        self.debug_signal.emit(
                            f"Reading data failed, attempt {attempt}."
                        )
                        continue  # Runs the retry-loop again.
                    else:
                        break  # Stop the retry-loop if no error occured.
                else:  # This gets executed only if the for loop is NOT stopped with break.
                    self.debug_signal.emit(
                        f"Reading data failed after {self.read_retries} retries."
                    )
                    self.error_signal.emit(
                        RetryLimitReached(
                            f"Reading data failed after {self.read_retries} tries."
                        )
                    )
                    break

        except AttributeError as e:
            self.debug_signal.emit(f"{e}")
            self.error_signal.emit(e)

        except BoardCommsError as e:
            self.debug_signal.emit(f"{e}")
            self.error_signal.emit(e)

        finally:
            with self.mutex:
                self.task_running = False

            self.board.close()
            self.task_done.emit()

    @Slot(str)  # pyright: ignore
    def get_calibration(self, calibration_type: str) -> None:
        try:
            self.to_log.emit("Start reading calibration from board.")
            self.board.open()

            with self.mutex:
                self.task_running = True

            match calibration_type.lower():
                case "magnetometer" | "magnetic":
                    id = "magnetometer"
                    res = self.board.get_magnetometer_calibration()

                case "gyroscope":
                    id = "gyroscope"
                    res = self.board.get_gyroscope_calibration()

                case "accelerometer":
                    id = "accelerometer"
                    res = self.board.get_accelerometer_calibration()

                case _:
                    raise ValueError("Wrong calibration type supplied")

            offset = res[:3]
            gain = res[3:]
            self.calibration_received.emit((id, offset, gain))

        finally:
            with self.mutex:
                self.task_running = False

            self.task_done.emit()
            self.board.close()
            self.to_log.emit("Done reading calibration.")

    @Slot(str, object, object)  # pyright: ignore
    def set_calibration(
        self, calibration_type: str, offset: np.ndarray, gain: np.ndarray
    ) -> None:
        try:
            self.to_log.emit("Start setting calibration to board.")
            self.board.open()

            with self.mutex:
                self.task_running = True

            calib = np.concatenate((offset, gain))

            match calibration_type.lower():
                case "magnetometer" | "magnetic":
                    self.board.set_magnetometer_calibration(calib)

                case "gyroscope":
                    self.board.set_gyroscope_calibration(calib)

                case "accelerometer":
                    self.board.set_accelerometer_calibration(calib)

                case _:
                    raise ValueError("Wrong calibration type supplied")

        finally:
            with self.mutex:
                self.task_running = False

            self.task_done.emit()
            self.board.close()
            self.to_log.emit("Done setting calibration.")

    @Slot()
    def set_stop_flag(self) -> None:
        self.to_log.emit("Stopping comms operation.")
        with self.mutex:
            self.stop = True


class TestSerialComms(QObject):
    def __init__(self, random_seed=None):
        super().__init__()

        self.rng = np.random.default_rng(seed=random_seed)

        self.magnetic_calibration = self.rng.random(6) * 40
        self.accelerometer_calibration = self.rng.random(6)
        self.gyroscope_calibration = self.rng.random(6)

        self.data = makeEllipsoidXYZ(
            20, 15, -12, 40, 35, 50, N=20, noise_scale=1, generator=self.rng
        )

    def open(self) -> None: ...

    def close(self) -> None: ...

    def reset_calibration(self) -> None: ...

    def set_output_mode(self, mode: int) -> None:
        pass

    def get_magnetometer_calibration(self) -> np.ndarray:
        return self.magnetic_calibration

    def set_magnetometer_calibration(self, data: np.ndarray) -> None:
        self.magnetic_calibration = data

    def get_accelerometer_calibration(self) -> np.ndarray:
        return self.accelerometer_calibration

    def set_accelerometer_calibration(self, data: np.ndarray) -> None:
        self.accelerometer_calibration = data

    def get_gyroscope_calibration(self) -> np.ndarray:
        return self.gyroscope_calibration

    def set_gyroscope_calibration(self, data: np.ndarray) -> None:
        self.gyroscope_calibration = data

    def read_row(self) -> np.ndarray:
        time.sleep(0.05)
        row = np.random.randint(0, self.data.shape[1])
        return self.data.transpose()[row].reshape(1, 3)


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

    def send_command_bytes(self, cmd: bytes) -> None:
        with self.mutex:
            try:
                self.ser.write(cmd)

            except SerialException as err:
                raise BoardCommsError(err)
            except AttributeError as err:
                raise BoardCommsError(err)

    def reset_calibration(self) -> None:
        cmd = struct.pack("<BB", SERIAL_RESET_KVSTORE, 2)
        self.send_command_bytes(cmd)

    def set_output_mode(self, mode: int) -> None:
        cmd = struct.pack("<BB", mode, 2)

        try:
            self.send_command_bytes(cmd)
        except SerialException as e:
            raise BoardCommsError(e)

    def get_magnetometer_calibration(self) -> np.ndarray:
        return np.array(self.get_calibration(SERIAL_MAG_GET_CALIB))

    def set_magnetometer_calibration(self, data: np.ndarray) -> None:
        self.set_calibration(SERIAL_MAG_SET_CALIB, data.astype("float").tolist())

    def get_accelerometer_calibration(self) -> np.ndarray:
        return np.array(self.get_calibration(SERIAL_ACC_GET_CALIB))

    def set_accelerometer_calibration(self, data: np.ndarray) -> None:
        self.set_calibration(SERIAL_ACC_SET_CALIB, data.astype("float").tolist())

    def get_gyroscope_calibration(self) -> np.ndarray:
        return np.array(self.get_calibration(SERIAL_GYRO_GET_CALIB))

    def set_gyroscope_calibration(self, data: np.ndarray) -> None:
        self.set_calibration(SERIAL_GYRO_SET_CALIB, data.astype("float").tolist())

    def open(self) -> None:
        try:
            self.ser = Serial(
                self.serial_port,
                timeout=self.serial_timeout,
                baudrate=self.serial_baudrate,
            )
        except SerialException as e:
            raise BoardCommsError(e)

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

    def get_calibration(self, calibration_type: int) -> Iterable[float] | None:
        """
        Get calibration data from the board.

        IN: calibration_type: One of the 'SERIAL_GET_...' constants.
        """
        response_format = "<BBffffff"
        response_size = struct.calcsize(response_format)
        calib = [0, 0, 0, 1, 1, 1]

        try:
            cmd_0 = struct.pack("<BB", SERIAL_PRINT_NOTHING, 2)
            cmd_1 = struct.pack("<BB", calibration_type, 2)
            self.send_command_bytes(cmd_0 + b";" + cmd_1 + b";")

            for i in range(5):
                # response = self.ser.read(response_size)
                response = self.ser.readlines()
                time.sleep(0.5)

                for raw_line in response:
                    line = raw_line.split(b";")[0]
                    try:
                        cmd_id, n_bytes, *calib = struct.unpack(response_format, line)
                        print(f"{cmd_id}, {n_bytes}, {calib}")
                        return calib

                    except struct.error as err:
                        print(
                            f"Try number {i}: response from board {line} create error: {err}"
                        )

            return calib

        except SerialException as err:
            raise BoardCommsError(err)
        finally:
            ...

    def set_calibration(
        self, calibration_type: int, data: tuple[float] | list[float]
    ) -> None:
        """
        Send calibration data to the board.

        IN: calibration_type: One of the 'SERIAL_SET_...' constants.
            data: list of calibration values.
        """
        try:
            command_format = "<BBffffff"
            command_size = struct.calcsize(command_format)
            self.send_command_bytes(
                struct.pack(command_format, calibration_type, command_size, *data[:6])
            )

        except SerialException as err:
            raise BoardCommsError(err)
        finally:
            ...

    @staticmethod
    def remove_control_characters(input: str) -> str:
        try:
            return "".join(
                char for char in input if unicodedata.category(char)[0] != "C"
            )
        except TypeError:
            return ""
