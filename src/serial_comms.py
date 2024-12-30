import time
import unicodedata
import numpy as np

from serial import Serial, SerialException
from dataclasses import dataclass

# Event and Queue are imported only for type hinting
from threading import Event, Lock
from queue import Queue

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


@dataclass
class SerialComms:
    serial_port: str = "/dev/ttyACM0"
    serial_baudrate: int = 57600
    serial_timeout: float = 2.0
    command_log: Queue = None
    output_log: Queue = None

    handshake_timeout: float = 5.0

    mutex: Lock = Lock()
    ser: Serial = None

    # TODO: Lots of repeating try... with Serial... except SerialException...
    #       Maybe refactor that to it's own function.

    def send_command(self, command_id: int) -> None:
        """
        Send a command to the board.
        """
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
                self.logStd("Serial error: {}".format(err), self.command_log)

    def reset_calibration(self) -> None:
        self.send_command(SERIAL_RESET_KVSTORE)

    def wait_for_board_response(self) -> bool:
        timeout = time.time() + self.handshake_timeout
        while (data := self.ser.readline()) == SERIAL_NO_OUTPUT:
            if time.time() > timeout:
                self.logStd("Timeout waiting for board response.\n", self.command_log)
                return False, str()
            else:
                continue

        self.logStd(data.decode("utf8"), self.output_log)
        return True, data.decode("utf8")

    def get_calibration(self, calibration_type: int) -> list[float]:
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
                self.logStd("Serial error: {}\n".format(err), self.command_log)
            finally:
                self.logStd("Done.\n", self.command_log)

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
                self.logStd("Serial error: {}\n".format(err))
            finally:
                self.logStd("Done.\n", self.command_log)

    def read_magnetic_calibration_data(
        self, sample_size: int, stop_event: Event = None
    ) -> np.ndarray:
        """
        Read uncalibrated magnetometer data from the board.

        IN: sample_size: How many data points to read.
            stop_event: threading.Event -object. Set 'stop_event.set()'
                        to abort the data reading.

        OUT: numpy.ndarray of size (3, sample_size) with X, Y, Z values
             in [0], [1], [2] positions respectively.
        """
        array_shape = (sample_size, 3)
        data = np.zeros(array_shape, dtype=float)
        command_str = self.parse_command_string(SERIAL_PRINT_MAG_RAW)

        try:
            with Serial(
                self.serial_port,
                timeout=self.serial_timeout,
                baudrate=self.serial_baudrate,
            ) as self.ser:
                success = self.send_command_string(command_str)
                if not success:
                    return data.transpose()

                _ = self.ser.readline()  # Discard first read.
                for i in range(sample_size):
                    raw = self.ser.readline().decode("utf8")
                    self.logStd(raw, self.output_log)

                    try:
                        data[i] = [float(d) for d in raw.split(sep=",")]
                    except ValueError:  # if no data was received.
                        data[i] = [0, 0, 0]

                    try:
                        if stop_event.isSet():
                            self.logStd("Data read aborted.", self.command_log)
                            break
                    except AttributeError:  # if stop_event doesn't have 'is_set'.
                        pass
        except SerialException as err:
            self.logStd("Serial error: {}".format(err), self.command_log)

        return data.transpose()

    def send_command_string(self, command: str) -> bool:
        """
        Send a command to the board.

        NOTE: The serial object 'self.ser' has to be opened before using this function.
        """
        if not self.serial_handshake():
            self.logStd("Handshake with board failed.\n", self.command_log)
            return False

        self.logStd("Handshake with board successful.\n", self.command_log)
        self.logStd("Sending command: " + command + "\n", self.command_log)
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

    def read_output_until_done():
        """
        Read serial output until SERIAL_DONE is received.
        """
        pass

    @staticmethod
    def logStd(line: str, log: Queue) -> None:
        """
        Send string to log.
        """
        try:
            log.put(line)
        except AttributeError:
            print(line)

    @staticmethod
    def remove_control_characters(input: str) -> str:
        try:
            return "".join(
                char for char in input if unicodedata.category(char)[0] != "C"
            )
        except TypeError:
            return ""

    @staticmethod
    def parse_command_string(command: int, data: list[int] = []) -> str:
        command_str = "0x{:02x}; ".format(command)
        for item in data:
            command_str += "{}, ".format(item)
        command_str += "; "

        return command_str
