"""Unit tests for file_utils.sync_report (both branches of its contract)."""

# Standard Library
import os

# PIP3 modules
import pytest

# local repo modules
import file_utils

# Unique throwaway report name so a stale repo-root file is never confused
# with a real hygiene report; each test cleans it up afterward.
SELFTEST_NAME = "report_sync_report_selftest.txt"


#============================================
@pytest.fixture(autouse=True)
def cleanup_selftest_report() -> pytest.FixtureRequest:
	"""Autouse fixture: purge the selftest report before and after each test."""
	file_utils.purge_report(SELFTEST_NAME)
	yield
	file_utils.purge_report(SELFTEST_NAME)


#============================================
class TestSyncReport:
	"""Behavioral tests pinning both branches of the sync_report contract."""

	def test_non_empty_lines_writes_exact_content(self) -> None:
		"""Non-empty lines produce a file holding each line plus one newline."""
		lines = ["== HEADER ==", "violation one", "", "violation two"]
		path = file_utils.sync_report(SELFTEST_NAME, lines)
		# The path returned must be the canonical report path.
		assert path == file_utils.report_path(SELFTEST_NAME)
		# Content is exactly the lines joined by newline plus a trailing newline.
		with open(path, encoding="utf-8") as handle:
			content = handle.read()
		assert content == "\n".join(lines) + "\n"

	def test_empty_lines_purges_report(self) -> None:
		"""Empty lines purge the report so a clean run leaves no file."""
		# Seed a stale report so we can prove sync_report removes it.
		file_utils.write_report(SELFTEST_NAME, "stale content\n")
		path = file_utils.sync_report(SELFTEST_NAME, [])
		# The file must be absent after a clean (empty-lines) sync.
		assert not os.path.exists(path)
