# Standard Library
import ast

# PIP3 modules
import pytest

# local repo modules
import file_utils

FILES = file_utils.discover_files(extensions=(".py",), test_key="import_dot")

REPORT_NAME = file_utils.report_name(__file__)

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def format_issue(rel_path: str, line_no: int, import_root: str) -> str:
	"""
	Format a report line for a relative from-import statement.

	Args:
		rel_path: Repo-relative POSIX path for the file containing the import.
		line_no: Line number of the offending import statement.
		import_root: The leading dot(s) and optional module name, e.g. '.repolib'.

	Returns:
		str: Human-readable violation line.
	"""
	return f"{rel_path}:{line_no}: relative import from {import_root}"


#============================================
def collect_violations(files: list[str]) -> dict[str, list[str]]:
	"""
	Scan each file for relative from-imports and return only those with violations.

	For each file, parses via file_utils.parse_source. On a SyntaxError records
	exactly one parse-error entry. Otherwise scans import nodes via
	file_utils.iter_imports and records any ImportFrom node whose level > 0.
	Files with no violations are omitted from the returned dict.

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
		# Parsing failed: record one SyntaxError entry and skip import checks.
		if tree is None:
			result[rel] = [f"{rel}: SyntaxError: {error}"]
			continue
		# Collect each relative from-import node (level > 0 means relative).
		issues = []
		for node in file_utils.iter_imports(tree):
			if not isinstance(node, ast.ImportFrom):
				continue
			if getattr(node, "level", 0) <= 0:
				continue
			line_no = getattr(node, "lineno", 0) or 0
			module_name = node.module or ""
			# Build the dotted import root, e.g. '.' or '.repolib'.
			import_root = f"{'.' * node.level}{module_name}"
			issues.append(format_issue(rel, line_no, import_root))
		# Deduplicate and sort, then store only when at least one violation exists.
		issues = sorted(set(issues))
		if issues:
			result[rel] = issues
	return result


#============================================
def make_report_lines(violations_by_file: dict[str, list[str]]) -> list[str]:
	"""
	Build the full report body from a violations dict.

	Header matches the prior report wording. Returns an empty list for a clean
	run so sync_report purges the file.

	Args:
		violations_by_file: Repo-relative POSIX key -> list of violation lines.

	Returns:
		list[str]: Raw report lines without trailing newlines. Empty when the
			violations dict is empty (clean run).
	"""
	# Empty dict means a clean run; sync_report will purge the file.
	if not violations_by_file:
		return []
	# Header matches prior wording: "Import dot report" then "Violations:".
	lines = ["Import dot report", "Violations:"]
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
def test_import_dot(file_path: str) -> None:
	"""Enforce no relative from-imports repo-wide."""
	rel = file_utils.rel_to_root(file_path)
	# Collect the violation lines for this file (empty list means clean).
	file_violations = VIOLATIONS_BY_FILE.get(rel, [])
	report_rel = file_utils.rel_to_root(file_utils.report_path(REPORT_NAME))
	message = (
		f"{len(file_violations)} relative import violation(s) in {rel}:\n"
		+ "\n".join(file_violations)
		+ f"\n See {report_rel}."
	)
	assert rel not in VIOLATIONS_BY_FILE, message
