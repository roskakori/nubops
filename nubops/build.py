import enum
import glob
import os
import os.path
import re
import string
from dataclasses import dataclass, field
from typing import Dict, List

from nubops import log
from nubops._common import DataError, text_content

TEMPLATES_FOLDER = os.path.join(os.path.dirname(__file__), "templates")
_KEY_LINE_REGEX = re.compile(r"^\s*(?P<key>[a-z][a-z0-9_]*)\s*:\s*(?P<value>.+)\s*$")
_TARGET_KEY = "target"
_VALID_KEYS = [_TARGET_KEY]


class BuildMode(enum.Enum):
    LOG = "log"
    FILE = "file"


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


@dataclass
class BuildContent:
    template_path: str
    symbol_to_value_map: Dict[str, str]
    target_path: str = field(init=False)
    content_template: str = field(init=False)
    first_content_line_number: int = field(init=False)

    def __post_init__(self):
        log.info("reading %s", self.template_path)
        self.target_path = None
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
                                self.target_path = self.resolved("target_path", self.template_path, line_number, value)
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
        if self.target_path is None:
            raise DataError(self.template_path, "target must be set", 0)
        if self.first_content_line_number is None:
            raise DataError(self.template_path, "content template must be set", line_number)

    def write(self, mode: BuildMode):
        log_message = ("writing" if mode == BuildMode.FILE else "printing") + " %s"
        log.info(log_message, self.target_path)
        resolved_content = self.resolved(
            "content", self.template_path, self.first_content_line_number, self.content_template
        )
        if mode == BuildMode.FILE:
            log.info("writing %s", self.target_path)
            with open(self.target_path, "w", encoding="utf-8") as target_file:
                target_file.write(resolved_content)
        elif mode == BuildMode.LOG:
            log.info("would write %s\n%s", self.target_path, resolved_content)
        else:
            assert False, f"mode={mode}"

    def resolved(self, name: str, source_path: str, line_number: int, template_text) -> str:
        try:
            return string.Template(template_text).substitute(self.symbol_to_value_map)
        except KeyError as error:
            raise DataError(
                source_path, f"cannot resolve {name} because of missing symbol: {error}", line_number
            ) from error
        except Exception as error:
            raise DataError(source_path, f"cannot resolve {name}: {error}", line_number) from error


class OpsBuilder:
    def __init__(self, name: str, symbol_to_value_map: Dict[str, str], mode: BuildMode):
        assert name is not None
        assert symbol_to_value_map is not None
        assert mode is not None

        self._name = name
        self._symbol_to_value_map = symbol_to_value_map
        self._mode = mode
        self._templates_folder = os.path.join(TEMPLATES_FOLDER, self._name)
        log.info("reading templates from %s", self._templates_folder)
        self._build_contents = self._create_build_contents()
        self._script_kind_to_content_map = self._create_script_kind_name_to_content_map()

        assert (
            self._build_contents or self._script_kind_to_content_map
        ), "template must have entries for at least one of the content maps"

    def _create_build_contents(self) -> List[BuildContent]:
        result = []
        glob_pattern = os.path.join(TEMPLATES_FOLDER, self._name, "*")
        for template_path in glob.iglob(glob_pattern):
            if os.path.isfile(template_path):
                result.append(BuildContent(template_path, self._symbol_to_value_map))
        return result

    def _create_script_kind_name_to_content_map(self) -> Dict[_ScriptKind, str]:
        result = {}
        command_templates_folder = os.path.join(self._templates_folder, "commands")
        for script_kind in _ScriptKind:
            script_path = os.path.join(command_templates_folder, f"{script_kind.value}.sh")
            try:
                result[script_kind] = text_content(script_path)
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
        scrip_template = self._script_kind_to_content_map.get(script_kind)
        script_name = script_kind.sh_name
        if scrip_template is not None:
            log.info("running %s", script_name)

    def _write_contents(self):
        for build_content in self._build_contents:
            build_content.write(self._mode)