import os
from typing import Optional


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
