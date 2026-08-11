"""Targeted edits to 86Box-style INI config files."""

from __future__ import annotations

import configparser
import io


def set_values(cfg_text: str, values: dict[tuple[str, str], str]) -> str:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # preserve key case (86Box keys are case-sensitive)
    parser.read_string(cfg_text)
    for (section, key), value in values.items():
        if not parser.has_section(section):
            parser.add_section(section)
        parser.set(section, key, value)
    out = io.StringIO()
    parser.write(out, space_around_delimiters=True)
    return out.getvalue()
