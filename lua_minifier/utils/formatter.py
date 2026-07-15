"""
Output Formatter
Utilities for rendering minification stats and results to the terminal.
"""

from typing import Optional


def format_size(n: int) -> str:
    """
    Human-readable byte size.
    """
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.2f} MB"


def format_stats(result, filename: Optional[str] = None) -> str:
    """
    Return a formatted stats string for a MinifyResult.
    Compatible with both color and plain output.
    """
    lines = []

    header = f"  File     : {filename}" if filename else "  Result"
    lines.append(header)
    lines.append(f"  Original : {format_size(result.original_size)} ({result.original_size:,} bytes)")
    lines.append(f"  Minified : {format_size(result.minified_size)} ({result.minified_size:,} bytes)")
    lines.append(f"  Saved    : {format_size(result.savings_bytes)} ({result.savings_pct:.1f}%)")

    if result.errors:
        lines.append(f"  Warnings : {len(result.errors)}")
        for w in result.errors[:5]:
            lines.append(f"    ! {w}")
        if len(result.errors) > 5:
            lines.append(f"    ... and {len(result.errors) - 5} more")

    return "\n".join(lines)


def color_stats(result, filename: Optional[str] = None) -> str:
    """
    Same as format_stats but with ANSI colors via colorama.
    """
    try:
        from colorama import Fore, Style
        has_color = True
    except ImportError:
        has_color = False

    raw = format_stats(result, filename)
    if not has_color:
        return raw

    lines = raw.splitlines()
    colored = []
    for line in lines:
        if "File" in line or "Result" in line:
            colored.append(Fore.CYAN + line + Style.RESET_ALL)
        elif "Original" in line:
            colored.append(line)
        elif "Minified" in line:
            colored.append(Fore.GREEN + line + Style.RESET_ALL)
        elif "Saved" in line:
            pct = result.savings_pct
            color = Fore.GREEN if pct >= 20 else Fore.YELLOW if pct >= 5 else Fore.WHITE
            colored.append(color + line + Style.RESET_ALL)
        elif "Warnings" in line or line.strip().startswith("!"):
            colored.append(Fore.YELLOW + line + Style.RESET_ALL)
        else:
            colored.append(line)
    return "\n".join(colored)
