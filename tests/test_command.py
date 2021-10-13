# Copyright (c) 2021, Thomas Aglassinger
# All rights reserved. Distributed under the BSD 3-Clause License.
from unittest import TestCase

from nubops.command import main_without_logging_setup


class CommandTest(TestCase):
    def test_can_show_help(self):
        with self.assertRaises(SystemExit):
            main_without_logging_setup(["--help"])

    def test_can_show_version(self):
        with self.assertRaises(SystemExit):
            main_without_logging_setup(["--version"])

    def test_can_build_nginx_django(self):
        main_without_logging_setup(["nginx-django", "test", "example", "www.example.com"])
