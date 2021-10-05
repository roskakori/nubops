# Copyright (c) 2021, Thomas Aglassinger
# All rights reserved. Distributed under the BSD 3-Clause License.
import argparse
import logging
import sys
from typing import Dict

from nubops.build import BuildMode, OpsBuilder

from . import __version__


def _parsed_args(args=None):
    parser = argparse.ArgumentParser(description="Build ")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(args)


def build_service(name: str, mode: BuildMode, name_to_value_map: Dict[str, str]):
    for symbol, value in sorted(name_to_value_map.items()):
        assert " " not in value, f"{symbol}={value!r}"

    ops_builder = OpsBuilder(name, name_to_value_map, mode)
    ops_builder.build()


def main_without_logging_setup(args=None) -> int:
    result = 0
    environment_name = "production"
    project = "example"
    domain = f"www.{project}.com"

    symbol_to_value_map = {
        "domain": domain,
        "project": project,
    }
    symbol_to_value_map.update(
        {
            "group": "www-data",
            "project_dir": f"/var/www/{environment_name}/{project}",
            "user": "www-data",
        }
    )

    build_service(
        "django_nginx_gunicorn",
        BuildMode.LOG,
        symbol_to_value_map,
    )
    return result


def main(args=None) -> int:
    logging.basicConfig(level=logging.INFO)
    return main_without_logging_setup(args)


if __name__ == "__main__":
    sys.exit(main())
