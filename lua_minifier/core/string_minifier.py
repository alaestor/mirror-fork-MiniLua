"""
String Minifier
Normalizes and compresses Lua/Luau string and number literals.

Strategies:
  - Convert long-bracket strings to short strings when safe
  - Normalize escape sequences (\\97 → \\a, redundant escapes removed)
  - Choose the quote style that results in fewer escapes (' vs ")
  - Compact decimal/hex escape sequences
  - Number: 1.0→1., 0.5→.5, 1e+03→1e3, 0x00FF→0xFF, Luau 1_000→1000
"""

import re


# Named escapes recognized by Lua
_NAMED_ESCAPES: dict = {
    "\a": "\\a",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\v": "\\v",
    "\\": "\\\\",
}


# ------------------------------------------------------------------ #
#  Public API                                                        #
# ------------------------------------------------------------------ #

def minify_string(token_value: str) -> str:
    """
    Given the raw string token (including surrounding quotes/brackets),
    return the most compact valid Lua/Luau representation.
    Returns the original unchanged on any error.
    """
    if not token_value:
        return token_value

    try:
        if token_value.startswith("["):
            return _compress_long_string(token_value)

        quote = token_value[0]
        if quote not in ('"', "'"):
            return token_value

        if len(token_value) < 2 or token_value[-1] != quote:
            return token_value
        inner = _decode_short_string(token_value[1:-1], quote)
        encoded = _encode_short_string(inner)
        return min((encoded, token_value), key=lambda value: len(value.encode("utf-8")))
    except Exception:
        # Never crash — return original token on any parse error
        return token_value


def minify_number(token_value: str) -> str:
    """
    Compress a numeric literal to its shortest valid Lua representation.
    Returns the original unchanged if compression is unsafe.
    """
    if not token_value:
        return token_value

    try:
        return _compress_number(token_value)
    except Exception:
        return token_value


# ------------------------------------------------------------------ #
#  Number compression                                                #
# ------------------------------------------------------------------ #

def _compress_number(v: str) -> str:
    # Strip Luau numeric separators (1_000_000 → 1000000)
    v = v.replace("_", "")

    lo = v.lower()

    # Hex float (0x1.8p+1) — preserve structure, fix exponent sign
    if lo.startswith("0x") and ("p" in lo or "." in lo):
        return _compress_hex_float(v)

    # Plain hex integer (0xFF)
    if lo.startswith("0x"):
        hex_part = v[2:]
        # Remove leading zeros but keep at least one digit
        stripped = hex_part.lstrip("0") or "0"
        # Use uppercase hex digits for readability / convention
        return "0x" + stripped.upper()

    # Work on spelling only. Python floats lose Lua's integer/float distinction,
    # overflow to infinity, and can round large integer literals.
    if re.fullmatch(r"[+-]?[0-9]+", v):
        sign = v[0] if v[0] in "+-" else ""
        return sign + (v.lstrip("+-").lstrip("0") or "0")

    if re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", v):
        return _compact_float_str(v)

    return v


def _compress_hex_float(v: str) -> str:
    """
    Normalise hex float exponent: 0x1.8P+1 → 0x1.8p1
    """
    lo = v.lower()
    if "p" not in lo:
        return v
    mantissa, exp_part = lo.split("p", 1)
    sign = "-" if exp_part.startswith("-") else ""
    exp_digits = exp_part.lstrip("+-").lstrip("0") or "0"
    return f"{mantissa}p{sign}{exp_digits}"


def _compact_float_str(s: str) -> str:
    """
    Remove trailing zeros and normalise exponent notation.
    """
    s = s.lower()
    if "e" in s:
        mantissa, exp = s.split("e", 1)
        mantissa = _strip_trailing_zeros(mantissa).rstrip(".")
        sign = "-" if exp.startswith("-") else ""
        digits = exp.lstrip("+-").lstrip("0") or "0"
        return f"{mantissa}e{sign}{digits}"
    return _strip_trailing_zeros(s)


def _strip_trailing_zeros(s: str) -> str:
    """Trim insignificant decimal zeros without changing float syntax."""
    if "." not in s:
        return s
    s = s.rstrip("0")
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    if s in (".", "-.", "+."):
        return s.replace(".", "0.")
    return s


# ------------------------------------------------------------------ #
#  String decode / encode                                            #
# ------------------------------------------------------------------ #

