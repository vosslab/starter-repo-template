#!/usr/bin/env python3
"""Propagate canonical docs/scripts/configs from this template to consumer repos under ~/nsh/."""

import os
import stat
import shutil
import argparse
import filecmp

# Try to import detect_repo_type from tools/; if not available, prediction is skipped.
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
try:
	import detect_repo_type
except ImportError:
	detect_repo_type = None

# ANSI color codes
class Colors:
	RESET = '\033[0m'
	RED = '\033[91m'
	GREEN = '\033[92m'
	YELLOW = '\033[93m'
	BLUE = '\033[94m'
	MAGENTA = '\033[95m'
	CYAN = '\033[96m'

# ============================================
# Propagation manifests: folder convention + thin rules
# ============================================

# Root-level files that propagate. Add a file to ship it to every consumer's root.
ROOT_PROPAGATE_ALLOWLIST = frozenset({
	'CLAUDE.md',
	'AGENTS.md',
	'source_me.sh',
})

# Files that ship only when absent at consumer (universal noexist).
# Overrides the docs/ universal-overwrite default. Example: docs/AUTHORS.md is universal but ships noexist-only.
# Path is repo-root-relative.
UNIVERSAL_NOEXIST = frozenset({
	'AGENTS.md',
	'source_me.sh',
	'docs/AUTHORS.md',
})

# Files at template root that only ship to python-typed consumers
# (and a subset to 'other' per per-type rules).
PYTHON_LANG_FILES = frozenset({
	'docs/PYTHON_STYLE.md',
	'devel/submit_to_pypi.py',
	'pip_requirements.txt',
	'pip_requirements-dev.txt',
})

# Files that NEVER ship (template-meta).
META_FILES = frozenset({
	'propagate_style_guides.py',
	'reset_repo.py',
	'tools/detect_repo_type.py',
	'docs/PROPAGATION_RULES.md',
	'README.md',
	'VERSION',
	'.gitignore',
	'REPO_TYPE',
	'Brewfile',
	'pip_extras.txt',
})

# Dirs that NEVER ship. Walked but never produce routing entries.
# 'meta' is defense-in-depth: SKIP_WALK_DIRS already trims it during os.walk,
# but is_in_meta_dir() also checks META_DIRS so any future code path that
# reaches that check for a meta/... rel-path is still excluded.
META_DIRS = frozenset({
	'LICENSES',
	'templates',
	'meta',
	'docs/active_plans',
	'docs/archive',
	'experiment_reports',
	'__pycache__',
	'.git',
})

# Existing constant; keep as-is.
# Template-meta tests: validate the template's own infrastructure
# (propagate_style_guides, reset_repo, detect_repo_type).
# These must NOT propagate to consumers because the imported modules
# are git rm'd at consumer bootstrap, causing ImportError at pytest collection.

DEFAULT_REPO_SKIP_NAMES = frozenset({
	'starter-repo-template',
	'vosslab-skills',
})

SKIP_WALK_DIRS = {
	'.git',
	'.mypy_cache',
	'.pytest_cache',
	'old_shell_folder',
	'.venv',
	'.system',
	'__pycache__',
	'build',
	'dist',
	'node_modules',
	'venv',
	'meta',  # tests/meta/ contains template-meta tests only; excluded from propagation
}

AUTO_DISCOVER_DOCS_EXCLUDE = {
	'AUTHORS.md',
	'CHANGELOG.md',
}

TEMPLATE_ROOT = os.path.dirname(os.path.abspath(__file__))


#============================================
def load_deprecation_list(rel_path: str) -> list[str]:
	"""Read newline-delimited deprecation entries from meta/propagation/.

	Skips blank lines and comment lines (those starting with '#').
	Raises FileNotFoundError if the file is missing; loud failure beats
	silent missing-deprecation scrub.
	"""
	full_path = os.path.join(TEMPLATE_ROOT, rel_path)
	with open(full_path) as f:
		return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith('#')]


# Deprecation lists live in meta/propagation/ so they are reviewable as plain
# text and do not require a .py diff for every churn cycle.
DEPRECATED_TEST_SCRIPTS = load_deprecation_list('meta/propagation/deprecated_tests.txt')
DEPRECATED_GITIGNORE_ENTRIES = load_deprecation_list('meta/propagation/deprecated_gitignore.txt')

# Template-meta tests: validate the template's own infrastructure
# (propagate_style_guides, reset_repo, detect_repo_type).
# These must NOT propagate to consumers because the imported modules
# are git rm'd at consumer bootstrap, causing ImportError at pytest collection.
META_TEST_PREFIXES = (
	'test_propagate_',
	'test_reset_repo_',
	'test_detect_repo_type',
)


