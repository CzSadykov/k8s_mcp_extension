"""Command validation helpers."""

from __future__ import annotations

import shlex

ALLOWED_K8S_TOOLS = {"kubectl", "istioctl", "helm", "argocd"}
ALLOWED_UNIX_COMMANDS = {
    "grep",
    "sed",
    "awk",
    "cut",
    "sort",
    "uniq",
    "wc",
    "head",
    "tail",
    "tr",
    "find",
    "jq",
    "yq",
    "tee",
    "cat",
}
FORBIDDEN_TOKENS = (";", "&&", "||", ">", "<", "$(", "`")


def validate_command(command: str) -> None:
    """Validate a command string."""

    if any(token in command for token in FORBIDDEN_TOKENS):
        raise ValueError("Shell control operators and redirections are not allowed")

    segments = [segment.strip() for segment in command.split("|")]
    if not segments or not segments[0]:
        raise ValueError("Command must not be empty")

    _validate_segment(segments[0], allowed=ALLOWED_K8S_TOOLS)
    for segment in segments[1:]:
        _validate_segment(segment, allowed=ALLOWED_UNIX_COMMANDS)


def _validate_segment(segment: str, allowed: set[str]) -> None:
    args = shlex.split(segment)
    if not args:
        raise ValueError("Command segment must not be empty")
    if args[0] not in allowed:
        raise ValueError(f"Command '{args[0]}' is not allowed in this position")
