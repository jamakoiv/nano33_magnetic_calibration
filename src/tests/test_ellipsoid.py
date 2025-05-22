import unittest
import numpy as np

from matplotlib.path import Path
from ellipsoid import (
    makePaths,
    makeSphericalMesh,
    makeEllipsoidXYZ,
    fitEllipsoidNonRotated,
)


class test_ellipsoid(unittest.TestCase):
    def setUp(self) -> None:
        self.N = 5
        self.test_params = (10, 10, 10, 15, 20, 25, self.N)

        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()

    def test_makeSphericalMesh(self) -> None:
        correct_polar_angle = np.array(
            [
                [0.0, 0.78539816, 1.57079633, 2.35619449, 3.14159265],
                [0.0, 0.78539816, 1.57079633, 2.35619449, 3.14159265],
                [0.0, 0.78539816, 1.57079633, 2.35619449, 3.14159265],
                [0.0, 0.78539816, 1.57079633, 2.35619449, 3.14159265],
                [0.0, 0.78539816, 1.57079633, 2.35619449, 3.14159265],
            ],
        )
        correct_azimuth = np.array(
            [
                [-3.14159265, -3.14159265, -3.14159265, -3.14159265, -3.14159265],
                [-1.57079633, -1.57079633, -1.57079633, -1.57079633, -1.57079633],
                [0.0, 0.0, 0.0, 0.0, 0.0],
                [1.57079633, 1.57079633, 1.57079633, 1.57079633, 1.57079633],
                [3.14159265, 3.14159265, 3.14159265, 3.14159265, 3.14159265],
            ]
        )

        try:
            polar_angle, azimuth = makeSphericalMesh(self.N)

            np.testing.assert_array_almost_equal(polar_angle, correct_polar_angle)
            np.testing.assert_array_almost_equal(azimuth, correct_azimuth)

            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_makeEllipsoidXYZ(self) -> None:
        correct = np.array(
            [
                [
                    10.0,
                    -0.60660172,
                    -5.0,
                    -0.60660172,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    20.60660172,
                    25.0,
                    20.60660172,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    -0.60660172,
                    -5.0,
                    -0.60660172,
                    10.0,
                ],
                [
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    -4.14213562,
                    -10.0,
                    -4.14213562,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    24.14213562,
                    30.0,
                    24.14213562,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                    10.0,
                ],
                [
                    35.0,
                    27.67766953,
                    10.0,
                    -7.67766953,
                    -15.0,
                    35.0,
                    27.67766953,
                    10.0,
                    -7.67766953,
                    -15.0,
                    35.0,
                    27.67766953,
                    10.0,
                    -7.67766953,
                    -15.0,
                    35.0,
                    27.67766953,
                    10.0,
                    -7.67766953,
                    -15.0,
                    35.0,
                    27.67766953,
                    10.0,
                    -7.67766953,
                    -15.0,
                ],
            ]
        )

        try:
            res = makeEllipsoidXYZ(*self.test_params, as_mesh=False)
            np.testing.assert_array_almost_equal(res, correct)

            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_makeEllipsoidXYZ_as_mesh(self) -> None:
        correct = np.array(
            [
                [
                    [10.0, -0.60660172, -5.0, -0.60660172, 10.0],
                    [10.0, 10.0, 10.0, 10.0, 10.0],
                    [10.0, 20.60660172, 25.0, 20.60660172, 10.0],
                    [10.0, 10.0, 10.0, 10.0, 10.0],
                    [10.0, -0.60660172, -5.0, -0.60660172, 10.0],
                ],
                [
                    [10.0, 10.0, 10.0, 10.0, 10.0],
                    [10.0, -4.14213562, -10.0, -4.14213562, 10.0],
                    [10.0, 10.0, 10.0, 10.0, 10.0],
                    [10.0, 24.14213562, 30.0, 24.14213562, 10.0],
                    [10.0, 10.0, 10.0, 10.0, 10.0],
                ],
                [
                    [35.0, 27.67766953, 10.0, -7.67766953, -15.0],
                    [35.0, 27.67766953, 10.0, -7.67766953, -15.0],
                    [35.0, 27.67766953, 10.0, -7.67766953, -15.0],
                    [35.0, 27.67766953, 10.0, -7.67766953, -15.0],
                    [35.0, 27.67766953, 10.0, -7.67766953, -15.0],
                ],
            ]
        )

        try:
            res = makeEllipsoidXYZ(*self.test_params, as_mesh=True)
            np.testing.assert_array_almost_equal(res, correct)

            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_fitEllipsoidNonRotated(self) -> None:
        x, y, z = makeEllipsoidXYZ(10, 10, 10, 15, 20, 25, 5)

        correct = np.array([10, 10, 10, 15, 20, 25])
        res = fitEllipsoidNonRotated(x, y, z)
        params = res[0]

        try:
            np.testing.assert_array_almost_equal(params, correct, decimal=3)

            self.assertTrue(True)
        except AssertionError:
            self.assertTrue(False)

    def test_makePaths(self) -> None:
        w, q = np.meshgrid(np.array([0, 10, 20]), np.array([0, 100, 200]), sparse=False)

        correct = [
            Path(np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 100.0], [0.0, 100.0]])),
            Path(np.array([[10.0, 0.0], [20.0, 0.0], [20.0, 100.0], [10.0, 100.0]])),
            Path(
                np.array([[0.0, 100.0], [10.0, 100.0], [10.0, 200.0], [0.0, 200.0]]),
            ),
            Path(
                np.array([[10.0, 100.0], [20.0, 100.0], [20.0, 200.0], [10.0, 200.0]]),
            ),
        ]
        res = makePaths(w, q)

        self.assertEqual(len(res), len(correct))
        for i in range(len(res)):
            try:
                np.testing.assert_array_almost_equal(
                    res[i].vertices,  # pyright: ignore
                    correct[i].vertices,  # pyright: ignore
                )

            except AssertionError:
                self.assertTrue(False)
