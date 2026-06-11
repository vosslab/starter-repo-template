# Standard Library
import ast
import os

# PIP3 modules
import pytest

# local repo modules
import file_utils

FILES = file_utils.discover_files(extensions=(".py",), test_key="function_typing")

REPORT_NAME = "report_function_typing.txt"

# Args that never require an annotation (implicit type from the call protocol).
IMPLICIT_ARG_NAMES = frozenset({"self", "cls"})


#============================================
@pytest.fixture(scope="module", autouse=True)
def reset_function_typing_report() -> None:
	"""
	Remove stale report file before this module runs.
	"""
	file_utils.purge_report(REPORT_NAME)


#============================================
def check_no_typing_import(tree: ast.Module, rel: str) -> list[str]:
	"""
	Fail if the file imports from the typing module.

	Checks for `import typing`, `import typing as X`, and
	`from typing import ...`. All three are banned; use builtin generics
	and PEP 604 unions instead.

	Args:
		tree: Parsed AST module.
		rel: Repo-relative POSIX path for error messages.

	Returns:
		list[str]: Violation messages (empty when clean).
	"""
	violations = []
	for node in file_utils.iter_imports(tree):
		if isinstance(node, ast.Import):
			# Catch `import typing`, `import typing as X`, and `import typing.something`.
			for alias in node.names:
				if alias.name == "typing" or alias.name.startswith("typing."):
					violations.append(
						f"{rel}:{node.lineno}: `import typing` is banned; "
						"use builtin generics (list, dict, tuple) and PEP 604 unions (X | None)."
					)
		elif isinstance(node, ast.ImportFrom):
			# Catch `from typing import ...` and `from typing.x import y`.
			if node.module == "typing" or (node.module is not None and node.module.startswith("typing.")):
				violations.append(
					f"{rel}:{node.lineno}: `from typing import ...` is banned; "
					"use builtin generics (list, dict, tuple) and PEP 604 unions (X | None)."
				)
	return violations


#============================================
def check_function_annotations(tree: ast.Module, rel: str) -> list[str]:
	"""
	Fail if any function def is missing return or argument annotations.

	Walks the tree and checks every ast.FunctionDef and
	ast.AsyncFunctionDef. Requires:
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
		# Check return annotation.
		if node.returns is None:
			violations.append(
				f"{rel}:{lineno}: {func_name}() missing return annotation."
			)
		# Check each annotatable argument group.
		all_args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
		for arg in all_args:
			if arg.arg in IMPLICIT_ARG_NAMES:
				# self and cls are exempted; type is implicit from protocol.
				continue
			if arg.annotation is None:
				violations.append(
					f"{rel}:{lineno}: {func_name}() arg `{arg.arg}` missing annotation."
				)
	return violations


#============================================
@pytest.mark.parametrize(
	"path", FILES,
	ids=lambda p: file_utils.rel_to_root(p),
)
def test_function_typing(path: str) -> None:
	"""Enforce no typing-module imports and full function annotations repo-wide."""
	rel = file_utils.rel_to_root(path)
	tree, error = file_utils.parse_source(path)
	if tree is None:
		raise AssertionError(f"{rel}: SyntaxError: {error}")
	violations = check_no_typing_import(tree, rel)
	violations += check_function_annotations(tree, rel)
	if violations:
		# Detect first creation before appending so the header is written once.
		file_exists = os.path.exists(file_utils.report_path(REPORT_NAME))
		lines = []
		if not file_exists:
			lines.append("function typing violations")
		lines.extend(violations)
		text = "".join(f"{line}\n" for line in lines)
		report_file = file_utils.append_report(REPORT_NAME, text)
		report_rel = file_utils.rel_to_root(report_file)
		raise AssertionError(
			f"{len(violations)} annotation/typing violation(s) in {rel}:\n"
			+ "\n".join(violations)
			+ f"\n See {report_rel}."
		)
