# Contributing to minilua

Thank you for your interest in contributing! This document covers everything
you need to know to get started.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Submitting Changes](#submitting-changes)
- [Commit Message Format](#commit-message-format)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Code Style](#code-style)

---

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/minilua.git
   cd minilua
   ```
3. Create a **branch** for your change:
   ```bash
   git checkout -b fix/your-description
   # or
   git checkout -b feat/your-feature-name
   ```

---

## Development Setup

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows

# Install in editable mode with dev dependencies
pip install -e .
pip install pytest
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

All 102 tests must pass before submitting a pull request. If you add a new
feature or fix a bug, please add a corresponding test.

---

## Submitting Changes

1. Make sure all tests pass.
2. Update `CHANGELOG.md` under `[Unreleased]` with a brief description of
   your change (Added / Fixed / Changed / Removed).
3. Push your branch and open a **Pull Request** against `main`.
4. Describe *what* you changed and *why* in the PR description.

---

## Commit Message Format

Follow the [Conventional Commits](https://www.conventionalcommits.org/) style:

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

**Types:**

| Type | When to use |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `refactor` | Code change that is neither a fix nor a feature |
| `chore` | Build process, dependency updates |
| `perf` | Performance improvement |

**Examples:**

```
feat(renamer): add support for method parameter renaming
fix(lexer): correctly tokenize vararg before concat operator
docs: update README installation section
test(separator): add edge case for keyword followed by unary minus
```

---

## Reporting Bugs

Please open a [GitHub Issue](https://github.com/USERNAME/minilua/issues) with:

- A minimal Lua snippet that reproduces the problem.
- The minilua version (`minilua --version`).
- The command you ran.
- The actual output vs. the expected output.

---

## Suggesting Features

Open a [GitHub Issue](https://github.com/USERNAME/minilua/issues) with the
label **enhancement** and describe:

- What problem the feature solves.
- What the expected behavior / interface would look like.
- Any edge cases to consider.

---

## Code Style

- Follow PEP 8.
- Use type hints on all public functions and class methods.
- Keep each module focused on a single responsibility.
- Document non-obvious logic with inline comments.
- New public-facing options in `MinifyOptions` must have a corresponding
  CLI flag in `cli.py` and a test in `tests/test_minifier.py`.
