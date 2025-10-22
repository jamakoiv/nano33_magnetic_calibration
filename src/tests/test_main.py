import unittest

import main


class test_arguments(unittest.TestCase):
    def test_verbose(self) -> None:
        args = main.parse_args(["-v"])
        self.assertEqual(args.verbose, 1)

        args = main.parse_args(["-vv"])
        self.assertEqual(args.verbose, 2)

        args = main.parse_args(["-v", "--verbose"])
        self.assertEqual(args.verbose, 2)

        args = main.parse_args(["--verbose"])
        self.assertEqual(args.verbose, 1)

        args = main.parse_args(["--verbose", "--verbose"])
        self.assertEqual(args.verbose, 2)
