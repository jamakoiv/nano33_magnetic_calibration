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

from src.ellipsoid import SphereSampling, fitEllipsoidNonRotated


class CalibrationDataModel(QAbstractTableModel):
    _data: np.ndarray
    data_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        self.sampling = SphereSampling(N=10)

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

        # TODO: Too much babysitting the input shape.
        row = np.append(row, self.calculate_magnitude(row))
        row = row.reshape(1, len(row))

        try:
            self._data = np.append(self._data, row, axis=0)
        except AttributeError:  # if self._data does not exists
            self.set_data(row)
        finally:
            self.update_sampling()
            self.endInsertRows()

    def removeRows(
        self,
        row: int,
        count: int,
        /,
        parent: QModelIndex | QPersistentModelIndex | None = None,
    ) -> bool:
        self.beginRemoveRows(QModelIndex(), row, row + count)

        row_index = np.arange(row, row + count)
        try:
            self._data = np.delete(self._data, row_index, axis=0)
        except IndexError:
            # TODO: Log error if we get indexerror.
            return False
        finally:
            self.endRemoveRows()

        return True

    def calculate_magnitude(self, row: np.ndarray) -> float:
        return np.sqrt((row**2).sum())

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        try:
            assert len(self._data) == self._data.shape[0], (
                "Error with data shape: 'len' and np.ndarray.shape[0] do not match."
            )

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
            0: "X [μT]",
            1: "Y [μT]",
            2: "Z [μT]",
            3: "total [μT]",
            4: "uguu [μT]",
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

    def get_xyz_data(self, with_offset: bool = False) -> np.ndarray:
        try:
            x, y, z, _ = self._data.copy().transpose()

            if with_offset:
                x_offset, y_offset, z_offset = self.ellipsoid_params[:3]
                x -= x_offset
                y -= y_offset
                z -= z_offset

        except AttributeError:
            x = np.zeros(0)
            y = np.zeros(0)
            z = np.zeros(0)

        return np.array([x, y, z])

    def update_offset(self) -> None:
        x, y, z = self.get_xyz_data(with_offset=False)
        res = fitEllipsoidNonRotated(x, y, z)
        self.ellipsoid_params = np.array(res[0])
        print(self.ellipsoid_params)

    def update_sampling(self) -> None:
        if self.rowCount() % 10 == 0:
            self.update_offset()

        x, y, z = self.get_xyz_data(with_offset=True)

        r = np.sqrt(x**2 + y**2 + z**2)
        polar_angle = np.arccos(z / r)
        azimuth = np.atan2(y, x)

        coords = np.array([polar_angle, azimuth]).transpose()

        # TODO: Should use the sampling.update_single_point instead of updating all.
        self.sampling.update(coords)

        print(f"offset: {self.ellipsoid_params[:3]}")
        print(
            f"sample coverage: {self.sampling.get_percentage()}, {self.sampling.get_count()} / {len(self.sampling.segments)}"
        )
        # print(coords)


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

    sys.exit(app.exec())


if __name__ == "__main__":
    # test_calibration_data_model()
    test_SerialPortsModel()
