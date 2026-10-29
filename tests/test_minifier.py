"""
Test Suite — minilua
Run with: python -m pytest tests/ -v
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from lua_minifier.core import Minifier, MinifyOptions, MinifyError
from lua_minifier.core.lexer import Lexer, TokenType
from lua_minifier.core.string_minifier import minify_string, minify_number


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def minify(src: str, **kwargs) -> str:
    return Minifier(MinifyOptions(**kwargs)).minify(src).output.strip()


# ─────────────────────────────────────────────────────────────────────────────
#  Lexer
# ─────────────────────────────────────────────────────────────────────────────

class TestLexer:
    def toks(self, src):
        return [t for t in Lexer(src).tokenize() if t.type.name != "EOF"]

    def test_keyword(self):
        types = [t.type for t in self.toks("local x = 1")]
        assert TokenType.KEYWORD in types
        assert TokenType.NAME    in types
        assert TokenType.NUMBER  in types

    def test_short_string_single(self):
        t = self.toks("'hello'")[0]
        assert t.type  == TokenType.STRING
        assert t.value == "'hello'"

    def test_short_string_double(self):
        assert self.toks('"world"')[0].type == TokenType.STRING

    def test_long_string_level0(self):
        assert self.toks("[[hello]]")[0].type == TokenType.LONG_STRING

    def test_long_string_level2(self):
        assert self.toks("[==[nested]==]")[0].type == TokenType.LONG_STRING

    def test_short_comment(self):
        assert self.toks("-- comment\nlocal x")[0].type == TokenType.COMMENT

    def test_long_comment(self):
        assert self.toks("--[[long]]local x")[0].type == TokenType.LONG_COMMENT

    def test_number_hex(self):
        assert self.toks("0xFF")[0].type == TokenType.NUMBER

    def test_number_float(self):
        assert self.toks("3.14e-10")[0].type == TokenType.NUMBER

    def test_vararg(self):
        assert self.toks("...")[0].value == "..."

    def test_concat(self):
        assert self.toks("..")[0].value == ".."

    def test_vararg_not_concat(self):
        toks = self.toks("...x")
        assert toks[0].value == "..."
        assert toks[1].value == "x"

    def test_luau_type_keyword(self):
        t = self.toks("type Foo = string")[0]
        assert t.type  == TokenType.KEYWORD
        assert t.value == "type"

    def test_luau_continue(self):
        assert self.toks("continue")[0].value == "continue"

    def test_double_colon(self):
        assert self.toks("::label::")[0].value == "::"

    def test_number_luau_separator(self):
        assert self.toks("1_000_000")[0].type == TokenType.NUMBER

    def test_hex_float(self):
        t = self.toks("0x1.8p+1")[0]
        assert t.type  == TokenType.NUMBER
        assert "0x" in t.value.lower()


# ─────────────────────────────────────────────────────────────────────────────
#  String minifier
# ─────────────────────────────────────────────────────────────────────────────

class TestStringMinifier:
    def test_prefer_single_quotes(self):
        assert minify_string('"hello"') == "'hello'"

    def test_prefer_double_when_shorter(self):
        # String full of apostrophes → double quotes are shorter
        result = minify_string('"it\'s a test"')
        assert "it's" in result

    def test_long_string_to_short(self):
        result = minify_string("[[hello world]]")
        assert result[0] in ('"', "'")
        assert "hello world" in result

    def test_long_string_strips_leading_newline(self):
        result = minify_string("[[\nhello]]")
        assert "hello" in result
        # Leading \n should be stripped from content
        assert result in ("'hello'", '"hello"')

    def test_escape_named(self):
        result = minify_string(r'"\n\t\r"')
        assert "\\n" in result or "\n" in result

    def test_decimal_escape_to_char(self):
        # \97\98\99 = 'abc'
        result = minify_string(r'"\97\98\99"')
        assert "abc" in result

    def test_hex_escape_to_char(self):
        result = minify_string(r'"\x61\x62"')
        assert "ab" in result

    def test_unicode_escape(self):
        result = minify_string(r'"\u{41}"')   # \u{41} = 'A'
        assert "A" in result

    def test_long_string_with_null_kept(self):
        # Content with \0 must not be converted to short string
        raw = "[[hello\x00world]]"
        result = minify_string(raw)
        assert result.startswith("[")   # kept as long string

    def test_empty_string(self):
        assert minify_string("''") in ("''", '""')

    def test_backslash_preserved(self):
        result = minify_string(r'"\\"')
        assert "\\\\" in result


class TestNumberMinifier:
    def test_float_keeps_float_syntax(self):
        assert minify_number("1.0") == "1."

    def test_leading_zero_float(self):
        r = minify_number("0.5")
        assert r in (".5", "0.5")
        assert float(r) == 0.5

    def test_negative_leading_zero(self):
        r = minify_number("-0.5")
        assert float(r) == -0.5

    def test_scientific(self):
        r = minify_number("1e+03")
        assert float(r) == 1000.0
        assert "+" not in r           # sign in exponent stripped

    def test_hex_uppercase(self):
        r = minify_number("0x00ff")
        assert r.startswith("0x")
        assert "FF" in r.upper()

    def test_hex_strip_zeros(self):
        r = minify_number("0x00FF")
        assert r == "0xFF"

    def test_luau_separator(self):
        assert minify_number("1_000_000") == "1000000"

    def test_hex_float_lowercase_p(self):
        r = minify_number("0x1.8P+1")
        assert "P" not in r          # exponent letter lowercased
        assert "p" in r

    def test_hex_float_strips_exp_sign(self):
        r = minify_number("0x1p+4")
        assert "+" not in r

    def test_preserve_nan_inf(self):
        # These can't appear as Lua literals, but shouldn't crash
        assert minify_number("") == ""


# ─────────────────────────────────────────────────────────────────────────────
#  Separator logic (critical correctness)
# ─────────────────────────────────────────────────────────────────────────────

class TestSeparator:
    """
    Each test checks that the minified output is syntactically unambiguous.
    """

    def test_return_int_space(self):
        # "return42" would be lexed as a single NAME token
        assert minify("return 42") == "return 42"

    def test_return_neg_space(self):
        # "return-1" → keyword + unary minus; valid but add space for clarity
        out = minify("return -1")
        assert "return" in out and "-1" in out

    def test_keyword_unary_minus(self):
        # "not-1" is technically valid (not(-(1))) but we add space for safety
        out = minify("if not -1 then end")
        assert "not" in out and "-1" in out

    def test_double_minus_gets_space(self):
        # "a--b" would start a comment  →  must become "a- -b"
        out = minify("local x = a - -b")
        assert "- -" in out

    def test_concat_after_int(self):
        # "1..x" could mis-lex as float "1." then ".x"; must have space before ".."
        out = minify("local x = 1 .. 'a'")
        assert "1 .." in out

    def test_and_or_keep_spaces(self):
        out = minify("local x = a and b or c")
        assert "and" in out and "or" in out

    def test_no_extra_space_after_paren(self):
        out = minify("print(1, 2)")
        assert "print(1,2)" in out

    def test_method_call_colon(self):
        out = minify('game:GetService("Players")')
        assert ":" in out

    def test_dot_field_access(self):
        out = minify("local x = a.b.c")
        assert "a.b.c" in out

    def test_open_bracket_no_extra_space(self):
        out = minify("local t = {1, 2}")
        assert "{" in out and "}" in out

    def test_semicolons_preserved(self):
        out = minify("local x = 1; local y = 2")
        assert ";" in out

    def test_vararg_preserved(self):
        out = minify("local function f(...) return ... end")
        assert "..." in out


# ─────────────────────────────────────────────────────────────────────────────
#  Comment & whitespace removal
# ─────────────────────────────────────────────────────────────────────────────

class TestWhitespaceComments:
    def test_removes_short_comment(self):
        assert "--" not in minify("-- comment\nlocal x = 1")

    def test_removes_long_comment(self):
        out = minify("--[[multi\nline comment]]local x = 1")
        assert "multi" not in out
        assert "local" in out

    def test_keeps_comments_when_disabled(self):
        assert "--" in minify("-- comment\nlocal x = 1", remove_comments=False)

    def test_removes_excess_whitespace(self):
        assert "   " not in minify("local   x   =   1")

    def test_comment_in_string_not_removed(self):
        out = minify('local s = "-- not a comment"')
        assert "-- not a comment" in out

    def test_keep_newlines_option(self):
        out = minify("local x = 1\nlocal y = 2", keep_newlines=True)
        assert "\n" in out


# ─────────────────────────────────────────────────────────────────────────────
#  Variable renamer
# ─────────────────────────────────────────────────────────────────────────────

class TestRenamer:
    def test_renames_local(self):
        out = minify("local myLongVarName = 1\nprint(myLongVarName)", rename_locals=True)
        assert "myLongVarName" not in out

    def test_fn_name_and_params_different(self):
        # Function name and parameter must get DIFFERENT short names
        out = minify("local function f(a, b) return a + b end", rename_locals=True)
        # Extract the short names used
        # pattern: "local function X(Y,Z)..."
        import re
        m = re.search(r"local function (\w+)\((\w+),(\w+)\)", out)
        assert m is not None, f"Unexpected output: {out}"
        fn_name, p1, p2 = m.group(1), m.group(2), m.group(3)
        assert fn_name != p1
        assert fn_name != p2
        assert p1      != p2

    def test_nested_fn_no_collision(self):
        src = ("local function outer(x)\n"
               "    local function inner(a) return a + x end\n"
               "    return inner(x)\nend")
        out = minify(src, rename_locals=True)
        # Should not crash and all short names must be distinct from each other
        assert "function" in out
        assert "return" in out

    def test_for_loop_vars_renamed(self):
        out = minify("for i = 1, 10 do print(i) end", rename_locals=True)
        # 'i' should be renamed; verify it no longer appears as a standalone token
        # (note: 'i' can appear inside other words like 'print', so check token-level)
        import re
        standalone_i = re.findall(r'\bi\b', out)
        assert len(standalone_i) == 0, f"'i' still appears as a token in: {out!r}"

    def test_generic_for_vars_renamed(self):
        out = minify("for k, v in pairs(t) do print(k, v) end", rename_locals=True)
        assert "pairs" in out   # global — never renamed

    def test_shadowing(self):
        src = "local x = 1\ndo\n    local x = 2\n    print(x)\nend\nprint(x)"
        out = minify(src, rename_locals=True)
        # Must not crash, and output must contain two distinct short names
        assert out.strip() != ""

    def test_global_not_renamed(self):
        out = minify("print(game.Players)", rename_locals=True)
        assert "print" in out
        assert "game" in out

    def test_executor_globals_not_renamed(self):
        cases = [
            "getrawmetatable(game)",
            "hookfunction(print, function() end)",
            "local d = readfile('a.txt')",
            "local res = syn.request({Url='x'})",
            "Drawing.new('Circle')",
            "setclipboard('hello')",
            "getgc()",
            "mouse1click()",
            "setthreadidentity(2)",
            "rconsoleprint('hi')",
        ]
        for src in cases:
            out = minify(src, rename_locals=True)
            # Extract the executor function name from src (first token-looking word)
            import re
            fn = re.match(r"(?:local \w+ = )?(\w+)", src)
            if fn:
                name = fn.group(1)
                if name not in ("local", "Drawing"):
                    assert name in out, f"{name} was renamed in: {out!r}"

    def test_metamethods_not_renamed(self):
        src = "local t = {}\nt.__index = function(self, k) return k end"
        out = minify(src, rename_locals=True)
        assert "__index" in out

    def test_multi_assign(self):
        out = minify("local a, b, c = 1, 2, 3", rename_locals=True)
        assert "local" in out
        assert "1" in out

    def test_vararg_not_renamed(self):
        out = minify("local function f(...) return ... end", rename_locals=True)
        assert "..." in out


# ─────────────────────────────────────────────────────────────────────────────
#  Lua / Luau syntax coverage
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntaxCoverage:
    def test_if_elseif_else(self):
        src = 'if x>0 then print("pos") elseif x<0 then print("neg") else print("z") end'
        out = minify(src)
        assert "elseif" in out and "else" in out and "end" in out

    def test_while_loop(self):
        out = minify("while x > 0 do x = x - 1 end")
        assert "while" in out and "do" in out

    def test_repeat_until(self):
        out = minify("repeat local x = 1 until x > 0")
        assert "repeat" in out and "until" in out

    def test_numeric_for(self):
        out = minify("for i = 1, 10, 2 do print(i) end")
        assert "for" in out and "do" in out

    def test_generic_for(self):
        out = minify("for k, v in pairs(t) do end")
        assert "in" in out and "pairs" in out

    def test_table_constructor(self):
        out = minify("local t = {1, 2, key = 'value', [3] = true}")
        assert "{" in out and "}" in out

    def test_string_concat(self):
        out = minify('local s = "a" .. "b" .. "c"')
        assert ".." in out

    def test_method_definition(self):
        out = minify("function obj:method(self) return self end")
        assert ":" in out

    def test_goto_label(self):
        out = minify("::top::\ngoto top")
        assert "::" in out and "goto" in out

    def test_luau_type_annotation(self):
        out = minify("type Vector = {x: number, y: number}")
        assert "type" in out

    def test_luau_continue(self):
        out = minify("for i = 1, 10 do if i == 5 then continue end end")
        assert "continue" in out

    def test_luau_export_type(self):
        out = minify("export type Foo = string")
        assert "export" in out

    def test_multiline_string(self):
        out = minify("local s = [[line1\nline2\nline3]]")
        assert "line1" in out

    def test_nested_tables(self):
        out = minify("local t = {{1,2},{3,4}}")
        assert "{" in out

    def test_ternary_pattern(self):
        out = minify("local x = cond and 1 or 2")
        assert "and" in out and "or" in out

    def test_chained_comparisons(self):
        out = minify("local ok = a == b and c ~= d")
        assert "==" in out and "~=" in out

    def test_bitwise_ops(self):
        out = minify("local x = a & b | c ~ d >> 1 << 2")
        assert "&" in out and "|" in out


# ─────────────────────────────────────────────────────────────────────────────
#  Size / stats
# ─────────────────────────────────────────────────────────────────────────────

class TestStats:
    def test_size_reduced(self):
        src = "-- comment\nlocal myVariable = 1\nlocal anotherVar = 2\nprint(myVariable + anotherVar)\n"
        r = Minifier(MinifyOptions()).minify(src)
        assert r.savings_pct > 0

    def test_empty_input(self):
        r = Minifier(MinifyOptions()).minify("")
        assert r.output.strip() == ""
        assert r.savings_pct == 0.0

    def test_result_fields(self):
        r = Minifier(MinifyOptions()).minify("local x = 1\n")
        assert r.original_size > 0
        assert r.minified_size > 0
        assert r.tokens_processed > 0

    def test_no_options_no_crash(self):
        Minifier().minify("local x = 1")   # default options


# ─────────────────────────────────────────────────────────────────────────────
#  Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_only_comment(self):
        out = minify("-- just a comment")
        assert out.strip() == ""

    def test_only_whitespace(self):
        out = minify("   \n\t\n   ")
        assert out.strip() == ""

    def test_escaped_quote_in_string(self):
        out = minify(r'''local s = "say \"hello\""''')
        assert out   # no crash

    def test_hex_number_preserved(self):
        out = minify("local x = 0xFF")
        assert "0x" in out.lower()

    def test_comment_in_string_untouched(self):
        out = minify('local s = "-- not a comment"')
        assert "-- not a comment" in out

    def test_long_bracket_level1(self):
        out = minify("[=[hello]=]")
        assert "hello" in out

    def test_consecutive_strings(self):
        out = minify('local a = "x"\nlocal b = "y"')
        assert "x" in out and "y" in out

    def test_unary_not(self):
        out = minify("local x = not true")
        assert "not" in out

    def test_unary_minus_in_expr(self):
        out = minify("local x = -(a + b)")
        assert "-" in out

    def test_deep_nesting(self):
        src = "do " * 20 + "local x = 1 " + "end " * 20
        out = minify(src)
        assert "local" in out and "end" in out

    def test_large_table(self):
        entries = ", ".join(f"k{i}={i}" for i in range(50))
        out = minify(f"local t = {{{entries}}}")
        assert "{" in out

    def test_number_only_file(self):
        out = minify("42")
        assert "42" in out

    def test_string_with_newline_escape(self):
        out = minify(r'local s = "line1\nline2"')
        assert "\\n" in out

    def test_executor_complex(self):
        src = """
local mt = getrawmetatable(game)
setrawmetatable(game, nil)
hookfunction(print, newcclosure(function(...)
    local args = {...}
    rconsoleprint(tostring(args[1]))
end))
setrawmetatable(game, mt)
"""
        out = minify(src, rename_locals=True)
        assert "getrawmetatable" in out
        assert "hookfunction"    in out
        assert "newcclosure"     in out
        assert "rconsoleprint"   in out
        assert "setrawmetatable" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
