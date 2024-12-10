# Copyright (c) 2021-2025, Thomas Aglassinger
# All rights reserved. Distributed under the BSD 3-Clause License.
import os
from typing import Optional

TEMPLATES_FOLDER = os.path.join(os.path.dirname(__file__), "templates")

# Generic example IP address. This particular address has been used as example
# on <https://en.wikipedia.org/wiki/IP_address>.
EXAMPLE_IP_ADDRESS = "172.16.254.1"


def text_content(text_path: str) -> str:
    with open(text_path, encoding="utf-8") as text_file:
        return text_file.read()


class DataError(Exception):
    def __init__(self, path: str, message: str, line_number: Optional[int] = None):
        assert path
        assert line_number >= 0
        assert message

        base_name = os.path.basename(path)
        error_message = f"{base_name}:"
        if line_number is not None:
            error_message += f"{line_number + 1}:"
        error_message += " " + message
        super().__init__(error_message)
