#!/usr/bin/env python3
"""
e2e_reset_routing.py - end-to-end harness for reset_repo.py routing.

Exercises the interactive reset path against real temp git repos, one per
project type, by copying the git-tracked template working tree into a scratch
directory, initializing a fresh git repo there, and driving reset_repo.py via
STDIN (no automation flags beyond --yes, which only skips the final
"Proceed?" confirmation). Because reset_repo.py mutates and self-removes, every
run happens in a throwaway copy; the real template checkout is never touched.

The harness asserts the reset routing matrix (presence/absence) for the files
WP16 cares about, plus stale-file removal and the noexist-vs-overwrite
second-run distinction. It also checks the exclude_repos gate for
docs/CLAUDE_HOOK_USAGE_GUIDE.md, but that gate is a CROSS-REPO propagation
concern (do not ship the template mirror over the hook repo's own canonical
copy), so a single-repo reset -- where the propagation source dir equals the
repo being reset -- cannot exercise it. WP16 therefore allows covering it via a
propagation-plan check against the engine directly, which is what this harness
does (see check_exclude_repos).

This is a tests/e2e/ runner: it lives outside pytest (excluded via
collect_ignore in tests/conftest.py), is self-contained, uses real git in a
temp dir, may use asserts, and exits non-zero on the first mismatch. Run it
directly:

    source source_me.sh && python3 tests/e2e/e2e_reset_routing.py
"""

import os
import sys
import shutil
import tempfile
import subprocess

# The exclude_repos gate is a cross-repo propagation concern that a single-repo
# reset cannot exercise, so it is checked against the propagation engine
# directly. Anchor sys.path on the template root (this file's repo) so the
# repolib package imports regardless of cwd, then import the planner module.
_TEMPLATE_ROOT = subprocess.run(
	["git", "rev-parse", "--show-toplevel"],
	cwd=os.path.dirname(os.path.abspath(__file__)),
	capture_output=True, text=True, check=True,
).stdout.strip()
if _TEMPLATE_ROOT not in sys.path:
	sys.path.insert(0, _TEMPLATE_ROOT)

# local repo modules
import repolib.files

# Interview answer order, derived directly from reset_repo.py main():
#   1. project type        ([p]ython / [t]ypescript / [r]ust / [o]ther)
#   2. code license        (we use 'm' -> MIT)
#   3. docs license         (empty line accepts CC-BY-4.0 default)
#   4. PyPI? (python only)  ([y/N]; prompt is SKIPPED for non-python types)
#   5. stage changes?       ([Y/n])
#   6. create a commit?     ([y/N])
# The final "Proceed? [y/N]" is skipped because the harness passes --yes.

# Each matrix entry: project type, pypi answer, and expected presence per file.
# A value of True means the file MUST exist after reset; False means it MUST be
# absent. The four checked files are the WP16 routing-matrix targets.
CHECKED_FILES = [
	"devel/submit_to_pypi.py",
	"pip_requirements.txt",
	"pip_requirements-dev.txt",
	"docs/PYTHON_STYLE.md",
]


#============================================
# Template source discovery
#============================================

def find_template_root() -> str:
	"""Return the template checkout root via git rev-parse on this file's dir."""
	# Anchor on this script's directory so the harness works regardless of cwd.
	script_dir = os.path.dirname(os.path.abspath(__file__))
	result = subprocess.run(
		["git", "rev-parse", "--show-toplevel"],
		cwd=script_dir, capture_output=True, text=True, check=True,
	)
	return result.stdout.strip()


#============================================
# Temp-repo construction
#============================================

def list_template_files(template_root: str) -> list[str]:
	"""Return repo-relative paths of every file a fresh clone-plus-edits would hold.

	Combines tracked files (git ls-files) with untracked-but-not-ignored files
	(git ls-files --others --exclude-standard). This yields exactly the file set a
	consumer would have: committed template content plus in-flight source files
	that are not yet committed (e.g. repolib/manifests.py,
	meta/propagation/manifests.yaml). Listing files only, both commands skip empty
	directories, which matters because reset_repo.py's end-state verifier rejects
	any leftover template-owned directory and git itself never carries empty dirs.

	Args:
		template_root (str): Source template checkout root.

	Returns:
		list[str]: Sorted, de-duplicated repo-relative file paths.
	"""
	tracked = subprocess.run(
		["git", "ls-files"],
		cwd=template_root, capture_output=True, text=True, check=True,
	).stdout.splitlines()
	untracked = subprocess.run(
		["git", "ls-files", "--others", "--exclude-standard"],
		cwd=template_root, capture_output=True, text=True, check=True,
	).stdout.splitlines()
	combined = sorted(set(tracked) | set(untracked))
	return combined