#============================================
def compute_propagation_plan(template_root: str, repo_type: str) -> dict:
	"""
	Compute the five-bucket propagation plan by walking the filesystem.

	Walks template_root and returns a dict with:
	- 'overwrite_files': repo-root-relative paths that overwrite at consumer
	- 'noexist_files': repo-root-relative paths that ship only when missing
	- 'devel_files': bare filenames under devel/ at consumer
	- 'test_files': paths under tests/ at consumer
	- 'gitignore_block': pattern lines for .gitignore

	Precedence (apply in this order; earlier rules win on conflict):
	  1. META_FILES / META_DIRS              -> never ship (drop from all buckets)
	  2. PYTHON_LANG_FILES                   -> ship only when repo_type == 'python'
	                                            (exception: 'other' gets docs/PYTHON_STYLE.md only)
	  3. UNIVERSAL_NOEXIST                   -> override universal overwrite -> noexist
	  4. templates/<type>/noexist/<path>     -> override typed overlay overwrite -> noexist
	  5. Type overlay wins over universal     -> when both target the same consumer destination,
	                                            the typed overlay version ships; log the override
	                                            so silent shadowing is visible.

	Routing rules:
	- Universal docs/ (not in META_FILES/META_DIRS) -> overwrite_files
	- Universal tests/test_*.py|.mjs (not matching META_TEST_PREFIXES) -> test_files
	- Universal tests/ helper files (TESTS_README.md, check_*, fix_*, git_file_utils.py) -> test_files
	- Universal devel/ -> devel_files
	- Root files in ROOT_PROPAGATE_ALLOWLIST -> overwrite_files
	- PYTHON_LANG_FILES only for python repos (docs/PYTHON_STYLE.md only for 'other' repos)
	- Paths in UNIVERSAL_NOEXIST override overwrite_files -> noexist_files
	- templates/<repo_type>/<path> (not noexist) -> overwrite_files
	- templates/<repo_type>/devel/<X> -> devel_files
	- templates/<repo_type>/tests/<X> -> test_files
	- templates/<repo_type>/noexist/<path> -> noexist_files
	- templates/gitignore.universal -> universal gitignore_block
	- templates/<repo_type>/gitignore.<repo_type> -> typed gitignore_block
	"""
	plan = {
		'overwrite_files': [],
		'noexist_files': [],
		'devel_files': [],
		'test_files': [],
		'gitignore_block': [],
	}

	# Helper: check if a path is under a meta directory
	def is_in_meta_dir(rel_path: str) -> bool:
		parts = rel_path.split(os.sep)
		for part in parts:
			if part in META_DIRS:
				return True
		return False

	# Special docs/ files that should never ship (per docs/REPO_STYLE.md)
	BLOCKED_DOCS_FILES = frozenset({
		'docs/CHANGELOG.md',
		'docs/active_plans',
		'docs/archive',
	})

	# 1. Walk universal files at template root
	if repo_type in ('python', 'other', 'typescript', 'rust'):
		for root, dirs, files in os.walk(template_root, topdown=True, followlinks=False):
			# Skip directories: meta, templates (we walk it separately)
			dirs[:] = [d for d in dirs if d not in SKIP_WALK_DIRS and not d.startswith('.') and d not in META_DIRS]

			rel_root = os.path.relpath(root, template_root)
			if rel_root == '.':
				rel_root = ''

			# Process files in this directory
			for name in files:
				if name.startswith('.'):
					continue

				file_rel = os.path.join(rel_root, name) if rel_root else name

				# Skip META_FILES (matches by full rel-path OR bare basename for
				# entries that may appear at any depth).
				if file_rel in META_FILES or name in META_FILES:
					continue

				# Skip if under a meta directory
				if is_in_meta_dir(file_rel):
					continue

				# Skip blocked docs files
				if file_rel in BLOCKED_DOCS_FILES or any(file_rel.startswith(f + '/') for f in BLOCKED_DOCS_FILES):
					continue

				# Skip PYTHON_LANG_FILES for non-python/non-other repo types
				if file_rel in PYTHON_LANG_FILES and repo_type not in ('python', 'other'):
					continue

				# Route by prefix/location
				if file_rel.startswith('docs/'):
					plan['overwrite_files'].append(file_rel)
				elif file_rel.startswith('devel/'):
					bare_name = os.path.basename(file_rel)
					# Skip devel files that are in PYTHON_LANG_FILES and not the right repo type
					if f'devel/{bare_name}' in PYTHON_LANG_FILES and repo_type not in ('python',):
						continue
					if bare_name not in plan['devel_files']:
						plan['devel_files'].append(bare_name)
				elif file_rel.startswith('tests/'):
					bare_name = os.path.basename(file_rel)
					# Skip template-meta test prefixes
					if any(bare_name.startswith(p) for p in META_TEST_PREFIXES):
						continue
					# Include test files and helpers
					if (bare_name.startswith('test_') and (bare_name.endswith('.py') or bare_name.endswith('.mjs'))) or \
						bare_name in ('TESTS_README.md',) or \
						bare_name.startswith(('check_', 'fix_')) or \
						bare_name in ('git_file_utils.py',):
						if file_rel not in plan['test_files']:
							plan['test_files'].append(file_rel)
				elif file_rel in ROOT_PROPAGATE_ALLOWLIST:
					plan['overwrite_files'].append(file_rel)
				# PYTHON_LANG_FILES: handle based on repo type
				elif file_rel in PYTHON_LANG_FILES:
					if repo_type == 'python':
						# For python repos, check if it's a pip_requirements file
						if file_rel.startswith('pip_requirements'):
							# pip_requirements files are noexist for python
							if file_rel not in plan['noexist_files']:
								plan['noexist_files'].append(file_rel)
						else:
							# Other PYTHON_LANG_FILES are overwrite for python
							plan['overwrite_files'].append(file_rel)
					elif repo_type == 'other' and file_rel == 'docs/PYTHON_STYLE.md':
						# 'other' repos get PYTHON_STYLE.md only
						plan['overwrite_files'].append(file_rel)
					# For other repo types, PYTHON_LANG_FILES are skipped entirely



	# 2. Walk typed overlay under templates/<repo_type>/
	type_overlay_root = os.path.join(template_root, 'templates', repo_type)
	if os.path.isdir(type_overlay_root):
		for root, dirs, files in os.walk(type_overlay_root, topdown=True, followlinks=False):
			dirs[:] = [d for d in dirs if d not in SKIP_WALK_DIRS and not d.startswith('.')]

			rel_root = os.path.relpath(root, type_overlay_root)
			if rel_root == '.':
				rel_root = ''

			for name in files:
				# Skip .gitkeep and other meta dotfiles, but allow .prettierrc.json, etc.
				if name == '.gitkeep' or (name.startswith('.') and not name.endswith('.json')):
					continue

				file_rel = os.path.join(rel_root, name) if rel_root else name

				# Route by subdirectory
				if file_rel.startswith('noexist/'):
					# Strip 'noexist/' prefix for the consumer path
					consumer_path = file_rel[8:]  # len('noexist/') = 8
					if consumer_path and consumer_path not in plan['noexist_files']:
						plan['noexist_files'].append(consumer_path)
				elif file_rel.startswith('devel/'):
					bare_name = os.path.basename(file_rel)
					if bare_name not in plan['devel_files']:
						plan['devel_files'].append(bare_name)
				elif file_rel.startswith('tests/'):
					if file_rel not in plan['test_files']:
						plan['test_files'].append(file_rel)
				elif name.startswith('gitignore.'):
					# Skip; will be loaded separately
					pass
				else:
					# Top-level files in templates/<type>/
					# rule 5: typed overlay shadows universal
					if file_rel in plan['overwrite_files']:
						plan['overwrite_files'].remove(file_rel)
						print(f"{Colors.CYAN}[OVERLAY-OVERRIDE]{Colors.RESET} {file_rel}: typed overlay shadows universal source")
					plan['overwrite_files'].append(file_rel)

	# 3. Load gitignore blocks
	# Universal block source: templates/gitignore.universal (not a canonical
	# consumer-root filename, so it lives under templates/ not at template root).
	gitignore_universal_path = os.path.join(template_root, 'templates', 'gitignore.universal')
	if os.path.isfile(gitignore_universal_path):
		with open(gitignore_universal_path, 'r', encoding='utf-8') as f:
			for line in f:
				stripped = line.rstrip('\n').strip()
				if stripped and not stripped.startswith('#'):
					plan['gitignore_block'].append(stripped)

	# Typed
	gitignore_typed_path = os.path.join(type_overlay_root, f'gitignore.{repo_type}')
	if os.path.isfile(gitignore_typed_path):
		with open(gitignore_typed_path, 'r', encoding='utf-8') as f:
			for line in f:
				stripped = line.rstrip('\n').strip()
				if stripped and not stripped.startswith('#'):
					plan['gitignore_block'].append(stripped)

	# 4. Apply UNIVERSAL_NOEXIST overrides
	# Any path in UNIVERSAL_NOEXIST must move from overwrite to noexist
	for path in UNIVERSAL_NOEXIST:
		if path in plan['overwrite_files']:
			plan['overwrite_files'].remove(path)
		if path not in plan['noexist_files']:
			plan['noexist_files'].append(path)

	# 5. Apply typed noexist overrides (rule 4: typed noexist shadows typed overwrite)
	# Any path in plan['noexist_files'] that is also in plan['overwrite_files'] must be removed from overwrite
	for path in list(plan['noexist_files']):
		if path in plan['overwrite_files']:
			plan['overwrite_files'].remove(path)

	return plan


