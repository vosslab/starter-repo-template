import os
import shutil
import subprocess

import pytest

import file_utils

REPO_ROOT = file_utils.get_repo_root()
REPORT_NAME = file_utils.report_name(__file__)
CHUNK_SIZE = 200

# Module-level dict of repo-relative POSIX key -> list of pyflakes output lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}

FILES = file_utils.discover_files(extensions=(".py",), test_key="pyflakes_code_lint")


#============================================
def chunked(items: list[str], size: int) -> list[list[str]]:
	"""
	Split items into fixed-size chunks.

	Args:
		items: The list to split.
		size: Maximum size for each chunk.

	Returns:
		list[list[str]]: Sub-lists of at most size items.
	"""
	chunks = []
	for start in range(0, len(items), size):
		chunks.append(items[start:start + size])
	return chunks


#============================================
def normalize_path(path: str) -> str:
	"""
	Normalize a path for stable comparisons.

	Args:
		path: Filesystem path.

	Returns:
		str: Absolute, real path.
	"""
	return os.path.realpath(os.path.abspath(path))


#============================================
def index_output_lines(lines: list[str]) -> dict[str, list[str]]:
	"""
	Index pyflakes output lines by normalized file path.

	Args:
		lines: Raw stdout/stderr lines from a pyflakes run.

	Returns:
		dict[str, list[str]]: Normalized absolute path -> list of pyflakes lines.
	"""
	index: dict[str, list[str]] = {}
	for line in lines:
		separator = line.find(":")
		if separator == -1:
			continue
		path_text = line[:separator]
		normalized = normalize_path(path_text)
		if normalized not in index:
			index[normalized] = []
		index[normalized].append(line)
	return index


#============================================
def run_pyflakes(repo_root: str, files: list[str]) -> list[str]:
	"""
	Run pyflakes on a file list and return output lines.

	Args:
		repo_root: Repository root used as the working directory.
		files: Absolute paths of Python files to check.

	Returns:
		list[str]: Combined stdout and stderr lines from pyflakes.
	"""
	if not files:
		return []
	pyflakes_bin = shutil.which("pyflakes")
	if not pyflakes_bin:
		raise RuntimeError("pyflakes not found on PATH.")
	output_lines = []
	for chunk in chunked(files, CHUNK_SIZE):
		result = subprocess.run(
			[pyflakes_bin] + chunk,
			capture_output=True,
			text=True,
			cwd=repo_root,
		)
		if result.stdout:
			output_lines.extend(result.stdout.splitlines())
		if result.stderr:
			output_lines.extend(result.stderr.splitlines())
	return output_lines


#============================================
def collect_violations(files: list[str]) -> dict[str, list[str]]:
	"""
	Run pyflakes once over all files and return per-file violation lines.

	Runs pyflakes on the full file list, indexes the output by file path,
	then maps each input file to its pyflakes lines using repo-relative POSIX
	keys. Files with no pyflakes output are omitted from the returned dict.

	Args:
		files: Sorted list of absolute paths to check.

	Returns:
		dict[str, list[str]]: Repo-relative POSIX key -> list of pyflakes
			output lines, containing only files that have at least one line.
	"""
	all_lines = run_pyflakes(REPO_ROOT, files)
	# Index raw lines by normalized absolute path for fast lookup.
	line_index = index_output_lines(all_lines)
	result: dict[str, list[str]] = {}
	for path in files:
		normalized = normalize_path(path)
		file_lines = line_index.get(normalized, [])
		if not file_lines:
			continue
		# Store under the repo-relative POSIX key.
		rel = file_utils.rel_to_root(path)
		result[rel] = file_lines
	return result


#============================================
def make_report_lines(violations_by_file: dict[str, list[str]]) -> list[str]:
	"""
	Build the full report body from a violations dict.

	Iterates keys in sorted order and emits each file's pyflakes lines in
	their existing order. Returns an empty list for a clean run.

	Args:
		violations_by_file: Repo-relative POSIX key -> list of pyflakes lines.

	Returns:
		list[str]: Raw report lines without trailing newlines.
			Empty when the violations dict is empty (clean run).
	"""
	if not violations_by_file:
		return []
	# Emit header then each file's lines in sorted key order.
	lines = ["pyflakes violations"]
	for rel in sorted(violations_by_file):
		lines += violations_by_file[rel]
	return lines


#============================================
@pytest.fixture(scope="module", autouse=True)
def collect_report() -> None:
	"""
	Autouse fixture: populate VIOLATIONS_BY_FILE and sync the report file.

	Clears and rebuilds the module-level violations dict, then calls
	file_utils.sync_report so that clean runs purge the report and failing
	runs write the full body. This is the single report-writing site;
	per-file test asserts read VIOLATIONS_BY_FILE after it is populated.
	"""
	# Clear any state left from a previous collection in the same process.
	VIOLATIONS_BY_FILE.clear()
	VIOLATIONS_BY_FILE.update(collect_violations(FILES))
	lines: list[str] = make_report_lines(VIOLATIONS_BY_FILE)
	file_utils.sync_report(REPORT_NAME, lines)


#============================================
@pytest.mark.parametrize(
	"file_path", FILES,
	ids=lambda p: file_utils.rel_to_root(p),
)
def test_pyflakes(file_path: str) -> None:
	"""Enforce zero pyflakes violations on every Python file in the repo."""
	rel = file_utils.rel_to_root(file_path)
	file_violations = VIOLATIONS_BY_FILE.get(rel, [])
	report_rel = file_utils.rel_to_root(file_utils.report_path(REPORT_NAME))
	message = (
		f"{len(file_violations)} pyflakes violation(s) in {rel}:\n"
		+ "\n".join(file_violations)
		+ f"\n See {report_rel}."
	)
	assert rel not in VIOLATIONS_BY_FILE, message