def build_temp_repo(template_root: str, dest_dir: str) -> None:
	"""Copy the clone-equivalent template file set into dest_dir, init a fresh repo.

	Copies tracked plus untracked-not-ignored files (see list_template_files) so
	the temp repo reflects the current template state, including uncommitted source
	files propagation depends on, while excluding empty directories and gitignored
	artifacts. A fresh git init plus an initial commit gives reset_repo.py a tracked
	tree so its `git rm` cleanup steps succeed and its end-state verifier passes.

	Args:
		template_root (str): Source template checkout root.
		dest_dir (str): Destination directory (created here if absent).
	"""
	os.makedirs(dest_dir, exist_ok=True)
	for rel_path in list_template_files(template_root):
		src = os.path.join(template_root, rel_path)
		# A listed path may have been removed on disk locally; skip if missing.
		if not os.path.isfile(src):
			continue
		dst = os.path.join(dest_dir, rel_path)
		os.makedirs(os.path.dirname(dst), exist_ok=True)
		shutil.copy2(src, dst)
	# Initialize a self-contained git repo so reset_repo.py git operations work.
	git_init_repo(dest_dir)


def git_init_repo(repo_dir: str) -> None:
	"""Initialize repo_dir as a git repo with one initial commit."""
	subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
	# Identity is required for the commit; set it locally so the harness does not
	# depend on the runner's global git config.
	subprocess.run(
		["git", "config", "user.email", "e2e@example.com"], cwd=repo_dir, check=True
	)
	subprocess.run(
		["git", "config", "user.name", "e2e harness"], cwd=repo_dir, check=True
	)
	subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
	subprocess.run(
		["git", "commit", "-q", "-m", "seed template snapshot"],
		cwd=repo_dir, check=True,
	)


#============================================
# Reset invocation
#============================================

def build_stdin(project_type: str, pypi: bool) -> str:
	"""Assemble the STDIN answer string for one reset interview.

	The PyPI prompt only appears for python repos, so it is included only then.
	Code license 'm' -> MIT; the empty docs-license line accepts the default;
	stage 'Y'; commit 'n'. The trailing newline terminates the last prompt.

	Args:
		project_type (str): One of python, typescript, rust, other.
		pypi (bool): Whether to answer yes to the python PyPI prompt.

	Returns:
		str: Newline-joined answers ready for subprocess input.
	"""
	type_key = project_type[0]
	answers = [type_key, "m", ""]
	if project_type == "python":
		answers.append("y" if pypi else "n")
	answers.append("Y")
	answers.append("n")
	# Join with newlines and add a trailing newline for the final prompt.
	stdin_text = "\n".join(answers) + "\n"
	return stdin_text


def run_reset(repo_dir: str, stdin_text: str) -> subprocess.CompletedProcess:
	"""Run the copied reset_repo.py inside repo_dir, fed by stdin_text.

	Uses --yes to skip only the final Proceed confirmation. The script is invoked
	by its path inside repo_dir so the copied repolib package (next to it) is the
	propagation source. cwd is repo_dir so git rev-parse resolves to the copy.

	Args:
		repo_dir (str): Temp repo root holding the copied reset_repo.py.
		stdin_text (str): Interview answers.

	Returns:
		subprocess.CompletedProcess: Completed process (not checked here so the
			caller can surface stdout/stderr on failure).
	"""
	script_path = os.path.join(repo_dir, "reset_repo.py")
	completed = subprocess.run(
		[sys.executable, script_path, "--yes"],
		cwd=repo_dir, input=stdin_text, text=True, capture_output=True,
	)
	return completed


def reset_must_succeed(repo_dir: str, stdin_text: str, label: str) -> None:
	"""Run reset and abort the harness with diagnostics if it fails."""
	completed = run_reset(repo_dir, stdin_text)
	if completed.returncode != 0:
		print(f"FAIL [{label}]: reset_repo.py exited {completed.returncode}")
		print("--- stdout ---")
		print(completed.stdout)
		print("--- stderr ---")
		print(completed.stderr)
		sys.exit(1)


