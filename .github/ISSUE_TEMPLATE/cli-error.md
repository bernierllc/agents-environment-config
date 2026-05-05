---
name: CLI error report
about: Report an error from the `aec` CLI (auto-linked from --debug output)
title: '[CLI ERROR] '
labels: bug, cli
assignees: ''
---

## What happened

<!-- One sentence: what command did you run, what did you expect, what did the CLI do instead? -->

## Command

```
# Paste the exact command you ran, e.g.
# aec upgrade
```

## Reproduction steps

1.
2.
3.

## Environment

- **OS / version**: <!-- e.g., macOS 15.1, Ubuntu 24.04 -->
- **Python version**: <!-- python3 --version -->
- **aec version**: <!-- aec version -->
- **Shell**: <!-- bash, zsh, fish -->

## Debug log

> Re-run the failing command with `--debug` (or `AEC_DEBUG=1`) and attach the
> log produced at `~/.agents-environment-config/logs/aec-debug.log`.
> The CLI redacts user paths and secret-shaped values before writing, but
> please skim it before posting and remove anything sensitive.

<details>
<summary>aec-debug.log</summary>

```
<!-- paste log contents here, or attach the file -->
```

</details>

## Additional context

<!-- Network conditions, recent changes, anything else that might help. -->
