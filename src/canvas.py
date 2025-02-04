from typing import Callable

from matplotlib.axes import Axes
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Line3D
from mpl_toolkits.mplot3d.axes3d import Axes3D
from matplotlib.lines import Line2D

from models import CalibrationDataModel


class MatplotlibCanvas(FigureCanvasQTAgg):
    """
    Canvas for drawing matplotlib-plots.
    """

    # NOTE: We should probably inherit QAbstractItemView as well since we
    # are basically implementing a Qt view. However both QAbstractItemView
    # and FigureCanvasQTAgg have paintEvent which conflict when inheriting both.
    #
    # NOTE: Lots of 'pyright: ignore' because of numpy type hints/function signatures being what they are

    plot: Callable
    update_plot: Callable

    fig: Figure
    axes: dict[str, Axes | Axes3D]
    plot_ref: dict[str, Line2D | Line3D]
    model: CalibrationDataModel

    def __init__(
        self,
        width: int = 5,
        height: int = 4,
        dpi: int = 100,
        projection: str = "3d",
    ) -> None:
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)

        self.axes = {}
        self.plot_ref = {}

        match projection:
            case "3d":
                self.plot = self.plot_3d
                self.update_plot = self.update_3d
            case "2d":
                self.plot = self.plot_2d
                self.update_plot = self.update_2d

    def setModel(self, model: CalibrationDataModel) -> None:
        self.model = model

        self.model.rowsInserted.connect(self.update_plot)
        self.model.rowsRemoved.connect(self.update_plot)
        self.model.modelReset.connect(self.update_plot)

        self.plot()

    def plot_3d(self) -> None:
        self.axes["3d"] = self.fig.add_subplot(111, projection="3d")

        self.axes["3d"].set_aspect("equal")
        self.axes["3d"].set_box_aspect((75, 75, 75))  # pyright: ignore
        self.fig.tight_layout()

        # Draw helper axes at origo.
        c = 60  # Scale
        self.axes["3d"].plot3D([-1 * c, 1 * c], [0, 0], [0, 0], "k:")  # pyright: ignore
        self.axes["3d"].plot3D([0, 0], [-1 * c, 1 * c], [0, 0], "k:")  # pyright: ignore
        self.axes["3d"].plot3D([0, 0], [0, 0], [-1 * c, 1 * c], "k:")  # pyright: ignore

        x, y, z = self.model.get_xyz_data()
        plot_ref_list = self.axes["3d"].plot3D(x, y, z, "rx")  # pyright: ignore

        self.plot_ref["3d"] = plot_ref_list[-1]

    def update_3d(self):
        x, y, z = self.model.get_xyz_data()
        self.plot_ref["3d"].set_data_3d(x, y, z)  # pyright: ignore

        self.draw()

    def update_wireframe(self, x, y, z) -> None:
        print("plot_wireframe")
        try:
            self.plot_ref["fit_wireframe"].remove()
            del self.plot_ref["fit_wireframe"]
        except (
            KeyError,
            AttributeError,
        ):  # If self.plot_ref or fit_wireframe do not exist.
            pass
        finally:
            self.plot_ref["fit_wireframe"] = self.axes["3d"].plot_wireframe(x, y, z)  # pyright: ignore
            self.draw()

    def delete_wireframe(self) -> None:
        try:
            self.plot_ref["fit_wireframe"].remove()
            del self.plot_ref["fit_wireframe"]
        except (
            KeyError,
            AttributeError,
        ):  # If self.plot_ref or fit_wireframe do not exist.
            pass
        finally:
            self.draw()

    def plot_2d(self) -> None:
        for i, axis in enumerate(["x", "y", "z"]):
            ax = self.fig.add_subplot(1, 3, i + 1)
            ax.set_aspect("equal")

            self.axes[axis] = ax

    def update_2d(self): ...
