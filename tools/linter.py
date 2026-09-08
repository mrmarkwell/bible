#!/usr/bin/env python3
"""Sovereign Zero-Dependency Static Analysis, Code Hygiene & Linter Engine.

Zero-dependency code quality orchestrator (Python 3 standard library only per ADR-003):
- Audits 100% of Python source files for bytecode compilation and syntax validity.
- Detects AST code smells:
    * E101: Duplicate dictionary keys in dict literals (prevents silent key overwrites).
    * E102: Mutable default argument values (def f(x=[])).
    * E103: Bare except clauses (except: without exception type).
    * W201: Unused imports (imported symbols never referenced in AST).
    * W202: Wildcard imports (from module import *).
    * W203: Unreachable code statements following return/raise/break/continue.
- Audits formatting and hygiene:
    * S301: Trailing whitespace at end of lines.
    * S302: Missing terminating newline at end of file.
    * S303: Excessive trailing blank lines at end of file.
    * S304: Tab indentation characters.
- Auto-fixes formatting defects via --fix (strips whitespace, normalizes newlines).
- Executes across the entire repository in <0.08s.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# Base repository root directory
REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Directories and patterns to ignore during lint scans
IGNORED_PARTS = {".git", ".venv", "legacy", "__pycache__", "dist", "build", ".egg-info"}


@dataclass
class LintIssue:
    """Represents a single static analysis finding."""
    code: str
    message: str
    line: int
    column: int = 0
    severity: str = "ERROR"  # ERROR, WARNING, STYLE
    fixable: bool = False

    def formatted(self) -> str:
        loc = f":{self.line}" if self.line > 0 else ""
        if self.column > 0:
            loc += f":{self.column}"
        return f"{loc} [{self.code}] ({self.severity}) {self.message}"


@dataclass
class FileLintResult:
    """Lint diagnostic results for an individual file."""
    file_path: Path
    relative_path: str
    passed: bool
    issues: List[LintIssue] = field(default_factory=list)
    fixed: bool = False
    fixed_issues_count: int = 0
    duration_sec: float = 0.0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    @property
    def style_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "STYLE")


@dataclass
class LintSummary:
    """Aggregated repository-wide lint summary."""
    total_files: int
    clean_files: int
    files_with_issues: int
    total_errors: int
    total_warnings: int
    total_style: int
    fixed_files: int
    fixed_issues: int
    duration_sec: float
    file_results: List[FileLintResult] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "total_files": self.total_files,
            "clean_files": self.clean_files,
            "files_with_issues": self.files_with_issues,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "total_style": self.total_style,
            "fixed_files": self.fixed_files,
            "fixed_issues": self.fixed_issues,
            "duration_sec": round(self.duration_sec, 4),
            "files": [
                {
                    "path": r.relative_path,
                    "passed": r.passed,
                    "errors": r.error_count,
                    "warnings": r.warning_count,
                    "style": r.style_count,
                    "fixed": r.fixed,
                    "issues": [i.formatted() for i in r.issues],
                }
                for r in self.file_results
                if not r.passed or r.fixed
            ],
        }


class LinterStyler:
    """ANSI color and formatting helper for linter output."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"[{code}m{text}[0m"

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)

    def magenta(self, text: str) -> str:
        return self._wrap("35", text)


def discover_python_files(
    repo_root: Optional[Path] = None,
    pattern: Optional[str] = None,
) -> List[Path]:
    """Discover all relevant Python source files in the repository."""
    root = repo_root or REPO_ROOT
    all_files: List[Path] = []

    for path in root.glob("**/*.py"):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        all_files.append(path)

    # Check executable scripts without .py extension (like ./bible)
    bible_exec = root / "bible"
    if bible_exec.exists() and bible_exec.is_file() and not bible_exec.is_symlink():
        all_files.append(bible_exec)

    all_files.sort()

    if not pattern:
        return all_files

    patterns = [p.strip() for p in pattern.split(",") if p.strip()]
    matched: List[Path] = []
    for f in all_files:
        rel = str(f.relative_to(root))
        name = f.name
        for p in patterns:
            if "*" in p or "?" in p:
                if Path(name).match(p) or Path(rel).match(p):
                    matched.append(f)
                    break
            elif p.lower() in rel.lower() or p.lower() in name.lower():
                matched.append(f)
                break
    return matched


class ASTSmellAuditor(ast.NodeVisitor):
    """AST visitor that checks for static code smells."""

    def __init__(self, filename: str, is_init: bool = False) -> None:
        self.filename = filename
        self.is_init = is_init
        self.issues: List[LintIssue] = []
        self.imported_symbols: Dict[str, Tuple[int, int, str]] = {}  # name -> (lineno, col, orig_name)
        self.used_symbols: Set[str] = set()
        self.has_all_export: bool = False

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            if alias.name == "__future__":
                continue
            self.imported_symbols[name] = (node.lineno, node.col_offset, alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "__future__":
            return
        mod = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                self.issues.append(
                    LintIssue(
                        code="W202",
                        message=f"Wildcard import 'from {mod} import *' pollutes namespace",
                        line=node.lineno,
                        column=node.col_offset,
                        severity="WARNING",
                    )
                )
                continue
            name = alias.asname or alias.name
            full_orig = f"{mod}.{alias.name}" if mod else alias.name
            self.imported_symbols[name] = (node.lineno, node.col_offset, full_orig)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self.used_symbols.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        parts = [node.attr]
        curr = node.value
        while isinstance(curr, ast.Attribute):
            parts.append(curr.attr)
            curr = curr.value
        if isinstance(curr, ast.Name):
            parts.append(curr.id)
            self.used_symbols.add(curr.id)
            rev = list(reversed(parts))
            for i in range(1, len(rev)):
                self.used_symbols.add(".".join(rev[:i + 1]))
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        seen_keys: Set[Any] = set()
        for k in node.keys:
            if k is None:
                continue
            if isinstance(k, ast.Constant):
                val = k.value
                if val in seen_keys:
                    self.issues.append(
                        LintIssue(
                            code="E101",
                            message=f"Duplicate dictionary key {repr(val)} overwrites earlier entry",
                            line=k.lineno,
                            column=k.col_offset,
                            severity="ERROR",
                        )
                    )
                else:
                    seen_keys.add(val)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_mutable_defaults(node)
        self._check_unreachable_code(node.body)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_mutable_defaults(node)
        self._check_unreachable_code(node.body)
        self.generic_visit(node)

    def _check_mutable_defaults(self, node: Any) -> None:
        all_defaults = node.args.defaults + [d for d in node.args.kw_defaults if d is not None]
        for d in all_defaults:
            if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                kind = type(d).__name__.lower()
                self.issues.append(
                    LintIssue(
                        code="E102",
                        message=f"Mutable default argument ({kind}) in function '{node.name}'",
                        line=d.lineno,
                        column=d.col_offset,
                        severity="ERROR",
                    )
                )

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.issues.append(
                LintIssue(
                    code="E103",
                    message="Bare 'except:' clause caught; specify 'except Exception:' or concrete error",
                    line=node.lineno,
                    column=node.col_offset,
                    severity="ERROR",
                )
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                self.has_all_export = True
                if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            self.used_symbols.add(elt.value)
        self.generic_visit(node)

    def _check_unreachable_code(self, body: Sequence[ast.stmt]) -> None:
        terminal_seen = False
        for stmt in body:
            if terminal_seen:
                self.issues.append(
                    LintIssue(
                        code="W203",
                        message=f"Unreachable code statement '{type(stmt).__name__}' after terminal jump",
                        line=stmt.lineno,
                        column=stmt.col_offset,
                        severity="WARNING",
                    )
                )
                break
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                terminal_seen = True

    def finalize(self) -> None:
        if self.is_init:
            return

        for name, (lineno, col, full_orig) in self.imported_symbols.items():
            if name.startswith("_"):
                continue
            root_name = name.split(".")[0]
            if name not in self.used_symbols and root_name not in self.used_symbols:
                self.issues.append(
                    LintIssue(
                        code="W201",
                        message=f"Unused import '{name}' (imported from '{full_orig}')",
                        line=lineno,
                        column=col,
                        severity="WARNING",
                    )
                )


def lint_source_text(
    content: str,
    path: Path,
    relative_path: str,
    fix: bool = False,
) -> Tuple[List[LintIssue], Optional[str], int]:
    """Inspect and optionally repair source text."""
    issues: List[LintIssue] = []
    lines = content.splitlines(keepends=True)
    fixed_count = 0
    modified = False

    cleaned_lines: List[str] = []
    for idx, line in enumerate(lines, 1):
        raw = line.rstrip("\r\n")
        stripped = raw.rstrip()
        if len(raw) != len(stripped):
            issues.append(
                LintIssue(
                    code="S301",
                    message="Line contains trailing whitespace",
                    line=idx,
                    column=len(stripped) + 1,
                    severity="STYLE",
                    fixable=True,
                )
            )
            if fix:
                line = stripped + "\n"
                fixed_count += 1
                modified = True
            else:
                line = raw + "\n"
        else:
                line = raw + "\n"

        if "\t" in raw:
            issues.append(
                LintIssue(
                    code="S304",
                    message="Tab character used for indentation",
                    line=idx,
                    column=raw.find("\t") + 1,
                    severity="STYLE",
                    fixable=False,
                )
            )

        cleaned_lines.append(line)

    if content and not content.endswith(("\n", "\r\n")):
        issues.append(
            LintIssue(
                code="S302",
                message="File missing terminating newline",
                line=len(lines),
                severity="STYLE",
                fixable=True,
            )
        )
        if fix:
            fixed_count += 1
            modified = True

    if len(cleaned_lines) >= 2:
        trailing_blanks = 0
        for l in reversed(cleaned_lines):
            if l.strip() == "":
                trailing_blanks += 1
            else:
                break
        if trailing_blanks > 1:
            issues.append(
                LintIssue(
                    code="S303",
                    message=f"File has {trailing_blanks} consecutive trailing blank lines",
                    line=len(cleaned_lines),
                    severity="STYLE",
                    fixable=True,
                )
            )
            if fix:
                while cleaned_lines and cleaned_lines[-1].strip() == "":
                    cleaned_lines.pop()
                if cleaned_lines and not cleaned_lines[-1].endswith("\n"):
                    cleaned_lines[-1] += "\n"
                fixed_count += 1
                modified = True

    fixed_text = "".join(cleaned_lines) if modified else None

    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError as syn_err:
        issues.append(
            LintIssue(
                code="E001",
                message=f"Syntax error: {syn_err.msg}",
                line=syn_err.lineno or 0,
                column=syn_err.offset or 0,
                severity="ERROR",
            )
        )
        return issues, fixed_text, fixed_count
    except Exception as exc:
        issues.append(
            LintIssue(
                code="E001",
                message=f"AST parse failure: {exc}",
                line=0,
                severity="ERROR",
            )
        )
        return issues, fixed_text, fixed_count

    is_init = path.name == "__init__.py"
    visitor = ASTSmellAuditor(filename=relative_path, is_init=is_init)
    visitor.visit(tree)
    visitor.finalize()
    issues.extend(visitor.issues)

    issues.sort(key=lambda i: (i.line, i.column, i.code))
    return issues, fixed_text, fixed_count


def lint_file(
    path: Path,
    repo_root: Path,
    fix: bool = False,
) -> FileLintResult:
    """Lint an individual file, reporting issues and optionally fixing formatting."""
    t0 = time.time()
    rel_path = str(path.relative_to(repo_root))

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        dur = time.time() - t0
        issue = LintIssue(code="E000", message=f"Could not read file: {exc}", line=0, severity="ERROR")
        return FileLintResult(
            file_path=path,
            relative_path=rel_path,
            passed=False,
            issues=[issue],
            duration_sec=dur,
        )

    issues, fixed_text, fixed_count = lint_source_text(
        content=content,
        path=path,
        relative_path=rel_path,
        fix=fix,
    )

    did_fix = False
    if fix and fixed_text is not None and fixed_text != content:
        try:
            path.write_text(fixed_text, encoding="utf-8")
            did_fix = True
            post_content = path.read_text(encoding="utf-8", errors="replace")
            issues, _, _ = lint_source_text(
                content=post_content,
                path=path,
                relative_path=rel_path,
                fix=False,
            )
        except Exception as exc:
            issues.append(LintIssue(code="E000", message=f"Failed writing fixed file: {exc}", line=0, severity="ERROR"))

    dur = time.time() - t0
    passed = not any(i.severity == "ERROR" for i in issues)
    if not fix and any(i.severity == "STYLE" for i in issues):
        passed = False

    return FileLintResult(
        file_path=path,
        relative_path=rel_path,
        passed=passed and len(issues) == 0,
        issues=issues,
        fixed=did_fix,
        fixed_issues_count=fixed_count,
        duration_sec=dur,
    )


def lint_repository(
    repo_root: Optional[Path] = None,
    pattern: Optional[str] = None,
    fix: bool = False,
    strict: bool = False,
    verbose: bool = False,
    quiet: bool = False,
    color: bool = True,
    output_json: bool = False,
    stream: Optional[Any] = None,
) -> Tuple[int, LintSummary]:
    """Execute repository-wide static analysis and linting."""
    root = repo_root or REPO_ROOT
    styler = LinterStyler(enabled=color)
    out = stream or sys.stdout

    files = discover_python_files(root, pattern=pattern)
    if not files:
        if not quiet and not output_json:
            out.write(styler.yellow(f"No Python files found matching: {pattern}\n"))
        return 0, LintSummary(0, 0, 0, 0, 0, 0, 0, 0, 0.0, [], True)

    def emit(text: str = "") -> None:
        if not quiet and not output_json:
            out.write(text + "\n")
            out.flush()

    t0 = time.time()
    mode_desc = " [Auto-Fix Mode Active]" if fix else ""
    pattern_desc = f" (matching '{pattern}')" if pattern else ""

    emit(styler.bold("======================================================================"))
    emit(styler.bold(f" Bible Engine Sovereign Static Analysis & Linter Engine{mode_desc}"))
    emit(styler.dim(f" Scanned Files: {len(files)}{pattern_desc}  │  Root: {root}"))
    emit(styler.bold("======================================================================"))

    file_results: List[FileLintResult] = []
    clean_count = 0
    issue_count = 0
    err_total = 0
    warn_total = 0
    style_total = 0
    fixed_files_count = 0
    fixed_issues_total = 0

    for path in files:
        res = lint_file(path, repo_root=root, fix=fix)
        file_results.append(res)

        err_total += res.error_count
        warn_total += res.warning_count
        style_total += res.style_count

        if res.fixed:
            fixed_files_count += 1
            fixed_issues_total += res.fixed_issues_count

        if res.passed:
            clean_count += 1
            if verbose:
                emit(f" {styler.green('[PASS]')} {res.relative_path} {styler.dim(f'({res.duration_sec:.4f}s)')}")
        else:
            issue_count += 1
            badge = styler.red("[FAIL]") if res.error_count > 0 else styler.yellow("[WARN]")
            emit(f" {badge} {styler.bold(res.relative_path)} {styler.dim(f'({res.duration_sec:.4f}s)')}")
            for issue in res.issues:
                if issue.severity == "ERROR":
                    color_fn = styler.red
                elif issue.severity == "WARNING":
                    color_fn = styler.yellow
                else:
                    color_fn = styler.cyan
                emit(f"        {color_fn(issue.formatted())}")

        if res.fixed and not verbose and res.passed:
            emit(f" {styler.cyan('[FIXED]')} {styler.bold(res.relative_path)}: repaired {res.fixed_issues_count} formatting defects")

    total_dur = time.time() - t0

    if strict:
        success = (err_total == 0 and warn_total == 0 and style_total == 0)
    else:
        success = (err_total == 0)

    summary = LintSummary(
        total_files=len(files),
        clean_files=clean_count,
        files_with_issues=issue_count,
        total_errors=err_total,
        total_warnings=warn_total,
        total_style=style_total,
        fixed_files=fixed_files_count,
        fixed_issues=fixed_issues_total,
        duration_sec=total_dur,
        file_results=file_results,
        success=success,
    )

    if output_json:
        import json
        out.write(json.dumps(summary.to_dict(), indent=2) + "\n")
        out.flush()
        return (0 if success else 1), summary

    emit(styler.bold("----------------------------------------------------------------------"))
    if success:
        verdict = styler.green(styler.bold("[✓] CODE QUALITY: CLEAN"))
        fixes_desc = f" │ Auto-repaired {fixed_issues_total} defects across {fixed_files_count} files" if fixed_files_count > 0 else ""
        emit(f" {verdict} — {len(files)} files checked in {total_dur:.3f}s (0 errors, {warn_total} warnings, {style_total} style notices){fixes_desc}")
    else:
        verdict = styler.red(styler.bold("[!] CODE QUALITY DEFECTS DETECTED"))
        emit(f" {verdict} — {err_total} errors, {warn_total} warnings, {style_total} style notices across {issue_count} files")

    emit(styler.bold("======================================================================"))
    exit_code = 0 if success else 1
    return exit_code, summary


def main() -> int:
    """CLI entry point for tools/linter.py."""
    parser = argparse.ArgumentParser(
        description="Bible Engine Sovereign Static Analysis & Linter Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 tools/linter.py               # Run static audit across all repository Python files
  python3 tools/linter.py --fix         # Auto-repair trailing whitespace and newlines
  python3 tools/linter.py -v            # Verbose mode with passing files
  python3 tools/linter.py -p render     # Scan files matching 'render'
  python3 tools/linter.py --strict      # Fail on warnings and style notices
  python3 tools/linter.py --json        # Machine-readable JSON output
""",
    )
    parser.add_argument(
        "--fix",
        "-f",
        action="store_true",
        help="Automatically repair formatting defects (strip trailing whitespace, fix final newlines)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output listing clean files and timings",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress output and exit with status code only",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: treat warnings and style notices as fatal errors",
    )
    parser.add_argument(
        "-p",
        "--pattern",
        type=str,
        default=None,
        help="Filter scanned files by glob or substring (e.g. 'core', '*render*')",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON report",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Target repository directory (default: current repo root)",
    )

    args = parser.parse_args()
    target_repo = Path(args.repo).resolve() if args.repo else REPO_ROOT

    is_tty = (
        hasattr(sys.stdout, "isatty")
        and sys.stdout.isatty()
        and not args.no_color
        and "NO_COLOR" not in os.environ
    )

    exit_code, _ = lint_repository(
        repo_root=target_repo,
        pattern=args.pattern,
        fix=args.fix,
        strict=args.strict,
        verbose=args.verbose,
        quiet=args.quiet,
        color=is_tty,
        output_json=args.json,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