#============================================
def parse_args():
	"""Parse CLI flags and return the argparse Namespace."""
	parser = argparse.ArgumentParser(
		description=(
			"Copy shared style/docs/scripts into each repo under ~/nsh/."
		)
	)
	parser.add_argument(
		'-n', '--dry-run', dest='dry_run',
		help='Only display planned changes', action='store_true'
	)
	parser.add_argument(
		'--source-dir', dest='source_dir',
		default=None,
		help=(
			'Directory containing style guides (default: <base>/starter_repo_template when present; '
			'otherwise the repo root containing this script; docs/ is preferred when present)'
		)
	)
	parser.add_argument(
		'--repo', dest='repo_name',
		default=None,
		help='Only update the named repo under base-dir (directory name)'
	)
	parser.add_argument(
		'--base-dir', dest='base_dir',
		default=None,
		help='Base directory containing repos (default: ~/nsh)'
	)
	parser.add_argument(
		'--bootstrap', dest='bootstrap',
		help='Force-copy every relevant file even when destination is absent',
		action='store_true'
	)
	parser.add_argument(
		'--sync-self', dest='sync_self',
		help='Treat template root as a python-token consumer; refresh template own files',
		action='store_true'
	)
	parser.add_argument(
		'--fix-permissions', dest='fix_permissions',
		help='Fix .git directory permissions (chmod g+w)',
		action='store_true'
	)
	parser.add_argument(
		'--no-auto-discover', dest='auto_discover',
		help='Disable automatic test file discovery (used by reset_repo.py bootstrap)',
		action='store_false'
	)
	parser.add_argument(
		'--write-marker', dest='write_marker',
		help='Predict and write REPO_TYPE if missing (single-repo mode only)',
		action='store_true'
	)
	parser.add_argument(
		'--yes', dest='skip_confirm',
		help='Accept predicted type without prompting (for medium confidence)',
		action='store_true'
	)
	parser.set_defaults(dry_run=False, bootstrap=False, sync_self=False, fix_permissions=False, auto_discover=True, write_marker=False, skip_confirm=False)
	args = parser.parse_args()
	return args


#============================================
def resolve_spec_for_type(repo_type: str, template_root: str = None) -> dict:
	"""
	Return the five-bucket propagation spec for the given repo_type.
	Uses compute_propagation_plan with template_root (defaults to script directory).
	"""
	if repo_type not in ('universal', 'python', 'typescript', 'rust', 'other'):
		raise ValueError(f"unknown repo type {repo_type!r}")
	if template_root is None:
		template_root = os.path.dirname(os.path.abspath(__file__))
	if repo_type == 'universal':
		repo_type = 'python'  # 'universal' is an alias for python in the fold scheme
	return compute_propagation_plan(template_root, repo_type)


#============================================
def source_path_for_bucket(template_root: str, bucket: str, file_rel: str, repo_type: str = 'universal') -> str:
	"""
	Resolve canonical source path for a file in a bucket.
	Handles universal files at template root and typed files under templates/<repo_type>/.
	For noexist_files, looks under templates/<repo_type>/noexist/ as well as root.
	"""
	# Normalize repo_type alias
	if repo_type == 'universal':
		repo_type = 'python'

	# Determine candidate paths based on bucket.
	if bucket == 'devel_files':
		# devel files: template_root/devel/<name>
		candidate = os.path.join(template_root, 'devel', file_rel)
		if os.path.isfile(candidate):
			return candidate
		# Also check typed overlay
		candidate = os.path.join(template_root, 'templates', repo_type, 'devel', file_rel)
		if os.path.isfile(candidate):
			return candidate

	elif bucket == 'test_files':
		# test files: file_rel already includes tests/ prefix, so just join directly
		candidate = os.path.join(template_root, file_rel)
		if os.path.isfile(candidate):
			return candidate
		candidate = os.path.join(template_root, 'templates', repo_type, file_rel)
		if os.path.isfile(candidate):
			return candidate

	elif bucket == 'noexist_files':
		# noexist files: could be at template root (universal) or under templates/<type>/noexist/<path>
		candidate = os.path.join(template_root, file_rel)
		if os.path.isfile(candidate):
			return candidate
		# Check typed noexist
		candidate = os.path.join(template_root, 'templates', repo_type, 'noexist', file_rel)
		if os.path.isfile(candidate):
			return candidate

	else:
		# overwrite_files (or default): typed under templates/<type>/ shadows universal at root
		candidate = os.path.join(template_root, 'templates', repo_type, file_rel)
		if os.path.isfile(candidate):
			return candidate
		candidate = os.path.join(template_root, file_rel)
		if os.path.isfile(candidate):
			return candidate

	raise FileNotFoundError(f"canonical source missing for {bucket} entry {file_rel!r}")


#============================================
def target_path_for_bucket(repo_dir: str, bucket: str, file_rel: str) -> str:
	"""
	Resolve target path at consumer repo.
	Note: for test_files, file_rel includes 'tests/' prefix (e.g., 'tests/test_foo.py').
	For devel_files, file_rel is a bare name (e.g., 'submit_to_pypi.py').
	"""
	if bucket == 'devel_files':
		return os.path.join(repo_dir, 'devel', file_rel)
	if bucket == 'test_files':
		# file_rel already includes tests/ prefix, just join it
		return os.path.join(repo_dir, file_rel)
	return os.path.join(repo_dir, file_rel)


#============================================
def auto_discover_test_files(template_root: str, repo_type: str) -> list[str]:
	"""
	Scan template tests/ for files matching test_*.py or test_*.mjs not already
	in the spec's test_files list. Return their relative paths under tests/.

	For universal and python types: scan template_root/tests/ directly.
	For typescript and rust: scan templates/<repo_type>/tests/.
	"""
	spec = resolve_spec_for_type(repo_type, template_root)
	spec_test_files = set(spec['test_files'])

	discovered = []

	if repo_type in ('universal', 'python', 'other'):
		# Scan template root tests/
		test_dir = os.path.join(template_root, 'tests')
	else:
		# Scan templates/<repo_type>/tests/
		test_dir = os.path.join(template_root, 'templates', repo_type, 'tests')

	if not os.path.isdir(test_dir):
		return discovered

	for root, dirs, files in os.walk(test_dir, topdown=True, followlinks=False):
		dirs[:] = [d for d in dirs if d not in SKIP_WALK_DIRS and not d.startswith('.')]
		for name in files:
			if not (name.startswith('test_') and (name.endswith('.py') or name.endswith('.mjs'))):
				continue
			# Exclude template-meta tests (propagate/reset_repo/detect_repo_type self-tests)
			if any(name.startswith(p) for p in META_TEST_PREFIXES):
				continue
			rel_path = os.path.relpath(os.path.join(root, name), test_dir)
			# Prepend 'tests/' to make it an absolute path from template_root
			full_rel_path = os.path.join('tests', rel_path)
			if full_rel_path not in spec_test_files and full_rel_path not in discovered:
				discovered.append(full_rel_path)

	return discovered


