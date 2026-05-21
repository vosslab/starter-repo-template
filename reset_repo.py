#!/usr/bin/env python3
"""
reset_repo.py - bootstrap a fresh clone of starter-repo-template.

Prompts (or accepts flags) for project type and SPDX licenses, writes the
REPO_TYPE marker, installs selected LICENSE files, invokes the
propagator with --bootstrap to lay down type-dispatched files, truncates
README + CHANGELOG, and removes itself.
"""

import os
import sys
import argparse
import datetime
import subprocess
import tempfile

# Try to import detect_repo_type from tools/; if not available, prediction is skipped.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
try:
	import detect_repo_type
except ImportError:
	detect_repo_type = None

CODE_LICENSES = ["MIT", "Apache-2.0", "LGPL-3.0", "GPL-3.0", "AGPL-3.0", "MPL-2.0"]
DOCS_LICENSES = ["CC-BY-4.0", "CC-BY-SA-4.0", "none"]

CODE_ALIASES = {
	"m": "MIT",
	"a": "Apache-2.0",
	"l": "LGPL-3.0",
	"g": "GPL-3.0",
	"ag": "AGPL-3.0",
	"mp": "MPL-2.0",
}

DOCS_ALIASES = {
	"cb": "CC-BY-4.0",
	"cs": "CC-BY-SA-4.0",
	"n": "none",
}

TYPE_TOKENS = ["python", "typescript", "rust", "other"]


def resolve_license(user_input: str, canonical: list, aliases: dict, default: str | None = None) -> str:
	"""Resolve license token via alias or unique prefix."""
	token = user_input.strip().lower()
	if token == "":
		if default is None:
			raise ValueError("empty license input; no default available")
		return default
	if token in aliases:
		return aliases[token]
	matches = [name for name in canonical if name.lower().startswith(token)]
	if len(matches) == 1:
		return matches[0]
	raise ValueError(f"ambiguous or unknown license: {user_input!r}")


def get_repo_root() -> str:
	"""Return the repository root path via git rev-parse."""
	try:
		result = subprocess.run(
			["git", "rev-parse", "--show-toplevel"],
			capture_output=True,
			text=True,
			check=True,
		)
		return result.stdout.strip()
	except subprocess.CalledProcessError:
		sys.exit("Error: not in a git repository")


def preflight_check(repo_root: str, code_license: str, docs_license: str) -> None:
	"""Verify that license files exist in LICENSES/ before proceeding."""
	code_path = os.path.join(repo_root, f"LICENSES/LICENSE.{code_license}.md")
	if not os.path.isfile(code_path):
		sys.exit(f"license file missing: {code_path}")
	if docs_license != "none":
		docs_path = os.path.join(repo_root, f"LICENSES/LICENSE.{docs_license}.md")
		if not os.path.isfile(docs_path):
			sys.exit(f"license file missing: {docs_path}")


def verify_license_copy(repo_root: str, license_type: str, spdx_id: str) -> bool:
	"""Check if license file was copied and contains recognizable license text."""
	target = os.path.join(repo_root, f"LICENSE.{spdx_id}.md")
	if not os.path.isfile(target):
		return False
	if os.path.getsize(target) == 0:
		return False
	with open(target, "r") as f:
		first_bytes = f.read(100)
	normalized_spdx = spdx_id.replace("-", " ")
	return spdx_id in first_bytes or normalized_spdx in first_bytes


def parse_args():
	parser = argparse.ArgumentParser(
		description="Reset a cloned starter-repo-template to base configuration"
	)
	parser.add_argument(
		"--type",
		dest="project_type",
		choices=TYPE_TOKENS,
		help="Project type (python, typescript, rust, other)",
	)
	parser.add_argument(
		"--code-license",
		dest="code_license",
		help="Code license (SPDX id, alias, or unique prefix)",
	)
	parser.add_argument(
		"--docs-license",
		dest="docs_license",
		help="Docs license (SPDX id, alias, unique prefix, or 'none')",
	)
	parser.add_argument(
		"--non-interactive",
		dest="non_interactive",
		action="store_true",
		help="Non-interactive mode (requires all three content flags)",
	)
	parser.add_argument(
		"--yes",
		dest="skip_confirm",
		action="store_true",
		help="Skip final confirmation prompt",
	)
	parser.add_argument(
		"--dry-run",
		dest="dry_run",
		action="store_true",
		help="Print actions without executing",
	)
	parser.add_argument(
		"--commit",
		dest="commit",
		action="store_true",
		help="Create commit after staging changes",
	)
	parser.add_argument(
		"--no-stage",
		dest="no_stage",
		action="store_true",
		help="Leave changes in working tree, do not stage",
	)
	parser.add_argument(
		"--force",
		dest="force",
		action="store_true",
		help="Allow overwriting existing marker and package.json",
	)
	return parser.parse_args()


