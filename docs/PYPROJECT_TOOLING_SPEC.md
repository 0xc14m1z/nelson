# Pyproject and Tooling Specification for Nelson

## Purpose

This document defines the required `pyproject.toml` structure and the mandatory development tooling configuration for Nelson v1.

It exists to turn the engineering standards into an executable project setup that a coding agent can implement consistently.

## Normative Language

The keywords below are used intentionally:

- `MUST`: mandatory rule
- `SHOULD`: strong default that may be overridden with explicit justification
- `MAY`: acceptable option

## Normative References

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [PYTHON_ENGINEERING_STANDARDS.md](./PYTHON_ENGINEERING_STANDARDS.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md)
- Python packaging guide: <https://packaging.python.org/>
- uv: <https://docs.astral.sh/uv/>
- Ruff: <https://docs.astral.sh/ruff/>
- Pyright: <https://github.com/microsoft/pyright>
- pytest: <https://docs.pytest.org/en/stable/>
- pytest-asyncio: <https://pytest-asyncio.readthedocs.io/en/stable/>
- coverage.py: <https://coverage.readthedocs.io/>
- pre-commit: <https://pre-commit.com/>
- Hatchling: <https://hatch.pypa.io/latest/>

## 1. Packaging Baseline

### 1.1 Build system

Nelson `MUST` use:

- `hatchling` as the build backend

The `pyproject.toml` build-system section `MUST` be configured accordingly.

### 1.2 Python requirement

The project metadata `MUST` require:

- `requires-python = ">=3.14"`

Nelson `MUST NOT` declare compatibility with earlier Python versions.

### 1.3 Layout

- Package code `MUST` live under `src/nelson/`
- Tests `SHOULD` live under `tests/`
- The project `MUST` use package discovery compatible with the `src/` layout

## 2. Dependency Groups

### 2.1 Runtime dependencies

Runtime dependencies `MUST` contain only libraries required to run Nelson as an installed CLI/package.

Expected runtime categories:

