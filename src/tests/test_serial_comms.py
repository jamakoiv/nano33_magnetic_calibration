import unittest
import numpy as np

from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication

from serial_comms import Board2GUI, Nano33SerialComms, TestSerialComms


class test_Board2GUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication()
        return super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.app.quit()
        del cls.app

        return super().tearDownClass()

    def setUp(self) -> None:
        self.board = TestSerialComms(random_seed=0xABCD)
        self.board_comms = Board2GUI()
        self.board_comms.set_board(self.board)
        self.board_comms.read_sample_size = 10

        self.correct_magnetic_calibration = np.array(
            [
                32.92342533,
                28.29592604,
                10.76117538,
                11.63470385,
                18.84903367,
                6.45735546,
            ]
        )
        self.correct_accelerometer_calibration = np.array(
            [0.98326345, 0.22859553, 0.91280166, 0.84211096, 0.0967116, 0.36238348]
        )
        self.correct_gyroscope_calibration = np.array(
            [0.80242609, 0.51806079, 0.21262697, 0.92620838, 0.30832967, 0.1353237]
        )

        return super().setUp()

    def tearDown(self) -> None:
        del self.board_comms
        del self.board

        return super().tearDown()

    def test_read_magnetic_calibration_data(self) -> None:
        spy = QSignalSpy(self.board_comms.data_row_received)
        self.assertTrue(spy.isValid())

        self.board_comms.read_magnetic_calibration_data()
        self.assertEqual(spy.count(), self.board_comms.read_sample_size)

        data = np.array([])
        for i in range(self.board_comms.read_sample_size):
            data = np.append(data, spy.at(i)[0])

        self.assertEqual(data.shape, (self.board_comms.read_sample_size * 3,))

    def test_read_magnetic_calibration_data_exceptions(self) -> None:
        self.board_comms.board = None  # pyright: ignore

    def test_get_calibration(self) -> None:
        spy = QSignalSpy(self.board_comms.calibration_received)
        self.assertTrue(spy.isValid())

        self.board_comms.get_calibration("magnetometer")
        self.assertEqual(spy.count(), 1)
        id, offset, gain = spy.at(0)[0]

        self.assertEqual(id, "magnetometer")
        try:
            np.testing.assert_array_almost_equal(
                np.concat((offset, gain)), self.correct_magnetic_calibration
            )
            self.assertTrue(True)
        except AttributeError:
            self.assertTrue(False)

        self.board_comms.get_calibration("accelerometer")
        self.assertEqual(spy.count(), 2)
        id, offset, gain = spy.at(1)[0]

        self.assertEqual(id, "accelerometer")
        try:
            np.testing.assert_array_almost_equal(
                np.concat((offset, gain)), self.correct_accelerometer_calibration
            )
            self.assertTrue(True)
        except AttributeError:
            self.assertTrue(False)

        self.board_comms.get_calibration("gyroscope")
        self.assertEqual(spy.count(), 3)
        id, offset, gain = spy.at(2)[0]

        self.assertEqual(id, "gyroscope")
        try:
            np.testing.assert_array_almost_equal(
                np.concat((offset, gain)), self.correct_gyroscope_calibration
            )
            self.assertTrue(True)
        except AttributeError:
            self.assertTrue(False)

    def test_set_calibration(self) -> None: ...


class test_Nano33SerialComms(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication()
        return super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.app.quit()
        del cls.app

        return super().tearDownClass()

    def test_parse_outbound_bytes(self) -> None:
        msg = b"abcd\x01abcd\x02abcd\x03abcd\x04"
        correct = b"abcd\x1b\x21abcd\x1b\x22abcd\x1b\x23abcd\x1b\x24"
        res = Nano33SerialComms.parse_outbound_bytes(msg)

        self.assertEqual(res, correct)

    def test_parse_inbound_bytes(self) -> None:
        msg = b"abcd\x1b\x21abcd\x1b\x22abcd\x1b\x23abcd\x1b\x24"
        correct = b"abcd\x01abcd\x02abcd\x03abcd\x04"
        res = Nano33SerialComms.parse_inbound_bytes(msg)

        self.assertEqual(res, correct)
