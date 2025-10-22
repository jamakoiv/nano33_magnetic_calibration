import unittest
import numpy as np

from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication

from widgets import (
    DeviceSelectWidget,
    CalibrationVectorWidget,
    CalibrationMatrixWidget,
    CalibrationMiscWidget,
)


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


class test_CalibrationVectorWidget(unittest.TestCase):
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
        self.widget = CalibrationVectorWidget()

        return super().setUp()

    def tearDown(self) -> None:
        del self.widget

        return super().tearDown()

    def test_get(self) -> None:
        correct = np.array([11.1, 22.2, 33.3])
        self.widget.x_edit.setText("11.1")
        self.widget.y_edit.setText("22.2")
        self.widget.z_edit.setText("33.3")

        np.testing.assert_allclose(self.widget.get(), correct)

    def test_set(self) -> None:
        self.widget.set(np.array([11.1, 22.2, 33.3]))

        self.assertEqual(self.widget.x_edit.text(), "11.1")
        self.assertEqual(self.widget.y_edit.text(), "22.2")
        self.assertEqual(self.widget.z_edit.text(), "33.3")

    def test_validator(self) -> None:
        correct = np.array([999, -999, 1.1234])
        self.widget.set(np.array([10000, -10000, 1.123456789]))
        np.testing.assert_allclose(self.widget.get(), correct)


class test_CalibrationMatrixWidget(unittest.TestCase):
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
        self.widget = CalibrationMatrixWidget()

        return super().setUp()

    def tearDown(self) -> None:
        del self.widget

        return super().tearDown()

    def test_get(self) -> None:
        correct = np.array([11, 22, 33, 44, 55, 66, 77, 88, 99]).reshape(3, 3)

        self.widget.xx_edit.setText("11.00")
        self.widget.xy_edit.setText("22.00")
        self.widget.xz_edit.setText("33.00")
        self.widget.yx_edit.setText("44.00")
        self.widget.yy_edit.setText("55.00")
        self.widget.yz_edit.setText("66.00")
        self.widget.zx_edit.setText("77.00")
        self.widget.zy_edit.setText("88.00")
        self.widget.zz_edit.setText("99.00")

        np.testing.assert_allclose(self.widget.get(), correct)

    def test_set(self) -> None:
        self.widget.set(
            np.array([11.1, 22.2, 33.3, 44.4, 55.5, 66.6, 77.7, 88.8, 99.9])
        )

        self.assertEqual(self.widget.xx_edit.text(), "11.1")
        self.assertEqual(self.widget.xy_edit.text(), "22.2")
        self.assertEqual(self.widget.xz_edit.text(), "33.3")
        self.assertEqual(self.widget.yx_edit.text(), "44.4")
        self.assertEqual(self.widget.yy_edit.text(), "55.5")
        self.assertEqual(self.widget.yz_edit.text(), "66.6")
        self.assertEqual(self.widget.zx_edit.text(), "77.7")
        self.assertEqual(self.widget.zy_edit.text(), "88.8")
        self.assertEqual(self.widget.zz_edit.text(), "99.9")

    def test_validator(self) -> None:
        correct = np.array(
            [999, 999, 999, -999, -999, -999, 1.1234, 1.1234, 1.1234]
        ).reshape(3, 3)

        self.widget.set(
            np.array(
                [
                    10000,
                    10000,
                    10000,
                    -10000,
                    -10000,
                    -10000,
                    1.123456789,
                    1.123456789,
                    1.123456789,
                ]
            )
        )
        np.testing.assert_allclose(self.widget.get(), correct)
