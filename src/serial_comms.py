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

SERIAL_MISC_SET_SETTINGS = 0x60
SERIAL_MISC_GET_SETTINGS = 0x61

SERIAL_RESET_KVSTORE = 0x75

# Valid print modes.
SERIAL_PRINT_NOTHING = 0x15
SERIAL_PRINT_AHRS = 0x16
SERIAL_PRINT_AHRS_DEBUG = 0x17

SERIAL_PRINT_MAG_ACC_GYRO_RAW = 0x20
SERIAL_PRINT_MAG_ACC_GYRO_CALIB = 0x21

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
ASCII_LF = 0x0A
ASCII_CR = 0x0D
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

    def get_magnetometer_calibration(self) -> tuple[np.ndarray, np.ndarray]: ...

    def set_magnetometer_calibration(
        self, soft_iron: np.ndarray, hard_iron: np.ndarray
    ) -> None: ...

    def get_accelerometer_calibration(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...

    def set_accelerometer_calibration(
        self, misalignment: np.ndarray, sensitivity: np.ndarray, offset: np.ndarray
    ) -> None: ...

    def get_gyroscope_calibration(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...

    def set_gyroscope_calibration(
        self, misalignment: np.ndarray, sensitivity: np.ndarray, offset: np.ndarray
    ) -> None: ...

    def get_misc_settings(self) -> tuple[np.ndarray, np.ndarray]: ...

    def set_misc_settings(self, output_offset, ahrs_settings) -> None: ...

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
    calibration_received = Signal(str, object)
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
            time.sleep(0.20)

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
                    soft_iron, hard_iron = self.board.get_magnetometer_calibration()
                    res = (soft_iron, hard_iron)

                case "gyroscope":
                    id = "gyroscope"
                    misalignment, sensitivity, offset = (
                        self.board.get_gyroscope_calibration()
                    )
                    res = (misalignment, sensitivity, offset)

                case "accelerometer":
                    id = "accelerometer"
                    misalignment, sensitivity, offset = (
                        self.board.get_accelerometer_calibration()
                    )
                    res = (misalignment, sensitivity, offset)

                case "misc":
                    id = "misc"
                    output_offset, ahrs_settings = self.board.get_misc_settings()
                    res = (output_offset, ahrs_settings)

                case _:
                    self.to_log.emit("Wrong calibration type supplied")
                    raise ValueError("Wrong calibration type supplied")

            self.calibration_received.emit(id, res)
            # self.to_log.emit(
            #     f"Received calibration data: {calibration_type}, offset {offset}, gain {gain}"
            # )

        finally:
            with self.mutex:
                self.task_running = False

            self.task_done.emit()
            self.board.close()
            self.to_log.emit("Done reading calibration.")

    @Slot(str, object, object)  # pyright: ignore
    def set_calibration(
        self, calibration_type: str, data: tuple[np.ndarray, ...]
    ) -> None:
        try:
            self.to_log.emit("Start setting calibration to board.")
            log.info(f"Start setting calibration to board: {calibration_type}")
            self.board.open()

            with self.mutex:
                self.task_running = True

            match calibration_type.lower():
                case "magnetometer" | "magnetic":
                    soft_iron, hard_iron = data
                    self.board.set_magnetometer_calibration(soft_iron, hard_iron)

                case "gyroscope":
                    misalignment, sensitivity, offset = data
                    self.board.set_gyroscope_calibration(
                        misalignment, sensitivity, offset
                    )

                case "accelerometer":
                    misalignment, sensitivity, offset = data
                    self.board.set_accelerometer_calibration(
                        misalignment, sensitivity, offset
                    )

                case "misc":
                    output_offset, ahrs_settings = data
                    self.board.set_misc_settings(output_offset, ahrs_settings)

                case _:
                    raise ValueError("Wrong calibration type supplied")

        finally:
            with self.mutex:
                self.task_running = False

            self.task_done.emit()
            self.board.close()

            msg = f"Set calibration data: {calibration_type}, offset , gain "
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

        self.magnetic_soft_iron = self.rng.random((3, 3)) * 40
        self.magnetic_hard_iron = self.rng.random(3) * 10

        self.accelerometer_misalignment = self.rng.random((3, 3))
        self.accelerometer_sensitivity = self.rng.random(3)
        self.accelerometer_offset = self.rng.random(3)

        self.gyroscope_misalignment = self.rng.random((3, 3))
        self.gyroscope_sensitivity = self.rng.random(3)
        self.gyroscope_offset = self.rng.random(3)

        self.magnetic_data = makeEllipsoidXYZ(
            20, 15, -12, 40, 35, 50, N=20, noise_scale=1, generator=self.rng
        )

    def open(self) -> None: ...

    def close(self) -> None: ...

    def reset_calibration(self) -> None: ...

    def set_output_mode(self, mode: int) -> None:
        pass

    def get_magnetometer_calibration(self) -> tuple[np.ndarray, np.ndarray]:
        return (self.magnetic_soft_iron, self.magnetic_hard_iron)

    def get_accelerometer_calibration(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return (
            self.accelerometer_misalignment,
            self.accelerometer_sensitivity,
            self.accelerometer_offset,
        )

    def get_gyroscope_calibration(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return (
            self.gyroscope_misalignment,
            self.gyroscope_sensitivity,
            self.gyroscope_offset,
        )

    def set_magnetometer_calibration(
        self, soft_iron: np.ndarray, hard_iron: np.ndarray
    ) -> None:
        self.magnetic_soft_iron = soft_iron
        self.magnetic_hard_iron = hard_iron

    def set_accelerometer_calibration(
        self, misalignment: np.ndarray, sensitivity: np.ndarray, offset: np.ndarray
    ) -> None:
        self.accelerometer_misalignment = misalignment
        self.accelerometer_sensitivity = sensitivity
        self.accelerometer_offset = offset

    def set_gyroscope_calibration(
        self, misalignment: np.ndarray, sensitivity: np.ndarray, offset: np.ndarray
    ) -> None:
        self.gyroscope_misalignment = misalignment
        self.gyroscope_sensitivity = sensitivity
        self.gyroscope_offset = offset

    def read_row(self) -> np.ndarray:
        time.sleep(0.05)
        idx = np.random.randint(0, self.magnetic_data.shape[1])

        mag = self.magnetic_data.transpose()[idx]
        acc = np.zeros(3)
        gyro = np.zeros(3)

        return np.concat([mag, acc, gyro])


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
        timeout: float = 3.0,
    ):
        super().__init__()

        self.serial_port = port
        self.serial_baudrate = baudrate
        self.serial_timeout = timeout

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
        raw_header = struct.pack("<BB", SERIAL_SET_PRINT_MODE, 1)
        raw_body = struct.pack("<f", float(mode))

        try:
            self.send_command(raw_header, raw_body)
        except SerialException as e:
            raise BoardCommsError(e)

    def calibration_reply_helper(self, struct_format: str) -> np.ndarray:
        """
        Helper function to handle read retries when receiving the calibration values from the board.
        """
        retry_number = 0
        reply = ""
        while retry_number != 30:
            try:
                reply = self.ser.readline()
                print(reply)
                _, reply_body = self.retrieve_header_and_body(reply)
                params = struct.unpack(struct_format, reply_body)
                # assert reply_header[1] == len(params)

                return np.array(params)

            except BoardCommsError as err:
                log.info(f"Reply from board {reply} created error {err}")
                retry_number += 1

            except struct.error as err:
                log.info(f"Unpacking failed with error {err}")
                retry_number += 1
        else:
            raise BoardCommsError(
                "Could not extract calibration values from any board response."
            )

    def get_magnetometer_calibration(self) -> tuple[np.ndarray, np.ndarray]:
        raw_header = struct.pack("<BB", SERIAL_MAG_GET_CALIB, 0)
        mag_struct_format = "<ffffffffffff"  # 3x3 matrix + xyz vector = 12 floats

        self.send_command(raw_header, b"")
        self.ser.reset_input_buffer()

        try:
            params = self.calibration_reply_helper(mag_struct_format)
            soft_iron = np.array(params[:9])
            soft_iron.resize(3, 3)
            # soft_iron = np.linalg.inv(soft_iron)
            hard_iron = np.array(params[9:])

        except BoardCommsError as err:
            log.info(f"Error receiving calibration values: {err}")

            soft_iron = np.array([[-1, -1, -1], [-1, -1, -1], [-1, -1, -1]])
            hard_iron = np.array([-1, -1, -1])

        return soft_iron, hard_iron

    def set_magnetometer_calibration(
        self, soft_iron: np.ndarray, hard_iron: np.ndarray
    ) -> None:
        raw_header = struct.pack("<BB", SERIAL_MAG_SET_CALIB, 9 + 3)

        # soft_iron = np.linalg.inv(soft_iron)
        raw_body = struct.pack("<ffffffffffff", *soft_iron.flatten(), *hard_iron)

        self.send_command(raw_header, raw_body)
        self.ser.reset_input_buffer()
        reply = self.ser.readline()
        log.info(f"Reply from board: {reply}")

    def get_accelerometer_calibration(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        raw_header = struct.pack("<BB", SERIAL_ACC_GET_CALIB, 0)
        acc_struct_format = "<fffffffffffffff"  # 3x3 matrix + 2 xyz-vectors = 15 floats

        self.send_command(raw_header, b"")
        self.ser.reset_input_buffer()

        try:
            params = self.calibration_reply_helper(acc_struct_format)
            misalignment = np.array(params[:9])
            misalignment.resize(3, 3)
            sensitivity = np.array(params[9:12])
            offset = np.array(params[12:15])

        except BoardCommsError as err:
            log.info(f"Error receiving calibration values: {err}")

            misalignment = np.array([[-1, -1, -1], [-1, -1, -1], [-1, -1, -1]])
            sensitivity = np.array([-1, -1, -1])
            offset = np.array([-1, -1, -1])

        return misalignment, sensitivity, offset

    def set_accelerometer_calibration(
        self, misalignment: np.ndarray, sensitivity: np.ndarray, offset: np.ndarray
    ) -> None:
        acc_struct_format = "<fffffffffffffff"  # 3x3 matrix + 2 xyz-vectors = 15 floats

        raw_header = struct.pack(
            "<BB", SERIAL_ACC_SET_CALIB, len(acc_struct_format) - 1
        )
        raw_body = struct.pack(
            acc_struct_format,
            *misalignment.flatten(),
            *sensitivity.flatten(),
            *offset.flatten(),
        )

        self.send_command(raw_header, raw_body)
        self.ser.reset_input_buffer()
        reply = self.ser.readline()
        log.info(f"Reply from board: {reply}")

    def get_gyroscope_calibration(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        raw_header = struct.pack("<BB", SERIAL_GYRO_GET_CALIB, 0)
        gyro_struct_format = (
            "<fffffffffffffff"  # 3x3 matrix + 2 xyz-vectors = 15 floats
        )

        self.send_command(raw_header, b"")
        self.ser.reset_input_buffer()

        try:
            params = self.calibration_reply_helper(gyro_struct_format)
            misalignment = np.array(params[:9])
            misalignment.resize(3, 3)
            sensitivity = np.array(params[9:12])
            offset = np.array(params[12:15])

        except BoardCommsError as err:
            log.info(f"Error receiving calibration values: {err}")

            misalignment = np.array([[-1, -1, -1], [-1, -1, -1], [-1, -1, -1]])
            sensitivity = np.array([-1, -1, -1])
            offset = np.array([-1, -1, -1])

        return misalignment, sensitivity, offset

    def set_gyroscope_calibration(
        self, misalignment: np.ndarray, sensitivity: np.ndarray, offset: np.ndarray
    ) -> None:
        gyro_struct_format = (
            "<fffffffffffffff"  # 3x3 matrix + 2 xyz-vectors = 15 floats
        )

        raw_header = struct.pack(
            "<BB", SERIAL_GYRO_SET_CALIB, len(gyro_struct_format) - 1
        )
        raw_body = struct.pack(
            gyro_struct_format,
            *misalignment.flatten(),
            *sensitivity.flatten(),
            *offset.flatten(),
        )

        self.send_command(raw_header, raw_body)
        self.ser.reset_input_buffer()
        reply = self.ser.readline()
        log.info(f"Reply from board: {reply}")

    def set_misc_settings(
        self, output_offset: np.ndarray, ahrs_settings: np.ndarray
    ) -> None:
        misc_struct_format = "<fffffff"  # xyz vector + 4 floats
        raw_header = struct.pack(
            "<BB", SERIAL_MISC_SET_SETTINGS, len(misc_struct_format) - 1
        )
        raw_body = struct.pack(
            misc_struct_format, *output_offset.flatten(), *ahrs_settings.flatten()
        )

        self.send_command(raw_header, raw_body)
        self.ser.reset_input_buffer()
        reply = self.ser.readline()
        log.info(f"Reply from board: {reply}")

    def get_misc_settings(
        self,
    ) -> tuple[np.ndarray, np.ndarray]:
        raw_header = struct.pack("<BB", SERIAL_MISC_GET_SETTINGS, 0)
        misc_struct_format = "<fffffff"  # xyz vector + 4 floats

        self.send_command(raw_header, b"")
        self.ser.reset_input_buffer()

        try:
            params = self.calibration_reply_helper(misc_struct_format)
            output_offset = params[:3]
            ahrs_settings = params[3:7]

        except BoardCommsError as err:
            log.info(f"Error receiving calibration values: {err}")

            output_offset = np.array([-1, -1, -1])
            ahrs_settings = np.array([-1, -1, -1, -1])

        return output_offset, ahrs_settings

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
            # TODO: Log error if ser does not exist.
            pass

    def read_row(self) -> np.ndarray:
        # Flush everything so we get the newest measurement value.
        self.ser.reset_input_buffer()

        stop_byte = "\n".encode("ASCII")
        raw = self.ser.read_until(stop_byte).decode("utf8")
        log.info(f"Received data: {raw}")

        try:
            str_floats = raw.split(sep=",")[:3]
            log.info(f"Split data: {str_floats}")
            row = np.array([float(d) for d in str_floats])
        except ValueError:  # if no data was received.
            raise NoDataReceived()

        return row.reshape(1, 3)

    @staticmethod
    def parse_outbound_bytes(d: bytes) -> bytes:
        """
        Prepend all ASCII transmission control characters with escape byte
        and offset the character with ESCAPE_OFFSET.
        """
        res = copy.deepcopy(d)  # Is this necessary?

        # NOTE: ASCII_ESC must be first in list or we replace all the escapes
        # created by escaping other control characters. This is fragile...
        for c in (
            ASCII_ESC,
            ASCII_SOH,
            ASCII_STX,
            ASCII_ETX,
            ASCII_EOT,
            ASCII_NUL,
            ASCII_CR,
            ASCII_LF,
        ):
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

    @staticmethod
    def retrieve_header_and_body(d: bytes, raw: bool = False) -> tuple[bytes, bytes]:
        """
        Split the received data into header and body.
        """
        try:
            i_soh = d.index(bytes([ASCII_SOH]))
            i_stx = d.index(bytes([ASCII_STX]))
            i_etx = d.index(bytes([ASCII_ETX]))
            i_eot = d.index(bytes([ASCII_EOT]))

            if not (i_soh < i_stx < i_etx < i_eot):
                raise BoardCommsError("Received data has invalid format")

            raw_header = d[i_soh + 1 : i_stx]
            raw_body = d[i_stx + 1 : i_etx]

            if raw:
                header = raw_header
                body = raw_body
            else:
                header = Nano33SerialComms.parse_inbound_bytes(raw_header)
                body = Nano33SerialComms.parse_inbound_bytes(raw_body)

            return header, body

        except ValueError as e:
            raise BoardCommsError(f"Received data has invalid format: {e}")
