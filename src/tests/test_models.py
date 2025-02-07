import unittest
from PySide6.QtCore import QAbstractItemModel, Qt
import numpy as np

from PySide6.QtWidgets import QApplication

from ..models import CalibrationDataModel, SerialPortsModel


class test_calibration_data_model(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        print("setUpClass")
        cls.app = QApplication.instance() or QApplication()

        return super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        print("tearDownClass")
        cls.app.quit()

        return super().tearDownClass()

    def setUp(self) -> None:
        print("setUp")
        self.model = CalibrationDataModel(parent=None)

        return super().setUp()

    def tearDown(self) -> None:
        print("tearDown")
        del self.model

        return super().tearDown()

    def test_set_data(self) -> None:
        print("test_set_data")

        data = np.arange(10 * 3).reshape(10, 3)
        self.model.set_data(data)
        self.assertTrue((self.model._data == data).all())

    def test_append_data_single(self) -> None:
        print("test_append_data")

        correct = np.array([1, 2, 3, 3.741657]).reshape(1, 4)
        self.model.append_data(np.array([1, 2, 3]))

        try:
            np.testing.assert_array_almost_equal(self.model._data, correct)
            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_append_data_multiple(self) -> None:
        print("test_append_data_multiple")
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
