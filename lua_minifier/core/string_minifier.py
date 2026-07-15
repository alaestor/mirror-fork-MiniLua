"""
String Minifier
Normalizes and compresses Lua/Luau string and number literals.

Strategies:
  - Convert long-bracket strings to short strings when safe
  - Normalize escape sequences (\\97 → \\a, redundant escapes removed)
  - Choose the quote style that results in fewer escapes (' vs ")
  - Compact decimal/hex escape sequences
  - Number: 1.0→1, 0.5→.5, 1e+03→1e3, 0x00FF→0xFF, Luau 1_000→1000
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

        inner = _decode_short_string(token_value[1:-1], quote)
        return _encode_short_string(inner)
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

    # Try integer
    try:
        int_val = int(v, 0)
        return str(int_val)
    except ValueError:
        pass

    # Float
    try:
        f = float(v)
        candidates = []
        for fmt in (repr(f), f"{f:g}", _compact_float_str(v)):
            if fmt and _float_round_trips(fmt, f):
                candidates.append(fmt)
        if candidates:
            return min(candidates, key=len)
    except (ValueError, OverflowError):
        pass

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
        mantissa = _strip_trailing_zeros(mantissa)
        sign = "-" if exp.startswith("-") else ""
        digits = exp.lstrip("+-").lstrip("0") or "0"
        return f"{mantissa}e{sign}{digits}"
    return _strip_trailing_zeros(s)


def _strip_trailing_zeros(s: str) -> str:
    """
    1.500 → 1.5, 1.0 → 1, 0.5 → .5, -0.5 → -.5
    """
    if "." not in s:
        return s
    s = s.rstrip("0")
    if s.endswith("."):
        s = s[:-1]               # "1." → "1"
    if s.startswith("0."):
        s = s[1:]                # "0.5" → ".5"
    elif s.startswith("-0."):
        s = "-" + s[2:]          # "-0.5" → "-.5"
    return s or "0"


def _float_round_trips(candidate: str, original: float) -> bool:
    try:
        return float(candidate) == original
    except (ValueError, OverflowError):
        return False


# ------------------------------------------------------------------ #
#  String decode / encode                                            #
# ------------------------------------------------------------------ #

def _decode_short_string(inner: str, quote: str) -> str:
    """
    Decode all escape sequences in a Lua short string body to a Python str.
    Handles: \\a \\b \\f \\n \\r \\t \\v \\\\ \\' \\" \\xHH \\u{H+} \\ddd \\z
    """
    result = []
    i = 0
    length = len(inner)

    while i < length:
        ch = inner[i]
        if ch != "\\":
            result.append(ch)
            i += 1
            continue

        i += 1
        if i >= length:
            break

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
        elif esc == "x":
            # \xHH — exactly two hex digits
            hex2 = inner[i+1:i+3]
            if len(hex2) == 2 and all(c in "0123456789abcdefABCDEF" for c in hex2):
                result.append(chr(int(hex2, 16)))
                i += 3
            else:
                result.append("x"); i += 1  # malformed, keep as-is
        elif esc == "u":
            # \u{HHHH}
            if i + 1 < length and inner[i+1] == "{":
                end = inner.find("}", i + 2)
                if end != -1:
                    code_str = inner[i+2:end]
                    try:
                        result.append(chr(int(code_str, 16)))
                        i = end + 1
                    except (ValueError, OverflowError):
                        result.append("u"); i += 1
                else:
                    result.append("u"); i += 1
            else:
                result.append("u"); i += 1
        elif esc == "z":
            # \z skips following whitespace
            i += 1
            while i < length and inner[i] in " \t\n\r":
                i += 1
        elif esc.isdigit():
            # \ddd — up to three decimal digits, value 0-255
            digits = ""
            while i < length and inner[i].isdigit() and len(digits) < 3:
                digits += inner[i]
                i += 1
            val = int(digits)
            if val > 255:
                # Out of byte range — keep as decimal escape
                result.append(f"\\{digits}")
            else:
                result.append(chr(val))
        else:
            # Unknown escape — keep literally
            result.append(esc)
            i += 1

    return "".join(result)


def _encode_short_string(s: str) -> str:
    """
    Encode a Python str back to the shortest valid Lua string literal,
    choosing between single and double quotes automatically.
    """
    single = _encode_with_quote(s, "'")
    double = _encode_with_quote(s, '"')
    return single if len(single) <= len(double) else double


def _encode_with_quote(s: str, quote: str) -> str:
    buf = [quote]
    for ch in s:
        code = ord(ch)
        if ch == quote:
            buf.append("\\" + quote)
        elif ch == "\\":
            buf.append("\\\\")
        elif ch in _NAMED_ESCAPES:
            buf.append(_NAMED_ESCAPES[ch])
        elif code < 32 or code == 127:
            # Use decimal escape; use short form where possible
            buf.append(f"\\{code}")
        elif code > 127:
            # Keep high-byte chars as-is (Lua strings are byte strings)
            buf.append(ch)
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

    short = _encode_short_string(content)

    # Only use short form if it's actually shorter or equal length
    return short if len(short) <= len(s) else s
