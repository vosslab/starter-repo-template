"""Protect the auto-fixer's successful-change exit code from becoming a test error."""

# Standard Library
import pathlib
import subprocess
import unittest.mock

# PIP3 modules
import pytest

# local repo modules
import file_utils


#============================================
def _make_script(tmp_path: pathlib.Path, name: str) -> None:
	"""Create a dummy script under tmp_path/tests/<name>."""
	tests_dir = tmp_path / "tests"
	tests_dir.mkdir(exist_ok=True)
	script = tests_dir / name
	script.write_text("# dummy")


#============================================
def test_run_fixer_script_returns_two(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
	"""Return code 2 (fixed by script) -> (2, stderr) with no exception.

	Regression guard for the original cascade bug: exit 2 (successful fix)
	was treated as failure and raised inside a module-scoped fixture.
	"""
	_make_script(tmp_path, "fix_dummy.py")

	fake_result = unittest.mock.MagicMock()
	fake_result.returncode = 2
	fake_result.stderr = "auto-fixed"

	monkeypatch.setattr(subprocess, "run", unittest.mock.MagicMock(return_value=fake_result))
	monkeypatch.setattr(file_utils, "get_repo_root", lambda: str(tmp_path))

	returncode, stderr = file_utils.run_fixer_script("fix_dummy.py", "some_file.py")
	assert returncode == 2
	assert stderr == "auto-fixed"
