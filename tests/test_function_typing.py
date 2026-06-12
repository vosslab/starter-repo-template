# Standard Library
import ast

# PIP3 modules
import pytest

# local repo modules
import file_utils

FILES = file_utils.discover_files(extensions=(".py",), test_key="function_typing")

REPORT_NAME = file_utils.report_name(__file__)

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}

# Args that never require an annotation (implicit type from the call protocol).
IMPLICIT_ARG_NAMES = frozenset({"self", "cls"})


#============================================
def _annotatable_args(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
	"""
	Return the args that require a type annotation for the given function def.

	Combines posonlyargs, args, and kwonlyargs and excludes self and cls, which
	are exempt because their type is implicit from the call protocol. Does not
	include *args (vararg) or **kwargs (kwarg), which are never required.

	Args:
		func_node: A parsed FunctionDef or AsyncFunctionDef AST node.

	Returns:
		list[ast.arg]: Argument nodes that must carry an annotation.
	"""
	# Combine all annotatable groups into one flat list.
	all_args = func_node.args.posonlyargs + func_node.args.args + func_node.args.kwonlyargs
	# Filter out self and cls; they are exempt from annotation.
	return [arg for arg in all_args if arg.arg not in IMPLICIT_ARG_NAMES]


#============================================
def _is_typing_import(node: ast.Import | ast.ImportFrom) -> bool:
	"""
	Return True if the import node references the typing module.

	Detects `import typing`, `import typing as X`, `import typing.something`,
	`from typing import ...`, and `from typing.x import y`. All of these are
	banned in this repo; callers should use builtin generics and PEP 604 unions.

	Args:
		node: An ast.Import or ast.ImportFrom node from a parsed module.

	Returns:
		bool: True when the node imports from the typing module.
	"""
	if isinstance(node, ast.Import):
		# Catch `import typing`, `import typing as X`, and `import typing.something`.
		return any(
			alias.name == "typing" or alias.name.startswith("typing.")
			for alias in node.names
		)
	# Catch `from typing import ...` and `from typing.x import y`.
	return node.module == "typing" or (
		node.module is not None and node.module.startswith("typing.")
	)


#============================================
def check_no_typing_import(tree: ast.Module, rel: str) -> list[str]:
	"""
	Return violations when the file imports from the typing module.

	A plain builtin type like `list`, `dict`, or `tuple` satisfies every
	annotation gate in this repo. Use builtin generics and PEP 604 unions
	(`X | None`) instead of the typing module.

	Checks for `import typing`, `import typing as X`, `import typing.something`,
	and `from typing import ...`. All four forms are banned.

	Args:
		tree: Parsed AST module.
		rel: Repo-relative POSIX path for error messages.

	Returns:
		list[str]: Violation messages (empty when clean).
	"""
	violations = []
	for node in file_utils.iter_imports(tree):
		if _is_typing_import(node):
			violations.append(
				f"{rel}:{node.lineno}: write `import typing` as builtin generics "
				"(list, dict, tuple) and PEP 604 unions (X | None) instead."
			)
	return violations


#============================================
def check_function_annotations(tree: ast.Module, rel: str) -> list[str]:
	"""
	Return violations for any function def missing return or argument annotations.

	A plain builtin type satisfies the gate -- `-> list` or `-> None` is enough
	for a return annotation, and `x: str` or `x: object` is enough for a param.
	Parametrized generics like `list[str]` are also accepted; the gate requires
	only that SOME annotation is present.

	Walks the tree and checks every ast.FunctionDef and ast.AsyncFunctionDef.
	Requires:
	- A return annotation (node.returns is not None).
	- An annotation on each positional-only, regular, and keyword-only arg,
	  except `self` and `cls` which are implicitly typed.

	Does NOT require annotations on *args (vararg) or **kwargs (kwarg).
	Lambdas are skipped (they cannot carry annotations).

	Args:
		tree: Parsed AST module.
		rel: Repo-relative POSIX path for error messages.

	Returns:
		list[str]: Violation messages, one per missing annotation.
	"""
	violations = []
	for node in ast.walk(tree):
		if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
			continue
		func_name = node.name
		lineno = node.lineno
		# Check return annotation -- a plain type like `-> list` or `-> None` is enough.
		if node.returns is None:
			violations.append(
				f"{rel}:{lineno}: {func_name}() needs a return annotation -- "
				"a plain type like `-> list` or `-> None` is enough."
			)
		# Check each annotatable argument; a bare type like `x: str` or `x: object` is enough.
		for arg in _annotatable_args(node):
			if arg.annotation is None:
				violations.append(
					f"{rel}:{lineno}: {func_name}() arg `{arg.arg}` needs an annotation -- "
					"a bare type like `x: str`, or `x: object` when the type is open, is enough."
				)
	return violations


#============================================
def collect_violations(files: list[str]) -> dict[str, list[str]]:
	"""
	Run all typing checks on each file and return only those with violations.

	Iterates files in the given order. For each file, parses it via
	file_utils.parse_source. If parsing fails, records exactly one SyntaxError
	entry for that file and skips the rule-specific checks. Otherwise runs
	check_no_typing_import and check_function_annotations. Files with no
	violations are omitted from the returned dict.

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
		# Run each typing rule check and accumulate violation lines.
		violations = check_no_typing_import(tree, rel)
		violations += check_function_annotations(tree, rel)
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
	lines = ["function typing violations"]
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
def test_function_typing(path: str) -> None:
	"""Enforce no typing-module imports and full function annotations repo-wide."""
	rel = file_utils.rel_to_root(path)
	# Collect the violation lines for this file (empty list means clean).
	file_violations = VIOLATIONS_BY_FILE.get(rel, [])
	report_rel = file_utils.rel_to_root(file_utils.report_path(REPORT_NAME))
	message = (
		f"{len(file_violations)} annotation/typing violation(s) in {rel}:\n"
		+ "\n".join(file_violations)
		+ f"\n See {report_rel}."
	)
	assert rel not in VIOLATIONS_BY_FILE, message
