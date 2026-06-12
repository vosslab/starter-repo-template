# Standard Library
import ast

# PIP3 modules
import pytest

# local repo modules
import file_utils

# Banned module-level Name assignments that indicate local discovery scaffold.
# Each entry is a Name node id that must not appear as a module-level assignment.
BANNED_MODULE_ASSIGNMENTS = frozenset({
	"SKIP_DIRS",
})

# Banned function names that indicate local discovery scaffold that was
# centralized into file_utils. These names must not appear as top-level
# FunctionDef nodes in hygiene test files.
BANNED_FUNCTION_NAMES = frozenset({
	"path_has_skip_dir",
	"gather_files",
	"gather_changed_files",
})

REPORT_NAME = file_utils.report_name(__file__)

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}

# Discover only the top-level tests/test_*.py files.
# Keep only files whose repo-relative POSIX path matches tests/test_*.py
# (top-level tests/ only, not tests/meta/ or deeper subtrees).

#============================================
def _keep_top_level_test(rel: str) -> bool:
	"""
	Keep only top-level tests/test_*.py files.

	Excludes test files in sub-directories like tests/meta/.

	Args:
		rel: Repo-relative POSIX path.

	Returns:
		bool: True when the path is exactly tests/test_<stem>.py.
	"""
	parts = rel.split("/")
	# Must be exactly two parts: "tests" / "test_*.py".
	if len(parts) != 2:
		return False
	if parts[0] != "tests":
		return False
	return parts[1].startswith("test_") and parts[1].endswith(".py")


FILES = file_utils.discover_files(
	extensions=(".py",),
	extra_filter=_keep_top_level_test,
	test_key="pytest_hygiene",
)


#============================================
def check_no_banned_module_assignments(tree: ast.Module, rel: str) -> list[str]:
	"""
	Fail when a module-level Name assignment duplicates file_utils scaffold.

	Checks for module-level Assign statements whose target is a plain Name
	matching one of the banned names (e.g. SKIP_DIRS). These were centralized
	into file_utils and must not be re-introduced locally.

	Args:
		tree: Parsed AST module.
		rel: Repo-relative POSIX path for error messages.

	Returns:
		list[str]: Violation messages (empty when clean).
	"""
	violations = []
	for node in tree.body:
		if not isinstance(node, ast.Assign):
			continue
		for target in node.targets:
			if not isinstance(target, ast.Name):
				continue
			if target.id in BANNED_MODULE_ASSIGNMENTS:
				violations.append(
					f"{rel}:{node.lineno}: module-level `{target.id}` found; "
					"file_utils is the single owner of this scaffold -- "
					"remove it and use file_utils.discover_files instead."
				)
	return violations


#============================================
def check_no_banned_functions(tree: ast.Module, rel: str) -> list[str]:
	"""
	Fail when a top-level FunctionDef duplicates file_utils scaffold.

	Checks the module body for FunctionDef nodes whose name matches a
	banned scaffold name. These functions were centralized into file_utils
	and must not be re-introduced in hygiene tests.

	Args:
		tree: Parsed AST module.
		rel: Repo-relative POSIX path for error messages.

	Returns:
		list[str]: Violation messages (empty when clean).
	"""
	violations = []
	for node in tree.body:
		if not isinstance(node, ast.FunctionDef):
			continue
		if node.name in BANNED_FUNCTION_NAMES:
			violations.append(
				f"{rel}:{node.lineno}: function `{node.name}` found; "
				"file_utils is the single owner of this scaffold -- "
				"remove it and use file_utils.discover_files instead."
			)
	return violations


#============================================
def collect_violations(files: list[str]) -> dict[str, list[str]]:
	"""
	Run all hygiene checks on each file and return only those with violations.

	Iterates files in the given order. For each file, parses it via
	file_utils.parse_source. If parsing fails, records exactly one SyntaxError
	entry for that file and skips the rule-specific checks. Otherwise runs
	check_no_banned_module_assignments and check_no_banned_functions. Files
	with no violations are omitted from the returned dict.

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
		# Run each hygiene rule check and accumulate violation lines.
		violations = check_no_banned_module_assignments(tree, rel)
		violations += check_no_banned_functions(tree, rel)
		# Only include files that have at least one violation.
		if violations:
			result[rel] = violations
	return result


#============================================
def make_report_lines(violations_by_file: dict[str, list[str]]) -> list[str]:
	"""
	Build the full report body from a violations dict.

	Iterates keys in sorted order and emits each file's violation lines in their
	existing order. Returns a flat list of raw lines without trailing newlines.
	The first element is a header line matching the prior report wording.

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
	lines = ["pytest hygiene violations"]
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
	"path", FILES,
	ids=lambda p: file_utils.rel_to_root(p),
)
def test_pytest_hygiene(path: str) -> None:
	"""Guard that hygiene tests do not reintroduce local discovery scaffold."""
	rel = file_utils.rel_to_root(path)
	file_violations = VIOLATIONS_BY_FILE.get(rel, [])
	report_rel = file_utils.rel_to_root(file_utils.report_path(REPORT_NAME))
	message = (
		f"{len(file_violations)} scaffold duplication(s) in {rel}:\n"
		+ "\n".join(file_violations)
		+ f"\n See {report_rel}."
	)
	assert rel not in VIOLATIONS_BY_FILE, message