#============================================
# Assertion helpers
#============================================

def assert_presence(repo_dir: str, rel_path: str, expected: bool, label: str) -> None:
	"""Assert a file's presence/absence after reset; record PASS or fail hard."""
	full_path = os.path.join(repo_dir, rel_path)
	present = os.path.isfile(full_path)
	state = "present" if present else "absent"
	want = "present" if expected else "absent"
	if present != expected:
		print(f"FAIL [{label}]: {rel_path} is {state}, expected {want}")
		sys.exit(1)
	print(f"  PASS [{label}]: {rel_path} {state} (expected {want})")


#============================================
# Scenario: routing matrix
#============================================

def expected_matrix(project_type: str, pypi: bool) -> dict[str, bool]:
	"""Return the expected presence map for one (type, pypi) combination."""
	# submit_to_pypi ships only on python + PyPI=yes.
	submit = (project_type == "python" and pypi)
	# pip_requirements.txt is python-only (python noexist bucket).
	pip_req = (project_type == "python")
	# pip_requirements-dev.txt is universal noexist (ships for every type).
	pip_dev = True
	# docs/PYTHON_STYLE.md is universal overwrite (ships for every type).
	py_style = True
	matrix = {
		"devel/submit_to_pypi.py": submit,
		"pip_requirements.txt": pip_req,
		"pip_requirements-dev.txt": pip_dev,
		"docs/PYTHON_STYLE.md": py_style,
	}
	return matrix


def check_matrix(template_root: str, scratch: str) -> None:
	"""Run reset for each type/pypi combination and assert the routing matrix."""
	combinations = [
		("python", True),
		("python", False),
		("typescript", False),
		("other", False),
	]
	print("\n=== routing matrix ===")
	for project_type, pypi in combinations:
		label = f"{project_type}/pypi={pypi}"
		repo_dir = os.path.join(scratch, f"matrix_{project_type}_{int(pypi)}")
		os.makedirs(repo_dir)
		build_temp_repo(template_root, repo_dir)
		stdin_text = build_stdin(project_type, pypi)
		reset_must_succeed(repo_dir, stdin_text, label)
		matrix = expected_matrix(project_type, pypi)
		for rel_path in CHECKED_FILES:
			assert_presence(repo_dir, rel_path, matrix[rel_path], label)


#============================================
# Scenario: stale-file handling
#============================================

def seed_stale_submit(repo_dir: str) -> None:
	"""Pre-seed a leftover, tracked devel/submit_to_pypi.py before reset.

	The content is a sentinel so a refresh (overwrite from the overlay) is
	distinguishable from the original stale file.
	"""
	devel_dir = os.path.join(repo_dir, "devel")
	os.makedirs(devel_dir, exist_ok=True)
	stale_path = os.path.join(devel_dir, "submit_to_pypi.py")
	with open(stale_path, "w") as f:
		f.write("# STALE SENTINEL - should be removed or overwritten\n")
	# Track it so reset_repo.py git rm can act on it (PyPI=no path).
	subprocess.run(["git", "add", "devel/submit_to_pypi.py"], cwd=repo_dir, check=True)
	subprocess.run(
		["git", "commit", "-q", "-m", "seed stale submit_to_pypi"],
		cwd=repo_dir, check=True,
	)


def file_contains(repo_dir: str, rel_path: str, needle: str) -> bool:
	"""Return True when rel_path exists and contains needle."""
	full_path = os.path.join(repo_dir, rel_path)
	if not os.path.isfile(full_path):
		return False
	with open(full_path, "r") as f:
		content = f.read()
	return needle in content


