import unittest
import numpy as np

from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication

from widgets import DeviceSelectWidget


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
