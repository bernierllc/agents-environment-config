"""Parse org-config YAML files into raw (frontmatter, body) dict pairs.

Frontmatter is a YAML block delimited by `---` lines at the start of the file.
Body is the rest. Both are loaded with safe_load.
"""
from __future__ import annotations

from typing import Any

import yaml

from .errors import OrgConfigParseError

FRONTMATTER_DELIMITER = "---"


def parse_org_config_text(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        raise OrgConfigParseError(
            "config must begin with a YAML frontmatter block delimited by '---'"
        )

    try:
        end_idx = next(
            i for i, line in enumerate(lines[1:], start=1)
            if line.strip() == FRONTMATTER_DELIMITER
        )
    except StopIteration:
        raise OrgConfigParseError(
            "frontmatter block is not terminated with a closing '---' line"
        ) from None

    frontmatter_text = "\n".join(lines[1:end_idx])
    body_text = "\n".join(lines[end_idx + 1:])

    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
        body = yaml.safe_load(body_text) or {}
    except yaml.YAMLError as exc:
        raise OrgConfigParseError(f"YAML parse error: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise OrgConfigParseError("frontmatter must be a YAML mapping")
    if not isinstance(body, dict):
        raise OrgConfigParseError("body must be a YAML mapping")

    return frontmatter, body