def check_stale_handling(template_root: str, scratch: str) -> None:
	"""Pre-seed a stale submit_to_pypi.py; verify removal (no) and refresh (yes)."""
	print("\n=== stale-file handling ===")

	# PyPI=no: the stale leftover must be removed.
	label_no = "stale/python/pypi=False"
	repo_no = os.path.join(scratch, "stale_python_0")
	os.makedirs(repo_no)
	build_temp_repo(template_root, repo_no)
	seed_stale_submit(repo_no)
	reset_must_succeed(repo_no, build_stdin("python", False), label_no)
	assert_presence(repo_no, "devel/submit_to_pypi.py", False, label_no)

	# PyPI=yes: the file must be present and refreshed (sentinel gone).
	label_yes = "stale/python/pypi=True"
	repo_yes = os.path.join(scratch, "stale_python_1")
	os.makedirs(repo_yes)
	build_temp_repo(template_root, repo_yes)
	seed_stale_submit(repo_yes)
	reset_must_succeed(repo_yes, build_stdin("python", True), label_yes)
	assert_presence(repo_yes, "devel/submit_to_pypi.py", True, label_yes)
	# Refreshed means the stale sentinel content is gone (overwritten by overlay).
	if file_contains(repo_yes, "devel/submit_to_pypi.py", "STALE SENTINEL"):
		print(f"FAIL [{label_yes}]: submit_to_pypi.py still holds the stale sentinel")
		sys.exit(1)
	print(f"  PASS [{label_yes}]: submit_to_pypi.py refreshed (stale sentinel gone)")


#============================================
# Scenario: second-run noexist vs overwrite
#============================================

def check_second_run(template_root: str, scratch: str) -> None:
	"""Run reset twice on python PyPI=yes; noexist file survives, overwrite refreshes.

	A consumer edit to pip_requirements-dev.txt (universal noexist) must be left
	intact on the second reset, while devel/submit_to_pypi.py (overlay overwrite)
	must be refreshed from the template overlay.
	"""
	print("\n=== second-run noexist vs overwrite ===")
	label = "second-run/python/pypi=True"
	repo_dir = os.path.join(scratch, "secondrun_python_1")
	os.makedirs(repo_dir)
	build_temp_repo(template_root, repo_dir)

	# First reset lays down both files.
	reset_must_succeed(repo_dir, build_stdin("python", True), label + "#1")
	assert_presence(repo_dir, "pip_requirements-dev.txt", True, label + "#1")
	assert_presence(repo_dir, "devel/submit_to_pypi.py", True, label + "#1")

	# Consumer edits the noexist file and corrupts the overwrite file. Re-seed the
	# template snapshot so a second reset can run (reset removed templates/ etc.),
	# but preserve the consumer-edited files by copying them across.
	consumer_dev_marker = "# CONSUMER EDIT - must survive second reset\n"
	dev_path = os.path.join(repo_dir, "pip_requirements-dev.txt")
	with open(dev_path, "a") as f:
		f.write(consumer_dev_marker)
	corrupt_marker = "# CORRUPTED - must be refreshed by second reset\n"
	submit_path = os.path.join(repo_dir, "devel", "submit_to_pypi.py")
	with open(submit_path, "w") as f:
		f.write(corrupt_marker)

	# Rebuild a fresh template snapshot in a new dir, then overlay the two
	# consumer-edited files so the second reset sees an already-bootstrapped repo
	# carrying consumer edits. This mirrors a re-run on a real consumer repo.
	repo2 = os.path.join(scratch, "secondrun_python_1b")
	os.makedirs(repo2)
	build_temp_repo(template_root, repo2)
	# Carry the consumer-edited noexist and corrupted overwrite files across.
	shutil.copy2(dev_path, os.path.join(repo2, "pip_requirements-dev.txt"))
	os.makedirs(os.path.join(repo2, "devel"), exist_ok=True)
	shutil.copy2(submit_path, os.path.join(repo2, "devel", "submit_to_pypi.py"))
	# pyproject.toml present from the first run would also normally carry over; the
	# second reset re-seeds it only when absent, which is fine either way for this
	# overwrite-vs-noexist check. Commit the carried edits so git rm can act.
	subprocess.run(["git", "add", "-A"], cwd=repo2, check=True)
	subprocess.run(
		["git", "commit", "-q", "-m", "carry consumer edits"], cwd=repo2, check=True
	)

	# Second reset.
	reset_must_succeed(repo2, build_stdin("python", True), label + "#2")
	# noexist file: consumer edit must survive (file present, not overwritten).
	if not file_contains(repo2, "pip_requirements-dev.txt", consumer_dev_marker.strip()):
		print(f"FAIL [{label}#2]: consumer edit to pip_requirements-dev.txt was lost")
		sys.exit(1)
	print(f"  PASS [{label}#2]: pip_requirements-dev.txt consumer edit survived (noexist)")
	# overwrite file: corruption must be gone (refreshed from overlay).
	assert_presence(repo2, "devel/submit_to_pypi.py", True, label + "#2")
	if file_contains(repo2, "devel/submit_to_pypi.py", "CORRUPTED"):
		print(f"FAIL [{label}#2]: submit_to_pypi.py was not refreshed (overwrite)")
		sys.exit(1)
	print(f"  PASS [{label}#2]: submit_to_pypi.py refreshed (overwrite)")


