import unittest
import numpy as np

import ellipsoid
import fit_functions


class test_fit_functions(unittest.TestCase):
    def setUp(self) -> None:
        self.correct_offset = (10, -10, 15)
        self.correct_semi_axes = (35, 35, 35)
        self.correct_no_rotation = np.eye(3)
        self.correct_rotation = ellipsoid.rotation(
            np.deg2rad(30), np.deg2rad(45), np.deg2rad(25)
        )
        self.ellipsoid = ellipsoid.makeEllipsoidXYZ(
            *self.correct_offset, *self.correct_semi_axes
        )

        self.correct_semi_axes_rotated = (30, 35, 40)
        self.ellipsoid_rotated = ellipsoid.makeEllipsoidXYZ(
            *self.correct_offset, *self.correct_semi_axes_rotated
        )
        self.ellipsoid_rotated = np.array(
            [
                np.matmul(self.correct_rotation, xyz)
                for xyz in self.ellipsoid_rotated.transpose()
            ]
        ).transpose()

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
        soft_iron, hard_iron, semi_axes, rotation = fit_functions.fit_sphere(
            *self.ellipsoid
        )

        # NOTE: Big tolerances since the fit function results are
        # not always identical run to run.
        np.testing.assert_allclose(self.correct_semi_axes, semi_axes, atol=0.1)
        np.testing.assert_allclose(np.diag(soft_iron), 1 / semi_axes, atol=0.1)
        np.testing.assert_allclose(self.correct_offset, hard_iron, atol=0.1)
        np.testing.assert_allclose(self.correct_no_rotation, rotation, atol=0.1)

    def test_fit_ellipsoid_nonrotated(self) -> None:
        soft_iron, hard_iron, semi_axes, rotation = (
            fit_functions.fit_ellipsoid_nonrotated(*self.ellipsoid)
        )

        np.testing.assert_allclose(self.correct_semi_axes, semi_axes, atol=0.1)
        np.testing.assert_allclose(np.diag(soft_iron), 1 / semi_axes, atol=0.1)
        np.testing.assert_allclose(self.correct_offset, hard_iron, atol=0.1)
        np.testing.assert_allclose(self.correct_no_rotation, rotation, atol=0.1)

    def test_fit_ellipsoid_rotated(self) -> None:
        soft_iron, hard_iron, semi_axes, rotation = fit_functions.fit_ellipsoid_rotated(
            *self.ellipsoid_rotated
        )
        breakpoint()

        np.testing.assert_allclose(self.correct_semi_axes_rotated, semi_axes, atol=0.1)
        np.testing.assert_allclose(self.correct_offset, hard_iron, atol=0.1)
        np.testing.assert_allclose(self.correct_rotation, rotation, atol=0.1)

    def test_fit_ellipsoid_rotated_alt(self) -> None: ...

    def test_refine_rotation_matrix_identity(self) -> None:
        # INFO: Check identity-matrix is left unmodified.
        gain = np.ones(3)
        rot = np.eye(3)

        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)
        np.testing.assert_allclose(res_gain, gain)
        np.testing.assert_allclose(res_rot, rot)

    def test_refine_rotation_matrix_float_diagonal(self) -> None:
        gain = np.array([1, 2, 3])
        rot = np.array(
            [
                [0.90, 0.01, 0.02],  # noqa
                [0.03, 0.80, 0.04],
                [0.05, 0.06, 0.70],
            ]
        )

        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)

        np.testing.assert_allclose(res_rot, rot)
        np.testing.assert_allclose(res_gain, gain)

    def test_refine_rotation_matrix_ones_off_diagonal_3x3(self) -> None:
        gain = np.array([1, 2, 3])
        rot = np.array(
            [
                [0, 0, 1],  # noqa
                [1, 0, 0],
                [0, 1, 0],
            ]
        )

        correct_gain = np.array([3, 1, 2])
        correct_rot = np.eye(3)

        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)

        np.testing.assert_allclose(res_rot, correct_rot)
        np.testing.assert_allclose(res_gain, correct_gain)

    def test_refine_rotation_matrix_ones_off_diagonal_2x2(self) -> None:
        gain = np.array([1, 2, 3])
        rot = np.array(
            [
                [1, 0, 0],  # noqa
                [0, 0, 1],
                [0, 1, 0],
            ]
        )

        correct_gain = np.array([1, 3, 2])
        correct_rot = np.eye(3)

        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)

        np.testing.assert_allclose(res_rot, correct_rot)
        np.testing.assert_allclose(res_gain, correct_gain)

    def test_refine_rotation_matrix_float_off_diagonal_3x3(self) -> None:
        # INFO: Tests where the 3x3 matrix is reordered, but the 2x2 submatrix is not.

        # NOTE: Case rm == 0.
        gain = np.array([1, 2, 3])
        rot = np.array(
            [
                [0.03, 0.90, 0.04],  # noqa
                [0.80, 0.01, 0.02],
                [0.05, 0.06, 0.70],
            ]
        )
        correct_gain = np.array([2, 1, 3])
        correct_rot = np.array(
            [
                [0.90, 0.03, 0.04],  # noqa
                [0.01, 0.80, 0.02],
                [0.06, 0.05, 0.70],
            ]
        )
        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)
        np.testing.assert_allclose(res_rot, correct_rot)
        np.testing.assert_allclose(res_gain, correct_gain)

        # NOTE: Case rm == 1.
        gain = np.array([1, 2, 3])
        rot = np.array(
            [
                [0.03, 0.80, 0.04],  # noqa
                [0.90, 0.01, 0.02],
                [0.05, 0.06, 0.70],
            ]
        )
        correct_gain = np.array([2, 1, 3])
        correct_rot = np.array(
            [
                [0.80, 0.03, 0.04],  # noqa
                [0.01, 0.90, 0.02],
                [0.06, 0.05, 0.70],
            ]
        )
        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)
        np.testing.assert_allclose(res_rot, correct_rot)
        np.testing.assert_allclose(res_gain, correct_gain)

        # NOTE: Case rm == 2.
        gain = np.array([1, 2, 3])
        rot = np.array(
            [
                [0.04, 0.03, 0.80],  # noqa
                [0.02, 0.70, 0.01],
                [0.90, 0.05, 0.06],
            ]
        )
        correct_gain = np.array([3, 2, 1])
        correct_rot = np.array(
            [
                [0.80, 0.03, 0.04],  # noqa
                [0.01, 0.70, 0.02],
                [0.06, 0.05, 0.90],
            ]
        )
        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)
        np.testing.assert_allclose(res_rot, correct_rot)
        np.testing.assert_allclose(res_gain, correct_gain)

    def test_refine_rotation_matrix_float_off_diagonal_2x2(self) -> None:
        # INFO: Tests where the 3x3 matrix is not reordered, but the 2x2 submatrix is.

        # NOTE: Case rm == 0.
        gain = np.array([1, 2, 3])
        rot = np.array(
            [
                [0.90, 0.04, 0.03],  # noqa
                [0.01, 0.02, 0.80],
                [0.06, 0.70, 0.05],
            ]
        )
        correct_gain = np.array([1, 3, 2])
        correct_rot = np.array(
            [
                [0.90, 0.04, 0.03],  # noqa
                [0.01, 0.80, 0.02],
                [0.06, 0.05, 0.70],
            ]
        )
        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)
        np.testing.assert_allclose(res_rot, correct_rot)
        np.testing.assert_allclose(res_gain, correct_gain)

        # NOTE: Case rm == 1.
        gain = np.array([1, 2, 3])
        rot = np.array(
            [
                [0.04, 0.03, 0.80],  # noqa
                [0.02, 0.90, 0.01],
                [0.70, 0.05, 0.06],
            ]
        )
        correct_gain = np.array([3, 2, 1])
        correct_rot = np.array(
            [
                [0.80, 0.03, 0.04],  # noqa
                [0.02, 0.90, 0.01],
                [0.06, 0.05, 0.70],
            ]
        )
        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)
        np.testing.assert_allclose(res_rot, correct_rot)
        np.testing.assert_allclose(res_gain, correct_gain)

        # NOTE: Case rm == 2.
        gain = np.array([1, 2, 3])
        rot = np.array(
            [
                [0.03, 0.80, 0.04],  # noqa
                [0.70, 0.01, 0.02],
                [0.05, 0.06, 0.90],
            ]
        )
        correct_gain = np.array([2, 1, 3])
        correct_rot = np.array(
            [
                [0.80, 0.03, 0.04],  # noqa
                [0.01, 0.70, 0.02],
                [0.05, 0.06, 0.90],
            ]
        )
        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)
        np.testing.assert_allclose(res_rot, correct_rot)
        np.testing.assert_allclose(res_gain, correct_gain)

    def test_refine_rotation_matrix_negative_diagonal(self):
        gain = np.array([1, 2, 3])
        rot = np.array(
            [
                [-0.9, 0.1, 0.1],  # noqa
                [0.1, -0.8, 0.1],
                [0.1, 0.1, -0.7],
            ]
        )
        correct_gain = np.array([1, 2, 3])
        correct_rot = np.array(
            [
                [0.9, -0.1, -0.1],  # noqa
                [-0.1, 0.8, -0.1],
                [-0.1, -0.1, 0.7],
            ]
        )

        res_gain, res_rot = fit_functions.refine_rotation_matrix(gain, rot)
        np.testing.assert_allclose(res_rot, correct_rot)
        np.testing.assert_allclose(res_gain, correct_gain)
