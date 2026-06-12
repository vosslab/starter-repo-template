import shutil
import subprocess

import file_utils


REPO_ROOT = file_utils.get_repo_root()
REPORT_NAME = file_utils.report_name(__file__)

FILES = file_utils.discover_files(extensions=(".py",), test_key="bandit_security")


#============================================
def run_bandit(repo_root: str) -> tuple[int, str]:
	"""
	Run bandit on tracked Python files and return (exit_code, combined_output).
	"""
	bandit_bin = shutil.which("bandit")
	if not bandit_bin:
		raise RuntimeError("bandit not found on PATH.")
	files = FILES
	if not files:
		return (0, "")
	command = [
		bandit_bin,
		"--severity-level",
		"medium",
		"--confidence-level",
		"medium",
	] + files
	result = subprocess.run(
		command,
		capture_output=True,
		text=True,
		cwd=repo_root,
	)
	output = result.stdout + result.stderr
	return (result.returncode, output)


#============================================
def test_bandit_security() -> None:
	"""
	Run bandit at severity medium or higher.
	"""
	exit_code, output = run_bandit(REPO_ROOT)

	# Build violation lines: header first, then bandit output lines (strip trailing blank)
	lines: list[str] = []
	has_violations = exit_code != 0
	if has_violations:
		header = "Bandit security issues detected:"
		output_lines = output.rstrip("\n").split("\n")
		lines = [header] + output_lines

	# Always sync: non-empty writes the report; empty purges any stale file
	report_path = file_utils.sync_report(REPORT_NAME, lines)

	assert not has_violations, (
		f"Bandit issues detected. See {file_utils.rel_to_root(report_path)}"
	)
