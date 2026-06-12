# Standard Library
import pathlib
import tokenize

# PIP3 modules
import pytest

# local repo modules
import file_utils

FILES = file_utils.discover_files(extensions=(".py",), test_key="indentation")

REPORT_NAME = file_utils.report_name(__file__)

# Module-level dict of repo-relative POSIX key -> list of violation lines.
# Populated by the autouse collect_report fixture before any test runs.
VIOLATIONS_BY_FILE: dict[str, list[str]] = {}


#============================================
def multiline_string_lines(path: pathlib.Path) -> set[int]:
	"""
	Collect lines that are part of multiline string tokens.

	Args:
		path: File path.

	Returns:
		set[int]: Line numbers inside multiline strings.
	"""
	in_string: set[int] = set()
	with tokenize.open(path) as handle:
		tokens = tokenize.generate_tokens(handle.readline)
		for token in tokens:
			if token.type != tokenize.STRING:
				continue
			start_line = token.start[0]
			end_line = token.end[0]
			if end_line > start_line:
				in_string.update(range(start_line, end_line + 1))
	return in_string


#============================================
def inspect_file(path: pathlib.Path) -> list[int]:
	"""
	Check a file for mixed leading indentation within a single line.

	Args:
		path: File path.

	Returns:
		list[int]: Line numbers with mixed indentation within a single line.
	"""
	ignore_lines = multiline_string_lines(path)
	with tokenize.open(path) as handle:
		lines = handle.read().splitlines()
	bad_lines = []
	for line_number, line in enumerate(lines, 1):
		if line_number in ignore_lines:
			continue
		if not line.strip():
			continue
		prefix_chars = []
		for ch in line:
			if ch == " " or ch == "\t":
				prefix_chars.append(ch)
				continue
			break
		if not prefix_chars:
			continue
		has_tab = "\t" in prefix_chars
		has_space = " " in prefix_chars
		if has_tab and has_space:
			bad_lines.append(line_number)
			continue
	return bad_lines


#============================================
def summarize_indentation(path: pathlib.Path) -> tuple[int, int] | None:
	"""
	Return first tab line and first space line if both exist in the file.

	Args:
		path: File path.

	Returns:
		tuple[int, int] | None: First tab line and first space line, or None.
	"""
	ignore_lines = multiline_string_lines(path)
	with tokenize.open(path) as handle:
		lines = handle.read().splitlines()
	first_tab_line = None
	first_space_line = None
	for line_number, line in enumerate(lines, 1):
		if line_number in ignore_lines:
			continue
		if not line.strip():
			continue
		prefix_chars = []
		for ch in line:
			if ch == " " or ch == "\t":
				prefix_chars.append(ch)
				continue
			break
		if not prefix_chars:
			continue
		has_tab = "\t" in prefix_chars
		has_space = " " in prefix_chars
		if has_tab and first_tab_line is None:
			first_tab_line = line_number
		if has_space and first_space_line is None:
			first_space_line = line_number
		if first_tab_line and first_space_line:
			return (first_tab_line, first_space_line)
	return None


#============================================
def collect_violations(files: list[str]) -> dict[str, list[str]]:
	"""
	Run indentation checks on each file and return only those with violations.

	Runs inspect_file (mixed indentation within a line) and
	summarize_indentation (tabs and spaces mixed across a file) for each
	path. Files with no violations are omitted from the returned dict.

	Args:
		files: List of absolute file paths to check.

	Returns:
		dict[str, list[str]]: Repo-relative POSIX key -> list of violation lines,
			containing only files that have at least one violation.
	"""
	result = {}
	for path in files:
		rel = file_utils.rel_to_root(path)
		p = pathlib.Path(path)
		# Check for mixed indentation within individual lines.
		bad_lines = inspect_file(p)
		violations = []
		if bad_lines:
			for ln in bad_lines[:5]:
				violations.append(f"{rel}:{ln}: mixed indentation within line")
		# Check for tabs and spaces mixed across the whole file.
		indent_lines = summarize_indentation(p)
		if indent_lines is not None:
			tab_line, space_line = indent_lines
			violations.append(
				f"{rel}: tabs and spaces in file "
				f"(tab line {tab_line}, space line {space_line})"
			)
		# Only include files that have at least one violation.
		if violations:
			result[rel] = violations
	return result


#============================================
def make_report_lines(violations_by_file: dict[str, list[str]]) -> list[str]:
	"""
	Build the full report body from a violations dict.

	Iterates keys in sorted order and emits each file's violation lines.
	Returns a flat list of raw lines without trailing newlines.
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
	lines = ["indentation violations"]
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
def test_indentation_style(path: str) -> None:
	"""Fail on mixed indentation within a line or within a file."""
	rel = file_utils.rel_to_root(path)
	# Collect the violation lines for this file (empty list means clean).
	file_violations = VIOLATIONS_BY_FILE.get(rel, [])
	report_rel = file_utils.rel_to_root(file_utils.report_path(REPORT_NAME))
	message = (
		f"{len(file_violations)} indentation violation(s) in {rel}:\n"
		+ "\n".join(file_violations)
		+ f"\n See {report_rel}."
	)
	assert rel not in VIOLATIONS_BY_FILE, message
