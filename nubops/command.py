# Copyright (c) 2021, Thomas Aglassinger
# All rights reserved. Distributed under the BSD 3-Clause License.
import argparse
import logging
import re
import sys
from typing import Dict

from nubops import __version__, log
from nubops._common import DataError
from nubops.build import (
    COMMAND_NAME_REGEX,
    COMMAND_SET_TIMEZONE,
    SUBPARSER_ARGUMENT,
    BuildError,
    BuildMode,
    OpsBuilder,
    resolved_symbol_to_value_map,
)

COMMAND_NGINX_DJANGO = "nginx-django"

SYMBOL_NAME_REGEX = re.compile("^[a-zA-Z][a-zA-Z0-9_]*$")
_COMMAND_TO_SYMBOLS_TO_RESOLVE_MAP = {COMMAND_NGINX_DJANGO: ["domain", "project_dir"]}
for _command, _symbols in _COMMAND_TO_SYMBOLS_TO_RESOLVE_MAP.items():
    assert (
        COMMAND_NAME_REGEX.match(_command) is not None
    ), f"command {_command!r} must match {COMMAND_NAME_REGEX.pattern}"
    for _symbol in _symbols:
        assert (
            SYMBOL_NAME_REGEX.match(_symbol) is not None
        ), f"symbol {_symbol!r} for command {_command!r} must match {SYMBOL_NAME_REGEX.pattern}"

# Regex for internet domain, for example "www.example.com".
# Source: <https://www.geeksforgeeks.org/how-to-validate-a-domain-name-using-regular-expression/>
_DOMAIN_REGEX = re.compile("^((?!-)[A-Za-z0-9-]{1,63}(?<!-)\\.)+[A-Za-z]{2,6}")


def parsed_template_and_symbols(args=None):
    parser = argparse.ArgumentParser(description="Build ")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    template_parsers = parser.add_subparsers(
        dest=SUBPARSER_ARGUMENT,
        description="available commands to install a service based on a template",
        title="template commands",
    )

    _add_nginx_django_parser(template_parsers)
    _add_set_timezone_parser(template_parsers)

    arguments = parser.parse_args(args)
    subparser_name = getattr(arguments, SUBPARSER_ARGUMENT)
    symbols_to_resolve = _COMMAND_TO_SYMBOLS_TO_RESOLVE_MAP.get(subparser_name, [])
    symbol_to_value_map = resolved_symbol_to_value_map(parser, arguments, symbols_to_resolve)
    return subparser_name, symbol_to_value_map


def _add_nginx_django_parser(template_parsers):
    nginx_django_parser = _added_template_parser(
        template_parsers,
        COMMAND_NGINX_DJANGO,
        "Django application within nginx web server",
        has_environment=True,
        has_project=True,
    )
    nginx_django_parser.add_argument(
        "domain",
        metavar="DOMAIN",
        type=_domain_type,
        help="domain the service can be reached at, for example: www,example,com",
    )
    nginx_django_parser.add_argument(
        "--group",
        "-g",
        default="www-data",
        metavar="GROUP",
        help="user group the service should run in, default; %(default)s",
    )
    nginx_django_parser.add_argument(
        "--project-dir",
        "-p",
        default="/var/www/${environment}/${project}",
        metavar="DIRECTORY",
        help=(
            "base folder the django project is located in; "
            "can use ${option} to refer to other options; default; %(default)s"
        ),
    )
    nginx_django_parser.add_argument(
        "--user",
        "-u",
        default="www-data",
        metavar="USERNAME",
        help="user the service should run in, default; %(default)s",
    )


def _add_set_timezone_parser(template_parsers):
    set_timezone_parser = _added_template_parser(
        template_parsers,
        COMMAND_SET_TIMEZONE,
        "permanently set system timezone",
    )
    set_timezone_parser.add_argument(
        "timezone",
        default="UTC",
        metavar="TIMEZONE",
        nargs="?",
        help="name of system time zone to set; default: %(default)s",
    )


def _added_template_parser(
    template_parsers,
    name: str,
    help_text: str,
    has_environment: bool = False,
    has_project: bool = False,
):
    result = template_parsers.add_parser(name, help=help_text)
    if has_environment:
        result.add_argument(
            "environment",
            metavar="ENVIRONMENT",
            help='environment the service runs ins, typically something like "production", "test", "ci" or "local"',
        )
    if has_project:
        result.add_argument(
            "project",
            metavar="PROJECT",
            type=_symbol_name_type,
            help="name of the service derived from project name",
        )
    result.set_defaults(func=_build_from_args)
    return result


def _symbol_name_type(argument_value: str) -> str:
    if not SYMBOL_NAME_REGEX.match(argument_value):
        raise argparse.ArgumentTypeError(
            "value must be a symbol name "
            "starting with an ASCII letter and continuing with ASCII letters, digits or underscore"
        )
    return argument_value


def _domain_type(argument_value: str) -> str:
    if not _DOMAIN_REGEX.match(argument_value):
        raise argparse.ArgumentTypeError(
            f"value is {argument_value!r} must match the regular expression {_DOMAIN_REGEX.pattern}"
        )
    return argument_value


def _build_from_args(args):
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
        "nginx_django",
        BuildMode.LOG,
        symbol_to_value_map,
    )


def build_service(name: str, mode: BuildMode, name_to_value_map: Dict[str, str]):
    for symbol, value in sorted(name_to_value_map.items()):
        assert " " not in value, f"{symbol}={value!r}"

    ops_builder = OpsBuilder(name, name_to_value_map, mode)
    ops_builder.build()


def main_without_logging_setup(args=None) -> int:
    result = 1
    try:
        service_name, symbol_to_value_map = parsed_template_and_symbols(args)
        print(symbol_to_value_map)
        build_service(
            service_name,
            BuildMode.LOG,
            symbol_to_value_map,
        )
    except (BuildError, DataError) as error:
        log.error(error)
    except Exception as error:
        log.exception(error)
    else:
        result = 0

    return result


def main(args=None) -> int:
    logging.basicConfig(level=logging.INFO)
    return main_without_logging_setup(args)


if __name__ == "__main__":
    sys.exit(main())