#============================================
def is_repo_dir(repo_dir: str) -> bool:
	"""Return True if directory contains a .git entry, False otherwise."""
	return os.path.exists(os.path.join(repo_dir, '.git'))


#============================================
def normalize_path(path: str) -> str:
	"""
	Normalize a path for stable filesystem comparisons.
	"""
	return os.path.normcase(os.path.realpath(os.path.abspath(path)))


#============================================
def read_repo_type(repo_path: str, single_repo_mode: bool = False, write_marker: bool = False, skip_confirm: bool = False, non_interactive: bool = False) -> str:
	"""Read REPO_TYPE marker; predict if single-repo mode with write_marker, else default to 'python'; fallback to legacy STARTER_REPO_TYPE for backward compatibility."""
	marker_path = os.path.join(repo_path, 'REPO_TYPE')
	legacy_marker_path = os.path.join(repo_path, 'STARTER_REPO_TYPE')

	# Check for legacy marker first if new marker doesn't exist
	if not os.path.isfile(marker_path) and os.path.isfile(legacy_marker_path):
		print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {repo_path}: legacy STARTER_REPO_TYPE marker found; rename to REPO_TYPE")
		with open(legacy_marker_path, 'r', encoding='utf-8') as f:
			token = f.read().strip()
		if token not in ('python', 'typescript', 'rust', 'other'):
			raise ValueError(f"unknown STARTER_REPO_TYPE token {token!r} in {legacy_marker_path}")
		return token

	if not os.path.isfile(marker_path):
		# Missing marker: predict if conditions met, else default to python
		if single_repo_mode and write_marker and detect_repo_type:
			token, confidence, reasoning = detect_repo_type.detect_repo_type(repo_path)

			if confidence == 'high' and token != 'ambiguous':
				# High confidence: write silently
				with open(marker_path, 'w', encoding='utf-8') as f:
					f.write(token + '\n')
				print(f"{Colors.CYAN}[PREDICTED]{Colors.RESET} repo={os.path.basename(repo_path)} type={token} confidence=high (auto-wrote marker)")
				return token

			if confidence == 'medium':
				# Medium confidence: print and ask
				print(f"{Colors.YELLOW}[PREDICTED-MEDIUM]{Colors.RESET} repo={os.path.basename(repo_path)} type={token}")
				print("  reasoning:")
				for bullet in reasoning:
					print(f"    - {bullet}")

				if skip_confirm or non_interactive:
					# Accept silently
					with open(marker_path, 'w', encoding='utf-8') as f:
						f.write(token + '\n')
					print(f"{Colors.CYAN}[PREDICTED-MEDIUM-ACCEPTED]{Colors.RESET} wrote marker")
					return token

				if not non_interactive:
					# Prompt user
					user_input = input(f"Accept predicted type '{token}'? [Y/n]: ").strip()
					if user_input == '' or user_input.lower() == 'y':
						with open(marker_path, 'w', encoding='utf-8') as f:
							f.write(token + '\n')
						return token
					else:
						# User rejected; re-prompt for explicit type
						while True:
							user_type = input(
								"Project type? [p]ython / [t]ypescript / [r]ust / [o]ther [p]: "
							).strip()
							if user_type == '':
								chosen_type = 'python'
							elif user_type.lower() == 'p':
								chosen_type = 'python'
							elif user_type.lower() == 't':
								chosen_type = 'typescript'
							elif user_type.lower() == 'r':
								chosen_type = 'rust'
							elif user_type.lower() == 'o':
								chosen_type = 'other'
							else:
								print("Invalid choice. Try again.")
								continue
							with open(marker_path, 'w', encoding='utf-8') as f:
								f.write(chosen_type + '\n')
							return chosen_type

			# Low confidence or ambiguous: abort if non-interactive, else prompt
			print(f"{Colors.RED}[AMBIGUOUS]{Colors.RESET} repo={os.path.basename(repo_path)}")
			print("  reasoning:")
			for bullet in reasoning:
				print(f"    - {bullet}")

			if non_interactive:
				raise SystemExit("ambiguous repo type; specify REPO_TYPE manually or use reset_repo.py")

			# Interactive prompt for ambiguous
			while True:
				user_type = input(
					"Project type? [p]ython / [t]ypescript / [r]ust / [o]ther: "
				).strip()
				if user_type.lower() == 'p':
					chosen_type = 'python'
				elif user_type.lower() == 't':
					chosen_type = 'typescript'
				elif user_type.lower() == 'r':
					chosen_type = 'rust'
				elif user_type.lower() == 'o':
					chosen_type = 'other'
				else:
					print("Invalid choice. Try again.")
					continue
				with open(marker_path, 'w', encoding='utf-8') as f:
					f.write(chosen_type + '\n')
				return chosen_type

		# Default to python (batch mode or no write_marker flag)
		return 'python'

	with open(marker_path, 'r', encoding='utf-8') as f:
		token = f.read().strip()
	if token not in ('python', 'typescript', 'rust', 'other'):
		raise ValueError(f"unknown REPO_TYPE token {token!r} in {marker_path}")
	return token


#============================================
def repo_is_on_path(repo_dir: str) -> bool:
	"""
	Check whether the repository directory is present in PATH.
	"""
	target = normalize_path(repo_dir)
	path_env = os.environ.get('PATH', '')
	for path_entry in path_env.split(os.pathsep):
		if not path_entry:
			continue
		if normalize_path(path_entry) == target:
			return True
	return False


#============================================
def find_repo_root(start_dir: str) -> str | None:
	"""
	Find the nearest ancestor that contains the expected style guides or templates.

	Args:
		start_dir (str): Starting directory.

	Returns:
		str | None: Repo root path when found, otherwise None.
	"""
	current = os.path.abspath(start_dir)
	while True:
		# Check for canonical template overlay (post-WP-F3 architecture)
		if os.path.isdir(os.path.join(current, 'templates', 'typescript')):
			return current
		if os.path.isfile(os.path.join(current, 'docs', 'PYTHON_STYLE.md')):
			return current
		parent = os.path.dirname(current)
		if parent == current:
			return None
		current = parent


