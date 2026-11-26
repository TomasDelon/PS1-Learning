#!/usr/bin/env python3
"""Preserve one Rmd and its local image bytes without modifying the attempt.

Usage: python3 tools/snapshot_attempt.py lesson/L04_Travail.Rmd evidence/L04-first
The destination must not exist. No network requests or R execution occur.
"""
from __future__ import annotations

import argparse
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit


class SnapshotError(ValueError):
    pass


class ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img":
            for key, value in attrs:
                if key.lower() == "srcset" and value:
                    raise SnapshotError("HTML srcset needs explicit local-image normalization first")
                if key.lower() == "src" and value:
                    self.paths.append(value)


def _link_target(s: str) -> str:
    s = s.strip()
    if s.startswith("<"):
        end = s.find(">")
        if end < 0:
            raise SnapshotError("Unclosed angle bracket in an image target")
        return s[1:end]
    # A title is separated from the path by whitespace and a quote.
    s = re.split(r'\s+[\"\']', s, maxsplit=1)[0].strip()
    return re.sub(r"\\([ ()])", r"\1", s)


def image_targets(text: str) -> list[str]:
    """Handle usual Visual Markdown images, reference images and HTML img.

    Literal knitr::include_graphics() strings are supported. Computed paths and
    unusual Markdown syntax are rejected when detected, rather than silently
    producing an incomplete snapshot.
    """
    code_blocks = re.findall(r"(?ms)^```[^\n]*\n(.*?)^```\s*$", text)
    prose = re.sub(r"(?ms)^```[^\n]*\n.*?^```\s*$", "", text)
    paths = []
    # Balance parentheses in Markdown targets (paths may contain parentheses).
    for match in re.finditer(r"!\[(?:\\.|[^\]])*\]\(", prose):
        start, depth, escaped, quoted = match.end(), 1, False, None
        angle = False
        for pos in range(start, len(prose)):
            char = prose[pos]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if quoted:
                if char == quoted:
                    quoted = None
                continue
            if char in "\"'" and pos > start and prose[pos-1].isspace():
                quoted = char
                continue
            if char == "<":
                angle = True
            elif char == ">":
                angle = False
            elif not angle and char == "(":
                depth += 1
            elif not angle and char == ")":
                depth -= 1
                if depth == 0:
                    paths.append(_link_target(prose[start:pos]))
                    break
        else:
            raise SnapshotError("Unclosed Markdown image target")

    definitions = {
        " ".join(m.group(1).lower().split()): _link_target(m.group(2))
        for m in re.finditer(r"(?m)^\s{0,3}\[([^\]]+)\]:\s*(.+)$", prose)
    }
    for m in re.finditer(r"!\[([^\]]*)\](?:\[([^\]]*)\])?(?!\()", prose):
        label = m.group(2) or m.group(1)
        key = " ".join(label.lower().split())
        if key in definitions:
            paths.append(definitions[key])
        else:
            raise SnapshotError(f"Missing reference image definition: {label}")

    html = ImageParser()
    html.feed(prose)
    paths.extend(html.paths)

    for code in code_blocks:
        for m in re.finditer(r"(?:knitr::)?include_graphics\s*\((.*?)\)", code, re.S):
            argument = m.group(1).strip()
            if re.fullmatch(r'''["'][^"']+["']''', argument):
                paths.append(argument[1:-1])
            else:
                raise SnapshotError("include_graphics must use one literal path for this snapshot tool")
    return sorted(set(paths))


def _safe_relative(target: str, base: Path) -> Path:
    target = unescape(target)
    split = urlsplit(target)
    if split.scheme or split.netloc:
        raise SnapshotError(f"External or embedded image is unsupported: {target}")
    if split.query:
        raise SnapshotError(f"Image query string is unsupported: {target}")
    relative = Path(unquote(split.path))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise SnapshotError(f"Image must stay below the lesson folder: {target}")
    if "\\" in str(relative):
        raise SnapshotError("Use portable forward slashes in local image paths")
    resolved = (base / relative).resolve()
    if not resolved.is_relative_to(base):
        raise SnapshotError(f"Image resolves outside the lesson folder: {target}")
    if not resolved.is_file():
        raise SnapshotError(f"Missing image: {target}")
    return relative


def snapshot(source: Path, destination: Path) -> dict:
    source = source.resolve(strict=True)
    if source.suffix.lower() != ".rmd" or not source.is_file():
        raise SnapshotError("Source must be an existing Rmd file")
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise SnapshotError("Destination already exists; choose a new snapshot name")
    document = source.read_bytes()
    text = document.decode("utf-8")
    base = source.parent.resolve()
    payloads = {Path(source.name): document}
    references = []
    for target in image_targets(text):
        relative = _safe_relative(target, base)
        if relative == Path("snapshot_manifest.json") or relative == Path(source.name):
            raise SnapshotError("Image target collides with snapshot metadata or document")
        payloads[relative] = (base / relative).read_bytes()
        references.append({"target": target, "snapshot_path": relative.as_posix()})
    manifest = {
        "schema_version": "1.0.0",
        "kind": "first_attempt_snapshot",
        "document": source.name,
        "image_references": references,
        "files": [{"path": p.as_posix(), "size_bytes": len(data),
                   "sha256": hashlib.sha256(data).hexdigest()}
                  for p, data in sorted(payloads.items(), key=lambda item: str(item[0]))],
        "learning_state_modified": False,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(exist_ok=False)
    try:
        for relative, data in payloads.items():
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (destination / "snapshot_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(destination)
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        result = snapshot(args.source, args.destination)
    except (OSError, UnicodeError, SnapshotError) as error:
        parser.exit(2, f"Snapshot refused: {error}\n")
    print(json.dumps({"status": "PASS", "destination": str(args.destination),
                      "files": len(result["files"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
