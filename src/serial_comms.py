import logging
import time
import copy
import unicodedata
import struct
import numpy as np

from typing import Iterable, Protocol
from serial import Serial, SerialException
from threading import Lock
from enum import Enum
from PySide6.QtCore import QObject, Signal, Slot, Qt

from ellipsoid import makeEllipsoidXYZ

log = logging.getLogger(__name__)

# TODO: The entire code for communication with the board is a horrible mess at the moment.
# We need to rewrite significant parts to handle the fact that accelerometer/gyroscope
# have different amount of calibration parameters than magnetometer.
#
# TODO: Should we just delete the entire Board2GUI and handle everything in each different board-type?
# As if there ever will be more than Nano33..
# Also the Nano33SerialComms still must inherit from QObject to be able to send it to another QThread...


"""
    Command IDs and parameters for controlling the board 
    output and sending calibration values.

"""
#  TODO: Make into Enum or dictionary or something...
#  TODO: Maybe also define valid amount of parameters for each command...

# Commands
SERIAL_SET_PRINT_MODE = 0x10

SERIAL_MAG_SET_CALIB = 0x30
SERIAL_MAG_GET_CALIB = 0x31

SERIAL_ACC_SET_CALIB = 0x40
SERIAL_ACC_GET_CALIB = 0x41

SERIAL_GYRO_SET_CALIB = 0x50
SERIAL_GYRO_GET_CALIB = 0x51

SERIAL_SET_OFFSET = 0x80
SERIAL_GET_OFFSET = 0x81

SERIAL_RESET_KVSTORE = 0x70

# Valid print modes.
SERIAL_PRINT_NOTHING = 0x15
SERIAL_PRINT_AHRS = 0x16
SERIAL_PRINT_AHRS_DEBUG = 0x17

SERIAL_PRINT_MAG_RAW = 0x35
SERIAL_PRINT_MAG_CALIB = 0x36
SERIAL_PRINT_ACC_RAW = 0x45
SERIAL_PRINT_ACC_CALIB = 0x46
SERIAL_PRINT_GYRO_RAW = 0x55
SERIAL_PRINT_GYRO_CALIB = 0x56

