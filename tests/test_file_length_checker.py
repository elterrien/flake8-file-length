import types
import pytest
from pathlib import Path
from typing import Callable, Iterable, Tuple, List

from src.no_long_files import FileLengthChecker


# ---------- Shared fixtures & helpers ----------

@pytest.fixture
def restore_defaults(monkeypatch):
    """
    Save and restore class-level options so each test starts clean.
    """
    orig = {
        "max_file_length": FileLengthChecker.max_file_length,
        "ignore_blank": FileLengthChecker.ignore_blank,
        "ignore_comments": FileLengthChecker.ignore_comments,
        "ignore_shebang": FileLengthChecker.ignore_shebang,
    }
    yield
    for k, v in orig.items():
        monkeypatch.setattr(FileLengthChecker, k, v, raising=False)


@pytest.fixture
def write_py(tmp_path: Path) -> Callable[[Iterable[str], str], Path]:
    """
    Create a Python file in a temp directory.
    Usage: p = write_py(["line1", "line2"], name="a.py")
    """
    def _write(lines: Iterable[str], name: str = "file.py") -> Path:
        p = tmp_path / name
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p
    return _write


@pytest.fixture
def run_checker() -> Callable[[str], List[Tuple[int, int, str, type]]]:
    """
    Run the checker and return the list of results for a given path.
    """
    def _run(path: str):
        checker = FileLengthChecker(tree=None, filename=path)
        return list(checker.run() or [])
    return _run


# ---------- Tests grouped by concern ----------

class TestTotalCounting:
    """Scenarios that rely on raw total line count (no ignores)."""

    def test_triggers_when_total_lines_exceed(
        self, write_py, run_checker, monkeypatch, restore_defaults
    ):
        p = write_py(["l1", "l2", "l3", "l4", "l5"], name="a.py")

        monkeypatch.setattr(FileLengthChecker, "max_file_length", 3, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_blank", False, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_comments", False, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_shebang", False, raising=False)

        errs = run_checker(str(p))
        assert len(errs) == 1
        (lineno, col, msg, _cls) = errs[0]
        assert (lineno, col) == (1, 0)
        assert msg.startswith("FLN001 file too long")
        assert "(limit 3)" in msg

    def test_no_error_when_within_limit(
        self, write_py, run_checker, monkeypatch, restore_defaults
    ):
        p = write_py(["l1", "l2", "l3"], name="b.py")

        monkeypatch.setattr(FileLengthChecker, "max_file_length", 3, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_blank", False, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_comments", False, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_shebang", False, raising=False)

        assert run_checker(str(p)) == []


class TestEffectiveCounting:
    """Scenarios using effective counting with ignore options."""

    def test_ignores_blank_and_comments(
        self, write_py, run_checker, monkeypatch, restore_defaults
    ):
        # total = 8; effective (code only) = 3
        p = write_py(
            [
                "# comment",
                "",
                "code1",
                "",
                "code2",
                "# another comment",
                "code3",
                "",
            ],
            name="c.py",
        )

        monkeypatch.setattr(FileLengthChecker, "max_file_length", 3, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_blank", True, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_comments", True, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_shebang", False, raising=False)

        assert run_checker(str(p)) == []  # only 3 effective lines

    def test_reports_when_effective_exceeds(
        self, write_py, run_checker, monkeypatch, restore_defaults
    ):
        # 4 code lines -> exceeds 3 even with ignores
        p = write_py(
            [
                "# comment",
                "",
                "code1",
                "code2",
                "code3",
                "code4",
            ],
            name="d.py",
        )

        monkeypatch.setattr(FileLengthChecker, "max_file_length", 3, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_blank", True, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_comments", True, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_shebang", False, raising=False)

        errs = run_checker(str(p))
        assert len(errs) == 1
        assert "effective=" in errs[0][2]  # suffix hints effective/total

    def test_shebang_ignored_when_option_set(
        self, write_py, run_checker, monkeypatch, restore_defaults
    ):
        p = write_py(
            [
                "#!/usr/bin/env python3",
                "code1",
                "code2",
                "code3",
            ],
            name="e.py",
        )

        monkeypatch.setattr(FileLengthChecker, "max_file_length", 3, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_blank", False, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_comments", False, raising=False)
        monkeypatch.setattr(FileLengthChecker, "ignore_shebang", True, raising=False)

        assert run_checker(str(p)) == []


class TestEdgeCases:
    """Edge cases such as stdin and unreadable files."""

    def test_stdin_is_ignored(self, run_checker, monkeypatch, restore_defaults):
        monkeypatch.setattr(FileLengthChecker, "max_file_length", 1, raising=False)
        assert run_checker("stdin") == []

    def test_nonexistent_file_is_ignored(self, run_checker, restore_defaults):
        assert run_checker("does/not/exist.py") == []


class TestOptionsParsing:
    """Ensure Flake8-style option parsing updates class attributes."""

    def test_parse_options_updates_class(self, restore_defaults):
        opts = types.SimpleNamespace(
            max_file_length=123,
            file_length_ignore_blank=True,
            file_length_ignore_comments=True,
            file_length_ignore_shebang=False,
        )

        FileLengthChecker.parse_options(opts)

        assert FileLengthChecker.max_file_length == 123
        assert FileLengthChecker.ignore_blank is True
        assert FileLengthChecker.ignore_comments is True
        assert FileLengthChecker.ignore_shebang is False
