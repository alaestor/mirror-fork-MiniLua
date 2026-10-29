#!/usr/bin/env python3
"""
minilua — CLI entry point

Usage examples:
  minilua script.lua
  minilua script.lua -o out.lua
  minilua *.lua --output-dir build/
  minilua script.lua --rename-locals
  cat script.lua | minilua -
  minilua script.lua --no-strings --no-comments
  minilua . --recursive
"""

import sys
import os
from pathlib import Path
from typing import Optional

import click

try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

# Allow running from project root without install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lua_minifier.core import Minifier, MinifyOptions, MinifyError
from lua_minifier.utils import (
    discover_files, read_source, write_output,
    iter_files_with_output, color_stats, format_stats,
)


BANNER = r"""
  _                 __  __ _       _  __ _
 | |_   _  __ _   |  \/  (_)_ __ (_)/ _(_) ___ _ __
 | | | | |/ _` |  | |\/| | | '_ \| | |_| |/ _ \ '__|
 | | |_| | (_| |  | |  | | | | | | |  _| |  __/ |
 |_|\__,_|\__,_|  |_|  |_|_|_| |_|_|_| |_|\___|_|

  MiniLua  •  v1.1.0
"""

# ------------------------------------------------------------------ #
#  Helpers                                                           #
# ------------------------------------------------------------------ #

def _cprint(text: str, color: str = "", bold: bool = False):
    if HAS_COLOR:
        prefix = (Style.BRIGHT if bold else "") + color
        print(prefix + text + Style.RESET_ALL, file=sys.stderr)
    else:
        print(text, file=sys.stderr)


def _err(msg: str):
    _cprint(f"  ✗ {msg}", Fore.RED if HAS_COLOR else "")


def _ok(msg: str):
    _cprint(f"  ✓ {msg}", Fore.GREEN if HAS_COLOR else "")


def _info(msg: str):
    _cprint(f"  · {msg}", Fore.CYAN if HAS_COLOR else "")