"""
    ASCII data transmit control characters.
"""
ASCII_NUL = 0x00
ASCII_SOH = 0x01  # Start of header
ASCII_STX = 0x02  # Start of data
ASCII_ETX = 0x03  # End of data
ASCII_EOT = 0x04  # End of transmission
ASCII_ESC = 0x1B  # Escape next character
ESCAPE_OFFSET = 0x20


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
            log.info("Start reading raw magnetometer data from board")

            self.board.open()
            self.board.set_output_mode(SERIAL_PRINT_MAG_RAW)

            while i < self.read_sample_size and not self.stop:
                # TODO: Retry code looks ugly and hard to read.
                for attempt in range(self.read_retries):
                    try:
                        row = self.board.read_row()
                        self.data_row_received.emit(row)
                        self.to_log.emit("Received data: {}".format(row))
                        log.info("Received data: {}".format(row))
                        i += 1
                        time.sleep(self.read_wait)
                    except NoDataReceived:
                        log.warning(f"Reading data failed, attempt {attempt}")
                        continue  # Runs the retry-loop again.
                    else:
                        break  # Stop the retry-loop if no error occured.
                else:  # This gets executed only if the for loop is NOT stopped with break.
                    log.warning(
                        f"Reading data failed after {self.read_retries} retries"
                    )
                    self.error_signal.emit(
                        RetryLimitReached(
                            f"Reading data failed after {self.read_retries} tries."
                        )
                    )
                    break

        except AttributeError as e:
            log.error(f"AttributeError: {e}")
            self.error_signal.emit(e)

        except BoardCommsError as e:
            log.error(f"BoardCommsError: {e}")
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
            log.info(f"Start reading calibration from board: {calibration_type}")
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
                    self.to_log.emit("Wrong calibration type supplied")
                    raise ValueError("Wrong calibration type supplied")

            offset, gain = res[:3], res[3:]
            self.calibration_received.emit((id, offset, gain))
            self.to_log.emit(
                f"Received calibration data: {calibration_type}, offset {offset}, gain {gain}"
            )

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
            log.info(f"Start setting calibration to board: {calibration_type}")
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

            msg = f"Set calibration data: {calibration_type}, offset {offset}, gain {gain}"
            self.to_log.emit(msg)
            log.info(msg)

    @Slot()
    def set_stop_flag(self) -> None:
        self.to_log.emit("Stopping comms operation.")
        log.info("Stopping comms operation")
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
        timeout: float = 5.0,
        handshake_timeout: float = 5.0,
    ):
        super().__init__()

        self.serial_port = port
        self.serial_baudrate = baudrate
        self.serial_timeout = timeout
        self.handshake_timeout = handshake_timeout

    def send_command(self, raw_header: bytes, raw_body: bytes) -> None:
        header = self.parse_outbound_bytes(raw_header)
        body = self.parse_outbound_bytes(raw_body)
        msg = (
            bytes([ASCII_SOH])
            + header
            + bytes([ASCII_STX])
            + body
            + bytes([ASCII_ETX, ASCII_EOT])
        )

        with self.mutex:
            try:
                self.ser.write(msg)

            except SerialException as err:
                raise BoardCommsError(err)
            except AttributeError as err:
                raise BoardCommsError(err)

    def reset_calibration(self) -> None:
        raw_header = struct.pack("<BB", SERIAL_RESET_KVSTORE, 0)
        self.send_command(raw_header, b"")

    def set_output_mode(self, mode: int) -> None:
        raw_header = struct.pack("<BB", mode, 1)
        raw_body = struct.pack("<f", float(mode))

        try:
            self.send_command(raw_header, raw_body)
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
        # response_size = struct.calcsize(response_format)
        calib = [0, 0, 0, 1, 1, 1]

        try:
            # cmd_0 = struct.pack("<BB", SERIAL_PRINT_NOTHING, 2)
            # self.ser.reset_output_buffer()
            # self.ser.reset_input_buffer()
            cmd_1 = struct.pack("<BB", calibration_type, 2)
            # self.send_command_bytes(cmd_0 + b";" + cmd_1 + b";")
            self.send_command_bytes(cmd_1 + b";")

            for i in range(5):
                response = self.ser.read_until(";".encode("UTF-8"))
                # response = self.ser.readline()
                log.info(f"Response from board: {response}")
                # time.sleep(0.5) # Why is this here?

                try:
                    cmd_id, n_bytes, *calib = struct.unpack(
                        response_format,
                        response.strip(b";").strip(b"\n").strip(b"\r"),
                        # TODO: Should use readline so we don't have to guard againts extra LFCR
                    )
                    log.info(f"Response unpacked: {cmd_id}, {n_bytes}, {calib}")
                    if cmd_id != calibration_type:
                        raise BoardCommsError(
                            f"Received cmd_id 0x{cmd_id:02x} does not match the requested type 0x{calibration_type:02x}"
                        )

                    return calib

                except (struct.error, BoardCommsError) as err:
                    log.warning(
                        f"Try number {i}: response from board {response} create error: {err}"
                    )

            log.error("Did not receive proper response after 5 tries")
            raise BoardCommsError("Did not receive proper response after 5 tries")

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
            self.ser.reset_input_buffer()
            log.info(
                f"Sending to board: {calibration_type:02x}, {command_size}, {data}"
            )

            cmd = struct.pack(command_format, calibration_type, command_size, *data[:6])
            self.send_command_bytes(cmd + b";")
            log.info(f"Send command: {cmd + b';'}")

            s = self.ser.readline()
            log.info(f"Set calibration reply from board: {s}")

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

    @staticmethod
    def parse_outbound_bytes(d: bytes) -> bytes:
        """
        Prepend all ASCII transmission control characters with escape byte.
        """
        res = copy.deepcopy(d)  # Is this necessary?

        # NOTE: ASCII_ESC must be first in list or we replace all the escapes
        # created by escaping other control characters. This is fragile...
        for c in (ASCII_ESC, ASCII_SOH, ASCII_STX, ASCII_ETX, ASCII_EOT, ASCII_NUL):
            res = res.replace(bytes([c]), bytes([ASCII_ESC, c + ESCAPE_OFFSET]))

        return res

    @staticmethod
    def parse_inbound_bytes(d: bytes) -> bytes:
        """
        Remove all ASCII_ESC characters and restore the following character.
        """

        res = copy.deepcopy(d)
        while True:
            i = res.find(bytes([ASCII_ESC]))

            if i == -1:
                return res
            else:
                c_esc = res[i + 1]
                c_real = c_esc - ESCAPE_OFFSET
                res = res.replace(bytes([ASCII_ESC, c_esc]), bytes([c_real]))
