# Standard Library
import ast

# PIP3 modules
import pytest

# local repo modules
import file_utils

FILES = file_utils.discover_files(extensions=(".py",), test_key="import_star")

REPORT_NAME = file_utils.report_name(__file__)

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def _find_import_star_matches(tree: ast.Module) -> list[tuple[int, str]]:
	"""
	Return (line_no, module_name) tuples for every from-import * in the tree.

	Uses file_utils.iter_imports for consistent import-node gathering.
	Each from-import * yields one tuple; line_no defaults to 0 when absent.

	Args:
		tree: Parsed AST module to scan.

	Returns:
		list[tuple[int, str]]: (line_no, module_name) pairs, one per star import.
	"""
	matches = []
	# Use shared iter_imports instead of a local ast.walk for import-node gathering.
	for node in file_utils.iter_imports(tree):
		if not isinstance(node, ast.ImportFrom):
			continue
		for alias in node.names:
			if alias.name != "*":
				continue
			line_no = getattr(node, "lineno", 0) or 0
			module_name = node.module or ""
			# Prepend dots for relative star imports (e.g., from . import *).
			if getattr(node, "level", 0):
				module_name = f"{'.' * node.level}{module_name}"
			matches.append((line_no, module_name))
			break
	return matches


#============================================
def _format_issue(rel_path: str, line_no: int, module_name: str) -> str:
	"""
	Format a single report line for an import * usage.

	Args:
		rel_path: Repo-relative POSIX path of the file.
		line_no: Line number of the star import.
		module_name: Module name being star-imported (empty string for bare `import *`).

	Returns:
		str: Formatted issue line.
	"""
	if module_name:
		return f"{rel_path}:{line_no}: import * from {module_name}"
	return f"{rel_path}:{line_no}: import *"


#============================================
def collect_violations(files: list[str]) -> dict[str, list[str]]:
	"""
	Scan each file for import * usage and return only those with violations.

	Parses each file via file_utils.parse_source. On a SyntaxError, records
	exactly one entry for that file and continues. On success, scans for
	from-import * statements and formats issue lines. Files with no violations
	are omitted from the returned dict.

	Args:
		files: List of absolute file paths to check.

	Returns:
		dict[str, list[str]]: Repo-relative POSIX key -> list of violation lines,
			containing only files that have at least one violation.
	"""
	result = {}
	for path in files:
		rel = file_utils.rel_to_root(path)
		tree, error = file_utils.parse_source(path)
		# Parsing failed: record one SyntaxError entry and skip rule checks.
		if tree is None:
			result[rel] = [f"{rel}: SyntaxError: {error}"]
			continue
		# Detect all from-import * usages in this file.
		matches = _find_import_star_matches(tree)
		if not matches:
			continue
		# Format and deduplicate issue lines, then sort for stable output.
		issues = sorted(set(_format_issue(rel, line_no, module_name) for line_no, module_name in matches))
		result[rel] = issues
	return result


#============================================
def make_report_lines(violations_by_file: dict[str, list[str]]) -> list[str]:
	"""
	Build the full report body from a violations dict.

	Iterates keys in sorted order and emits each file's violation lines in their
	existing order. Returns a flat list of raw lines without trailing newlines.
	The first two elements are header lines matching the prior report wording.

	Args:
		violations_by_file: Repo-relative POSIX key -> list of violation lines.

	Returns:
		list[str]: Raw report lines without trailing newlines. Empty when the
			violations dict is empty (clean run).
	"""
	# Return an empty list for a clean run; sync_report will purge the file.
	if not violations_by_file:
		return []
	# Emit header then each file's lines in sorted key order.
	lines = ["Import star report", "Violations:"]
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
	runs write the full body.
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
def test_import_star(file_path: str) -> None:
	"""Enforce no import * usage repo-wide."""
	rel = file_utils.rel_to_root(file_path)
	# Collect the violation lines for this file (empty list means clean).
	file_violations = VIOLATIONS_BY_FILE.get(rel, [])
	report_rel = file_utils.rel_to_root(file_utils.report_path(REPORT_NAME))
	message = (
		f"{len(file_violations)} import * violation(s) in {rel}:\n"
		+ "\n".join(file_violations)
		+ f"\n See {report_rel}."
	)
	assert rel not in VIOLATIONS_BY_FILE, message
