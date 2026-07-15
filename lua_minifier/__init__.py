"""
minilua
A Lua / Luau source code minifier supporting Lua 5.1–5.4 and Luau (Roblox).

Programmatic API:

    from lua_minifier.core import Minifier, MinifyOptions

    opts = MinifyOptions(remove_comments=True, rename_locals=True)
    result = Minifier(opts).minify(source_code)
    print(result.output)
    print(f"Saved {result.savings_pct:.1f}%")
"""

__version__ = "1.1.0"
__author__  = "Ardo"

from lua_minifier.core import Minifier, MinifyOptions, MinifyResult, MinifyError

__all__ = ["Minifier", "MinifyOptions", "MinifyResult", "MinifyError"]
