"""Parsing helpers shared by the pack loader: YAML documents, front matter, and body placeholders."""

import re
from typing import Any

import yaml

from bank_agent.domain.decision import ParamValue
from bank_agent.domain.money import Money

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]{0,63})\}")


class PackProblems:
    """Collects every problem found while loading, so one run reports them all."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, path: str, message: str) -> None:
        self.items.append(f"{path}: {message}")

    def __bool__(self) -> bool:
        return bool(self.items)


def load_yaml(path: str, text: str, problems: PackProblems) -> Any:
    """Parse a YAML document with the safe loader; a parse error is recorded and gives ``None``."""
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        problems.add(path, f"invalid YAML ({type(error).__name__})")
        return None


def split_front_matter(path: str, text: str, problems: PackProblems) -> tuple[Any, str] | None:
    """Return the parsed front matter and the stripped body, or ``None`` when the file has no front matter."""
    match = _FRONT_MATTER.fullmatch(text.replace("\r\n", "\n"))
    if match is None:
        problems.add(path, "a clause file starts with a front matter block between --- lines")
        return None
    front = load_yaml(path, match[1], problems)
    return front, match[2].strip()


def placeholders(body: str) -> frozenset[str]:
    return frozenset(PLACEHOLDER.findall(body))


def stray_braces(body: str) -> bool:
    """True when a brace remains after removing the valid placeholders."""
    remainder = PLACEHOLDER.sub("", body)
    return "{" in remainder or "}" in remainder


def is_renderable(value: ParamValue) -> bool:
    """Placeholders may name integers, strings, and amounts; never booleans or code lists."""
    return isinstance(value, Money | str) or (isinstance(value, int) and not isinstance(value, bool))
