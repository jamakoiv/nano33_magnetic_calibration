import unittest
import numpy as np

from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication

from ..widgets import CalibrationFormWidget, DeviceSelectWidget


class test_DeviceSelectWidget(unittest.TestCase):
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
        self.widget = DeviceSelectWidget()

        return super().setUp()

    def tearDown(self) -> None:
        del self.widget

        return super().tearDown()

    def test_data_points_default_value(self) -> None:
        self.assertEqual(self.widget.data_points.value(), 20)

    def test_data_points_default_step(self) -> None:
        self.widget.data_points.stepUp()
        self.assertEqual(self.widget.data_points.value(), 30)

    def test_data_points_range(self) -> None:
        self.widget.data_points.stepBy(10000)
        self.assertEqual(self.widget.data_points.value(), 500)

        self.widget.data_points.stepBy(-20000)
        self.assertEqual(self.widget.data_points.value(), 10)

    def test_refresh_serial_ports(self) -> None:
        # TODO: Only tests that the debug-entry exists.
        # Others hard to test since the serial port names are OS-specific.

        QTest.mouseClick(self.widget.scan_devices_button, Qt.MouseButton.LeftButton)
        self.assertIn("debug", self.widget.serial_ports_model.ports)


class test_CalibrationFormWidget(unittest.TestCase):
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
        self.widget = CalibrationFormWidget()

        self.widget.x_gain.setText("12.3")
        self.widget.y_gain.setText("45.6")
        self.widget.z_gain.setText("78.9")
        self.widget.x_offset.setText("55.5")
        self.widget.y_offset.setText("66.6")
        self.widget.z_offset.setText("77.7")

        return super().setUp()

    def tearDown(self) -> None:
        del self.widget

        return super().tearDown()

    def test_validator(self) -> None:
        for edit in [
            self.widget.x_gain,
            self.widget.y_gain,
            self.widget.z_gain,
            self.widget.x_offset,
            self.widget.y_offset,
            self.widget.z_offset,
        ]:
            edit.setText("")
            QTest.keyClicks(edit, "123456")
            self.assertEqual(edit.text(), "123")

            edit.setText("")
            QTest.keyClicks(edit, "123.456")
            self.assertEqual(edit.text(), "123.45")

    def test_get_gain(self) -> None:
        correct = np.array([12.3, 45.6, 78.9])

        try:
            np.testing.assert_array_almost_equal(self.widget.get_gain(), correct)
            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_get_offset(self) -> None:
        correct = np.array([55.5, 66.6, 77.7])

        try:
            np.testing.assert_array_almost_equal(self.widget.get_offset(), correct)
            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)
