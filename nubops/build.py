# Copyright (c) 2021, Thomas Aglassinger
# All rights reserved. Distributed under the BSD 3-Clause License.
import enum
import glob
import os
import os.path
import re
import string
import tempfile
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from nubops import log
from nubops._common import TEMPLATES_FOLDER, DataError, text_content

SUBPARSER_ARGUMENT = "subparser_name"

ARGUMENT_NAME_REGEX = re.compile("^[a-zA-Z][a-zA-Z0-9-]*$")
COMMAND_NAME_REGEX = ARGUMENT_NAME_REGEX

COMMAND_NGINX_DJANGO = "nginx-django"
COMMAND_FAIL2BAN = "fail2ban"
COMMAND_SET_TIMEZONE = "set-timezone"

_KEY_LINE_REGEX = re.compile(r"^\s*(?P<key>[a-z][a-z0-9_]*)\s*:\s*(?P<value>.+)\s*$")
_TARGET_KEY = "target"
_VALID_KEYS = [_TARGET_KEY]


class BuildError(Exception):
    pass


class BuildMode(enum.Enum):
    SHOW = "show"
    WRITE = "write"
    OVERWRITE = "overwrite"


_BUILD_MODE_TO_LOG_VERB_MAP = {
    BuildMode.OVERWRITE: "overwriting",
    BuildMode.SHOW: "showing",
    BuildMode.WRITE: "writing",
}


class _BuildParserState(enum.Enum):
    AT_HEADER = "at_header"
    AFTER_TARGET = "after_target"
    AT_CONTENT = "at_content"


class _ScriptKind(enum.Enum):
    AFTER = "after"
    BEFORE = "before"
    INSTALL = "install"

    @property
    def sh_name(self):
        return f"{self.value}.sh"


def symbol_name_from(argument_name: str) -> str:
    return argument_name.replace("-", "_")


def resolved_symbol_to_value_map(
    parser: ArgumentParser, arguments: Namespace, symbols_to_resolve: List[str]
) -> Dict[str, Optional[Any]]:
    def create_symbol_name_to_argument_value_map():
        return {
            symbol_name_from(argument_name): argument_value
            for argument_name, argument_value in vars(arguments).items()
            if argument_name
            not in [
                "func",  # Remove callback from ArgumentParser.set_defaults().
                SUBPARSER_ARGUMENT,  # Remove internal argument to store the name of the subparser used.
            ]
        }

    def resolve_argument_values(symbol_name_to_argument_value_map):
        for symbol_to_resolve in symbols_to_resolve:
            try:
                argument_value = symbol_name_to_argument_value_map[symbol_to_resolve]
            except KeyError:
                assert False, (
                    f"symbol {symbol_to_resolve!r} must be part of arguments: "
                    f"{sorted(symbol_name_to_argument_value_map.keys())}"
                )
            else:
                try:
                    resolved_symbol_value = resolved_value(
                        f"argument {symbol_to_resolve}", argument_value, symbol_name_to_argument_value_map
                    )
                except BuildError as error:
                    parser.error(str(error))  # Raises SystemExit and thus terminates this function.
                else:
                    symbol_name_to_argument_value_map[symbol_to_resolve] = resolved_symbol_value

    result = create_symbol_name_to_argument_value_map()
    resolve_argument_values(result)
    return result


def resolved_value(name: str, template_text: str, symbol_to_value_map: Dict[str, str]):
    try:
        return string.Template(template_text).substitute(symbol_to_value_map)
    except KeyError as error:
        raise BuildError(f"cannot resolve symbol {name} because it references missing symbol: {error}") from error
    except Exception as error:
        raise BuildError(f"cannot resolve {name}: {error}") from error


def resolved_line(
    name: str, source_path: str, line_number: int, template_text: str, symbol_to_value_map: Dict[str, str]
) -> str:
    try:
        return string.Template(template_text).substitute(symbol_to_value_map)
    except KeyError as error:
        raise DataError(
            source_path, f"cannot resolve {name} because of missing symbol: {error}", line_number
        ) from error
    except Exception as error:
        raise DataError(source_path, f"cannot resolve {name}: {error}", line_number) from error


