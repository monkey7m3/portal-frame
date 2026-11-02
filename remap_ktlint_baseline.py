#!/usr/bin/env python3
"""Remap a main-branch KtLint baseline onto unchanged lines in the working tree."""
from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: remap_ktlint_baseline.py <baseline.xml>", file=sys.stderr)
        return 2

    baseline_path = Path(sys.argv[1])
    tree = ET.parse(baseline_path)
    root = tree.getroot()
    kept = removed = 0

    for file_node in list(root.findall("file")):
        relative_path = file_node.get("name")
        if not relative_path:
            continue
        result = subprocess.run(
            ["git", "show", f"origin/main:app/{relative_path}"],
            check=False, capture_output=True, text=True,
        )
        current_path = Path("app") / relative_path
        if result.returncode != 0 or not current_path.is_file():
            removed += len(file_node.findall("error"))
            root.remove(file_node)
            continue

        old_lines = result.stdout.splitlines(keepends=True)
        new_lines = current_path.read_text(encoding="utf-8").splitlines(keepends=True)
        mapping: dict[int, int] = {}
        matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
        for old_start, new_start, length in matcher.get_matching_blocks():
            for offset in range(length):
                mapping[old_start + offset + 1] = new_start + offset + 1

        for error in list(file_node.findall("error")):
            line = error.get("line", "")
            new_line = mapping.get(int(line)) if line.isdigit() else None
            if new_line is None:
                file_node.remove(error)
                removed += 1
            else:
                error.set("line", str(new_line))
                kept += 1
        if not file_node.findall("error"):
            root.remove(file_node)

    ET.indent(tree, space="    ")
    tree.write(baseline_path, encoding="utf-8", xml_declaration=True)
    print(f"KtLint baseline remapped: kept {kept} unchanged-line findings; "
          f"removed {removed} findings on changed/removed lines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
