"""Find / replace the agent-blurb block inside agent instruction files.

The block is delimited by:
  <!-- aec-blurb:start ... -->
  ...
  <!-- aec-blurb:end -->

Surrounding user content is never modified.
"""

from dataclasses import dataclass
from typing import Optional

from aec.lib.agent_blurb.render import START_MARKER_PREFIX, END_MARKER


class BlockNotFoundError(Exception):
    pass


class MalformedBlockError(Exception):
    pass


@dataclass
class BlockLocation:
    start: int  # index of '<' of start marker
    end: int    # index just after newline following end marker


def find_block(content: str) -> Optional[BlockLocation]:
    """Locate a single well-formed block. Raises MalformedBlockError on duplicates
    or unclosed blocks. Returns None if no block exists.
    """
    starts = []
    pos = 0
    while True:
        idx = content.find(START_MARKER_PREFIX, pos)
        if idx == -1:
            break
        starts.append(idx)
        pos = idx + 1
    if not starts:
        return None
    if len(starts) > 1:
        raise MalformedBlockError(f"duplicate aec-blurb start markers at offsets {starts}")
    start = starts[0]
    end_idx = content.find(END_MARKER, start)
    if end_idx == -1:
        raise MalformedBlockError("aec-blurb start found but missing end marker")
    end = end_idx + len(END_MARKER)
    if end < len(content) and content[end] == "\n":
        end += 1
    return BlockLocation(start=start, end=end)


def replace_block(content: str, new_block: str) -> str:
    """Replace the existing block with new_block, or append if none exists.

    `new_block` must end with a newline.
    """
    loc = find_block(content)
    if loc is None:
        if content and not content.endswith("\n"):
            content += "\n"
        if content and not content.endswith("\n\n"):
            content += "\n"
        return content + new_block
    return content[:loc.start] + new_block + content[loc.end:]
