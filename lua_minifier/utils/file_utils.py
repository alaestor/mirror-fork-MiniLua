"""
File Utilities
Handles file discovery, reading, and writing for batch operations.
"""

import os
import glob
import sys
from pathlib import Path
from typing import List, Tuple, Iterator, Optional


def discover_files(patterns: List[str], recursive: bool = False) -> List[Path]:
    """
    Expand a list of file paths / glob patterns into resolved Path objects.
    Duplicates are removed while preserving order.
    """
    seen = set()
    result = []
    for pattern in patterns:
        if recursive and "**" not in pattern:
            # Auto-wrap for recursive directory expansion
            p = Path(pattern)
            if p.is_dir():
                pattern = str(p / "**" / "*.lua")

        matched = glob.glob(pattern, recursive=recursive)
        if not matched:
            # Treat as literal path even if it doesn't exist yet (for writing)
            matched = [pattern]

        for m in matched:
            resolved = Path(m).resolve()
            if resolved not in seen:
                seen.add(resolved)
                result.append(resolved)
    return result


def read_source(path: Path) -> str:
    """
    Read a Lua source file. Raises FileNotFoundError or IOError on failure.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def write_output(path: Path, content: str, overwrite: bool = False) -> Path:
    """
    Write minified content to *path*.
    If overwrite is False and the file exists, raises FileExistsError.
    Returns the written path.
    """
    if not overwrite and path.exists():
        raise FileExistsError(f"Output file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def derive_output_path(
    input_path: Path,
    output_dir: Optional[Path] = None,
    suffix: str = ".min.lua",
    in_place: bool = False,
) -> Path:
    """
    Determine the output path for a given input file.

    Rules:
      - in_place=True  → overwrite the original file
      - output_dir set → put <name>.min.lua inside that directory
      - otherwise      → sibling file with suffix
    """
    if in_place:
        return input_path

    stem = input_path.stem
    # Remove any existing .min suffix to avoid .min.min
    if stem.endswith(".min"):
        stem = stem[:-4]

    out_name = stem + suffix

    if output_dir:
        return output_dir / out_name
    return input_path.parent / out_name


def iter_files_with_output(
    inputs: List[Path],
    output_dir: Optional[Path],
    suffix: str,
    in_place: bool,
) -> Iterator[Tuple[Path, Path]]:
    for inp in inputs:
        out = derive_output_path(inp, output_dir, suffix, in_place)
        yield inp, out
