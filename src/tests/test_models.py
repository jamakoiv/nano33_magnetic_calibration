import unittest
import numpy as np

from collections import OrderedDict
from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication

from models import CalibrationDataModel, SerialPortsModel


class test_calibrationDataModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication()

        return super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.app.quit()

        return super().tearDownClass()

    def setUp(self) -> None:
        self.model = CalibrationDataModel(parent=None)

        return super().setUp()

    def tearDown(self) -> None:
        del self.model

        return super().tearDown()

    def test_set_data(self) -> None:
        data = np.arange(10 * 3).reshape(10, 3)
        self.model.set_data(data)
        self.assertTrue((self.model._data == data).all())

    def test_append_data_single(self) -> None:
        correct = np.array([1, 2, 3, 3.741657]).reshape(1, 4)
        self.model.append_data(np.array([1, 2, 3]))

        try:
            np.testing.assert_array_almost_equal(self.model._data, correct)
            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_append_data_multiple(self) -> None:
        correct = np.array([1, 2, 3, 3.741657, 10, 20, 30, 37.41657386]).reshape(2, 4)
        self.model.append_data(np.array([1, 2, 3]))
        self.model.append_data(np.array([10, 20, 30]))

        try:
            np.testing.assert_array_almost_equal(self.model._data, correct)
            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_get_xyz_data(self) -> None:
        self.model.append_data(np.array([1, 2, 3]))
        self.model.append_data(np.array([10, 20, 30]))

        x, y, z = self.model.get_xyz_data()
        try:
            np.testing.assert_array_equal(x, np.array([1, 10]))
            np.testing.assert_array_equal(y, np.array([2, 20]))
            np.testing.assert_array_equal(z, np.array([3, 30]))
            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_rowCount(self) -> None:
        self.model.append_data(np.array([1, 2, 3]))
        self.model.append_data(np.array([10, 20, 30]))
        self.model.append_data(np.array([100, 200, 300]))

        self.assertEqual(self.model.rowCount(), 3)

    def test_columnCount(self) -> None:
        self.model.append_data(np.array([1, 2, 3]))

        self.assertEqual(self.model.columnCount(), 4)

    def test_data(self) -> None:
        self.model.append_data(np.array([1, 2, 3]))
        self.model.append_data(np.array([10, 20, 30]))

        correct = self.model.data(
            self.model.createIndex(0, 1), Qt.ItemDataRole.DisplayRole
        )

        self.assertEqual(float(correct), 2)  # pyright: ignore

        correct = self.model.data(
            self.model.createIndex(1, 2), Qt.ItemDataRole.DisplayRole
        )

        self.assertEqual(float(correct), 30)  # pyright: ignore

    def test_insert_row_signal(self) -> None:
        spy = QSignalSpy(self.model.rowsInserted)
        self.assertTrue(spy.isValid())
        self.model.append_data(np.array([1, 2, 3]))
        self.model.append_data(np.array([10, 20, 30]))
        self.assertEqual(spy.count(), 2)

    def test_remove_row_signal(self) -> None:
        spy = QSignalSpy(self.model.rowsRemoved)
        self.assertTrue(spy.isValid())
        self.model.append_data(np.array([1, 2, 3]))
        self.model.append_data(np.array([10, 20, 30]))
        self.model.removeRows(0, 2)

        self.assertEqual(spy.count(), 1)


class test_SerialPortsModel(unittest.TestCase):
    def setUp(self) -> None:
        self.model = SerialPortsModel()

        self.test_ports = OrderedDict()
        self.test_ports["/dev/ttyACM1"] = "TestBoard ABC123"
        self.test_ports["/dev/tty10"] = ""

        return super().setUp()

    def tearDown(self) -> None:
        del self.model

        return super().tearDown()

    def test_set_ports(self) -> None:
        self.model.set_ports(self.test_ports)

        self.assertEqual(self.model.ports, self.test_ports)

    def test_rowCount(self) -> None:
        self.model.set_ports(self.test_ports)

        self.assertEqual(self.model.rowCount(), 2)

    def test_data(self) -> None:
        self.model.set_ports(self.test_ports)

        index = self.model.createIndex(0, 0)
        correct_displayrole = "/dev/ttyACM1 - TestBoard ABC123"
        correct_userrole = "/dev/ttyACM1"

        self.assertEqual(
            self.model.data(index, role=Qt.ItemDataRole.DisplayRole),
            correct_displayrole,
        )
        self.assertEqual(
            self.model.data(index, role=Qt.ItemDataRole.UserRole), correct_userrole
        )

    def test_modelReset_signal(self) -> None:
        spy = QSignalSpy(self.model.modelReset)

        print(spy.count())
        self.assertTrue(spy.isValid())
        self.model.set_ports(self.test_ports)
        self.assertEqual(spy.count(), 1)