#============================================
# Module-level helpers (extracted from main)
#============================================

def dry_run_print(msg: str, dry_run: bool) -> None:
	"""Print DRY-RUN prefixed message if dry_run is True."""
	if dry_run:
		print(f"DRY-RUN: {msg}")


def write_marker(repo_root: str, project_type: str, dry_run: bool) -> int:
	"""Write REPO_TYPE marker atomically via temp + replace."""
	marker_path = os.path.join(repo_root, "REPO_TYPE")
	content = f"{project_type}\n"
	if dry_run:
		escaped_content = content.replace('"', '\\"').replace('\n', '\\n')
		dry_run_print(f'write REPO_TYPE ("{escaped_content}")', dry_run)
	else:
		with tempfile.NamedTemporaryFile(
			mode="w", dir=repo_root, delete=False
		) as tmp:
			tmp.write(content)
			tmp_name = tmp.name
		os.replace(tmp_name, marker_path)
	return 1


def copy_and_verify_license(repo_root: str, source_path: str, target_filename: str, spdx_id: str, dry_run: bool) -> int:
	"""Copy LICENSES/LICENSE.<spdx>.md to repo root and verify."""
	target_path = os.path.join(repo_root, target_filename)
	if dry_run:
		dry_run_print(f"copy {source_path} -> {target_path}", dry_run)
		dry_run_print(
			f"verify {target_filename}: file exists, non-zero, contains {spdx_id}", dry_run
		)
		return 2
	else:
		with open(source_path, "r") as src:
			content = src.read()
		with open(target_path, "w") as dst:
			dst.write(content)
		if not verify_license_copy(repo_root, "code", spdx_id):
			rollback_msg = "Rollback: run 'git restore --staged . && git restore .' to discard staged and working-tree changes."
			sys.exit(
				f"License copy verification failed: {target_filename}\n{rollback_msg}"
			)
		return 1


def git_rm(path: str, dry_run: bool) -> int:
	"""Remove tracked file via git rm."""
	if dry_run:
		dry_run_print(f"git rm {path}", dry_run)
	else:
		subprocess.run(["git", "rm", path], check=True, capture_output=True)
	return 1


def git_rm_recursive(path: str, dry_run: bool) -> int:
	"""Remove tracked directory recursively via git rm -r."""
	if dry_run:
		dry_run_print(f"git rm -r {path}", dry_run)
	else:
		subprocess.run(["git", "rm", "-r", path], check=True, capture_output=True)
	return 1


def substitute_typescript_package_json(repo_root: str, dry_run: bool) -> int:
	"""Substitute __REPO_NAME__ and __REPO_VERSION__ in package.json in-place."""
	package_json_path = os.path.join(repo_root, "package.json")
	if not os.path.isfile(package_json_path):
		return 0
	with open(package_json_path, "r") as f:
		content = f.read()
	# Guard: only substitute when placeholders are present, so an existing
	# consumer-customized package.json is left untouched (noexist bucket
	# already protects against overwrite at copy time; this is belt-and-braces).
	if "__REPO_NAME__" not in content:
		return 0
	repo_name = os.path.basename(repo_root)
	# CalVer: YYYY.M.0 (no leading zero on month per CalVer convention)
	now = datetime.datetime.now()
	repo_version = f"{now.year}.{now.month}.0"
	if dry_run:
		dry_run_print(
			f"substitute __REPO_NAME__ -> {repo_name}, __REPO_VERSION__ -> {repo_version} in {package_json_path}", dry_run
		)
		return 1
	content = content.replace("__REPO_NAME__", repo_name)
	content = content.replace("__REPO_VERSION__", repo_version)
	with open(package_json_path, "w") as f:
		f.write(content)
	return 1


def run_propagate(repo_root: str, dry_run: bool) -> int:
	"""Run propagate_style_guides.py --bootstrap to dispatch type-specific files."""
	source_dir = os.path.dirname(os.path.abspath(__file__))
	repo_name = os.path.basename(repo_root)
	cmd = [
		"python3",
		"propagate_style_guides.py",
		"--bootstrap",
		"--repo",
		repo_name,
		"--source-dir",
		source_dir,
		"--no-auto-discover",
	]
	if dry_run:
		dry_run_print(f"subprocess: {' '.join(cmd)}", dry_run)
	else:
		subprocess.run(cmd, cwd=repo_root, check=True)
	return 1


