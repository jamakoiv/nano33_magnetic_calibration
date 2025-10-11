import logging
import numpy as np

from typing import Tuple, List
from matplotlib.path import Path

log = logging.getLogger(__name__)


def makeSphericalMesh(N: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Helper function for creating meshgrid for spherical coordinates theta = [0, pi], phi = [0, 2*pi].
    """
    assert N > 0, "Number N must be positive number."

    polar_angle = np.linspace(0.0, np.pi, N)
    azimuth = np.linspace(-1 * np.pi, np.pi, N)
    polar_angle, azimuth = np.meshgrid(polar_angle, azimuth)

    return polar_angle, azimuth


def makeEllipsoidXYZ(
    x0: float,
    y0: float,
    z0: float,
    a: float,
    b: float,
    c: float,
    N: int = 20,
    noise_scale: float = 0.0,
    as_mesh=False,
    generator: np.random.Generator | None = None,
) -> np.ndarray:
    """
    Create ellipsoid with center offset (x0, y0, z0) and axes (a, b, c).

    noise_scale: Standard deviation of noise added to coordinates.
    as_mesh: If True, return as meshgrid. If False, return as flattened xyz-arrays.
    generator: Optional numpy generator for generating noise (mainly for testing purposes).
    """

    try:
        noise = generator.normal(size=(N, N), loc=0, scale=noise_scale)  # pyright: ignore
    except AttributeError:
        noise = np.random.normal(size=(N, N), loc=0, scale=noise_scale)

    theta, phi = makeSphericalMesh(N)

    x = a * np.sin(theta) * np.cos(phi) + x0 + noise
    y = b * np.sin(theta) * np.sin(phi) + y0 + noise
    z = c * np.cos(theta) + z0 + noise

    if as_mesh:
        return np.array([x, y, z])
    else:
        return np.array([x.flatten(), y.flatten(), z.flatten()])


def makePaths(w: np.ndarray, q: np.ndarray) -> List[Path]:
    """
    Creates matplotlib Path-objects from 2D-grid.
    Each path describes a square of the 2D-grid.

    w, q: numpy.arrays as returned by numpy.meshgrid(x, y, sparse=False).

    returns: list of matplotlib.path.Path -objects.

    """
    # TODO: There is no real need for w and q to have same dimensions.
    assert w.shape == q.shape, "Input arrays must have same shape."
    assert w.shape[0] == w.shape[1], "Input array shape must be square."

    paths = []
    # TODO: Can we write this with numpy.vectorize instead of loops?
    for i in range(w.shape[0] - 1):
        for j in range(w.shape[0] - 1):
            p = Path(
                [
                    (w[i, j], q[i, j]),
                    (w[i, j + 1], q[i, j + 1]),
                    (w[i + 1, j + 1], q[i + 1, j + 1]),
                    (w[i + 1, j], q[i + 1, j]),
                ]
            )
            paths.append(p)

    return paths


class SamplingError(Exception):
    pass


class SphereSampling:
    """
    Create a mesh describing a parameter-space for spherical coordinates, and track
    how many segments in the space have been sampled.
    """

    def __init__(self, N: int = 10):
        self.polar_angle, self.azimuth = makeSphericalMesh(N)
        self.segments = makePaths(self.polar_angle, self.azimuth)
        self.sampled = np.zeros(len(self.segments))

    def update_single_point(self, point: np.ndarray | Tuple[float, float]) -> None:
        for i, segment in enumerate(self.segments):
            if segment.contains_point(point):  # pyright: ignore
                self.sampled[i] = 1
                # print(f"i: {i}")
                return

        raise SamplingError(f"Point {point} is not contained in any parameter segment.")

    def update(self, points: np.ndarray | List[Tuple[float, float]]) -> None:
        for point in points:
            self.update_single_point(point)

    def get_count(self) -> int:
        return int(np.count_nonzero(self.sampled))

    def get_percentage(self) -> float:
        return float(np.count_nonzero(self.sampled) / len(self.sampled))

    def get_segments(self) -> Tuple:
        return self.segments, self.sampled


def rotation(alpha: float, beta: float, gamma: float) -> np.ndarray:
    Rz = np.array(  # Yaw
        [
            [np.cos(alpha), -1 * np.sin(alpha), 0],
            [np.sin(alpha), np.cos(alpha), 0],
            [0, 0, 1],
        ]
    )

    Ry = np.array(
        [  # Pitch
            [np.cos(beta), 0, np.sin(beta)],
            [0, 1, 0],
            [-1 * np.sin(beta), 0, np.cos(beta)],
        ]
    )

    Rx = np.array(  # Roll
        [
            [1, 0, 0],
            [0, np.cos(gamma), -1 * np.sin(gamma)],
            [0, np.sin(gamma), np.cos(gamma)],
        ]
    )

    return np.linalg.matmul(np.linalg.matmul(Rz, Ry), Rx)
