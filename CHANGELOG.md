# Changelog

All notable changes to **minilua** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- **Nix flake** — CLI packaging, a development shell, and checks running
  the test suite against Lua 5.1–5.4 and Luau.
- **Behavioral regression tests** — execute original and minified programs
  with known expected results, including byte strings, scope boundaries,
  and negative cases; exercise CLI streams and file operations.

### Changed

- **Local renaming** — replace keyword-based scope tracking with
  parser-backed binding analysis. Unsupported syntax, including typed Luau
  and interpolation, skips the entire rename pass with a warning in
  `MinifyResult.errors` rather than partially rewriting names.
- **Dialect-sensitive literals** — leave `\x`, `\u`, and `\z` string escapes
  unchanged because their meanings differ between Lua dialects.
- **README** — document fork provenance, Nix usage, and supported behavior;
  remove universal semantic-equivalence claims and stale test counts.

### Fixed

- **Renamer scopes** — resolve initializer references, redeclarations,
  closures, loop headers, repeat conditions, branches, recursive local
  functions, and implicit method `self` using Lua binding rules.
- **Renamer name collisions** — generated locals no longer capture globals
  or preserved names, and table keys and member names remain unchanged.
- **String bytes** — preserve high-byte values, decimal escape boundaries,
  and long-string newline semantics across Lua dialects.
- **Number literals** — preserve integer/float distinctions, signed zero,
  large integer precision, overflow, and underflow without Python float
  conversion.
- **Lexer line handling** — recognize CR-only and paired line endings,
  multiline `\z` whitespace, vertical tabs, and form feeds; reject
  unterminated short strings instead of truncating them.
- **Luau syntax** — preserve interpolated strings, binary literals,
  exponent separators, and three-character compound assignment operators.
- **Token boundaries** — keep concatenation, leading-dot numbers, long
  brackets, comparison operators, and retained comments from merging into
  different tokens or swallowing executable code.
- **Whitespace preservation** — retain source spaces and line breaks when
  whitespace removal is disabled, without inserting duplicate separators.
- **Shebang scripts** — retain the interpreter directive and its line
  boundary so minified files still execute through file loaders and directly.
- **File encoding** — read and write raw non-UTF-8 literal bytes and original
  newline spellings without transcoding; report physical byte sizes.
- **Overwrite protection** — stdin output now requires `--overwrite` for
  existing files. `--in-place` no longer authorizes overwriting an unrelated
  explicit output path.
- **CLI streams** — send banners, diagnostics, and statistics to stderr,
  leaving stdout suitable for piping generated source.
- **File discovery** — include `.luau` files in directory scans, deduplicate
  overlapping inputs, and handle empty matches without inventing paths.
- **Batch destinations** — reject colliding outputs and destinations that
  would replace another unread input before writing any files; require a
  single input for `--output`.

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
