from PySide6 import QtWidgets
import pygame

import sys
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QGuiApplication, QQuaternion, QVector3D
from PySide6.Qt3DCore import Qt3DCore
from PySide6.Qt3DExtras import Qt3DExtras


class Joystick:
    def __init__(self, id: int) -> None:
        pygame.init()
        pygame.joystick.init()

        joystick_count = pygame.joystick.get_count()
        if joystick_count == 0:
            raise Exception("No joysticks detected by pygame.")

        elif id >= joystick_count:
            raise IndexError(
                f"Joystick ID {id} is out of range. Select ID from list {list(range(joystick_count))}"
            )

        self.joystick = pygame.joystick.Joystick(id)
        self.joystick.init()

        self.axis_mappings = {"pitch": 1, "yaw": 5, "roll": 0}
        self.axis_inverts = {"pitch": -1, "yaw": -1, "roll": 1}

        # INFO: get_axis() outputs float in range [-1, 1].
        # Multiply by axis range to get the output on desired range.
        # TODO: Should use map in case we want non-symmetrical outputs.
        self.axis_ranges = {"pitch": 180, "yaw": 180, "roll": 180}

    def get_euler(self) -> tuple:
        pygame.event.pump()

        pitch = (
            self.joystick.get_axis(self.axis_mappings["pitch"])
            * self.axis_ranges["pitch"]
            * self.axis_inverts["pitch"]
        )
        roll = (
            self.joystick.get_axis(self.axis_mappings["roll"])
            * self.axis_ranges["roll"]
            * self.axis_inverts["roll"]
        )
        yaw = (
            self.joystick.get_axis(self.axis_mappings["yaw"])
            * self.axis_ranges["yaw"]
            * self.axis_inverts["yaw"]
        )
        print(f"pitch {pitch}, yaw {yaw}, roll {roll}")

        return (pitch, roll, yaw)


class Arrow3D(Qt3DCore.QEntity):
    def __init__(self, parent: Qt3DCore.QEntity, color: QColor) -> None:
        super().__init__(parent)

        self.arrow = Qt3DCore.QEntity(parent)
        self.material = Qt3DExtras.QDiffuseSpecularMaterial(self.arrow)
        self.material.setAmbient(color)

        self.body = Qt3DExtras.QCylinderMesh()
        self.body.setRadius(2.0)
        self.body.setLength(10.0)
        self.body_transform = Qt3DCore.QTransform()
        self.body_transform.setTranslation(QVector3D(0.0, 0.0, 0.0))
        self.body_entity = Qt3DCore.QEntity(self.arrow)
        self.body_entity.addComponent(self.body)
        self.body_entity.addComponent(self.body_transform)
        self.body_entity.addComponent(self.material)

        self.head = Qt3DExtras.QConeMesh()
        self.head.setTopRadius(0.0)
        self.head.setBottomRadius(3)
        self.head.setLength(5)
        self.head_transform = Qt3DCore.QTransform()
        self.head_transform.setTranslation(QVector3D(0.0, 7.50, 0.0))
        self.head_entity = Qt3DCore.QEntity(self.arrow)
        self.head_entity.addComponent(self.head)
        self.head_entity.addComponent(self.head_transform)
        self.head_entity.addComponent(self.material)

        self.transform = Qt3DCore.QTransform()
        self.arrow.addComponent(self.transform)


class AxisArrows(Qt3DCore.QEntity):
    def __init__(self, parent: Qt3DCore.QEntity) -> None:
        super().__init__(parent)

        self.axis = Qt3DCore.QEntity(parent)

        # NOTE: By default the arrow body is aligned to the Y-axis.
        self.arrowX = Arrow3D(self.axis, color=QColor(255, 0, 0))
        self.arrowX.transform.setRotationZ(-90)
        self.arrowX.transform.setTranslation(QVector3D(5.0, 0.0, 0.0))

        self.arrowY = Arrow3D(self.axis, color=QColor(0, 255, 0))
        self.arrowY.transform.setTranslation(QVector3D(0.0, 5.0, 0.0))

        self.arrowZ = Arrow3D(self.axis, color=QColor(0, 0, 255))
        self.arrowZ.transform.setRotationX(90)
        self.arrowZ.transform.setTranslation(QVector3D(0.0, 0.0, 5.0))

        self.transform = Qt3DCore.QTransform()
        self.axis.addComponent(self.transform)


class OrientationWindow(Qt3DExtras.Qt3DWindow):
    """
    Display board orientation as 3D-model.
    """

    def __init__(self):
        super().__init__()

        self.i = 0

        # TODO: Supply joystick as argument, or just callable returning the angles.
        self.joystick = Joystick(0)

        # Camera
        self.camera().lens().setPerspectiveProjection(45, 16 / 9, 0.1, 1000)
        self.camera().setPosition(QVector3D(10, 10, -15))
        self.camera().setViewCenter(QVector3D(0, 0, 0))

        # For camera controls
        self.createScene()
        self.camController = Qt3DExtras.QOrbitCameraController(self.rootEntity)
        self.camController.setLinearSpeed(50)
        self.camController.setLookSpeed(180)
        self.camController.setCamera(self.camera())

        self.setRootEntity(self.rootEntity)

    def createScene(self):
        self.rootEntity = Qt3DCore.QEntity()

        self.material = Qt3DExtras.QPhongMaterial(self.rootEntity)

        self.boardEntity = Qt3DCore.QEntity(self.rootEntity)
        self.boardMesh = Qt3DExtras.QCuboidMesh()
        self.boardMesh.setXExtent(4.0)
        self.boardMesh.setYExtent(1.0)
        self.boardMesh.setZExtent(10.0)

        self.boardTransform = Qt3DCore.QTransform()
        self.boardEntity.addComponent(self.boardMesh)
        self.boardEntity.addComponent(self.boardTransform)
        self.boardEntity.addComponent(self.material)

        self.axes = AxisArrows(self.boardEntity)
        self.axes.transform.setScale(0.5)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(10)

    def update(self):
        # # NOTE: QVector for fromEulerAngles is (pitch, yaw, roll).

        pitch, roll, yaw = self.joystick.get_euler()
        print(f"update {self.i}: pitch {pitch}, yaw {yaw}, roll {roll}")

        self.boardTransform.setRotation(QQuaternion.fromEulerAngles(pitch, yaw, roll))

        self.i += 1


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    view = OrientationWindow()

    view.show()
    sys.exit(app.exec())
