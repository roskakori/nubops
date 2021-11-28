# Copyright (c) 2021, Thomas Aglassinger
# All rights reserved. Distributed under the BSD 3-Clause License.
from unittest import TestCase

from nubops.build import COMMAND_FAIL2BAN, COMMAND_NGINX_DJANGO, COMMAND_SET_TIMEZONE
from nubops.command import main_without_logging_setup


class CommandTest(TestCase):
    def test_can_show_help(self):
        with self.assertRaises(SystemExit):
            main_without_logging_setup(["--help"])

    def test_can_show_nginx_django_help(self):
        with self.assertRaises(SystemExit):
            main_without_logging_setup([COMMAND_NGINX_DJANGO, "--help"])

    def test_can_show_fail2ban_help(self):
        with self.assertRaises(SystemExit):
            main_without_logging_setup([COMMAND_FAIL2BAN, "--help"])

    def test_can_show_set_timezone_help(self):
        with self.assertRaises(SystemExit):
            main_without_logging_setup([COMMAND_SET_TIMEZONE, "--help"])

    def test_can_show_version(self):
        with self.assertRaises(SystemExit):
            main_without_logging_setup(["--version"])

    def test_can_build_nginx_django(self):
        main_without_logging_setup(["--mode", "show", "nginx-django", "test", "example", "www.example.com"])

    def test_can_build_fail2ban(self):
        main_without_logging_setup(["--mode", "show", "fail2ban"])