# ------------------------------------------------------------------ #
#  CLI                                                               #
# ------------------------------------------------------------------ #

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("inputs", nargs=-1, metavar="FILE|DIR|GLOB...")
@click.option("-o", "--output",         default=None,  help="Output file path (single-file mode).")
@click.option("--output-dir", "-d",     default=None,  type=click.Path(), help="Output directory for batch mode.")
@click.option("--suffix",               default=".min.lua", show_default=True, help="Output filename suffix.")
@click.option("--in-place", "-i",       is_flag=True,  help="Overwrite input files (DANGEROUS).")
@click.option("--recursive", "-r",      is_flag=True,  help="Recurse into directories.")
@click.option("--stdout",               is_flag=True,  help="Print result to stdout instead of writing files.")
@click.option("--no-comments",          is_flag=True,  default=False, help="Keep comments (default: remove).")
@click.option("--no-whitespace",        is_flag=True,  default=False, help="Keep whitespace (default: remove).")
@click.option("--no-strings",           is_flag=True,  default=False, help="Skip string literal minification.")
@click.option("--no-numbers",           is_flag=True,  default=False, help="Skip number literal minification.")
@click.option("--rename-locals", "-R",  is_flag=True,  help="Rename local variables to short names.")
@click.option("--keep-newlines",        is_flag=True,  help="Preserve one newline per statement.")
@click.option("--quiet", "-q",          is_flag=True,  help="Suppress all output except errors.")
@click.option("--no-banner",            is_flag=True,  help="Hide the startup banner.")
@click.option("--overwrite", "-f",      is_flag=True,  help="Allow overwriting existing output files.")
@click.version_option("1.1.0", "-v", "--version")
def cli(
    inputs,
    output,
    output_dir,
    suffix,
    in_place,
    recursive,
    stdout,
    no_comments,
    no_whitespace,
    no_strings,
    no_numbers,
    rename_locals,
    keep_newlines,
    quiet,
    no_banner,
    overwrite,
):
    """
    \b
    Lua / Luau Minifier — compress Lua source files.

    Supports Lua 5.1–5.4 and Luau (Roblox) syntax.

    \b
    Examples:
      minilua script.lua
      minilua *.lua --output-dir dist/
      minilua src/ --recursive --rename-locals
      cat input.lua | minilua - --stdout
    """
    if not quiet and not no_banner:
        if HAS_COLOR:
            _cprint(BANNER, Fore.CYAN, bold=True)
        else:
            print(BANNER, file=sys.stderr)

    # Build options
    opts = MinifyOptions(
        remove_comments   = not no_comments,
        remove_whitespace = not no_whitespace,
        minify_strings    = not no_strings,
        minify_numbers    = not no_numbers,
        rename_locals     = rename_locals,
        keep_newlines     = keep_newlines,
    )
    minifier = Minifier(opts)

    # stdin mode
    if not inputs or (len(inputs) == 1 and inputs[0] == "-"):
        if not sys.stdin.isatty() or inputs:
            source = sys.stdin.read()
        else:
            _err("No input provided. Use FILE arguments or pipe via stdin.")
            _info("Run 'minilua --help' for usage.")
            sys.exit(1)

        try:
            result = minifier.minify(source)
        except MinifyError as e:
            _err(str(e))
            sys.exit(1)

        if stdout or not output:
            print(result.output, end="")
        else:
            out_path = Path(output)
            try:
                write_output(out_path, result.output, overwrite=overwrite)
                if not quiet:
                    _ok(f"Written → {out_path}")
            except OSError as e:
                _err(str(e)); sys.exit(1)

        if not quiet and not stdout:
            print(file=sys.stderr)
            print(color_stats(result) if HAS_COLOR else format_stats(result), file=sys.stderr)
        return

    # File mode
    input_list = list(inputs)
    out_dir = Path(output_dir) if output_dir else None

    all_inputs = discover_files(input_list, recursive=recursive)

    # Filter to only .lua / .luau files (unless user explicitly passes a file)
    lua_inputs = [
        f for f in all_inputs
        if f.suffix in (".lua", ".luau") or (len(all_inputs) == 1)
    ]

    if not lua_inputs:
        _err("No Lua/Luau files found matching the provided input(s).")
        sys.exit(1)

    if output and len(lua_inputs) != 1:
        _err("--output requires exactly one input file.")
        sys.exit(1)

    planned_outputs = list(iter_files_with_output(lua_inputs, out_dir, suffix, in_place))
    if output:
        planned_outputs = [(lua_inputs[0], Path(output))]

    # Reject ambiguous batches before writing anything, even with --overwrite.
    if not stdout:
        destinations = {}
        sources = {path.resolve() for path in lua_inputs}
        for source, destination in planned_outputs:
            resolved = destination.resolve()
            if resolved in destinations:
                _err(f"Output collision: {destinations[resolved]} and {source} both target {destination}")
                sys.exit(1)
            if resolved in sources and resolved != source.resolve():
                _err(f"Output collision: {destination} would replace another input file.")
                sys.exit(1)
            destinations[resolved] = source

    total_orig = 0
    total_mini = 0
    success = 0
    failed = 0

    for inp_path, out_path in planned_outputs:
        # Read
        try:
            source = read_source(inp_path)
        except (FileNotFoundError, IOError) as e:
            _err(f"Cannot read {inp_path}: {e}")
            failed += 1
            continue

        # Minify
        try:
            result = minifier.minify(source)
        except MinifyError as e:
            _err(f"{inp_path.name}: {e}")
            failed += 1
            continue

        # Write / print
        if stdout:
            print(result.output, end="")
        else:
            try:
                replacing_source = in_place and out_path.resolve() == inp_path.resolve()
                write_output(out_path, result.output, overwrite=(overwrite or replacing_source))
            except FileExistsError:
                _err(f"Output exists: {out_path}  (use -f to overwrite)")
                failed += 1
                continue
            except OSError as e:
                _err(str(e))
                failed += 1
                continue

        total_orig += result.original_size
        total_mini += result.minified_size
        success += 1

        if not quiet:
            if HAS_COLOR:
                print(color_stats(result, str(inp_path.name)), file=sys.stderr)
            else:
                print(format_stats(result, str(inp_path.name)), file=sys.stderr)
            if not stdout:
                _ok(f"→ {out_path}")
            print(file=sys.stderr)

    # Summary 
    if not quiet and len(lua_inputs) > 1:
        from lua_minifier.utils.formatter import format_size
        saved = total_orig - total_mini
        pct = (saved / total_orig * 100) if total_orig else 0
        _cprint(
            f"  ── Summary: {success} OK, {failed} failed  "
            f"| {format_size(total_orig)} → {format_size(total_mini)} "
            f"({pct:.1f}% saved) ──",
            Fore.CYAN if HAS_COLOR else "",
            bold=True,
        )

    if failed:
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
