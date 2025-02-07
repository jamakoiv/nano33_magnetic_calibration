import unittest
import numpy as np

from PySide6.QtWidgets import QApplication

from ..models import CalibrationDataModel, SerialPortsModel


class test_calibration_data_model(unittest.TestCase):
    def setUp(self) -> None:
        self.app = QApplication.instance() or QApplication()

        return super().setUp()

    def tearDown(self) -> None:
        self.app.quit()

        return super().tearDown()

    def test_set_data(self) -> None:
        self.model = CalibrationDataModel(parent=None)

        data = np.arange(10 * 3).reshape(10, 3)
        self.model.set_data(data)

        self.assertTrue((self.model._data == data).all())
