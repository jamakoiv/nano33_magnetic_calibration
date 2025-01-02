import sys
import logging
import numpy as np

from collections import OrderedDict

from PySide6.QtCore import (
    Slot,
    Signal,
    QObject,
    QAbstractListModel,
    QAbstractTableModel,
    QPersistentModelIndex,
    QModelIndex,
    Qt,
)
from PySide6.QtWidgets import (
    QComboBox,
    QMainWindow,
    QMessageBox,
    QTableView,
    QApplication,
)
from PySide6.QtGui import QColor


class CalibrationDataModel(QAbstractTableModel):
    _data: np.ndarray
    data_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent=parent)

    def set_data(self, array: np.ndarray) -> None:
        self.beginResetModel()

        try:
            self._data = array
        finally:
            self.endResetModel()

    @Slot(object)  # pyright: ignore
    def append_data(self, row: np.ndarray) -> None:
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())

        try:
            self._data = np.append(self._data, row, axis=0)
        except AttributeError:  # if self._data does not exists
            self.set_data(row)
        finally:
            self.endInsertRows()

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        try:
            assert (
                len(self._data) == self._data.shape[0]
            ), "Error with data shape: 'len' and np.ndarray.shape[0] do not match."

            return len(self._data)
        except AttributeError:
            return 0

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        try:
            return self._data.shape[1]
        except AttributeError:
            return 0

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        columns = {
            0: "X [mT]",
            1: "Y [mT]",
            2: "Z [mT]",
            3: "total [mT]",
            4: "uguu [mT]",
        }

        match role:
            case Qt.ItemDataRole.DisplayRole:
                if orientation == Qt.Orientation.Horizontal:
                    try:
                        res = columns[section]
                    except KeyError:
                        res = "uguu"
                else:
                    res = str(section)

            case Qt.ItemDataRole.BackgroundRole:
                res = QColor(Qt.GlobalColor.white)
            case Qt.ItemDataRole.TextAlignmentRole:
                res = Qt.AlignmentFlag.AlignRight
            case _:
                res = None

        return res

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        coord = (index.row(), index.column())

        match role:
            case Qt.ItemDataRole.DisplayRole:
                return str(self._data[coord])
            case Qt.ItemDataRole.BackgroundRole:
                return QColor(Qt.GlobalColor.white)
            case Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignRight
            case _:
                return None

    def get_xyz_data(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        try:
            x, y, z = self._data.transpose()
        except AttributeError:
            x = np.zeros(0)
            y = np.zeros(0)
            z = np.zeros(0)

        return x, y, z


class SerialPortsModel(QAbstractListModel):
    data_changed = Signal()

    # Ports should dict like {"/dev/ttyACM0": "Board name", "/dev/tty0": ""} etc.
    ports: OrderedDict[str, str]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent=parent)

        self.ports = OrderedDict()
        self.ports["no device"] = ""

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        coord = index.row()
        device, name = list(self.ports.items())[coord]

        match role:
            case Qt.ItemDataRole.DisplayRole:
                if name in [None, ""]:
                    res = f"{device}"
                else:
                    res = f"{device} - {name}"

                return res
            case Qt.ItemDataRole.UserRole:
                return device
            case Qt.ItemDataRole.BackgroundRole:
                return QColor(Qt.GlobalColor.white)
            case Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignRight
            case _:
                return None

    def set_ports(self, ports: OrderedDict) -> None:
        try:
            self.beginResetModel()
            self.ports = ports

        finally:
            self.endResetModel()

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        return len(self.ports)


def test_calibration_data_model():
    model = CalibrationDataModel()

    d = np.arange(50 * 4).reshape(50, 4)
    model.set_data(d)

    app = QApplication()
    main = QMainWindow()

    view = QTableView(parent=main)
    view.setModel(model)
    view.verticalHeader().setVisible(False)
    main.setCentralWidget(view)
    main.show()

    sys.exit(app.exec())


def test_SerialPortsModel():
    model = SerialPortsModel()

    d = OrderedDict()
    d["aaa"] = "Portti numero A"
    d["bbb"] = "Toinen portti"
    d["ccc"] = "kolmas portti."
    model.set_ports(d)

    app = QApplication()
    main = QMainWindow()

    view = QComboBox(parent=main)
    view.setModel(model)
    main.setCentralWidget(view)
    main.show()

    view.currentIndexChanged.connect(
        lambda: QMessageBox.information(
            main,
            "IndexChanged",
            f"Selected: {view.currentIndex()}, {view.currentData()}",
        )
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    # test_calibration_data_model()
    test_SerialPortsModel()
