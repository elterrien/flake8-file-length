import os
import sys
import subprocess
from pathlib import Path
import pytest

def _run(cmd, cwd):
    """Run a command and return (rc, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr

@pytest.fixture(scope="session")
def ensure_flake8_installed():
    pytest.importorskip("flake8")
    return True

@pytest.fixture(scope="session")
def ensure_plugin_registered(ensure_flake8_installed):
    rc, out, _ = _run([sys.executable, "-m", "flake8", "--version"], cwd=os.getcwd())
    if "flake8-file-length" not in out:
        pytest.skip(
            "flake8-file-length plugin not registered. "
            "Install it first: `pip install -e .`"
        )
    return True

@pytest.fixture
def write_cfg(tmp_path: Path):
    def _write(content: str) -> Path:
        cfg = tmp_path / ".flake8"
        cfg.write_text(content, encoding="utf-8")
        return cfg
    return _write

@pytest.fixture
def write_py(tmp_path: Path):
    def _write(lines, name="sample.py") -> Path:
        p = tmp_path / name
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p
    return _write

class TestFlake8IntegrationBasic:
    def test_violation_emitted_with_default_counting(
        self, tmp_path, write_cfg, write_py, ensure_plugin_registered
    ):
        write_py(["l1", "l2", "l3", "l4", "l5"], name="too_long.py")
        write_cfg(
            """
[flake8]
select = FLN
max-file-length = 3
file-length-ignore-blank = false
file-length-ignore-comments = false
file-length-ignore-shebang = false
            """.strip()
        )
        # Force config + select from CLI for robustness
        rc, out, err = _run(
            [sys.executable, "-m", "flake8", ".", "--config", ".flake8", "--select", "FLN"],
            cwd=tmp_path,
        )
        if rc != 1 or "FLN001 file too long" not in out:
            # Helpful debug when the assertion would fail
            raise AssertionError(
                f"Unexpected flake8 result:\nRC={rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
            )

    def test_no_violation_when_within_limit(
        self, tmp_path, write_cfg, write_py, ensure_plugin_registered
    ):
        write_py(["l1", "l2", "l3"], name="ok.py")
        write_cfg(
            """
[flake8]
select = FLN
max-file-length = 3
            """.strip()
        )
        rc, out, err = _run(
            [sys.executable, "-m", "flake8", ".", "--config", ".flake8", "--select", "FLN"],
            cwd=tmp_path,
        )
        if rc != 0 or out.strip() != "":
            raise AssertionError(
                f"Expected no violations.\nRC={rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
            )

class TestFlake8IntegrationIgnores:
    def test_ignore_blank_and_comments_allows_three_code_lines(
        self, tmp_path, write_cfg, write_py, ensure_plugin_registered
    ):
        write_py(
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
            name="filtered.py",
        )
        write_cfg(
            """
[flake8]
select = FLN
max-file-length = 3
file-length-ignore-blank = true
file-length-ignore-comments = true
file-length-ignore-shebang = false
            """.strip()
        )
        rc, out, err = _run(
            [sys.executable, "-m", "flake8", ".", "--config", ".flake8", "--select", "FLN"],
            cwd=tmp_path,
        )
        if rc != 0 or out.strip() != "":
            raise AssertionError(
                f"Expected no violations with ignores.\nRC={rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
            )

    def test_ignore_shebang(
        self, tmp_path, write_cfg, write_py, ensure_plugin_registered
    ):
        write_py(
            [
                "#!/usr/bin/env python3",
                "code1",
                "code2",
                "code3",
            ],
            name="shebang.py",
        )
        write_cfg(
            """
[flake8]
select = FLN
max-file-length = 3
file-length-ignore-shebang = true
            """.strip()
        )
        rc, out, err = _run(
            [sys.executable, "-m", "flake8", ".", "--config", ".flake8", "--select", "FLN"],
            cwd=tmp_path,
        )
        if rc != 0 or out.strip() != "":
            raise AssertionError(
                f"Expected no violations with shebang ignored.\nRC={rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
            )

class TestFlake8IntegrationMessages:
    def test_suffix_includes_effective_totals(
        self, tmp_path, write_cfg, write_py, ensure_plugin_registered
    ):
        write_py(
            [
                "# comment",
                "",
                "code1",
                "code2",
                "code3",
                "code4",
            ],
            name="too_many_effective.py",
        )
        write_cfg(
            """
[flake8]
select = FLN
max-file-length = 3
file-length-ignore-blank = true
file-length-ignore-comments = true
file-length-ignore-shebang = false
            """.strip()
        )
        rc, out, err = _run(
            [sys.executable, "-m", "flake8", ".", "--config", ".flake8", "--select", "FLN"],
            cwd=tmp_path,
        )
        if rc != 1 or "effective=" not in out:
            raise AssertionError(
                f"Expected a violation with effective suffix.\nRC={rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
            )
