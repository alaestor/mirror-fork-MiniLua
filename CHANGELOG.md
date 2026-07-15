# Changelog

All notable changes to **minilua** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.1.0] — 2025-05-22

### Added
- **Executor / exploit global protection** — 80+ executor function names
  (`getrawmetatable`, `hookfunction`, `syn`, `readfile`, `Drawing`,
  `setclipboard`, `rconsoleprint`, `setthreadidentity`, `mouse1click`,
  and many more) are now permanently protected from renaming when
  `--rename-locals` is active.
- **Luau numeric separator support** — `1_000_000` is now correctly
  compressed to `1000000`.
- **Hex float normalization** — `0x1.8P+1` is now correctly lowercased
  and sign-stripped to `0x1.8p1`.
- **102-test suite** — expanded from 43 to 102 tests covering separators,
  renamer correctness, executor globals, Luau syntax, and edge cases.

### Fixed
- **Critical: parameter name collision in renamer** — `local function f(a, b)`
  previously gave the function name and its first parameter the same short
  name (e.g. both became `a`). Root cause: the substitute pass was creating
  fresh empty child scopes, discarding all mappings from the collect pass.
  Fixed by sharing a single scope tree across both passes.
- **Critical: comments not emitted when `--no-comments` flag was unset** —
  `_assemble` only processed tokens in `_REAL_TYPES`, so comment tokens
  were silently dropped even when the user opted to keep them.
  Fixed by emitting comment tokens directly with a trailing newline.
- **Separator: keyword followed by unary `-` or `~`** — expressions like
  `not -1` and `return -1` could lose the required space between the keyword
  and the operator. Fixed by adding explicit separator rules for these cases.
- **Separator: single `.` followed by `.`** — could accidentally form `..`
  (concat operator). Fixed with an explicit `.`+`.` separator rule.
- **Number: hex float exponent letter was uppercased** — `0x1p4` was
  incorrectly emitted as `0x1P4`. Fixed in `_compress_hex_float`.
- **Renamer: `local function` scope boundary** — the function name is now
  correctly defined in the *outer* scope while parameters are defined in
  the *inner* (body) scope, preventing cross-scope name collisions.
- **Renamer: for-loop variable scope** — numeric and generic `for` loop
  variables are now correctly scoped to the loop body, not the enclosing block.
- **String minifier: `\0` in long strings** — long strings containing null
  bytes are no longer converted to short strings, as the conversion is lossy
  in some Lua runtimes.
- **String minifier: `\<newline>` continuation** — backslash-newline
  continuation sequences inside short strings are now decoded correctly.
- **Number minifier: no longer crashes on empty input** — `minify_number("")`
  now returns `""` instead of raising an exception.
- All minification paths now wrap in `try/except`; the original token is
  returned unchanged if any parse error occurs (no silent data loss).

### Changed
- **Renamer architecture** — replaced dual independent scope stacks with a
  single shared scope *tree* (`Scope.children` list + child cursor). This is
  the structural fix that resolves the parameter collision and scope-boundary
  bugs above.
- `_needs_separator` rewritten with explicit, documented rules for every
  edge case; previously relied on implicit heuristics that missed several
  patterns.
- `_assemble` now handles comment, space, and newline tokens explicitly
  instead of skipping all non-`_REAL_TYPES` tokens unconditionally.

---

## [1.0.0] — 2025-05-21

Initial public release.

### Added
- Lua / Luau lexer (`core/lexer.py`) — full token stream including trivia
  (whitespace, comments, newlines). Supports Lua 5.1–5.4 and Luau keywords
  (`type`, `continue`, `export`, `::`, type annotations).
- Core minification pipeline (`core/minifier.py`) with `MinifyOptions` and
  `MinifyResult` dataclasses.
- String & number literal compressor (`core/string_minifier.py`):
  - Short string: optimal quote style, named escape normalization,
    `\xHH` / `\u{H+}` / `\ddd` decoding.
  - Long string → short string conversion where safe.
  - Number: `1.0→1`, `0.5→.5`, `1e+03→1e3`, `0x00FF→0xFF`.
- Local variable renamer (`core/renamer.py`) — scope-aware two-pass renamer
  generating compact names (`a`, `b`, …, `z`, `aa`, …).
- CLI (`cli.py`) powered by Click:
  - Single file, batch glob, recursive directory modes.
  - `--stdout` / stdin (`-`) for pipeline use.
  - `--rename-locals`, `--keep-newlines`, `--in-place`, `--overwrite`.
  - Color-aware stats output via colorama.
- File utilities (`utils/file_utils.py`) — glob expansion, file discovery,
  output path derivation.
- Stats formatter (`utils/formatter.py`) — human-readable size and savings.
- 43-test suite covering lexer, string/number compression, and minifier.
- `pip install minilua` / `minilua` CLI entry point.

---

[Unreleased]: https://github.com/USERNAME/minilua/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/USERNAME/minilua/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/USERNAME/minilua/releases/tag/v1.0.0
