#!/usr/bin/env python3
"""Extract one version section from CHANGELOG.md for GitHub Release notes."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def normalize_version(tag: str) -> str:
    tag = tag.strip()
    if tag.startswith(("v", "V")):
        tag = tag[1:]
    return tag


def extract_section(text: str, version: str) -> str:
    # Accept examples such as:
    #   ## 1.2.0
    #   ## 1.2.0 - ReQRemeshify fork
    #   ## [1.2.0] - 2026-08-17
    heading = re.compile(
        rf"^##\s+(?:\[)?{re.escape(version)}(?:\])?(?:\s|$).*?$",
        re.MULTILINE,
    )
    match = heading.search(text)
    if not match:
        raise ValueError(f"No CHANGELOG section found for version {version!r}")

    body_start = match.end()
    next_heading = re.search(r"^##\s+", text[body_start:], re.MULTILINE)
    body_end = body_start + next_heading.start() if next_heading else len(text)

    body = text[body_start:body_end].strip()
    if not body:
        raise ValueError(f"CHANGELOG section for {version!r} is empty")

    return body + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag", help="Git tag, e.g. v1.2.0 or 1.2.0")
    parser.add_argument("changelog", nargs="?", default="CHANGELOG.md")
    parser.add_argument("output", nargs="?", default="release-notes.md")
    args = parser.parse_args()

    version = normalize_version(args.tag)
    changelog_path = Path(args.changelog)
    output_path = Path(args.output)

    if not version:
        print("error: empty version/tag", file=sys.stderr)
        return 2
    if not changelog_path.is_file():
        print(f"error: {changelog_path} does not exist", file=sys.stderr)
        return 2

    try:
        notes = extract_section(changelog_path.read_text(encoding="utf-8"), version)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_path.write_text(notes, encoding="utf-8")
    print(f"Release notes for {version} -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