def truncate_file(path: str, repo_root: str, dry_run: bool) -> int:
	"""Truncate file to zero bytes."""
	full_path = os.path.join(repo_root, path)
	if dry_run:
		dry_run_print(f"truncate {path}", dry_run)
	else:
		open(full_path, "w").close()
	return 1


#============================================
# Config resolution helpers
#============================================

def resolve_project_type(repo_root: str, project_type: str, force: bool, non_interactive: bool) -> str:
	"""Resolve project type via detection, existing marker, or user input."""
	marker_path = os.path.join(repo_root, "REPO_TYPE")
	existing_marker = None
	if os.path.isfile(marker_path):
		with open(marker_path, "r") as f:
			existing_marker = f.read().strip()

	if not project_type:
		if existing_marker and not force:
			default_type = existing_marker
		else:
			# Try to predict repo type (if detect_repo_type module is available)
			if detect_repo_type:
				token, confidence, _ = detect_repo_type.detect_repo_type(repo_root)
				if confidence == 'high' and token != 'ambiguous':
					default_type = token
					if not force:
						# Auto-select high confidence without prompting
						print(f"Detected: {token} (auto-selected; use --force to override)")
						project_type = token
				elif confidence == 'medium':
					default_type = token
				else:
					default_type = "python"
			else:
				default_type = "python"

		if project_type is None:
			if non_interactive:
				project_type = default_type
			else:
				user_input = input(
					f"Project type? [p]ython / [t]ypescript / [r]ust / [o]ther [{default_type[0]}]: "
				).strip()
				if user_input == "":
					project_type = default_type
				elif user_input.lower() == "p":
					project_type = "python"
				elif user_input.lower() == "t":
					project_type = "typescript"
				elif user_input.lower() == "r":
					project_type = "rust"
				elif user_input.lower() == "o":
					project_type = "other"
				else:
					sys.exit("Invalid project type")

	if existing_marker and existing_marker != project_type and not force:
		sys.exit(
			f"Marker already exists ({existing_marker}); use --force to change to {project_type}"
		)

	return project_type


def resolve_licenses(code_license: str, docs_license: str, non_interactive: bool) -> tuple:
	"""Resolve code and docs licenses via alias, prefix, or user input."""
	if not code_license:
		if non_interactive:
			sys.exit("--code-license required in non-interactive mode")
		while True:
			user_input = input(
				"Code license?\n  [m] MIT\n  [a] Apache-2.0\n  [l] LGPL-3.0\n  [g] GPL-3.0\n  [ag] AGPL-3.0\n  [mp] MPL-2.0\nChoice: "
			).strip()
			try:
				code_license = resolve_license(
					user_input, CODE_LICENSES, CODE_ALIASES, default=None
				)
				break
			except ValueError as e:
				print(f"Error: {e}. Please try again.")
	else:
		try:
			code_license = resolve_license(
				code_license, CODE_LICENSES, CODE_ALIASES, default=None
			)
		except ValueError as e:
			sys.exit(f"Invalid code license: {e}")

	if not docs_license:
		if non_interactive:
			docs_license = "CC-BY-4.0"
		else:
			user_input = input(
				"Docs license?\n  [cb] CC-BY-4.0\n  [cs] CC-BY-SA-4.0\n  [n] none\nChoice [cb]: "
			).strip()
			try:
				docs_license = resolve_license(
					user_input, DOCS_LICENSES, DOCS_ALIASES, default="CC-BY-4.0"
				)
			except ValueError as e:
				sys.exit(f"Invalid docs license: {e}")
	else:
		try:
			docs_license = resolve_license(
				docs_license, DOCS_LICENSES, DOCS_ALIASES, default=None
			)
		except ValueError as e:
			sys.exit(f"Invalid docs license: {e}")

	return code_license, docs_license


def confirm_plan(project_type: str, code_license: str, docs_license: str, stage: bool, commit: bool, dry_run: bool, skip_confirm: bool, non_interactive: bool) -> None:
	"""Print summary and prompt for confirmation."""
	if not skip_confirm and not non_interactive:
		mode = "DRY-RUN" if dry_run else "LIVE"
		print("")
		print("Summary:")
		print(f"  type:         {project_type}")
		print(f"  code license: {code_license}")
		print(f"  docs license: {docs_license}")
		print(f"  stage:        {'yes' if stage else 'no'}")
		print(f"  commit:       {'yes' if commit else 'no'}")
		print(f"  mode:         {mode}")
		confirm_input = input("Proceed? [y/N]: ").strip()
		if not confirm_input or confirm_input.lower() != "y":
			sys.exit("Aborted")


