import unittest
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

        res = np.array([1, 2, 3, 3.741657]).reshape(1, 4)
        self.model.append_data(np.array([1, 2, 3]))

        try:
            np.testing.assert_array_almost_equal(self.model._data, res)
            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_append_data_multiple(self) -> None:
        print("test_append_data_multiple")
        res = np.array([1, 2, 3, 3.741657, 10, 20, 30, 37.41657386]).reshape(2, 4)
        self.model.append_data(np.array([1, 2, 3]))
        self.model.append_data(np.array([10, 20, 30]))

        try:
            np.testing.assert_array_almost_equal(self.model._data, res)
            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_get_xyz_data(self) -> None: ...