#============================================
def ensure_git_perms(repo_dir: str, dry_run: bool) -> bool:
	"""
	Make .git group-writable so Git can create .git/index.lock and update the index.

	Note: This only helps if the user is in the repo group.
	"""
	git_dir = os.path.join(repo_dir, '.git')
	if not os.path.isdir(git_dir):
		return False

	changed = False

	def add_group_write(path: str) -> None:
		nonlocal changed
		# stat may fail on broken symlinks / vanished files; skip silently in that case
		try:
			st = os.stat(path, follow_symlinks=False)
		except OSError:
			return
		mode = stat.S_IMODE(st.st_mode)
		new_mode = mode | 0o020
		if new_mode == mode:
			return
		changed = True
		if dry_run:
			print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} chmod g+w {path}")
			return
		os.chmod(path, new_mode, follow_symlinks=False)

	add_group_write(git_dir)

	index_path = os.path.join(git_dir, 'index')
	if os.path.exists(index_path):
		add_group_write(index_path)

	for root, dirs, files in os.walk(git_dir, topdown=True, followlinks=False):
		for d in dirs:
			add_group_write(os.path.join(root, d))
		for f in files:
			add_group_write(os.path.join(root, f))

	return changed


#============================================
def ensure_changelog_file(changelog_path: str, dry_run: bool) -> bool:
	"""
	Create docs/CHANGELOG.md if missing.

	Args:
		changelog_path (str): Path to docs/CHANGELOG.md.
		dry_run (bool): If True, do not write changes.

	Returns:
		bool: True if file was created, False otherwise.
	"""
	if os.path.exists(changelog_path):
		return False

	if dry_run:
		return True

	with open(changelog_path, 'w', encoding='utf-8') as f:
		f.write('')
	return True


#============================================
def ensure_tests_dir(tests_dir: str, dry_run: bool) -> bool:
	"""
	Create the tests directory if missing.

	Args:
		tests_dir (str): Path to tests directory.
		dry_run (bool): If True, do not write changes.

	Returns:
		bool: True if directory was created, False otherwise.
	"""
	if os.path.isdir(tests_dir):
		return False
	if dry_run:
		return True
	os.makedirs(tests_dir, exist_ok=True)
	return True


#============================================
def remove_gitignore_entries(gitignore_path: str, entries: list[str], dry_run: bool) -> int:
	"""
	Remove deprecated entries from .gitignore file.

	Args:
		gitignore_path (str): Path to .gitignore file.
		entries (list[str]): List of gitignore patterns to remove.
		dry_run (bool): If True, do not write changes.

	Returns:
		int: Number of lines removed.
	"""
	if not os.path.isfile(gitignore_path):
		return 0

	with open(gitignore_path, 'r', encoding='utf-8') as f:
		lines = [line.rstrip('\n') for line in f]

	entries_set = set(entry.strip() for entry in entries)
	filtered_lines = []
	removed_count = 0

	for line in lines:
		stripped = line.strip()
		if stripped in entries_set:
			removed_count += 1
			continue
		filtered_lines.append(line.rstrip())

	if removed_count == 0:
		return 0

	if dry_run:
		return removed_count

	with open(gitignore_path, 'w', encoding='utf-8') as f:
		for line in filtered_lines:
			f.write(line + '\n')

	return removed_count


#============================================
def deduplicate_gitignore(gitignore_path: str, dry_run: bool) -> tuple[int, bool]:
	"""
	Remove duplicate lines and trailing whitespace from .gitignore file.
	Preserves all empty lines and comments for visual grouping.

	Args:
		gitignore_path (str): Path to .gitignore file.
		dry_run (bool): If True, do not write changes.

	Returns:
		tuple[int, bool]: (duplicates_removed, whitespace_cleaned)
	"""
	if not os.path.isfile(gitignore_path):
		return (0, False)

	with open(gitignore_path, 'r', encoding='utf-8') as f:
		original_lines = [line.rstrip('\n') for line in f]

	stripped_lines = [line.rstrip() for line in original_lines]

	seen = set()
	unique_lines = []
	for line in stripped_lines:
		if line == '':
			unique_lines.append(line)
		elif line not in seen:
			seen.add(line)
			unique_lines.append(line)

	duplicates_removed = len(stripped_lines) - len(unique_lines)
	whitespace_cleaned = any(orig != stripped for orig, stripped in zip(original_lines, stripped_lines))

	if duplicates_removed == 0 and not whitespace_cleaned:
		return (0, False)

	if dry_run:
		return (duplicates_removed, whitespace_cleaned)

	with open(gitignore_path, 'w', encoding='utf-8') as f:
		for line in unique_lines:
			f.write(line + '\n')

	return (duplicates_removed, whitespace_cleaned)


#============================================
def merge_claude_md(source_file: str, dest_file: str) -> str:
	"""
	Merge source CLAUDE.md with destination CLAUDE.md, preserving extra @ lines.

	Reads both files, finds any @ reference lines in the destination that are
	not present in the source, and appends them to the source content.

	Args:
		source_file (str): Path to the template CLAUDE.md.
		dest_file (str): Path to the destination CLAUDE.md.

	Returns:
		str: Merged file content with extra destination @ lines preserved.
	"""
	with open(source_file, 'r') as f:
		source_lines = f.read().splitlines()
	with open(dest_file, 'r') as f:
		dest_lines = f.read().splitlines()
	source_refs = set()
	for line in source_lines:
		stripped = line.strip()
		if stripped.startswith('@'):
			source_refs.add(stripped)
	extra_lines = []
	for line in dest_lines:
		stripped = line.strip()
		if stripped.startswith('@') and stripped not in source_refs:
			extra_lines.append(line)
	merged = source_lines[:]
	if extra_lines:
		while merged and merged[-1].strip() == '':
			merged.pop()
		for line in extra_lines:
			merged.append(line)
		merged.append('')
	merged_text = '\n'.join(merged)
	if not merged_text.endswith('\n'):
		merged_text += '\n'
	return merged_text


#============================================
def merge_conftest(source_file: str, dest_file: str) -> str | None:
	"""
	Inject the canonical collect_ignore block into a destination conftest.py.

	Mirrors merge_claude_md: source is canonical for the collect_ignore line,
	but any other content the repo has added (imports, fixtures, etc.) is
	preserved. Returns the merged text when the destination needs an update,
	or None when no change is needed.

	Args:
		source_file (str): Path to the canonical tests/conftest.py.
		dest_file (str): Path to the consumer repo's tests/conftest.py.

	Returns:
		str | None: Merged content when an update is needed, None otherwise.
	"""
	with open(source_file, 'r', encoding='utf-8') as f:
		source_text = f.read()
	if not os.path.isfile(dest_file):
		return source_text
	with open(dest_file, 'r', encoding='utf-8') as f:
		dest_text = f.read()
	if 'collect_ignore' in dest_text:
		return None
	if dest_text.strip() == '':
		return source_text
	merged = source_text.rstrip() + '\n\n' + dest_text
	if not merged.endswith('\n'):
		merged += '\n'
	return merged