def _decode_short_string(inner: str, quote: str) -> bytes:
    """
    Decode Lua bytes. Latin-1 fragments preserve byte values until joining.
    Dialect-sensitive escapes remain unchanged through the public fallback.
    """
    result = []
    i = 0
    length = len(inner)

    while i < length:
        ch = inner[i]
        if ch != "\\":
            if ch == quote or ch in "\r\n":
                raise ValueError("unescaped quote or newline")
            result.append(ch.encode("utf-8").decode("latin-1"))
            i += 1
            continue

        i += 1
        if i >= length:
            raise ValueError("unfinished escape")

        esc = inner[i]

        if   esc == "a":  result.append("\a"); i += 1
        elif esc == "b":  result.append("\b"); i += 1
        elif esc == "f":  result.append("\f"); i += 1
        elif esc == "n":  result.append("\n"); i += 1
        elif esc == "r":  result.append("\r"); i += 1
        elif esc == "t":  result.append("\t"); i += 1
        elif esc == "v":  result.append("\v"); i += 1
        elif esc == "\\":  result.append("\\"); i += 1
        elif esc == "'":  result.append("'");  i += 1
        elif esc == '"':  result.append('"');  i += 1
        elif esc == "\n": result.append("\n"); i += 1  # line continuation
        elif esc == "\r":
            # \r or \r\n line continuation
            result.append("\n")
            i += 1
            if i < length and inner[i] == "\n":
                i += 1
        elif esc in "xuz":
            # Lua 5.1 treats these literally; newer dialects interpret them.
            # With no target dialect, only keeping the source is safe.
            raise ValueError("dialect-sensitive escape")
        elif esc in "0123456789":
            # \ddd — up to three decimal digits, value 0-255
            digits = ""
            while i < length and inner[i] in "0123456789" and len(digits) < 3:
                digits += inner[i]
                i += 1
            val = int(digits)
            if val > 255:
                # Invalid bytes must leave the original literal unchanged.
                raise ValueError("decimal escape outside byte range")
            else:
                result.append(chr(val))
        else:
            # Dialects differ on unknown escapes; preserve the source token.
            raise ValueError("unsupported escape")

    return "".join(result).encode("latin-1")


def _encode_short_string(s: bytes) -> str:
    """
    Encode Lua bytes back to the shortest valid Lua string literal,
    choosing between single and double quotes automatically.
    """
    single = _encode_with_quote(s, "'")
    double = _encode_with_quote(s, '"')
    return single if len(single) <= len(double) else double


def _encode_with_quote(s: bytes, quote: str) -> str:
    buf = [quote]
    for i, code in enumerate(s):
        ch = chr(code)
        if ch == quote:
            buf.append("\\" + quote)
        elif ch == "\\":
            buf.append("\\\\")
        elif ch in _NAMED_ESCAPES:
            buf.append(_NAMED_ESCAPES[ch])
        elif code < 32 or code >= 127:
            # Lua consumes at most three decimal digits, including source digits.
            followed_by_digit = i + 1 < len(s) and 48 <= s[i + 1] <= 57
            buf.append(f"\\{code:03d}" if followed_by_digit else f"\\{code}")
        else:
            buf.append(ch)
    buf.append(quote)
    return "".join(buf)


# ------------------------------------------------------------------ #
#  Long string compression                                           #
# ------------------------------------------------------------------ #

def _compress_long_string(s: str) -> str:
    """
    Try to convert a long-bracket string [[...]] to a shorter short string.
    Falls back to original if the content contains characters that would
    require complex escaping or if the result would be longer.
    """
    if not s.startswith("["):
        return s

    # Determine bracket level
    i = 1
    while i < len(s) and s[i] == "=":
        i += 1

    if i >= len(s) or s[i] != "[":
        return s  # not a valid long bracket

    level = i - 1
    open_bracket  = "[" + "=" * level + "["
    close_bracket = "]" + "=" * level + "]"

    close_pos = s.rfind(close_bracket)
    if close_pos == -1:
        return s

    content = s[len(open_bracket):close_pos]

    # Long strings strip exactly one leading newline
    if content.startswith("\n"):
        content = content[1:]

    # Don't convert if content has null bytes (Lua strings can have them
    # in long form, but short string encoding is lossy for \0 in some runtimes)
    if "\0" in content:
        return s

    short = _encode_short_string(content.encode("utf-8"))

    # Only use short form if it's actually shorter or equal length
    return short if len(short) <= len(s) else s