- CLI framework
- LLM provider SDK (OpenAI Python SDK, pointed at OpenRouter's base URL)
- validation and schemas
- optional runtime observability integration

### 2.2 Development dependencies

Nelson `MUST` define a `dev` dependency group containing at least:

- `ruff`
- `pyright`
- `pytest`
- `pytest-asyncio`
- `coverage`
- `pre-commit`

If additional dev-only tooling is added, it `SHOULD` go into the `dev` group unless there is a strong reason for a separate group.

### 2.3 Versioning policy

- `pyproject.toml` `MUST` use controlled version ranges, not unbounded specifiers.
- `uv.lock` `MUST` be committed to the repository.
- Reproducibility `MUST` come from `uv.lock`, not from exact pinning every dependency in `pyproject.toml`.

Recommended rule of thumb:

- use narrow compatible ranges for toolchain packages
- use controlled ranges for runtime packages

## 3. Required Project Metadata

The project metadata in `pyproject.toml` `MUST` define at least:

- project name
- version or version source
- description
- readme
- requires-python
- dependencies
- optional dependency groups
- console script entrypoint for `nelson`

The CLI entrypoint `MUST` install the `nelson` command through standard project metadata, not via ad hoc wrapper scripts.

## 4. Required Runtime Dependencies

The exact versions may evolve, but the dependency set `MUST` support the agreed architecture.

Expected runtime dependencies:

- `typer`
- `openai` (Python SDK, pointed at OpenRouter's base URL)
- `pydantic`
- `pydantic-settings` only if later needed, not automatically
- `rich` for human CLI rendering
- `logfire` as an optional runtime integration

Notes:

- `logfire` is optional in behavior, but the dependency may still be installed as part of runtime if that simplifies instrumentation design.
- The code `MUST` behave correctly when Logfire is not configured.

## 5. Required Development Dependencies

At minimum, the `dev` group `MUST` include packages sufficient for:

- linting
- formatting
- import ordering
- strict typing
- async testing
- coverage
- pre-commit

The intended baseline is:

- `ruff`
- `pyright`
- `pytest`
- `pytest-asyncio`
- `coverage`
- `pre-commit`

## 6. Ruff Configuration

### 6.1 Role

Ruff `MUST` be the single tool for:

- linting
- formatting
- import ordering

### 6.2 Strictness

Ruff `MUST` be configured in a relatively strict mode suitable for production Python.

The ruleset `SHOULD` cover at least:

- pyflakes / unused imports and names
- pycodestyle errors
- import sorting
- bug-risk and correctness rules
- modernization rules that align with Python 3.14
- async misuse where supported
- unnecessary exception anti-patterns where supported

### 6.3 Formatting

- Ruff formatting `MUST` be the canonical formatter.
- The repository `MUST NOT` introduce Black in parallel.

### 6.4 Import ordering

- Ruff import sorting `MUST` be enabled.
- Import grouping and order `MUST` be tool-enforced, not manually debated in code review.

## 7. Pyright Configuration

### 7.1 Strict mode

Pyright `MUST` run in global strict mode for the project.

### 7.2 Coverage of package and tests

- Package code `MUST` be type checked.
- Tests `SHOULD` also be type checked where practical.

### 7.3 Suppression policy

- Type ignores and suppressions `MUST` be rare.
- Each suppression `SHOULD` carry a clear reason when not self-evident.
- Suppressions `MUST NOT` become the default way to integrate poorly typed code.

## 8. Pytest Configuration

### 8.1 Markers

Pytest `MUST` define explicit markers for:

- `unit`
- `integration`
- `live`

### 8.2 Warning policy

- Tests `MUST` fail on warnings by default.
- Warning exemptions `MAY` be added only when explicit and justified.

### 8.3 Async configuration

`pytest-asyncio` `MUST` be configured for the project's async testing strategy.

Recommended default:

- `asyncio_mode = auto`

### 8.4 Test discovery

The project `MUST` define a stable test discovery pattern through pytest configuration.

## 9. Coverage Configuration

### 9.1 Thresholds

The project `MUST` enforce:

- minimum line coverage: `90%`
- minimum branch coverage: `85%`

### 9.2 Exclusions

Coverage exclusions `MUST` remain narrow and explicit.

Acceptable exclusions include:

- `if TYPE_CHECKING:`
- intentionally unreachable defensive branches
- lines marked with `pragma: no cover` and a real reason

Coverage exclusions `MUST NOT` become a way to hide under-tested logic.

### 9.3 Scope

Coverage should focus on package code under `src/nelson/`.

## 10. Pre-commit Configuration

### 10.1 Required status

`pre-commit` is mandatory for the project standard.

### 10.2 Required hooks

The pre-commit setup `MUST` run at least:

- Ruff lint
- Ruff format check or formatting
- Pyright

The project `MAY` include lightweight schema validation or targeted test hooks if execution time remains acceptable.

### 10.3 Philosophy

Pre-commit should catch obvious local issues before CI, but it `SHOULD NOT` turn into a slow full-suite gate on every commit.

## 11. Development Commands

The project `SHOULD` standardize a small set of canonical commands, runnable through `uv run`.

Recommended canonical commands:

### 11.1 Format

```bash
uv run ruff format .
```

### 11.2 Lint

```bash
uv run ruff check .
```

### 11.3 Auto-fix lint issues where safe

```bash
uv run ruff check . --fix
```

### 11.4 Type check

```bash
uv run pyright
```

### 11.5 Run all non-live tests

```bash
uv run pytest -m "not live"
```

### 11.6 Run unit tests only

```bash
uv run pytest -m unit
```

### 11.7 Run integration tests

```bash
uv run pytest -m integration
```

### 11.8 Run live smoke tests

```bash
uv run pytest -m live
```

### 11.9 Coverage run

```bash
uv run coverage run -m pytest -m "not live"
uv run coverage report --show-missing --fail-under=90
```

If branch coverage is enforced separately, the coverage configuration `MUST` reflect that in the underlying tool settings, not only in ad hoc command flags.

## 12. Suggested `pyproject.toml` Sections

The final file may differ in exact syntax, but it `SHOULD` contain sections equivalent to:

- `[build-system]`
- `[project]`
- `[project.optional-dependencies]`
- `[project.scripts]`
- `[tool.ruff]`
- `[tool.ruff.lint]`
- `[tool.ruff.format]`
- `[tool.pyright]`
- `[tool.pytest.ini_options]`
- `[tool.coverage.run]`
- `[tool.coverage.report]`

## 13. Suggested `pyproject.toml` Behavioral Defaults

These defaults are recommended and consistent with all current Nelson specs:

- line length chosen once and enforced by Ruff
- `src` and `tests` recognized in tooling config
- pytest markers declared explicitly
- warnings treated as errors in tests
- branch coverage enabled
- strict type checking enabled

## 14. Coding Agent Guidance

When implementing `pyproject.toml`, a coding agent `MUST`:

- prefer one canonical tool per concern
- avoid speculative optional tooling
- keep the file coherent with the engineering standards
- ensure command-line and test workflows can be run locally with `uv`

When uncertain, the agent `SHOULD` choose the simplest configuration that still enforces the required standards.

## 15. Future Adjustments

The following are intentionally allowed to evolve later without invalidating this spec:

- exact version ranges
- exact Ruff rule selection
- exact coverage exclusion list
- whether tests receive full strict type coverage
- whether additional dependency groups are introduced

These changes `SHOULD` remain compatible with the core principles in [PYTHON_ENGINEERING_STANDARDS.md](./PYTHON_ENGINEERING_STANDARDS.md).

## 16. References

- [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- [PYTHON_ENGINEERING_STANDARDS.md](./PYTHON_ENGINEERING_STANDARDS.md)
- [CLI_SPEC.md](./CLI_SPEC.md)
- [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md)
- Python packaging guide: <https://packaging.python.org/>
- uv: <https://docs.astral.sh/uv/>
- Ruff: <https://docs.astral.sh/ruff/>
- Pyright: <https://github.com/microsoft/pyright>
- pytest: <https://docs.pytest.org/en/stable/>
- pytest-asyncio: <https://pytest-asyncio.readthedocs.io/en/stable/>
- coverage.py: <https://coverage.readthedocs.io/>
- pre-commit: <https://pre-commit.com/>
- Hatchling: <https://hatch.pypa.io/latest/>
