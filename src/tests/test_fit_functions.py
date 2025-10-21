import unittest
import numpy as np

import fit_functions
from ellipsoid import (
    makeEllipsoidXYZ,
)


class test_fit_functions(unittest.TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()

    def test_register_fit_function(self) -> None:
        @fit_functions.register_fit_function("__test_function__")
        def foo(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple:
            return (x**2, y**2, z**2, x * y * z)  # Suppress 'variable not used'.

        self.assertIn("__test_function__", fit_functions.register)
        self.assertIs(fit_functions.register["__test_function__"], foo)

    def test_fit_sphere(self) -> None:
        ellipsoid_offset = (10, -10, 15)
        ellipsoid_semi_axes = (35, 35, 35)
        ellipsoid_rotation = np.eye(3)

        ellipsoid = makeEllipsoidXYZ(*ellipsoid_offset, *ellipsoid_semi_axes)
        soft_iron, hard_iron, semi_axes, rotation = fit_functions.fit_sphere(*ellipsoid)

        # NOTE: Big tolerances since the fit function results are
        # not always identical run to run.
        np.testing.assert_allclose(ellipsoid_semi_axes, semi_axes, atol=0.1)
        np.testing.assert_allclose(np.diag(soft_iron), 1 / semi_axes, atol=0.1)
        np.testing.assert_allclose(ellipsoid_offset, hard_iron, atol=0.1)
        np.testing.assert_allclose(ellipsoid_rotation, rotation, atol=0.1)

    def test_fit_ellipsoid_nonrotated(self) -> None:
        ellipsoid_offset = (10, -10, 15)
        ellipsoid_semi_axes = (35, 45, 50)
        ellipsoid_rotation = np.eye(3)

        ellipsoid = makeEllipsoidXYZ(*ellipsoid_offset, *ellipsoid_semi_axes)
        soft_iron, hard_iron, semi_axes, rotation = (
            fit_functions.fit_ellipsoid_nonrotated(*ellipsoid)
        )

        np.testing.assert_allclose(ellipsoid_semi_axes, semi_axes, atol=0.1)
        np.testing.assert_allclose(np.diag(soft_iron), 1 / semi_axes, atol=0.1)
        np.testing.assert_allclose(ellipsoid_offset, hard_iron, atol=0.1)
        np.testing.assert_allclose(ellipsoid_rotation, rotation, atol=0.1)

    # TODO: Make code to rotate ellipsoid so we can create synthetic data for the tests.
    def test_fit_ellipsoid_rotated(self) -> None: ...

    def test_fit_ellipsoid_rotated_alt(self) -> None: ...
