# Copyright (c) 2021, Thomas Aglassinger
# All rights reserved. Distributed under the BSD 3-Clause License.
import argparse
import enum
import glob
import logging
import os.path
import re
import string
import sys
from typing import Dict

from . import __version__, log

TEMPLATES_FOLDER = os.path.join(os.path.dirname(__file__), "templates")
KEY_LINE_REGEX = re.compile(r"^\s*(?P<key>[a-z][a-z0-9_]*)\s*:\s*(?P<value>.+)\s*$")
TARGET_KEY = "target"
VALID_KEYS = [TARGET_KEY]


def _parsed_args(args=None):
    parser = argparse.ArgumentParser(description="Build ")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(args)


class BuildMode(enum.Enum):
    LOG = "log"
    FILE = "file"


class BuildParserState(enum.Enum):
    AT_HEADER = "at_header"
    AFTER_TARGET = "after_target"
    AT_CONTENT = "AT_content"


class DataError(Exception):
    def __init__(self, path: str, line_number: int, message: str):
        assert path
        assert line_number >= 0
        assert message

        base_name = os.path.basename(path)
        error_message = f"{base_name}:{line_number + 1}: {message}"
        super().__init__(error_message)


def build_service(name: str, mode: BuildMode, name_to_value_map: Dict[str, str]):
    for symbol, value in sorted(name_to_value_map.items()):
        assert " " not in value, f"{symbol}={value!r}"

    for service_path in glob.iglob(os.path.join(TEMPLATES_FOLDER, name, "*")):
        if os.path.isfile(service_path):
            build_file(service_path, mode, name_to_value_map)


def _resolved(template_text: str, symbol_to_value_map) -> str:
    return string.Template(template_text).substitute(symbol_to_value_map)


def build_file(service_path: str, mode: BuildMode, symbol_to_value_map: Dict[str, str]):
    log.info("reading %s", service_path)
    target_path = None
    content_template = ""
    parser_state = BuildParserState.AT_HEADER
    first_content_line_number = 0
    with open(service_path, encoding="utf-8") as service_file:
        for line_number, line_with_newline in enumerate(service_file):
            line = line_with_newline.rstrip("\n")
            is_empty_line = line.strip() == ""
            if parser_state == BuildParserState.AT_HEADER:
                is_comment_line = line.lstrip().startswith("#")
                if is_empty_line or is_comment_line:
                    pass
                else:
                    key_value_match = KEY_LINE_REGEX.match(line)
                    if key_value_match is None:
                        raise DataError(service_path, line_number, f"line must match 'key: value' but is: {line}")
                    key = key_value_match.group("key")
                    if key not in VALID_KEYS:
                        raise DataError(service_path, line_number, f"key is {key!r} but must be one of: {VALID_KEYS}")
                    value = key_value_match.group("value")
                    if key == TARGET_KEY:
                        try:
                            target_path = _resolved(value, symbol_to_value_map)
                        except Exception as error:
                            raise DataError(
                                service_path, first_content_line_number, f"cannot resolve target path: {error}"
                            ) from error
                        parser_state = BuildParserState.AFTER_TARGET
                        log_message = ("writing" if mode == BuildMode.FILE else "printing") + " %s"
                        log.info(log_message, target_path)
                    else:
                        assert False
            elif parser_state == BuildParserState.AFTER_TARGET:
                if not is_empty_line:
                    content_template = line_with_newline
                    first_content_line_number = line_number
                    parser_state = BuildParserState.AT_CONTENT
            elif parser_state == BuildParserState.AT_CONTENT:
                content_template += line_with_newline
            else:
                assert False
    if target_path is None:
        raise DataError(service_path, 0, "target must be set")
    try:
        resolved_content = _resolved(content_template, symbol_to_value_map)
    except KeyError as error:
        raise DataError(
            service_path, first_content_line_number, f"cannot resolve content because of unknown symbol: {error}"
        ) from error
    except Exception as error:
        raise DataError(service_path, first_content_line_number, f"cannot resolve content: {error}") from error
    _write_build_file(target_path, mode, resolved_content)


def _write_build_file(target_path: str, mode: BuildMode, resolved_content: str):
    if mode == BuildMode.FILE:
        log.info("writing %s", target_path)
        with open(target_path, "w", encoding="utf-8") as target_file:
            target_file.write(resolved_content)
    elif mode == BuildMode.LOG:
        log.info("would write %s\n%s", target_path, resolved_content)
    else:
        assert False


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
