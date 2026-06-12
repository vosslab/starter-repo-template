# Standard Library
import ast

# PIP3 modules
import pytest

# local repo modules
import file_utils

FILES = file_utils.discover_files(extra_filter=lambda r: r.split("/")[-1] == "__init__.py", test_key="init_files")

REPORT_NAME = file_utils.report_name(__file__)

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}

_MIN_SUBSTANTIVE_LINES = 20
_MIN_CONTENT_CHARS = 100


#============================================
def count_substantive_lines(source: str) -> int:
	"""
	Count non-empty, non-comment lines in a source string.

	Args:
		source: Python source text.

	Returns:
		int: Number of lines that are non-empty and not pure comments.
	"""
	count = 0
	for line in source.splitlines():
		stripped = line.strip()
		if not stripped:
			continue
		if stripped.startswith("#"):
			continue
		count += 1
	return count


#============================================
def should_check_file(source: str) -> bool:
	"""
	Return True when file content is substantial enough to warrant linting.

	Args:
		source: Python source text.

	Returns:
		bool: True when the file meets the substantive-content threshold.
	"""
	if count_substantive_lines(source) >= _MIN_SUBSTANTIVE_LINES:
		return True
	if len(source.strip()) >= _MIN_CONTENT_CHARS:
		return True
	return False


#============================================
def is_module_docstring(node: ast.stmt) -> bool:
	"""
	Return True when a module-level node is a literal docstring expression.

	Args:
		node: A top-level AST statement node.

	Returns:
		bool: True when node is a string-literal Expr (module docstring).
	"""
	if not isinstance(node, ast.Expr):
		return False
	value = getattr(node, "value", None)
	if not isinstance(value, ast.Constant):
		return False
	return isinstance(value.value, str)


#============================================
def extract_target_names(node: ast.stmt) -> list[str]:
	"""
	Collect direct assignment target names for simple top-level checks.

	Args:
		node: A top-level AST statement node.

	Returns:
		list[str]: Simple Name target strings found in this assignment node.
	"""
	names = []
	if isinstance(node, ast.Assign):
		targets = node.targets
	elif isinstance(node, ast.AnnAssign):
		targets = [node.target]
	elif isinstance(node, ast.AugAssign):
		targets = [node.target]
	else:
		return names
	for target in targets:
		if isinstance(target, ast.Name):
			names.append(target.id)
	return names


#============================================
def find_init_issues(tree: ast.Module) -> list[tuple[int, str]]:
	"""
	Return line-numbered style violations for a parsed __init__.py AST.

	Does not read files; the caller is responsible for parsing and passing
	the tree. Returns an empty list when the tree body is empty or contains
	only a module docstring.

	Args:
		tree: Parsed AST module from an __init__.py file.

	Returns:
		list[tuple[int, str]]: (line_no, message) pairs for each violation.
	"""
	body = list(tree.body)
	if not body:
		return []
	if len(body) == 1 and is_module_docstring(body[0]):
		return []
	issues = []
	for node in body:
		if is_module_docstring(node):
			continue
		line_no = getattr(node, "lineno", 1) or 1
		if isinstance(node, (ast.Import, ast.ImportFrom)):
			issues.append((line_no, "imports are not allowed in __init__.py"))
			continue
		if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
			issues.append((line_no, "definitions are not allowed in __init__.py"))
			continue
		if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
			target_names = extract_target_names(node)
			if "__version__" in target_names:
				issues.append((line_no, "__version__ must not be assigned in __init__.py"))
				continue
			if "__all__" in target_names:
				issues.append((line_no, "__all__ is not allowed in __init__.py"))
				continue
			if any("EXPORTED_MODULES" in name for name in target_names):
				issues.append((line_no, "manual export lists are not allowed in __init__.py"))
				continue
			if any(name.endswith("_MAP") for name in target_names):
				issues.append((line_no, "function/class maps are not allowed in __init__.py"))
				continue
			issues.append((line_no, "global assignments are not allowed in __init__.py"))
			continue
		if isinstance(node, ast.If):
			issues.append((line_no, "conditional logic is not allowed in __init__.py"))
			continue
		issues.append((line_no, "implementation code is not allowed in __init__.py"))
	return issues


#============================================
def collect_violations(files: list[str]) -> dict[str, list[str]]:
	"""
	Run __init__.py style checks on each file and return only those with violations.

	For each file, reads source and skips trivially small files. Parses via
	file_utils.parse_source; on parse error records exactly one SyntaxError
	entry. Otherwise runs find_init_issues and formats each (line_no, message)
	pair. Files with no violations are omitted.

	Args:
		files: List of absolute file paths to __init__.py files to check.

	Returns:
		dict[str, list[str]]: Repo-relative POSIX key -> list of violation lines,
			containing only files with at least one violation.
	"""
	result = {}
	for path in files:
		rel = file_utils.rel_to_root(path)
		source = file_utils.read_source(path)
		# Skip trivially small files that are not worth linting.
		if not should_check_file(source):
			continue
		tree, error = file_utils.parse_source(path)
		# Parsing failed: record one SyntaxError entry and skip rule checks.
		if tree is None:
			result[rel] = [f"{rel}: SyntaxError: {error}"]
			continue
		issues = find_init_issues(tree)
		if not issues:
			continue
		# Format each (line_no, message) pair into a violation line.
		violations = sorted(set(f"{rel}:{line_no}: {message}" for line_no, message in issues))
		result[rel] = violations
	return result


#============================================
def make_report_lines(violations_by_file: dict[str, list[str]]) -> list[str]:
	"""
	Build the full report body from a violations dict.

	Returns a flat list of raw lines without trailing newlines. The first two
	elements are the header lines matching the prior report wording. Returns
	an empty list when the violations dict is empty (clean run).

	Args:
		violations_by_file: Repo-relative POSIX key -> list of violation lines.

	Returns:
		list[str]: Raw report lines without trailing newlines. Empty when clean.
	"""
	# Return an empty list for a clean run; sync_report will purge the file.
	if not violations_by_file:
		return []
	# Emit header then each file's lines in sorted key order.
	lines = ["__init__.py style report", "Violations:"]
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
def test_init_files(path: str) -> None:
	"""Report obvious __init__.py style violations in one file."""
	rel = file_utils.rel_to_root(path)
	# Collect the violation lines for this file (empty list means clean).
	file_violations = VIOLATIONS_BY_FILE.get(rel, [])
	report_rel = file_utils.rel_to_root(file_utils.report_path(REPORT_NAME))
	message = (
		f"{len(file_violations)} __init__.py violation(s) in {rel}:\n"
		+ "\n".join(file_violations)
		+ f"\n See {report_rel}."
	)
	assert rel not in VIOLATIONS_BY_FILE, message
