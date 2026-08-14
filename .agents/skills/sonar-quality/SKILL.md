---
name: sonar-quality
description: Prevent SonarCloud/SonarQube issues when writing or changing code in this repo.
---

# Xylella Sonar Quality Standards

Apply these rules when writing or changing code in this repo. The repository's Sonar
project is `bckirkup_Xylella_SPQR`, with analysis wired through
`.github/workflows/ci.yml`.

## Local validation

```bash
pre-commit run --all-files
python scripts/sonar_guard.py src tests scripts baselines
python scripts/sonar_guard.py --workflows .github/workflows
ruff check src/ tests/ scripts/ baselines/
ruff format --check src/ tests/ scripts/ baselines/
mypy src/
pytest --strict-markers -ra
```

## Rule catalog

- `python:S3776`: keep cognitive complexity at or below the repository's current
  complexity ceiling. New or changed functions must stay below the pre-commit
  threshold of 15.
- `python:S9073`: use separate assertions for separate conditions; do not write
  `assert condition_a and condition_b`.
- `python:S1172`: rename intentionally unused parameters with a leading underscore.
- `python:S116` and `python:S117`: use conventional snake_case names for Python
  methods, variables, and attributes.
- `python:S107`: keep function signatures focused; group related options into a
  configuration object when a signature would otherwise grow too large.
- `githubactions:S8541`: published-package `pip install` commands must include
  `--only-binary :all:`.
- `githubactions:S8544`: published-package installs must use explicit versions,
  immutable commit references, or hashes. Local editable installs such as
  `pip install -e .` are exempt because their version is defined by the checked-out
  project metadata; they must still be reviewed for dependency reproducibility.
- The same workflow checks cover UV installers:
  - `uv sync` requires `--no-build` and `--locked` or `--frozen`.
  - `uv pip install`, `uv add`, and `uv tool install` require `--no-build` and
    pinned or hashed requirements.
  - `uvx` and `uv tool run` require `--no-build` and a pinned `--from
    package==version` requirement.
  - `--no-binary-package <package>` may document source-build exceptions, but
    does not replace `--no-build`.
  - Non-installing commands such as `uv run`, `uv run --no-sync`, `uv lock`, and
    `uv --version` are not checked by these rules.

The mechanical guard is intentionally conservative and checks Python files plus
workflow YAML. `zizmor` separately checks GitHub Actions action pinning.

## CI complexity ratchet

CI checks the whole repository with the current `ruff` complexity ceiling recorded
in `pyproject.toml`. That ceiling only ratchets downward. Pre-commit applies the
goal threshold of 15 to changed Python files.

## Existing source findings

Do not add `# noqa`, `nosonar`, or equivalent suppressions. Fix unused parameters,
naming, complexity, and oversized signatures at their causes. Taint-analysis
findings require review in the SonarQube Cloud job because local Ruff and the
mechanical guard cannot prove inter-procedural data flow.
