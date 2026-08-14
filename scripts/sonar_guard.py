#!/usr/bin/env python3
"""Fast, conservative checks for Sonar patterns without upstream lint rules."""

from __future__ import annotations

import argparse
import ast
import io
import re
import shlex
import tokenize
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule: str
    message: str


_PIP_INSTALL = re.compile(r"(?<![\w-])(?:python(?:\s+-m)?\s+)?pip\s+install\b")
_SHA256 = re.compile(r"(?:sha256=|#sha256=)[0-9a-fA-F]{64}")
_COMMIT_SHA = re.compile(r"@[0-9a-fA-F]{40}(?:[#/]|$)")
_VERSIONED_PACKAGE = re.compile(r"(?:===|==|~=|!=|>=|<=|>|<)")
_WORKFLOW_SUFFIXES = {".yml", ".yaml"}


def _float_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, float)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        return _float_literal(node.operand)
    return False


def _approx_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "approx"
    )


def _assert_float_comparisons(tree: ast.AST, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for comparison in ast.walk(node.test):
            if not isinstance(comparison, ast.Compare):
                continue
            if not any(isinstance(op, ast.Eq | ast.NotEq) for op in comparison.ops):
                continue
            operands = [comparison.left, *comparison.comparators]
            if any(_float_literal(operand) for operand in operands) and not any(
                _approx_call(operand) for operand in operands
            ):
                findings.append(
                    Finding(
                        path,
                        comparison.lineno,
                        "S1244",
                        "float equality in assert; use pytest.approx",
                    )
                )
                break
    return findings


def _composite_assertions(tree: ast.AST, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assert)
            and isinstance(node.test, ast.BoolOp)
            and isinstance(node.test.op, ast.And)
        ):
            findings.append(
                Finding(
                    path,
                    node.lineno,
                    "S9073",
                    "composite assertion; assert each condition separately",
                )
            )
    return findings


def _numpy_random_imports(tree: ast.AST) -> set[str]:
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module != "numpy.random":
            continue
        imported_names.update(
            alias.asname or alias.name for alias in node.names if alias.name != "*"
        )
    return imported_names


def _random_call_name(call: ast.Call, imported_names: set[str]) -> str | None:
    function = call.func
    if isinstance(function, ast.Name) and function.id in imported_names:
        return function.id
    if not isinstance(function, ast.Attribute):
        return None
    random_module = function.value
    if not (
        isinstance(random_module, ast.Attribute)
        and random_module.attr == "random"
        and isinstance(random_module.value, ast.Name)
        and random_module.value.id == "np"
    ):
        return None
    return function.attr