#============================================
# Scenario: exclude_repos gate
#============================================

def assert_plan_contains(
	template_root: str, repo_dir: str, rel_path: str, expected: bool, label: str
) -> None:
	"""Assert rel_path's presence in a propagation plan's overwrite_files bucket.

	Computes the plan for a python consumer whose destination basename comes from
	repo_dir, then checks whether rel_path is routed into overwrite_files. The
	repo_dir argument is consumed by should_ship_override purely for its basename,
	so it need not exist on disk. Records PASS or fails the harness hard.

	Args:
		template_root (str): Source template checkout root (propagation source).
		repo_dir (str): Destination repo path; only its basename is consulted.
		rel_path (str): Repo-root-relative path to look for in overwrite_files.
		expected (bool): True if rel_path must be present in overwrite_files.
		label (str): Scenario label for PASS/FAIL output.
	"""
	plan = repolib.files.compute_propagation_plan(
		template_root, "python", repo_dir=repo_dir
	)
	present = rel_path in plan["overwrite_files"]
	state = "present" if present else "absent"
	want = "present" if expected else "absent"
	basename = os.path.basename(os.path.normpath(repo_dir))
	if present != expected:
		print(
			f"FAIL [{label}]: {rel_path} is {state} in overwrite_files for "
			f"basename {basename!r}, expected {want}"
		)
		sys.exit(1)
	print(
		f"  PASS [{label}]: {rel_path} {state} in overwrite_files for "
		f"basename {basename!r} (expected {want})"
	)


def check_exclude_repos(template_root: str) -> None:
	"""Confirm the exclude_repos gate via the propagation engine, not a reset.

	The exclude_repos gate is a CROSS-REPO propagation concern: when the template
	propagates into the source repo claude-code-permissions-hook, it must NOT ship
	its mirror of docs/CLAUDE_HOOK_USAGE_GUIDE.md over that repo's own canonical
	copy. A single-repo reset (propagation source dir == repo being reset) cannot
	exercise this gate, and asserting the file absent after such a reset would
	wrongly demand destroying the hook repo's own doc.

	The gate keys off the destination repo basename (see should_ship_override), so
	it is checked here by calling compute_propagation_plan twice and asserting that
	docs/CLAUDE_HOOK_USAGE_GUIDE.md is routed into overwrite_files for a normal
	basename but withheld for the excluded basename. The destination repo_dir is
	consulted only for its basename, so no on-disk repo is needed.
	"""
	print("\n=== exclude_repos gate (propagation plan) ===")
	hook_doc = "docs/CLAUDE_HOOK_USAGE_GUIDE.md"

	# Normal-named destination: the hook guide is routed to overwrite_files.
	normal_dir = os.path.join(tempfile.gettempdir(), "some-consumer")
	assert_plan_contains(template_root, normal_dir, hook_doc, True, "exclude/normal-name")

	# Excluded destination: basename matches exactly; the guide is withheld.
	excluded_dir = os.path.join(tempfile.gettempdir(), "claude-code-permissions-hook")
	assert_plan_contains(
		template_root, excluded_dir, hook_doc, False,
		"exclude/claude-code-permissions-hook",
	)


#============================================
# Main
#============================================

def main() -> None:
	template_root = find_template_root()
	print(f"template root: {template_root}")
	# All temp repos live under one scratch dir so cleanup is a single rmtree.
	scratch = tempfile.mkdtemp(prefix="e2e_reset_routing_")
	print(f"scratch dir:   {scratch}")
	try:
		check_matrix(template_root, scratch)
		check_stale_handling(template_root, scratch)
		check_second_run(template_root, scratch)
		check_exclude_repos(template_root)
	finally:
		# Always clean up the scratch tree, even on a mid-run failure exit path.
		shutil.rmtree(scratch, ignore_errors=True)

	print("\n=== SUMMARY ===")
	print("PASS: all reset routing scenarios succeeded.")


if __name__ == "__main__":
	main()