#============================================
def merge_gitignore_blocks(repo_dir: str, repo_type: str, template_root: str, dry_run: bool) -> tuple[int, int, int]:
	"""
	Manage .gitignore as a sequence of named blocks delimited by '# === <NAME> ==='.
	Blocks: UNIVERSAL (always), and <REPO_TYPE_UPPERCASE> (when non-empty).
	If block header exists, replace just that block. If not, append at end.
	User-added lines OUTSIDE any managed block stay untouched.

	Returns:
		tuple[int, int, int]: (created, updated, lines_added)
	"""
	gitignore_path = os.path.join(repo_dir, '.gitignore')

	created_count = 0
	updated_count = 0
	lines_added_total = 0

	file_exists = os.path.isfile(gitignore_path)
	existing_lines = []
	if file_exists:
		with open(gitignore_path, 'r', encoding='utf-8') as f:
			existing_lines = [line.rstrip('\n') for line in f]

	# Load universal and type-specific gitignore blocks from files.
	# Universal source lives under templates/ (not a canonical consumer-root filename).
	universal_lines = []
	gitignore_universal_path = os.path.join(template_root, 'templates', 'gitignore.universal')
	if os.path.isfile(gitignore_universal_path):
		with open(gitignore_universal_path, 'r', encoding='utf-8') as f:
			for line in f:
				stripped = line.rstrip('\n').strip()
				if stripped and not stripped.startswith('#'):
					universal_lines.append(stripped)

	type_lines = []
	gitignore_typed_path = os.path.join(template_root, 'templates', repo_type, f'gitignore.{repo_type}')
	if os.path.isfile(gitignore_typed_path):
		with open(gitignore_typed_path, 'r', encoding='utf-8') as f:
			for line in f:
				stripped = line.rstrip('\n').strip()
				if stripped and not stripped.startswith('#'):
					type_lines.append(stripped)

	universal_header = '# === UNIVERSAL ==='
	type_header = f"# === {repo_type.upper()} ==="

	# Find existing blocks in the file
	def find_block(lines: list[str], header: str) -> tuple[int, int]:
		"""Find start and end indices of a block. Returns (start_idx, end_idx) or (-1, -1) if not found."""
		start_idx = -1
		for i, line in enumerate(lines):
			if line.startswith(header):
				start_idx = i
				break
		if start_idx == -1:
			return (-1, -1)
		end_idx = start_idx + 1
		for i in range(start_idx + 1, len(lines)):
			if lines[i].startswith('# ==='):
				end_idx = i
				break
		else:
			end_idx = len(lines)
		return (start_idx, end_idx)

	# Build new content
	new_lines = list(existing_lines)

	# Handle UNIVERSAL block
	uni_start, uni_end = find_block(new_lines, universal_header)
	if uni_start != -1:
		new_lines = new_lines[:uni_start] + [universal_header] + universal_lines + new_lines[uni_end:]
	else:
		new_lines.append(universal_header)
		new_lines.extend(universal_lines)

	# Handle type-specific block (if any)
	if type_lines:
		type_start, type_end = find_block(new_lines, type_header)
		if type_start != -1:
			new_lines = new_lines[:type_start] + [type_header] + type_lines + new_lines[type_end:]
		else:
			new_lines.append(type_header)
			new_lines.extend(type_lines)

	# Build content with proper trailing newline
	content = '\n'.join(new_lines)
	if content and not content.endswith('\n'):
		content += '\n'

	existing_content = '\n'.join(existing_lines)
	if existing_lines and not existing_content.endswith('\n'):
		existing_content += '\n'

	# Write if needed
	if not file_exists:
		created_count = 1
		if dry_run:
			print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} create {gitignore_path}")
		else:
			with open(gitignore_path, 'w', encoding='utf-8') as f:
				f.write(content)
			print(f"{Colors.BLUE}[CREATED]{Colors.RESET} {gitignore_path}")
		lines_added_total = len(universal_lines) + len(type_lines)
	elif content != existing_content:
		updated_count = 1
		if dry_run:
			print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} update {gitignore_path}")
		else:
			with open(gitignore_path, 'w', encoding='utf-8') as f:
				f.write(content)
			print(f"{Colors.BLUE}[UPDATED]{Colors.RESET} {gitignore_path}")
		lines_added_total = len(universal_lines) + len(type_lines)

	return (created_count, updated_count, lines_added_total)


#============================================
def resolve_target_repo(base_dir: str, repo_name: str | None) -> str | None:
	"""
	Resolve and validate an optional single target repo under base_dir.

	Args:
		base_dir (str): Base directory that contains repos.
		repo_name (str | None): Optional repo directory name.

	Returns:
		str | None: Absolute repo path if provided, otherwise None.
	"""
	if not repo_name:
		return None
	target_repo = os.path.join(base_dir, repo_name)
	if not os.path.isdir(target_repo):
		raise FileNotFoundError(
			f"Repo not found under {base_dir}: {repo_name}"
		)
	if not is_repo_dir(target_repo):
		raise FileNotFoundError(
			f"Repo missing .git under {base_dir}: {repo_name}"
		)
	return target_repo


#============================================
def resolve_source_dir(base_dir: str, source_dir_arg: str | None) -> str:
	"""
	Resolve the source directory used for propagation.

	Args:
		base_dir (str): Base directory for default lookup.
		source_dir_arg (str | None): Optional user-provided source dir.

	Returns:
		str: Absolute source directory path.
	"""
	source_dir = source_dir_arg
	if source_dir is None:
		preferred_source = os.path.join(base_dir, 'starter_repo_template')
		if os.path.isdir(preferred_source):
			source_dir = preferred_source
		else:
			script_dir = os.path.dirname(os.path.abspath(__file__))
			detected_repo_root = find_repo_root(script_dir)
			if detected_repo_root is None:
				raise FileNotFoundError(
					"Default source dir not found. Provide --source-dir."
				)
			source_dir = detected_repo_root
	return os.path.abspath(os.path.expanduser(source_dir))


#============================================
def collect_repo_dirs(base_dir: str, target_repo: str | None) -> list[str]:
	"""
	Collect repository directories to process.

	If target_repo is provided, return it. Otherwise, walk from base_dir to discover
	repositories by finding .git directories. Max depth of 3 levels deep from base_dir.
	Skip directories in DEFAULT_REPO_SKIP_NAMES unless explicitly targeted by target_repo.

	Args:
		base_dir (str): Base directory containing repos.
		target_repo (str | None): Optional single target repo (overrides skip list).

	Returns:
		list[str]: List of repository paths to process.
	"""
	if target_repo:
		return [target_repo]

	repo_dirs = []

	for root, dirs, files in os.walk(base_dir, topdown=True, followlinks=False):
		# Calculate depth from base_dir
		rel_path = os.path.relpath(root, base_dir)
		if rel_path == '.':
			depth = 0
		else:
			depth = len(rel_path.split(os.sep))

		# Check if this directory is a git repo.
		# Note: '.git' as a FILE (not dir) indicates a submodule/worktree --
		# intentionally NOT detected here. Vendored submodules like PROBLEMS/PG_v2.17
		# should not receive propagation.
		if '.git' in dirs:
			repo_dirs.append(root)
			# Don't descend into a repo once we find its .git
			dirs[:] = []
		else:
			# Prune beyond max depth and filter skip dirs
			if depth >= 3:
				dirs[:] = []
			else:
				# Filter out skip dirs and dotdirs
				dirs[:] = [d for d in dirs if d not in SKIP_WALK_DIRS and not d.startswith('.')]

	# Apply skip list: drop repos whose basename is in DEFAULT_REPO_SKIP_NAMES
	repo_dirs = [r for r in repo_dirs if os.path.basename(r) not in DEFAULT_REPO_SKIP_NAMES]

	return sorted(repo_dirs)


