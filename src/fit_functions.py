import numpy as np
import logging
import scipy

from functools import wraps
from typing import Callable

import matplotlib.pyplot as plt

log = logging.getLogger(__name__)

"""
Solve ellipsoid parameters by fitting the ellipsoid general equation,
as described in STMicroelectronics DT0059 -design tip.

aX^2 + bY^2 + cZ^2 + d2XY + e2XZ + f2YZ + g2X + h2Y + i2Z = 1

X, Y, and Z are measured by the sensor, from which you calculate the terms 
X^2, etc. terms in the above equation. Coefficients a, b, ... are obtained
by minimizing function aX^2 + ... + i2Z - 1 = 0.

Calculation of the gain and offset for the different cases are explained in
the DT0059.

"""


type fit_function_t = Callable[[np.ndarray, np.ndarray, np.ndarray], tuple]
register: dict[str, fit_function_t] = {}


# INFO: Use the 'register_fit_function' -decorator to add the function automatically
# to the FitWidget function selector.
# Code pretty much copied from https://www.youtube.com/watch?v=g7EGMWvJ1fI
def register_fit_function(name: str) -> Callable[[fit_function_t], fit_function_t]:
    def decorator(fn: fit_function_t) -> fit_function_t:
        @wraps(fn)
        def wrapper(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple:
            return fn(x, y, z)

        register[name] = wrapper
        return wrapper

    return decorator


@register_fit_function("Sphere")
def fit_sphere(
    x: np.ndarray, y: np.ndarray, z: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    # INFO:For sphere: a = b = c and d = e = f = 0.
    fit_data = np.array([x**2 + y**2 + z**2, 2 * x, 2 * y, 2 * z])

    def predict(params: np.ndarray) -> np.ndarray:
        abc, g, h, i = params
        return abc * fit_data[0] + g * fit_data[1] + h * fit_data[2] + i * fit_data[3]

    def loss(params: np.ndarray) -> float:
        pred = predict(params)
        target = np.ones_like(pred)
        return np.square(pred - target).mean()

    params_guess = np.array([1.0, 0.0, 0.0, 0.0])
    a, g, h, i = scipy.optimize.fmin_bfgs(loss, params_guess)

    offset = -1 * np.array([g / a, h / a, i / a])
    G = 1 + g**2 / a + h**2 / a + i**2 / a
    gain = np.array([np.sqrt(a / G), np.sqrt(a / G), np.sqrt(a / G)])

    soft_iron = np.diag(gain)
    semi_axes = 1 / gain
    no_rotation = np.diag(np.ones(3))

    return soft_iron, offset, semi_axes, no_rotation


@register_fit_function("Ellipsoid (non-rotated)")
def fit_ellipsoid_nonrotated(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple:
    # INFO: For non-rotated ellipsoid: d = e = f = 0.
    fit_data = np.array([x**2, y**2, z**2, 2 * x, 2 * y, 2 * z])

    def predict(params: np.ndarray) -> np.ndarray:
        a, b, c, g, h, i = params
        return np.array(
            [
                a * fit_data[0]
                + b * fit_data[1]
                + c * fit_data[2]
                + g * fit_data[3]
                + h * fit_data[4]
                + i * fit_data[5]
            ]
        )

    def loss(params: np.ndarray) -> float:
        pred = predict(params)
        target = np.ones_like(pred)
        return np.square(pred - target).mean()

    params_guess = np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0])
    a, b, c, g, h, i = scipy.optimize.fmin_bfgs(loss, params_guess)

    offset = -1 * np.array([g / a, h / b, i / c])
    G = 1 + g**2 / a + h**2 / b + i**2 / c
    gain = np.array([np.sqrt(a / G), np.sqrt(b / G), np.sqrt(c / G)])

    soft_iron = np.diag(gain)
    semi_axes = 1 / gain
    no_rotation = np.diag(np.ones(3))

    return soft_iron, offset, semi_axes, no_rotation


# INFO: from rotation matrix R to soft-iron matrix:
# soft_iron = np.matmul(np.diag(gain), R)


@register_fit_function("Ellipsoid (rotated)")
def fit_ellipsoid_rotated(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple:
    fit_data = np.array(
        [x**2, y**2, z**2, 2 * x * y, 2 * x * z, 2 * y * z, 2 * x, 2 * y, 2 * z]
    )

    def predict(params: np.ndarray) -> np.ndarray:
        a, b, c, d, e, f, g, h, i = params
        return np.array(
            [
                a * fit_data[0]
                + b * fit_data[1]
                + c * fit_data[2]
                + d * fit_data[3]
                + e * fit_data[4]
                + f * fit_data[5]
                + g * fit_data[6]
                + h * fit_data[7]
                + i * fit_data[8]
            ]
        )

    def loss(params: np.ndarray) -> float:
        pred = predict(params)
        target = np.ones_like(pred)
        return np.square(pred - target).mean()

    params_guess = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    a, b, c, d, e, f, g, h, i = scipy.optimize.fmin_bfgs(loss, params_guess)

    # Auxiliary matrices and vectors
    v_ghi = np.array([g, h, i]).transpose()
    A_4 = np.array([[a, d, e, g], [d, b, f, g], [e, f, c, i], [g, h, i, -1]])
    A_3 = A_4[0:3].transpose()[0:3].transpose()  # Slice 4x4 into 3x3 matrix.

    offset = -1 * np.matmul(np.linalg.inv(A_3), v_ghi)

    T = np.array(
        [
            [1, 0, 0, 0],  # fmt: skip
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [offset[0], offset[1], offset[2], 1],
        ]
    )

    B_4 = np.matmul(np.matmul(T, A_4), T.transpose())
    B_3 = B_4[0:3].transpose()[0:3].transpose() / (-1 * B_4[(3, 3)])

    eigenvalues, eigenvectors = np.linalg.eig(B_3)
    # INFO: For some reason in numpy eig returns the eigenvectors so that
    # eigenvectors[:,i] is the eigenvector corresponding to eigenvalues[i].

    semi_axes = np.sqrt(1 / eigenvalues)
    rotation = eigenvectors.transpose()
    semi_axes, rotation = refine_rotation_matrix(semi_axes, rotation)
    soft_iron = np.matmul(np.diag(1 / semi_axes), rotation)

    return soft_iron, offset, semi_axes, rotation


@register_fit_function("Ellipsoid (rotated, alt)")
def fit_ellipsoid_rotated_alt(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple:
    """
    The proposed scheme for improving fit-quality for slightly rotated ellipsoid.
    """
    D = np.array(
        [
            x**2 + y**2 - 2 * z**2,
            x**2 - 2 * y**2 + z**2,
            4 * x * y,
            2 * x * z,
            2 * y * z,
            2 * x,
            2 * y,
            2 * z,
            np.ones_like(x),
        ]
    )
    E = np.array([x**2 + y**2 + z**2])

    def predict(params: np.ndarray) -> np.ndarray:
        return (
            params[0] * D[0]
            + params[1] * D[1]
            + params[2] * D[2]
            + params[3] * D[3]
            + params[4] * D[4]
            + params[5] * D[5]
            + params[6] * D[6]
            + params[7] * D[7]
            + params[8] * D[8]
        )

    def loss(params: np.ndarray) -> float:
        return np.square(predict(params) - E).mean()

    u_guess = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    u = scipy.optimize.fmin_bfgs(loss, u_guess)

    # NOTE: This was so stupidly given in the DT0059. Maybe correct, maybe not.
    S = np.array(
        [
            [3.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [3.0, 1.0, -2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [3.0, -2.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ]
    )

    vd = np.linalg.matmul(S, np.concat([np.array([-1 / 3]), u]))
    v = -1 * vd[0:9] / vd[9]
    a, b, c, d, e, f, g, h, i = v

    # Auxiliary matrices and vectors
    v_ghi = np.array([g, h, i]).transpose()
    A_4 = np.array([[a, d, e, g], [d, b, f, g], [e, f, c, i], [g, h, i, -1]])
    A_3 = A_4[0:3].transpose()[0:3].transpose()  # Slice 4x4 into 3x3 matrix.

    offset = -1 * np.matmul(np.linalg.inv(A_3), v_ghi)

    T = np.array(
        [
            [1, 0, 0, 0],  # fmt: skip
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [offset[0], offset[1], offset[2], 1],
        ]
    )

    B_4 = np.matmul(np.matmul(T, A_4), T.transpose())
    B_3 = B_4[0:3].transpose()[0:3].transpose() / (-1 * B_4[(3, 3)])

    eigenvalues, eigenvectors = np.linalg.eig(B_3)
    # INFO: For some reason in numpy eig returns the eigenvectors so that
    # eigenvectors[:,i] is the eigenvector corresponding to eigenvalues[i].

    semi_axes = np.sqrt(1 / eigenvalues)
    rotation = eigenvectors.transpose()
    semi_axes, rotation = refine_rotation_matrix(semi_axes, rotation)
    soft_iron = np.matmul(np.diag(1 / semi_axes), rotation)

    return soft_iron, offset, semi_axes, rotation


def refine_rotation_matrix(
    gain: np.ndarray, rot: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """
    Reorder elements to put biggest values to the diagonal of the rotation matrix,
    i.e. create the minimum necessary rotation to achieve the desired result.
    """
    assert rot.shape == (3, 3), "Rotation matrix must be 3x3 shaped matrix."

    # INFO: Reorder the columns if the maximum is not on the diagonal.
    # BUG: Fails if there are more than one max-values.
    # For quick fix we just pick the first max-value coordinates [0] for now.
    rm, cm = np.where(np.abs(rot) == np.abs(rot).max())
    rm, cm = rm[0], cm[0]
    if rm != cm:
        rot[:, [cm, rm]] = rot[:, [rm, cm]]
        gain[cm], gain[rm] = gain[rm], gain[cm]

    # INFO: Create 2x2 matrix from the remaining parts.
    if rm == 0:
        i0, i1 = 1, 2
    elif rm == 1:
        i0, i1 = 0, 2
    else:  # rm == 2
        i0, i1 = 0, 1

    aux_idx = [(i0, i0), (i0, i1), (i1, i0), (i1, i1)]
    aux_rows, aux_cols = zip(*aux_idx)
    aux_rot = rot[aux_rows, aux_cols].reshape(2, 2)

    # INFO: Same as before, put maximum on the diagonal and insert
    # back to the original rotation matrix.
    # BUG: See the above bug.
    rm, cm = np.where(np.abs(aux_rot) == np.abs(aux_rot).max())
    rm, cm = rm[0], cm[0]
    if rm != cm:
        aux_rot[:, [0, 1]] = aux_rot[:, [1, 0]]

        rot[aux_idx[0]] = aux_rot[(0, 0)]
        rot[aux_idx[1]] = aux_rot[(0, 1)]
        rot[aux_idx[2]] = aux_rot[(1, 0)]
        rot[aux_idx[3]] = aux_rot[(1, 1)]

        gain[i0], gain[i1] = gain[i1], gain[i0]

    # INFO: Flip column sign if the diagonal is negative.
    if rot[0, 0] < 0:
        rot[:, 0] = -rot[:, 0]
    if rot[1, 1] < 0:
        rot[:, 1] = -rot[:, 1]
    if rot[2, 2] < 0:
        rot[:, 2] = -rot[:, 2]

    return gain, rot


if __name__ == "__main__":
    data = np.loadtxt("data.csv", delimiter=",")

    x, y, z = data.transpose()[1:4]

    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")