@dataclass
class BuildContent:
    template_path: str
    target_folder: str
    symbol_to_value_map: Dict[str, str]
    target_path: str = field(init=False)
    content_template: str = field(init=False)
    first_content_line_number: int = field(init=False)

    def __post_init__(self):
        log.info("reading %s", self.template_path)
        self.target_path = ""
        self.content_template = ""
        parser_state = _BuildParserState.AT_HEADER
        self.first_content_line_number = 0
        with open(self.template_path, encoding="utf-8") as service_file:
            for line_number, line_with_newline in enumerate(service_file):
                line = line_with_newline.rstrip("\n")
                is_empty_line = line.strip() == ""
                if parser_state == _BuildParserState.AT_HEADER:
                    is_comment_line = line.lstrip().startswith("#")
                    if is_empty_line or is_comment_line:
                        pass
                    else:
                        key_value_match = _KEY_LINE_REGEX.match(line)
                        if key_value_match is None:
                            raise DataError(
                                self.template_path, f"line must match 'key: value' but is: {line}", line_number
                            )
                        key = key_value_match.group("key")
                        if key not in _VALID_KEYS:
                            raise DataError(
                                self.template_path, f"key is {key!r} but must be one of: {_VALID_KEYS}", line_number
                            )
                        value = key_value_match.group("value")
                        if key == _TARGET_KEY:
                            try:
                                self.target_path = self._resolved("target_path", self.template_path, line_number, value)
                                if self.target_path.startswith("/"):
                                    self.target_path = os.path.join(self.target_folder, self.target_path[1:])
                            except Exception as error:
                                raise DataError(
                                    self.template_path,
                                    f"cannot resolve target path: {error}",
                                    self.first_content_line_number,
                                ) from error
                            parser_state = _BuildParserState.AFTER_TARGET
                        else:
                            assert False
                elif parser_state == _BuildParserState.AFTER_TARGET:
                    if not is_empty_line:
                        self.content_template = line_with_newline
                        self.first_content_line_number = line_number
                        parser_state = _BuildParserState.AT_CONTENT
                elif parser_state == _BuildParserState.AT_CONTENT:
                    self.content_template += line_with_newline
                else:
                    assert False
        if not self.target_path:
            raise DataError(self.template_path, "target must be set", 0)
        if self.first_content_line_number is None:
            raise DataError(self.template_path, "content template must be set", line_number)

    def write(self, mode: BuildMode):
        log.info("%s %s", _BUILD_MODE_TO_LOG_VERB_MAP[mode], self.target_path)
        resolved_content = self._resolved(
            "content", self.template_path, self.first_content_line_number, self.content_template
        )
        if mode in (BuildMode.OVERWRITE, BuildMode.WRITE):
            if mode == BuildMode.OVERWRITE and os.path.exists(self.target_path):
                raise BuildError(
                    "cannot write existing target file, use --mode=overwrite to overwrite: " + self.target_path,
                )
            with open(self.target_path, "w", encoding="utf-8") as target_file:
                target_file.write(resolved_content)
        else:
            assert mode == BuildMode.SHOW, f"mode={mode}"

    def _resolved(self, name: str, source_path: str, line_number: int, template_text: str):
        return resolved_line(name, source_path, line_number, template_text, self.symbol_to_value_map)


class OpsBuilder:
    def __init__(self, command: str, symbol_to_value_map: Dict[str, str], mode: BuildMode, target_folder: str = "/"):
        assert command is not None
        assert COMMAND_NAME_REGEX.match(command) is not None, f"name {command} must match {COMMAND_NAME_REGEX.pattern}"
        assert symbol_to_value_map is not None
        assert mode is not None
        assert target_folder is not None

        self._name = symbol_name_from(command)
        self._symbol_to_value_map = symbol_to_value_map
        self._mode = mode
        self._target_folder = target_folder
        self._templates_folder = os.path.join(TEMPLATES_FOLDER, self._name)
        log.info("reading templates from %s", self._templates_folder)
        self._build_contents = self._create_build_contents()
        self._script_kind_to_content_map = self._create_script_kind_name_to_content_map()
        self._has_to_run_shell_scripts = mode in (BuildMode.OVERWRITE, BuildMode.WRITE) and target_folder == "/"

        assert (
            self._build_contents or self._script_kind_to_content_map
        ), f"template {self.name!r} must have entries for at least one of the content maps"

    @property
    def name(self):
        return self._name

    def _create_build_contents(self) -> List[BuildContent]:
        result = []
        glob_pattern = os.path.join(TEMPLATES_FOLDER, self._name, "*")
        for template_path in glob.iglob(glob_pattern):
            if os.path.isfile(template_path):
                result.append(BuildContent(template_path, self._target_folder, self._symbol_to_value_map))
        return result

    def _create_script_kind_name_to_content_map(self) -> Dict[_ScriptKind, str]:
        result = {}
        command_templates_folder = os.path.join(self._templates_folder, "commands")
        for script_kind in _ScriptKind:
            script_path = os.path.join(command_templates_folder, f"{script_kind.value}.sh")
            try:

                script_template = text_content(script_path)
                result[script_kind] = resolved_line(
                    f"script {script_kind.sh_name}", script_path, 0, script_template, self._symbol_to_value_map
                )
            except FileNotFoundError:
                pass  # No template, nothing to add.
            except OSError as error:
                raise DataError(script_path, f"cannot read command template: {error}") from error
        return result

    def build(self):
        self._run_script(_ScriptKind.INSTALL)
        self._run_script(_ScriptKind.BEFORE)
        self._write_contents()
        self._run_script(_ScriptKind.AFTER)

    def _run_script(self, script_kind: _ScriptKind):
        scrip_content = self._script_kind_to_content_map.get(script_kind)
        script_name = script_kind.sh_name
        if scrip_content is not None:
            with tempfile.NamedTemporaryFile(
                "w+", encoding="utf-8", prefix=f"nubops_{script_kind.value}_", suffix=".sh"
            ) as shell_file:
                if self._has_to_run_shell_scripts:
                    log.info("running %s from %s", script_name, shell_file.name)
                    shell_file.write(scrip_content)
                    shell_file.seek(0)
                else:
                    log.info("would run %s from %s\n%s", script_name, shell_file.name, scrip_content)

    def _write_contents(self):
        for build_content in self._build_contents:
            build_content.write(self._mode)