def main():
	args = parse_args()
	repo_root = get_repo_root()

	# === phase: arg validation ===
	if args.non_interactive:
		if not args.project_type or not args.code_license or not args.docs_license:
			sys.exit("--non-interactive requires --type, --code-license, and --docs-license")
		if not args.skip_confirm:
			sys.exit("--non-interactive requires --yes")

	if args.commit and args.no_stage:
		sys.exit("--commit and --no-stage conflict")

	# === phase: config resolution ===
	project_type = resolve_project_type(repo_root, args.project_type, args.force, args.non_interactive)
	code_license, docs_license = resolve_licenses(args.code_license, args.docs_license, args.non_interactive)
	preflight_check(repo_root, code_license, docs_license)

	# === phase: summary and confirmation ===
	stage = not args.no_stage
	confirm_plan(project_type, code_license, docs_license, stage, args.commit, args.dry_run, args.skip_confirm, args.non_interactive)

	action_count = 0

	# === phase: marker write ===
	action_count += write_marker(repo_root, project_type, args.dry_run)

	# === phase: license install ===
	code_source = os.path.join(repo_root, f"LICENSES/LICENSE.{code_license}.md")
	action_count += copy_and_verify_license(repo_root, code_source, f"LICENSE.{code_license}.md", code_license, args.dry_run)

	if docs_license != "none":
		docs_source = os.path.join(repo_root, f"LICENSES/LICENSE.{docs_license}.md")
		action_count += copy_and_verify_license(repo_root, docs_source, f"LICENSE.{docs_license}.md", docs_license, args.dry_run)

	# === phase: cleanup LICENSES/ ===
	action_count += git_rm_recursive("LICENSES/", args.dry_run)

	# === phase: propagate subprocess ===
	action_count += run_propagate(repo_root, args.dry_run)

	# === phase: typescript-specific work ===
	# Must run AFTER propagate so the noexist bucket has placed package.json at repo root.
	if project_type == "typescript":
		action_count += substitute_typescript_package_json(repo_root, args.dry_run)

	# === phase: truncate boilerplate ===
	action_count += truncate_file("README.md", repo_root, args.dry_run)
	action_count += truncate_file("docs/CHANGELOG.md", repo_root, args.dry_run)

	# === phase: git rm cleanup ===
	action_count += git_rm("propagate_style_guides.py", args.dry_run)
	action_count += git_rm_recursive("propagate/", args.dry_run)
	action_count += git_rm_recursive("tools/", args.dry_run)
	action_count += git_rm_recursive("meta/", args.dry_run)

	if project_type != "python":
		action_count += git_rm("devel/submit_to_pypi.py", args.dry_run)

	action_count += git_rm("reset_repo.py", args.dry_run)

	# === phase: stage changes ===
	if not args.no_stage:
		action_count += 1
		if args.dry_run:
			dry_run_print("git add -A", args.dry_run)
		else:
			subprocess.run(["git", "add", "-A"], check=True, capture_output=True)

	# === phase: commit ===
	if args.commit:
		action_count += 1
		commit_msg = f"initial commit: reset repo to base template ({project_type})"
		if args.dry_run:
			dry_run_print(f"git commit -m {repr(commit_msg)}", args.dry_run)
		else:
			subprocess.run(
				["git", "commit", "-m", commit_msg], check=True, capture_output=True
			)

	# === phase: summary print ===
	if args.dry_run:
		print(f"DRY-RUN: {action_count} actions planned. No files changed.")
	else:
		if args.commit:
			print("Committed.")
		elif args.no_stage:
			print("Working tree modified. Run 'git add -A && git commit' when ready.")
		else:
			print("Staged. Run 'git commit' when ready.")

		subprocess.run(["git", "status", "--short"], check=False)

	if project_type == "python":
		print("\nNext steps:")
		print("  pip install -r pip_requirements.txt && pip install -r pip_requirements-dev.txt")
	elif project_type == "typescript":
		print("\nNext steps:")
		print("  npm install && bash devel/setup_playwright.sh")
	elif project_type == "rust":
		print("\nNext steps:")
		print("  cargo build")


if __name__ == "__main__":
	main()
