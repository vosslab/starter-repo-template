"""Unit tests for file_utils.report_name and file_utils.append_report_block."""

# Standard Library
import pathlib

# PIP3 modules
import pytest

# local repo modules
import file_utils


#============================================
class TestReportName:
	"""Behavioral tests for the report_name helper."""

	def test_report_name_strips_test_prefix_and_extension(self) -> None:
		"""report_name maps a test module path to its canonical report filename."""
		result = file_utils.report_name("/x/tests/test_foo.py")
		assert result == "report_foo.txt"

	def test_report_name_with_compound_stem(self) -> None:
		"""report_name handles multi-word test file stems correctly."""
		result = file_utils.report_name("/some/path/tests/test_ascii_compliance.py")
		assert result == "report_ascii_compliance.txt"


#============================================
class TestAppendReportBlock:
	"""Behavioral tests for the append_report_block helper."""

	def test_header_written_once_and_lines_present(
		self,
		tmp_path: pathlib.Path,
		monkeypatch: pytest.MonkeyPatch,
	) -> None:
		"""Header appears exactly once; both appended line sets are present."""
		# Redirect report_path to write under tmp_path instead of the repo root.
		monkeypatch.setattr(file_utils, "get_repo_root", lambda: str(tmp_path))

		name = "report_test_helpers_test.txt"
		header = "== TEST REPORT HEADER =="

		# First call: file does not yet exist, so the header should be written.
		file_utils.append_report_block(name, header, ["line_alpha", "line_beta"])
		# Second call: file already exists, header must NOT be written again.
		file_utils.append_report_block(name, header, ["line_gamma", "line_delta"])

		report_file = pathlib.Path(tmp_path) / name
		content = report_file.read_text(encoding="utf-8")

		# Header written exactly once.
		assert content.count(header) == 1

		# All four lines are present.
		assert "line_alpha\n" in content
		assert "line_beta\n" in content
		assert "line_gamma\n" in content
		assert "line_delta\n" in content