#============================================
def remove_deprecated_tests(tests_dir: str, dry_run: bool) -> int:
	"""
	Remove deprecated tests scripts from one repo's tests directory.
	"""
	removed = 0
	for deprecated_test_file in DEPRECATED_TEST_SCRIPTS:
		deprecated_test_path = os.path.join(tests_dir, deprecated_test_file)
		if not os.path.isfile(deprecated_test_path):
			continue
		if dry_run:
			print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} remove {deprecated_test_path}")
		else:
			os.remove(deprecated_test_path)
			print(f"{Colors.BLUE}[REMOVED]{Colors.RESET} {deprecated_test_path}")
		removed += 1
	return removed


#============================================
def main():
	"""
	Copy shared docs/scripts into each repo under base_dir.
	Type-aware dispatch based on REPO_TYPE marker.
	"""
	args = parse_args()

	if args.base_dir:
		base_dir = os.path.abspath(os.path.expanduser(args.base_dir))
	else:
		base_dir = os.path.abspath(os.path.expanduser('~/nsh'))
	target_repo = resolve_target_repo(base_dir, args.repo_name)
	source_dir = resolve_source_dir(base_dir, args.source_dir)
	template_root = normalize_path(source_dir)

	repo_dirs = collect_repo_dirs(base_dir, target_repo)

	# --sync-self: re-add template even though skip-list excludes it by name.
	if args.sync_self and template_root not in [normalize_path(r) for r in repo_dirs]:
		# Use the actual on-disk path (source_dir), not the normalized form,
		# so downstream logging shows a clean absolute path.
		repo_dirs = [os.path.abspath(os.path.expanduser(source_dir))] + repo_dirs

	copied_count = 0
	updated_count = 0
	merged_count = 0
	created_count = 0
	skipped_by_policy = 0
	auto_discovered_count = 0
	errors = 0

	for repo_dir in repo_dirs:
		if not is_repo_dir(repo_dir):
			continue

		repo_normalized = normalize_path(repo_dir)
		if repo_normalized == template_root:
			if not args.sync_self:
				print(f"{Colors.CYAN}[SKIP SELF]{Colors.RESET} {repo_dir} (use --sync-self to update template)")
				continue
			else:
				print(f"{Colors.CYAN}[SYNC SELF]{Colors.RESET} {repo_dir}")

		try:
			single_repo_mode = target_repo is not None
			repo_type = read_repo_type(
				repo_dir,
				single_repo_mode=single_repo_mode,
				write_marker=args.write_marker,
				skip_confirm=args.skip_confirm,
				non_interactive=False
			)
		except ValueError as exc:
			errors += 1
			print(f"{Colors.RED}[ERROR]{Colors.RESET} {repo_dir}: {exc}")
			continue

		# Per-repo counters for summary line
		repo_updates = 0
		repo_copies = 0
		repo_skips = 0

		spec = resolve_spec_for_type(repo_type, source_dir)

		auto_discovered = []
		if args.auto_discover:
			auto_discovered = auto_discover_test_files(source_dir, repo_type)
			if auto_discovered:
				auto_discovered_count += len(auto_discovered)
				spec['test_files'].extend(auto_discovered)
				print(f"{Colors.CYAN}[AUTO-DISCOVER]{Colors.RESET} found {len(auto_discovered)} test files: {', '.join(auto_discovered)}")

		if args.fix_permissions:
			# return value intentionally ignored; chmod side-effect is the purpose
			ensure_git_perms(repo_dir, args.dry_run)

		docs_dir = os.path.join(repo_dir, 'docs')
		if not os.path.isdir(docs_dir):
			if args.dry_run:
				print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} mkdir {docs_dir}")
			else:
				os.makedirs(docs_dir, exist_ok=True)

		tests_dir = os.path.join(repo_dir, 'tests')
		if ensure_tests_dir(tests_dir, args.dry_run):
			if args.dry_run:
				print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} mkdir {tests_dir}")

		conftest_path = os.path.join(tests_dir, 'conftest.py')
		source_conftest = os.path.join(source_dir, 'tests', 'conftest.py')
		if os.path.abspath(conftest_path) != os.path.abspath(source_conftest):
			merged_conftest = merge_conftest(source_conftest, conftest_path)
			if merged_conftest is not None:
				dest_existed = os.path.isfile(conftest_path)
				if args.dry_run:
					action = 'inject collect_ignore into' if dest_existed else 'create'
					print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} {action} {conftest_path}")
				else:
					with open(conftest_path, 'w', encoding='utf-8') as f:
						f.write(merged_conftest)
					if dest_existed:
						print(f"{Colors.BLUE}[MERGED]{Colors.RESET} injected collect_ignore into {conftest_path}")
						merged_count += 1
					else:
						print(f"{Colors.BLUE}[CREATED]{Colors.RESET} {conftest_path}")
						created_count += 1

		remove_deprecated_tests(tests_dir, args.dry_run)

		devel_dir = os.path.join(repo_dir, 'devel')
		if not os.path.isdir(devel_dir):
			if args.dry_run:
				print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} mkdir {devel_dir}")
			else:
				os.makedirs(devel_dir, exist_ok=True)

		changelog_path = os.path.join(docs_dir, 'CHANGELOG.md')
		if ensure_changelog_file(changelog_path, args.dry_run):
			if args.dry_run:
				print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} create {changelog_path}")
			else:
				created_count += 1

		# Process overwrite_files
		for file_rel in spec['overwrite_files']:
			try:
				source_file = source_path_for_bucket(source_dir, 'overwrite_files', file_rel, repo_type)
			except FileNotFoundError:
				errors += 1
				print(f"{Colors.RED}[ERROR]{Colors.RESET} source missing for {file_rel}")
				continue

			dest_file = os.path.join(repo_dir, file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				print(f"{Colors.CYAN}[SKIP SOURCE]{Colors.RESET} {dest_file}")
				continue

			dest_parent = os.path.dirname(dest_file)
			if dest_parent and not os.path.isdir(dest_parent):
				if args.dry_run:
					print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} mkdir {dest_parent}")
				else:
					os.makedirs(dest_parent, exist_ok=True)

			dest_exists = os.path.isfile(dest_file)

			# Special case: CLAUDE.md merges to preserve user @ lines
			if file_rel == 'CLAUDE.md' and dest_exists:
				merged_content = merge_claude_md(source_file, dest_file)
				with open(dest_file, 'r') as f:
					existing_content = f.read()
				if merged_content == existing_content:
					print(f"{Colors.CYAN}[NO CHANGE]{Colors.RESET} {dest_file}")
					continue
				if args.dry_run:
					print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} merge {source_file} -> {dest_file}")
				else:
					with open(dest_file, 'w') as f:
						f.write(merged_content)
					print(f"{Colors.BLUE}[MERGED]{Colors.RESET} {source_file} -> {dest_file}")
					merged_count += 1
				continue

			is_same = False
			if dest_exists:
				is_same = filecmp.cmp(source_file, dest_file, shallow=False)
			if is_same:
				print(f"{Colors.CYAN}[NO CHANGE]{Colors.RESET} {dest_file}")
				continue

			if args.dry_run:
				action = 'update' if dest_exists else 'copy'
				print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} {action} {source_file} -> {dest_file}")
				if dest_exists:
					repo_updates += 1
			else:
				shutil.copy2(source_file, dest_file)
				if dest_exists:
					print(f"{Colors.BLUE}[UPDATED]{Colors.RESET} {source_file} -> {dest_file}")
					updated_count += 1
					repo_updates += 1
				else:
					print(f"{Colors.BLUE}[COPIED]{Colors.RESET} {source_file} -> {dest_file}")
					copied_count += 1

		# Process noexist_files
		for file_rel in spec['noexist_files']:
			try:
				source_file = source_path_for_bucket(source_dir, 'noexist_files', file_rel, repo_type)
			except FileNotFoundError:
				errors += 1
				print(f"{Colors.RED}[ERROR]{Colors.RESET} source missing for {file_rel}")
				continue

			dest_file = os.path.join(repo_dir, file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				print(f"{Colors.CYAN}[SKIP SOURCE]{Colors.RESET} {dest_file}")
				continue

			if file_rel == 'source_me.sh' and repo_is_on_path(repo_dir):
				print(f"{Colors.CYAN}[SKIP PATH]{Colors.RESET} {dest_file} (repo is already on PATH)")
				continue

			if os.path.exists(dest_file) and not args.bootstrap:
				print(f"{Colors.CYAN}[SKIP]{Colors.RESET} {dest_file} (exists, use --bootstrap to override)")
				skipped_by_policy += 1
				repo_skips += 1
				continue

			dest_parent = os.path.dirname(dest_file)
			if dest_parent and not os.path.isdir(dest_parent):
				if args.dry_run:
					print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} mkdir {dest_parent}")
				else:
					os.makedirs(dest_parent, exist_ok=True)

			if args.dry_run:
				print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} copy {source_file} -> {dest_file}")
				repo_copies += 1
			else:
				shutil.copy2(source_file, dest_file)
				print(f"{Colors.BLUE}[COPIED]{Colors.RESET} {source_file} -> {dest_file}")
				copied_count += 1
				repo_copies += 1

		# Process devel_files
		for file_rel in spec['devel_files']:
			try:
				source_file = source_path_for_bucket(source_dir, 'devel_files', file_rel, repo_type)
			except FileNotFoundError:
				errors += 1
				print(f"{Colors.RED}[ERROR]{Colors.RESET} source missing for devel_files:{file_rel}")
				continue

			dest_file = target_path_for_bucket(repo_dir, 'devel_files', file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				print(f"{Colors.CYAN}[SKIP SOURCE]{Colors.RESET} {dest_file}")
				continue

			dest_parent = os.path.dirname(dest_file)
			if dest_parent and not os.path.isdir(dest_parent):
				if args.dry_run:
					print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} mkdir {dest_parent}")
				else:
					os.makedirs(dest_parent, exist_ok=True)

			dest_exists = os.path.isfile(dest_file)
			is_same = False
			if dest_exists:
				is_same = filecmp.cmp(source_file, dest_file, shallow=False)
			if is_same:
				print(f"{Colors.CYAN}[NO CHANGE]{Colors.RESET} {dest_file}")
				continue

			if args.dry_run:
				action = 'update' if dest_exists else 'copy'
				print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} {action} {source_file} -> {dest_file}")
			else:
				shutil.copy2(source_file, dest_file)
				if dest_exists:
					print(f"{Colors.BLUE}[UPDATED]{Colors.RESET} {source_file} -> {dest_file}")
					updated_count += 1
				else:
					print(f"{Colors.BLUE}[COPIED]{Colors.RESET} {source_file} -> {dest_file}")
					copied_count += 1

		# Process test_files
		for file_rel in spec['test_files']:
			try:
				source_file = source_path_for_bucket(source_dir, 'test_files', file_rel, repo_type)
			except FileNotFoundError:
				errors += 1
				print(f"{Colors.RED}[ERROR]{Colors.RESET} source missing for test_files:{file_rel}")
				continue

			dest_file = target_path_for_bucket(repo_dir, 'test_files', file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				print(f"{Colors.CYAN}[SKIP SOURCE]{Colors.RESET} {dest_file}")
				continue

			dest_parent = os.path.dirname(dest_file)
			if dest_parent and not os.path.isdir(dest_parent):
				if args.dry_run:
					print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} mkdir {dest_parent}")
				else:
					os.makedirs(dest_parent, exist_ok=True)

			dest_exists = os.path.isfile(dest_file)
			is_same = False
			if dest_exists:
				is_same = filecmp.cmp(source_file, dest_file, shallow=False)
			if is_same:
				print(f"{Colors.CYAN}[NO CHANGE]{Colors.RESET} {dest_file}")
				continue

			if args.dry_run:
				action = 'update' if dest_exists else 'copy'
				print(f"{Colors.YELLOW}[DRY RUN]{Colors.RESET} {action} {source_file} -> {dest_file}")
			else:
				shutil.copy2(source_file, dest_file)
				if dest_exists:
					print(f"{Colors.BLUE}[UPDATED]{Colors.RESET} {source_file} -> {dest_file}")
					updated_count += 1
				else:
					print(f"{Colors.BLUE}[COPIED]{Colors.RESET} {source_file} -> {dest_file}")
					copied_count += 1

		# Process gitignore blocks, then dedupe across blocks (e.g., dist/ in
		# both python and typescript would otherwise duplicate).
		merge_gitignore_blocks(repo_dir, repo_type, source_dir, args.dry_run)
		gitignore_path = os.path.join(repo_dir, '.gitignore')
		deduplicate_gitignore(gitignore_path, args.dry_run)
		removed_deprecated = remove_gitignore_entries(gitignore_path, DEPRECATED_GITIGNORE_ENTRIES, args.dry_run)
		merged_count += removed_deprecated

		# Per-repo summary line
		repo_basename = os.path.basename(repo_dir)
		repo_abspath = os.path.abspath(repo_dir)
		print(f"{Colors.CYAN}repo={repo_basename} path={repo_abspath} type={repo_type} updates={repo_updates} copies={repo_copies} skips={repo_skips}{Colors.RESET}")

	print("")
	print(f"{Colors.CYAN}GLOBAL SUMMARY:{Colors.RESET}")
	print(f"  copied={copied_count} updated={updated_count} merged={merged_count} created={created_count} skipped-by-policy={skipped_by_policy} auto-discovered={auto_discovered_count} errors={errors}")


if __name__ == '__main__':
	main()
