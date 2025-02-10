import numpy as np
from numpy.typing import NDArray
from scipy import optimize
from typing import Tuple


def makeSphericalMesh(N: int) -> Tuple[np.ndarray, np.ndarray]:
    print("make spherical")
    theta = np.linspace(0.0, np.pi, N)
    phi = np.linspace(0.0, np.pi * 2.0, N)
    theta, phi = np.meshgrid(theta, phi)

    return theta, phi


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
) -> np.ndarray:
    noise = np.random.normal(size=(N, N), loc=0, scale=noise_scale)

    theta, phi = makeSphericalMesh(N)

    x = a * np.sin(theta) * np.cos(phi) + x0 + noise
    y = b * np.sin(theta) * np.sin(phi) + y0 + noise
    z = c * np.cos(theta) + z0 + noise

    if as_mesh:
        return np.array([x, y, z])
    else:
        return np.array([x.flatten(), y.flatten(), z.flatten()])


def fitEllipsoidNonRotated(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> Tuple:
    gamma_guess = np.zeros(6)
    # Center offset values can be estimated from the mean of the axes.
    gamma_guess[0] = x.mean()  # X-offset x0
    gamma_guess[1] = y.mean()  # Y-offset y0
    gamma_guess[2] = z.mean()  # Z-offset z0
    # Semi-axes can be estimated from the range of values on that axis.
    gamma_guess[3] = (x.max() - x.min()) / 2
    gamma_guess[4] = (y.max() - y.min()) / 2
    gamma_guess[5] = (z.max() - z.min()) / 2
    gamma_guess = np.array(gamma_guess)

    print("First guess of the parameters: ", end="")
    print(gamma_guess)

    print("Mean squared error of first guess: ")
    print(loss(gamma_guess, x, y, z))

    print("Gradient: ")
    # print(jax.grad(loss)(gamma_guess, x, y, z))

    # Do the actual fit using BFGS-method.
    res = optimize.fmin_bfgs(
        loss,  # Error-function to minimize.
        gamma_guess,  # Initial guess of the parameters.
        # fprime=jax.grad(loss),  # Error-function gradient.
        fprime=None,  # Error-function gradient.
        norm=2.0,  # Order of norm (???)
        args=(x, y, z),  # Extra arguments for the error-function.
        gtol=1e-17,  # Gradient norm must be less than gtol
        maxiter=300,  # Maximum number of iterations.
        full_output=True,
        disp=1,
        retall=0,
        callback=None,
    )

    return res


# Error function to be minimized.
def predict(
    gamma: np.ndarray, x: np.ndarray, y: np.ndarray, z: np.ndarray
) -> np.ndarray:
    # compute f hat
    x0 = gamma[0]
    y0 = gamma[1]
    z0 = gamma[2]
    a2 = gamma[3] ** 2
    b2 = gamma[4] ** 2
    c2 = gamma[5] ** 2
    zeta0 = (x - x0) ** 2 / a2
    zeta1 = (y - y0) ** 2 / b2
    zeta2 = (z - z0) ** 2 / c2

    return zeta0 + zeta1 + zeta2


def loss(g: np.ndarray, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.float64:
    # compute mean squared error
    pred = predict(g, x, y, z)
    target = np.ones_like(pred)
    mse = np.square(pred - target).mean()

    return mse