def _bare_random_calls(tree: ast.AST, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    imported_names = _numpy_random_imports(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _random_call_name(node, imported_names)
        if name is None:
            continue
        if name == "default_rng":
            has_seed = bool(node.args) or any(keyword.arg == "seed" for keyword in node.keywords)
            if has_seed:
                continue
        findings.append(
            Finding(
                path,
                node.lineno,
                "S6709",
                f"bare NumPy random call {name!r}; use a seeded Generator",
            )
        )
    return findings


def _comment_lines(source: str) -> set[int]:
    comments: set[int] = set()
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    with suppress(tokenize.TokenError):
        comments.update(token.start[0] for token in tokens if token.type == tokenize.COMMENT)
    return comments


def _uncommented_passes(tree: ast.AST, source: str, path: Path) -> list[Finding]:
    comments = _comment_lines(source)
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Pass):
            continue
        if node.lineno in comments or node.lineno - 1 in comments:
            continue
        findings.append(
            Finding(path, node.lineno, "S1186", "empty pass stub needs an explanatory comment")
        )
    return findings


def _is_test_file(path: Path) -> bool:
    return "tests" in path.parts or path.name.startswith("test_") or path.name.endswith("_test.py")


def _check_python_file(path: Path) -> list[Finding]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as error:
        print(f"{path}: unable to inspect ({error})")
        return []
    findings = [
        *_assert_float_comparisons(tree, path),
        *_bare_random_calls(tree, path),
        *_uncommented_passes(tree, source, path),
    ]
    if _is_test_file(path):
        findings.extend(_composite_assertions(tree, path))
    return findings


def _python_files(paths: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            files.add(path)
        elif path.is_dir():
            files.update(candidate for candidate in path.rglob("*.py") if candidate.is_file())
    return sorted(files)


def _workflow_files(paths: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix in _WORKFLOW_SUFFIXES:
            files.add(path)
        elif path.is_dir():
            files.update(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix in _WORKFLOW_SUFFIXES
            )
    return sorted(files)


def _workflow_commands(source: str) -> list[tuple[int, str]]:
    lines = source.splitlines()
    commands: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not _PIP_INSTALL.search(line):
            index += 1
            continue
        start = index
        command_lines = [line]
        while command_lines[-1].rstrip().endswith("\\") and index + 1 < len(lines):
            index += 1
            command_lines.append(lines[index])
        commands.append((start + 1, "\n".join(command_lines)))
        index += 1
    return commands


def _pip_command_segments(command: str) -> list[str]:
    segments: list[str] = []
    for match in _PIP_INSTALL.finditer(command):
        segment = command[match.start() :]
        segment = re.split(r"\s*(?:&&|;)\s*", segment, maxsplit=1)[0]
        segments.append(segment.replace("\\\n", " "))
    return segments


def _local_target(target: str) -> bool:
    package = target.split("[", maxsplit=1)[0]
    if package.startswith((".", "/")):
        return True
    return Path(package).exists()


def _editable_install_is_local(tokens: list[str]) -> bool:
    targets: list[str] = []
    editable = False
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"-e", "--editable"}:
            editable = True
            if index + 1 < len(tokens):
                targets.append(tokens[index + 1])
                index += 2
                continue
        index += 1
    return editable and bool(targets) and all(_local_target(target) for target in targets)


def _requirement_tokens(tokens: list[str]) -> list[str]:
    option_values = {
        "--config-settings",
        "--constraint",
        "-c",
        "--extra-index-url",
        "--find-links",
        "-f",
        "--index-url",
        "--only-binary",
        "--platform",
        "--python-version",
        "--requirement",
        "-r",
        "--target",
        "-t",
        "--trusted-host",
    }
    requirements: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"-e", "--editable"}:
            index += 2
            continue
        if token in option_values:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        requirements.append(token)
        index += 1
    return requirements


def _requirement_is_pinned(requirement: str) -> bool:
    return bool(
        _SHA256.search(requirement)
        or _COMMIT_SHA.search(requirement)
        or _VERSIONED_PACKAGE.search(requirement)
    )


def _workflow_findings(path: Path) -> list[Finding]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"{path}: unable to inspect ({error})")
        return []
    findings: list[Finding] = []
    for line, command in _workflow_commands(source):
        for segment in _pip_command_segments(command):
            try:
                tokens = shlex.split(segment)
            except ValueError:
                tokens = segment.split()
            install_index = next(
                (index for index, token in enumerate(tokens) if token == "install"),
                len(tokens),
            )
            install_tokens = tokens[install_index + 1 :]
            if "--only-binary" not in install_tokens and not _editable_install_is_local(
                install_tokens
            ):
                findings.append(
                    Finding(
                        path,
                        line,
                        "S8541",
                        "pip install must include --only-binary :all: for published packages",
                    )
                )
            if _editable_install_is_local(install_tokens):
                continue
            if "--require-hashes" not in install_tokens:
                requirements = _requirement_tokens(install_tokens)
                if requirements and not all(_requirement_is_pinned(req) for req in requirements):
                    findings.append(
                        Finding(
                            path,
                            line,
                            "S8544",
                            "pip install requirements must be version-pinned or hashed",
                        )
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflows",
        action="store_true",
        help="scan workflow YAML files instead of Python files",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="files or directories to scan",
    )
    args = parser.parse_args()
    if args.workflows:
        paths = args.paths or [Path(".github/workflows")]
        findings = [
            finding for path in _workflow_files(paths) for finding in _workflow_findings(path)
        ]
    else:
        paths = args.paths or [Path("src"), Path("tests"), Path("scripts"), Path("baselines")]
        findings = [
            finding for path in _python_files(paths) for finding in _check_python_file(path)
        ]
        workflow_paths = [path for path in args.paths if path.suffix in _WORKFLOW_SUFFIXES]
        findings.extend(
            finding
            for path in _workflow_files(workflow_paths)
            for finding in _workflow_findings(path)
        )
    for finding in findings:
        print(f"{finding.path}:{finding.line}:1: {finding.rule} {finding.message}")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
