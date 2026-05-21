#!/usr/bin/env python3
"""Propagate canonical docs/scripts/configs from this template to consumer repos under ~/nsh/."""

import os
import stat
import shutil
import argparse
import filecmp
from dataclasses import dataclass

# Try to import detect_repo_type from tools/; if not available, prediction is skipped.
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
try:
	import detect_repo_type
except ImportError:
	detect_repo_type = None

# Rich console for colored output
from rich.console import Console

# highlight=False disables rich's auto-coloring of paths/numbers (renders as magenta in some terminals).
# width=200 hard-coded to prevent CI soft-wrap; keeps one line per action (determinism for snapshot tests).
CONSOLE = Console(width=200, highlight=False)

# Color philosophy: color signals importance/structure, not verb taxonomy.
# Action row verbs get meaningful color (changed files = yellow/blue, exceptions = red).
# Mode prefix "dry run" always dim. Counter rows + paths stay plain. Section headings use bold.
#
# Verb palette: update (yellow) = edit-in-place; copy/merge/create (blue) = file added/moved;
# removed (red) = destructive; skip/no change (dim) = no-op; warn (yellow) = caution; error (red) = failure.
ACTION_STYLES = {
	# mode prefix
	"dry run":   "dim",
	# changed-file verbs (color = "look here, file changed")
	"update":    "yellow",
	"copy":      "blue",
	"merge":     "blue",
	"create":    "blue",
	"removed":   "red",
	# non-change verbs (dim - usually suppressed)
	"skip":      "dim",
	"no change": "dim",
	# exceptions (warn/error)
	"warn":      "yellow",
	"error":     "red",
}

# Compute column width for verb alignment: widest verb name + 1 space.
# Exclude 'dry run': rendered as separate mode prefix token, not as a verb in the aligned column.
_VERB_WIDTH = max(len(v) for v in ACTION_STYLES if v != "dry run") + 1

# Verbs whose log lines are suppressed; counts roll into per-repo summary instead.
# Counter dispatch (skip message-prefix -> counter key) lives in log_action() body.
# When counters is None, quiet verbs still print (fallthrough behavior).
_QUIET_TAGS = {"no change", "skip"}

def log_action(verb: str, message: str, counters: dict | None = None, dry_run: bool = False) -> None:
	"""Log an action with separate mode and verb styling.

	For verbs in _QUIET_TAGS, suppress printing and increment counter instead.
	For other verbs, print with styled output: optional "dry run" prefix (dim) + verb (colored).

	Args:
		verb (str): Action verb in lowercase (must exist in ACTION_STYLES).
		message (str): Message body (separate from markup for safety).
		counters (dict | None): Optional counter dict to increment for quiet tags.
			When provided and verb is quiet, increments appropriate counter based on
			message prefix ('self:', 'source:', 'path:', or 'policy' default for SKIP;
			'unchanged' for NO CHANGE). When None or verb not quiet, behaves as before.
		dry_run (bool): If True, prepend "dry run" prefix (dim) before the verb.

	Raises:
		KeyError: If verb is not in ACTION_STYLES.
	"""
	style = ACTION_STYLES[verb]

	# Quiet tags: suppress printing and increment counter
	if verb in _QUIET_TAGS and counters is not None:
		if verb == "no change":
			counters['unchanged'] += 1
		elif verb == "skip":
			# Parse message prefix to attribute to correct counter
			if message.startswith("self:"):
				counters['skipped_self'] += 1
			elif message.startswith("source:"):
				counters['skipped_source'] += 1
			elif message.startswith("path:"):
				counters['skipped_path'] += 1
			else:
				counters['skipped_policy'] += 1
		return

	# Non-quiet tags: print with styled output
	padded_verb = verb.ljust(_VERB_WIDTH)
	if dry_run:
		CONSOLE.print(f"[dim]dry run[/] [{style}]{padded_verb}[/] {message}")
	else:
		CONSOLE.print(f"[{style}]{padded_verb}[/] {message}")

# ============================================
# Orchestration context dataclass
# ============================================

@dataclass
class PropagateContext:
	"""
	Context object passed to orchestration helpers.
	Mirrors all args fields that downstream helpers need. Treat as read-only after construction.
	"""
	base_dir: str
	source_dir: str
	template_root: str
	repo_name: str | None
	dry_run: bool
	bootstrap: bool
	sync_self: bool
	auto_discover: bool
	fix_permissions: bool
	write_marker: bool
	skip_confirm: bool
	verbose_paths: bool  # If True, show absolute src + dst paths in action lines (default False).

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

DEFAULT_REPO_SKIP_NAMES = frozenset({
	'starter-repo-template',
	'vosslab-skills',
})

SKIP_WALK_DIRS = frozenset({
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
})

AUTO_DISCOVER_DOCS_EXCLUDE = frozenset({
	'AUTHORS.md',
	'CHANGELOG.md',
})

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
# Meta tests use these prefixes to distinguish from regular repo tests.
META_TEST_PREFIXES = (
	'test_propagate_',
	'test_reset_repo_',
	'test_detect_repo_type',
)


#============================================
# File and text mutation helpers
#============================================

def copy_file_safe(src: str, dst: str, dry_run: bool, action: str = 'copy', message: str = None) -> bool:
	"""
	Copy a file from src to dst, preserving mode bits (executable bit).

	Returns False on dry-run (logs dry-run line), True on actual copy.
	Raises exception on error (no try/except per code style).

	Args:
		src (str): Source file path.
		dst (str): Destination file path.
		dry_run (bool): If True, only log without copying.
		action (str): Action word for dry-run message (default 'copy').
		message (str): Optional pre-formatted message. If provided, overrides default formatting.

	Returns:
		bool: False on dry-run, True on actual copy.
	"""
	if dry_run:
		if message is None:
			message = f"{src} -> {dst}"
		log_action(action, message, dry_run=True)
		return False
	shutil.copy2(src, dst)
	return True


def make_dir_safe(path: str, dry_run: bool) -> bool:
	"""
	Create a directory if it does not exist.

	Returns False on dry-run, True on actual mkdir.
	"""
	if dry_run:
		log_action("create", path, dry_run=True)
		return False
	os.makedirs(path, exist_ok=True)
	return True


def copy_if_changed(source: str, dest: str, dry_run: bool, counters: dict, action_label: str = 'copy', format_path=None) -> str:
	"""
	Copy source to dest only if they differ; return indicator and suppress or log outcome.

	Args:
		source (str): Path to source file.
		dest (str): Path to destination file.
		dry_run (bool): If True, only log planned action without copying.
		counters (dict): Mutable counter dict to increment for SKIP and NO CHANGE (quiet tags).
			When counters is provided, these tags are counted but not printed.
		action_label (str): Label for dry-run output (default 'copy').
		format_path (callable | None): Optional function to format path pairs.
			Called as format_path(source, dest) and should return formatted path string.
			If None, uses default "{source} -> {dest}" format.

	Returns:
		str: One of 'skipped_source', 'no_change', 'copied', 'updated'.

	Behavior:
		- If source missing: logs SKIP to counters, returns 'skipped_source'.
		- If dest exists and files match: logs NO CHANGE to counters, returns 'no_change'.
		- Otherwise: copies/updates, logs COPIED or UPDATED (non-quiet, always printed),
		  returns 'copied' or 'updated'.

	Note:
		Message-prefix ('source:', 'self:', 'path:') drives counter dispatch via log_action().
		Callers that log non-standard prefixes must ensure log_action() handles them.

	Uses copy_file_safe() and make_dir_safe() underneath.
	"""
	def _default_format_path(s: str, d: str) -> str:
		"""Default path formatter when none provided."""
		return f"{s} -> {d}"

	if format_path is None:
		format_path = _default_format_path

	# Check if source exists
	if not os.path.isfile(source):
		log_action("skip", f"source: {source} (not found)", counters)
		return 'skipped_source'

	# Check if dest exists and compare
	dest_exists = os.path.isfile(dest)
	is_same = False
	if dest_exists:
		is_same = filecmp.cmp(source, dest, shallow=False)
	if is_same:
		log_action("no change", dest, counters)
		return 'no_change'

	# Ensure parent directory exists
	dest_parent = os.path.dirname(dest)
	if dest_parent and not os.path.isdir(dest_parent):
		make_dir_safe(dest_parent, dry_run)

	# Copy the file
	formatted_path = format_path(source, dest)
	action = 'update' if dest_exists else 'copy'
	copy_file_safe(source, dest, dry_run, action=action, message=formatted_path if dry_run else None)
	if not dry_run:
		if dest_exists:
			log_action("update", formatted_path)
			return 'updated'
		else:
			log_action("copy", formatted_path)
			return 'copied'
	else:
		# On dry-run, copy_file_safe() already printed; return the action we would take
		return 'updated' if dest_exists else 'copied'


def read_text(path: str) -> str:
	"""
	Read a UTF-8 text file.

	Returns the file contents as a string.
	"""
	with open(path, 'r', encoding='utf-8') as f:
		return f.read()


def write_text(path: str, content: str, dry_run: bool = False, action: str = 'update') -> bool:
	"""
	Write content to a UTF-8 text file.

	Returns False on dry-run (logs dry-run line), True on actual write.
	"""
	if dry_run:
		log_action(action, path, dry_run=True)
		return False
	with open(path, 'w', encoding='utf-8') as f:
		f.write(content)
	return True


#============================================
def safe_walk(root: str):
	"""
	Walk directory tree filtering out unwanted directories.

	Yields (dirpath, dirs, files) tuples like os.walk, with the following filters applied:
	- Skips directories in SKIP_WALK_DIRS
	- Skips directories starting with '.' (dotdirs)
	- Mutates dirs[:] internally so callers don't need to

	Args:
		root (str): Root directory to walk

	Yields:
		tuple: (dirpath, dirs, files) with dirs[:] already filtered
	"""
	for dirpath, dirs, files in os.walk(root, topdown=True, followlinks=False):
		dirs[:] = [d for d in dirs if d not in SKIP_WALK_DIRS and not d.startswith('.')]
		yield dirpath, dirs, files


#============================================
def load_gitignore_block(path: str) -> list[str]:
	"""
	Load gitignore block from file, filtering blanks and comments.

	Args:
		path (str): Path to gitignore source file.

	Returns:
		list[str]: List of non-blank, non-comment lines (stripped).
	"""
	if not os.path.isfile(path):
		return []
	content = read_text(path)
	lines = []
	for line in content.split('\n'):
		stripped = line.rstrip('\n').strip()
		if stripped and not stripped.startswith('#'):
			lines.append(stripped)
	return lines


#============================================
def write_repo_type_marker(path: str, token: str, dry_run: bool = False) -> bool:
	"""
	Write REPO_TYPE marker file.

	Args:
		path (str): Path to REPO_TYPE marker file.
		token (str): Canonical type token (python, typescript, rust, other).
		dry_run (bool): If True, do not write changes.

	Returns:
		bool: True if written, False on dry-run.
	"""
	content = token + '\n'
	return write_text(path, content, dry_run, action='create')


#============================================
def parse_repo_type_choice(text: str, default: str = None) -> str | None:
	"""
	Parse user input for repo type choice.

	Maps single-letter aliases and full words to canonical tokens.
	Unknown input returns default.

	Args:
		text (str): User input or single-letter choice.
		default (str): Default token if input is unrecognized.

	Returns:
		str: Canonical token (python, typescript, rust, other) or default.
	"""
	if not text:
		return default
	choice = text.strip().lower()
	if choice in ('p', 'python'):
		return 'python'
	if choice in ('t', 'typescript'):
		return 'typescript'
	if choice in ('r', 'rust'):
		return 'rust'
	if choice in ('o', 'other'):
		return 'other'
	return default


#============================================
def replace_managed_block(lines: list[str], header: str, block_lines: list[str]) -> list[str]:
	"""
	Replace or append a named managed block in a line list.

	Finds the named block (starting with header) and replaces it with the new content.
	If the block is absent, appends at end. Idempotent: works correctly on multiple calls.

	Args:
		lines (list[str]): Existing lines.
		header (str): Block header to search for (e.g., '# === UNIVERSAL ===').
		block_lines (list[str]): New block content (without header).

	Returns:
		list[str]: New line list with the block replaced or appended.
	"""
	start_idx = -1
	for i, line in enumerate(lines):
		if line.startswith(header):
			start_idx = i
			break

	if start_idx == -1:
		# Block not found: append
		result = list(lines)
		result.append(header)
		result.extend(block_lines)
		return result

	# Block found: replace
	end_idx = start_idx + 1
	for i in range(start_idx + 1, len(lines)):
		if lines[i].startswith('# ==='):
			end_idx = i
			break
	else:
		end_idx = len(lines)

	result = lines[:start_idx] + [header] + block_lines + lines[end_idx:]
	return result


#============================================
def compute_propagation_plan(template_root: str, repo_type: str, counters: dict | None = None) -> dict:
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
		for root, dirs, files in safe_walk(template_root):
			# Skip directories: meta, templates (we walk it separately)
			dirs[:] = [d for d in dirs if d not in META_DIRS]

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
						log_action("skip", f"overlay: {file_rel} (typed overlay shadows universal source)", counters)
					plan['overwrite_files'].append(file_rel)

	# 3. Load gitignore blocks
	# Universal block source: templates/gitignore.universal (not a canonical
	# consumer-root filename, so it lives under templates/ not at template root).
	gitignore_universal_path = os.path.join(template_root, 'templates', 'gitignore.universal')
	plan['gitignore_block'].extend(load_gitignore_block(gitignore_universal_path))

	# Typed
	gitignore_typed_path = os.path.join(type_overlay_root, f'gitignore.{repo_type}')
	plan['gitignore_block'].extend(load_gitignore_block(gitignore_typed_path))

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
# Orchestration helpers
#============================================

def build_context(args) -> 'PropagateContext':
	"""
	Build a typed context object from parse_args() result.

	Takes the argparse Namespace and returns a PropagateContext with every field
	that downstream helpers need. Resolves paths to absolute form.

	Args:
		args (argparse.Namespace): Result from parse_args().

	Returns:
		PropagateContext: Immutable context for all orchestration helpers.
	"""
	base_dir = args.base_dir
	if base_dir:
		base_dir = os.path.abspath(os.path.expanduser(base_dir))
	else:
		base_dir = os.path.abspath(os.path.expanduser('~/nsh'))

	source_dir = resolve_source_dir(base_dir, args.source_dir)
	template_root = normalize_path(source_dir)

	return PropagateContext(
		base_dir=base_dir,
		source_dir=source_dir,
		template_root=template_root,
		repo_name=args.repo_name,
		dry_run=args.dry_run,
		bootstrap=args.bootstrap,
		sync_self=args.sync_self,
		auto_discover=args.auto_discover,
		fix_permissions=args.fix_permissions,
		write_marker=args.write_marker,
		skip_confirm=args.skip_confirm,
		verbose_paths=args.verbose_paths,
	)


def resolve_target_repos(context: 'PropagateContext') -> list[str]:
	"""
	Resolve target repository list from context.

	Returns a single-element list with the resolved target repo if context.repo_name
	is set, otherwise returns discover_repos(context.base_dir).
	When --sync-self is set, prepends template_root to the repo list (unless already present).

	Args:
		context (PropagateContext): Orchestration context with base_dir and repo_name.

	Returns:
		list[str]: List of repository paths to process.
	"""
	if context.repo_name:
		target_repo = resolve_target_repo(context.base_dir, context.repo_name)
		repos = [target_repo]
	else:
		repos = discover_repos(context.base_dir)

	# --sync-self: re-add template even though skip-list excludes it by name.
	if context.sync_self and context.template_root not in [normalize_path(r) for r in repos]:
		# Use the actual on-disk path (source_dir), not the normalized form,
		# so downstream logging shows a clean absolute path.
		repos = [context.source_dir] + repos

	return repos


def discover_repos(base_dir: str) -> list[str]:
	"""
	Discover repositories under base_dir and apply --sync-self insertion logic.

	Wraps collect_repo_dirs to find all repos, then does NOT insert template_root
	here (that logic stays in main() after build_context). This function only discovers
	and returns discovered repos from base_dir.

	Args:
		base_dir (str): Base directory containing repos.

	Returns:
		list[str]: List of repository paths, sorted, with skip-list applied.
	"""
	return collect_repo_dirs(base_dir, target_repo=None)


def init_counters() -> dict:
	"""
	Initialize mutable counter dictionary for global tracking.

	Returns a dict with all expected counter keys, each initialized to 0.

	Returns:
		dict: Counter dict with keys: copied_count, updated_count, merged_count,
			created_count, auto_discovered_count, errors,
			unchanged, skipped_source, skipped_self, skipped_path, skipped_policy.
	"""
	return {
		'copied_count': 0,
		'updated_count': 0,
		'merged_count': 0,
		'created_count': 0,
		'auto_discovered_count': 0,
		'errors': 0,
		'unchanged': 0,
		'skipped_source': 0,
		'skipped_self': 0,
		'skipped_path': 0,
		'skipped_policy': 0,
	}


def validate_counters(counters: dict) -> None:
	"""
	Validate that all expected counter keys are present.

	Raises AssertionError if any expected key is missing from the counters dict.
	Called at end-of-run to ensure data integrity.

	Args:
		counters (dict): Counter dict to validate.

	Raises:
		AssertionError: If any expected key is missing.
	"""
	expected_keys = {
		'copied_count',
		'updated_count',
		'merged_count',
		'created_count',
		'auto_discovered_count',
		'errors',
		'unchanged',
		'skipped_source',
		'skipped_self',
		'skipped_path',
		'skipped_policy',
	}
	actual_keys = set(counters.keys())
	missing = expected_keys - actual_keys
	if missing:
		raise AssertionError(f"counters missing keys: {missing}")


def print_summary(counters: dict, repo_results: list = None, dry_run: bool = False) -> None:
	"""
	Print the summary block at end of run.

	For single-repo mode (len(repo_results) == 1), emits one SUMMARY block with
	repo and type rows plus counters.

	For multi-repo mode (len(repo_results) > 1), emits a final SUMMARY block with
	repos count plus aggregated counters.

	When dry_run is True, counter labels switch from past-tense to "would X" form:
	  updated -> would update
	  copied -> would copy
	  merged -> would merge
	  created -> would create
	  unchanged, skipped, errors stay as-is

	Suppresses zero-valued routine counters (only show nonzero action/state counters
	plus errors, which always displays even at 0). Order preserved: action counters
	first, then state counters, then errors.

	Args:
		counters (dict): Counter dict with all keys present (should be validated).
		repo_results (list): List of dicts with 'name' and 'type' keys (single-repo mode
			expects one element; multi-repo mode expects >1). When None or empty,
			defaults to multi-repo display with repos count.
		dry_run (bool): If True, use "would X" labels instead of past-tense.
	"""
	if repo_results is None:
		repo_results = []

	CONSOLE.print("")
	CONSOLE.print("[bold white]SUMMARY[/]")

	# Define counter label mapping based on dry_run flag
	if dry_run:
		action_labels = {
			'updated_count': 'would update',
			'copied_count': 'would copy',
			'merged_count': 'would merge',
			'created_count': 'would create',
		}
	else:
		action_labels = {
			'updated_count': 'updated',
			'copied_count': 'copied',
			'merged_count': 'merged',
			'created_count': 'created',
		}

	# Build counter rows based on single vs. multi-repo mode
	if len(repo_results) == 1:
		# Single-repo mode: include repo and type rows at top
		repo_info = repo_results[0]
		counter_rows = [
			('repo', repo_info['name']),
			('type', repo_info['type']),
			(action_labels['updated_count'], counters['updated_count']),
			(action_labels['copied_count'], counters['copied_count']),
			(action_labels['merged_count'], counters['merged_count']),
			(action_labels['created_count'], counters['created_count']),
			('unchanged', counters['unchanged']),
			('skipped', counters['skipped_source'] + counters['skipped_self'] + counters['skipped_path'] + counters['skipped_policy']),
			('errors', counters['errors']),
		]
	else:
		# Multi-repo mode: repos count instead of repo/type rows
		counter_rows = [
			('repos', len(repo_results)),
			(action_labels['updated_count'], counters['updated_count']),
			(action_labels['copied_count'], counters['copied_count']),
			(action_labels['merged_count'], counters['merged_count']),
			(action_labels['created_count'], counters['created_count']),
			('unchanged', counters['unchanged']),
			('skipped', counters['skipped_source'] + counters['skipped_self'] + counters['skipped_path'] + counters['skipped_policy']),
			('errors', counters['errors']),
		]

	# Suppress zero-valued routine counters (except errors, which always shows)
	# Routine counters: action counters and state counters (skip repo/repos/type rows)
	visible_rows = []
	for name, value in counter_rows:
		# Identity rows (repo/repos/type) always visible
		if name in ('repo', 'repos', 'type'):
			visible_rows.append((name, value))
		# Errors always visible
		elif name == 'errors':
			visible_rows.append((name, value))
		# Routine counters: show only if nonzero
		elif value != 0:
			visible_rows.append((name, value))

	# Compute column width based on visible counter names
	col_width = max(len(name) for name, _ in visible_rows) + 1

	# Print each visible row
	for name, value in visible_rows:
		if name == 'errors' and value > 0:
			CONSOLE.print(f"  {name.ljust(col_width)}[bold red]{value}[/]")
		else:
			CONSOLE.print(f"  {name.ljust(col_width)}{value}")


def exit_code_for(counters: dict) -> int:
	"""
	Compute exit code based on error count.

	Returns 1 if counters['errors'] > 0, else returns 0.

	Args:
		counters (dict): Counter dict with 'errors' key.

	Returns:
		int: 0 if no errors, 1 if any errors occurred.
	"""
	if counters['errors'] > 0:
		return 1
	return 0


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
	parser.add_argument(
		'-v', '--verbose-paths', dest='verbose_paths',
		help='Show full absolute src + dst paths in action lines',
		action='store_true'
	)
	parser.set_defaults(dry_run=False, bootstrap=False, sync_self=False, fix_permissions=False, auto_discover=True, write_marker=False, skip_confirm=False, verbose_paths=False)
	args = parser.parse_args()
	return args


#============================================
def resolve_spec_for_type(repo_type: str, template_root: str = None, counters: dict | None = None) -> dict:
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
	return compute_propagation_plan(template_root, repo_type, counters=counters)


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
def find_source_for_bucket(template_root: str, bucket: str, file_rel: str, repo_type: str = 'universal') -> str | None:
	"""
	Resolve canonical source path for a file in a bucket, or return None if not found.

	Non-raising variant of source_path_for_bucket() for cleaner predicate-based control flow.

	Args:
		template_root (str): Template root directory.
		bucket (str): Bucket name (overwrite_files, noexist_files, devel_files, test_files).
		file_rel (str): Relative path of the file.
		repo_type (str): Repository type (python, typescript, rust, other). Defaults to 'universal'.

	Returns:
		str | None: Canonical source path if found, None otherwise.
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

	return None


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

	for root, dirs, files in safe_walk(test_dir):
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
def read_repo_type(repo_path: str, single_repo_mode: bool = False, write_marker: bool = False, skip_confirm: bool = False, non_interactive: bool = False, counters: dict | None = None) -> str:
	"""Read REPO_TYPE marker; predict if single-repo mode with write_marker, else default to 'python'; fallback to legacy STARTER_REPO_TYPE for backward compatibility."""
	marker_path = os.path.join(repo_path, 'REPO_TYPE')
	legacy_marker_path = os.path.join(repo_path, 'STARTER_REPO_TYPE')

	# Check for legacy marker first if new marker doesn't exist
	if not os.path.isfile(marker_path) and os.path.isfile(legacy_marker_path):
		log_action("warn", f"{repo_path}: legacy STARTER_REPO_TYPE marker found; rename to REPO_TYPE")
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
				write_repo_type_marker(marker_path, token, dry_run=False)
				log_action("skip", f"repo={os.path.basename(repo_path)} type={token} confidence=high (auto-wrote marker, predicted)", counters)
				return token

			if confidence == 'medium':
				# Medium confidence: print and ask
				log_action("warn", f"repo={os.path.basename(repo_path)} type={token} (predicted, medium confidence)")
				CONSOLE.print("  reasoning:")
				for bullet in reasoning:
					CONSOLE.print(f"    - {bullet}")

				if skip_confirm or non_interactive:
					# Accept silently
					write_repo_type_marker(marker_path, token, dry_run=False)
					log_action("skip", "wrote marker (medium confidence accepted)", counters)
					return token

				if not non_interactive:
					# Prompt user
					user_input = input(f"Accept predicted type '{token}'? [Y/n]: ").strip()
					if user_input == '' or user_input.lower() == 'y':
						write_repo_type_marker(marker_path, token, dry_run=False)
						return token
					else:
						# User rejected; re-prompt for explicit type
						while True:
							user_type = input(
								"Project type? [p]ython / [t]ypescript / [r]ust / [o]ther [p]: "
							).strip()
							chosen_type = parse_repo_type_choice(user_type, 'python')
							write_repo_type_marker(marker_path, chosen_type, dry_run=False)
							return chosen_type

			# Low confidence or ambiguous: abort if non-interactive, else prompt
			log_action("error", f"repo={os.path.basename(repo_path)} (ambiguous, could not predict)")
			CONSOLE.print("  reasoning:")
			for bullet in reasoning:
				CONSOLE.print(f"    - {bullet}")

			if non_interactive:
				raise SystemExit("ambiguous repo type; specify REPO_TYPE manually or use reset_repo.py")

			# Interactive prompt for ambiguous
			while True:
				user_type = input(
					"Project type? [p]ython / [t]ypescript / [r]ust / [o]ther: "
				).strip()
				chosen_type = parse_repo_type_choice(user_type, None)
				if chosen_type is None:
					print("Invalid choice. Try again.")
					continue
				write_repo_type_marker(marker_path, chosen_type, dry_run=False)
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
			log_action("create", path, dry_run=True)
			return
		os.chmod(path, new_mode, follow_symlinks=False)

	add_group_write(git_dir)

	index_path = os.path.join(git_dir, 'index')
	if os.path.exists(index_path):
		add_group_write(index_path)

	for root, dirs, files in safe_walk(git_dir):
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

	write_text(changelog_path, '', dry_run, action='create')
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

	content = read_text(gitignore_path)
	lines = [line.rstrip('\n') for line in content.split('\n')]

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

	new_content = '\n'.join(filtered_lines) + '\n' if filtered_lines else ''
	write_text(gitignore_path, new_content, dry_run)

	return removed_count


#============================================
def deduplicate_gitignore(gitignore_path: str, dry_run: bool, counters: dict | None = None) -> None:
	"""
	Remove duplicate lines and trailing whitespace from .gitignore file.
	Preserves all empty lines and comments for visual grouping.

	Updates counters dict in-place if provided: increments 'merged_count' when changes
	are made (duplicates removed and/or whitespace cleaned).

	Args:
		gitignore_path (str): Path to .gitignore file.
		dry_run (bool): If True, do not write changes.
		counters (dict | None): Optional counter dict to update with merged_count.
	"""
	if not os.path.isfile(gitignore_path):
		return

	content = read_text(gitignore_path)
	original_lines = [line.rstrip('\n') for line in content.split('\n')]

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
		return

	new_content = '\n'.join(unique_lines) + '\n' if unique_lines else ''
	write_text(gitignore_path, new_content, dry_run)

	if not dry_run and counters is not None:
		counters['merged_count'] += 1


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
	source_text = read_text(source_file)
	if not os.path.isfile(dest_file):
		return source_text
	dest_text = read_text(dest_file)
	if 'collect_ignore' in dest_text:
		return None
	if dest_text.strip() == '':
		return source_text
	merged = source_text.rstrip() + '\n\n' + dest_text
	if not merged.endswith('\n'):
		merged += '\n'
	return merged


#============================================
def merge_gitignore_blocks(repo_dir: str, repo_type: str, template_root: str, context: 'PropagateContext', counters: dict | None = None) -> None:
	"""
	Manage .gitignore as a sequence of named blocks delimited by '# === <NAME> ==='.
	Blocks: UNIVERSAL (always), and <REPO_TYPE_UPPERCASE> (when non-empty).
	If block header exists, replace just that block. If not, append at end.
	User-added lines OUTSIDE any managed block stay untouched.

	Updates counters dict in-place if provided: increments 'created_count' or 'merged_count'
	depending on whether .gitignore was newly created or updated.

	Args:
		repo_dir (str): Repository directory path.
		repo_type (str): Type of repository (python, typescript, rust, other).
		template_root (str): Template root directory for gitignore sources.
		context (PropagateContext): Context with dry_run and path formatting info.
		counters (dict | None): Optional counter dict to update with created/merged counts.
	"""
	gitignore_path = os.path.join(repo_dir, '.gitignore')

	file_exists = os.path.isfile(gitignore_path)
	existing_lines = []
	if file_exists:
		content = read_text(gitignore_path)
		existing_lines = [line.rstrip('\n') for line in content.split('\n')]

	# Load universal and type-specific gitignore blocks from files.
	# Universal source lives under templates/ (not a canonical consumer-root filename).
	gitignore_universal_path = os.path.join(template_root, 'templates', 'gitignore.universal')
	universal_lines = load_gitignore_block(gitignore_universal_path)

	gitignore_typed_path = os.path.join(template_root, 'templates', repo_type, f'gitignore.{repo_type}')
	type_lines = load_gitignore_block(gitignore_typed_path)

	universal_header = '# === UNIVERSAL ==='
	type_header = f"# === {repo_type.upper()} ==="

	# Build new content
	new_lines = list(existing_lines)
	new_lines = replace_managed_block(new_lines, universal_header, universal_lines)

	# Handle type-specific block (if any)
	if type_lines:
		new_lines = replace_managed_block(new_lines, type_header, type_lines)

	# Build content with proper trailing newline
	content = '\n'.join(new_lines)
	if content and not content.endswith('\n'):
		content += '\n'

	existing_content = '\n'.join(existing_lines)
	if existing_lines and not existing_content.endswith('\n'):
		existing_content += '\n'

	# Write if needed
	if not file_exists:
		display_path = format_path_pair(gitignore_path, gitignore_path, repo_dir, context)
		if context.dry_run:
			log_action("create", display_path, dry_run=True)
		else:
			with open(gitignore_path, 'w', encoding='utf-8') as f:
				f.write(content)
			log_action("create", display_path)
			if counters is not None:
				counters['created_count'] += 1
	elif content != existing_content:
		display_path = format_path_pair(gitignore_path, gitignore_path, repo_dir, context)
		if context.dry_run:
			log_action("update", display_path, dry_run=True)
		else:
			with open(gitignore_path, 'w', encoding='utf-8') as f:
				f.write(content)
			log_action("update", display_path)
			if counters is not None:
				counters['merged_count'] += 1


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
			log_action("removed", deprecated_test_path, dry_run=True)
		else:
			os.remove(deprecated_test_path)
			log_action("removed", deprecated_test_path)
		removed += 1
	return removed


#============================================
def format_path_pair(source_file: str, dest_file: str, repo_dir: str, context: 'PropagateContext') -> str:
	"""
	Format a source-dest file pair for logging based on verbose_paths flag.

	If verbose_paths is True, show absolute paths as "src -> dst".
	If False (default), show repo-relative paths:
	  - If src relative path == dst relative path, show only the dst relative path
	  - Otherwise, show both as "src_rel -> dst_rel"

	Args:
		source_file (str): Absolute source file path.
		dest_file (str): Absolute destination file path.
		repo_dir (str): Repository directory path.
		context (PropagateContext): Context with verbose_paths flag and source_dir.

	Returns:
		str: Formatted path string for logging.
	"""
	if context.verbose_paths:
		return f"{source_file} -> {dest_file}"

	# Compute relative paths
	src_relative = os.path.relpath(source_file, context.source_dir)
	dst_relative = os.path.relpath(dest_file, repo_dir)

	# If relative paths are the same, show only one
	if src_relative == dst_relative:
		return dst_relative

	# Otherwise show both
	return f"{src_relative} -> {dst_relative}"


#============================================
def apply_file_bucket(bucket_name: str, spec: dict, repo_dir: str, repo_type: str, context: 'PropagateContext', counters: dict) -> tuple:
	"""
	Process one file bucket (overwrite_files, noexist_files, devel_files, test_files).

	Returns a tuple of (updates, copies, skips) for the per-repo summary line.
	Updates counters in-place.

	Args:
		bucket_name: One of 'overwrite_files', 'noexist_files', 'devel_files', 'test_files'.
		spec: The spec dict containing all four bucket lists.
		repo_dir: The repo directory path.
		repo_type: The detected repo type.
		context: The PropagateContext object.
		counters: The global counters dict (modified in-place).

	Returns:
		Tuple of (bucket_updates, bucket_copies, bucket_skips) for per-repo summary.
	"""
	bucket_updates = 0
	bucket_copies = 0
	bucket_skips = 0

	if bucket_name == 'overwrite_files':
		# ============ OVERWRITE BUCKET ============
		# Overwrite: copy to repo at exact path; CLAUDE.md merges to preserve user @ lines.
		for file_rel in spec['overwrite_files']:
			source_file = find_source_for_bucket(context.source_dir, 'overwrite_files', file_rel, repo_type)
			if source_file is None:
				counters['errors'] += 1
				log_action("error", f"source missing for {file_rel}")
				continue

			dest_file = os.path.join(repo_dir, file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				log_action("skip", f"self: {dest_file}", counters)
				continue

			# Special case: CLAUDE.md merges to preserve user @ lines
			if file_rel == 'CLAUDE.md':
				dest_exists = os.path.isfile(dest_file)
				if dest_exists:
					merged_content = merge_claude_md(source_file, dest_file)
					existing_content = read_text(dest_file)
					if merged_content == existing_content:
						log_action("no change", dest_file, counters)
						continue
					write_text(dest_file, merged_content, context.dry_run, action='merge')
					if not context.dry_run:
						formatted_path = format_path_pair(source_file, dest_file, repo_dir, context)
						log_action("merge", formatted_path)
						counters['merged_count'] += 1
					continue

			# Regular overwrite: use copy_if_changed
			def _format_overwrite_path(s: str, d: str) -> str:
				"""Format path for overwrite bucket with context."""
				return format_path_pair(s, d, repo_dir, context)
			result = copy_if_changed(source_file, dest_file, context.dry_run, counters, action_label='update', format_path=_format_overwrite_path)
			if not context.dry_run:
				if result == 'copied':
					counters['copied_count'] += 1
				elif result == 'updated':
					counters['updated_count'] += 1
					bucket_updates += 1
			else:
				# On dry-run, result is still the action we would take
				if result == 'updated':
					bucket_updates += 1

	elif bucket_name == 'noexist_files':
		# ============ NOEXIST BUCKET ============
		# Noexist: copy only if destination does not exist; --bootstrap overrides.
		for file_rel in spec['noexist_files']:
			source_file = find_source_for_bucket(context.source_dir, 'noexist_files', file_rel, repo_type)
			if source_file is None:
				counters['errors'] += 1
				log_action("error", f"source missing for {file_rel}")
				continue

			dest_file = os.path.join(repo_dir, file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				log_action("skip", f"self: {dest_file}", counters)
				continue

			if file_rel == 'source_me.sh' and repo_is_on_path(repo_dir):
				log_action("skip", f"path: {dest_file} (repo is already on PATH)", counters)
				continue

			if os.path.exists(dest_file) and not context.bootstrap:
				log_action("skip", f"{dest_file} (exists, use --bootstrap to override)", counters)
				bucket_skips += 1
				continue

			dest_parent = os.path.dirname(dest_file)
			if dest_parent and not os.path.isdir(dest_parent):
				make_dir_safe(dest_parent, context.dry_run)

			formatted_path = format_path_pair(source_file, dest_file, repo_dir, context)
			copy_file_safe(source_file, dest_file, context.dry_run, action='copy', message=formatted_path if context.dry_run else None)
			if not context.dry_run:
				log_action("copy", formatted_path)
				counters['copied_count'] += 1
			bucket_copies += 1

	elif bucket_name == 'devel_files':
		# ============ DEVEL BUCKET ============
		# Devel: copy to repo/devel/<basename>; flat namespace, not subdirectory-preserved.
		for file_rel in spec['devel_files']:
			source_file = find_source_for_bucket(context.source_dir, 'devel_files', file_rel, repo_type)
			if source_file is None:
				counters['errors'] += 1
				log_action("error", f"source missing for devel_files:{file_rel}")
				continue

			dest_file = target_path_for_bucket(repo_dir, 'devel_files', file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				log_action("skip", f"self: {dest_file}", counters)
				continue

			# Use copy_if_changed for standard overwrite semantics
			path_formatter = lambda s, d: format_path_pair(s, d, repo_dir, context)
			result = copy_if_changed(source_file, dest_file, context.dry_run, counters, action_label='update', format_path=path_formatter)
			if not context.dry_run:
				if result == 'copied':
					counters['copied_count'] += 1
				elif result == 'updated':
					counters['updated_count'] += 1
					bucket_updates += 1
			else:
				# On dry-run, result is still the action we would take
				if result == 'updated':
					bucket_updates += 1

	elif bucket_name == 'test_files':
		# ============ TEST BUCKET ============
		# Test: copy to tests/<file_rel> preserving tests/ prefix; auto-discovered files merge here.
		for file_rel in spec['test_files']:
			source_file = find_source_for_bucket(context.source_dir, 'test_files', file_rel, repo_type)
			if source_file is None:
				counters['errors'] += 1
				log_action("error", f"source missing for test_files:{file_rel}")
				continue

			dest_file = target_path_for_bucket(repo_dir, 'test_files', file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				log_action("skip", f"self: {dest_file}", counters)
				continue

			# Use copy_if_changed for standard overwrite semantics
			def _format_test_path(s: str, d: str) -> str:
				"""Format path for test bucket with context."""
				return format_path_pair(s, d, repo_dir, context)
			result = copy_if_changed(source_file, dest_file, context.dry_run, counters, action_label='update', format_path=_format_test_path)
			if not context.dry_run:
				if result == 'copied':
					counters['copied_count'] += 1
				elif result == 'updated':
					counters['updated_count'] += 1
					bucket_updates += 1
			else:
				# On dry-run, result is still the action we would take
				if result == 'updated':
					bucket_updates += 1

	return (bucket_updates, bucket_copies, bucket_skips)


#============================================
def process_repo(repo_dir: str, context: 'PropagateContext', counters: dict, emit_per_repo_summary: bool = True) -> dict | None:
	"""
	Process a single repository: read type, discover files, and perform propagation.

	Handles all per-repo logic: type detection, directory creation, file propagation
	across four buckets (overwrite, noexist, devel, test), gitignore management,
	and optionally per-repo summary output. Updates counters in-place.

	Returns a dict with 'name' and 'type' keys for the processed repo, or None if skipped.

	Args:
		repo_dir (str): Path to the repository directory.
		context (PropagateContext): Immutable context with template, base, and flag info.
		counters (dict): Mutable counter dict (copied_count, updated_count, etc.).
		emit_per_repo_summary (bool): If False, suppress per-repo summary output
			(used in single-repo mode where summary is printed at end).

	Returns:
		dict | None: {'name': repo_basename, 'type': repo_type} or None if repo was skipped.
	"""
	if not is_repo_dir(repo_dir):
		return None

	repo_normalized = normalize_path(repo_dir)
	if repo_normalized == context.template_root:
		if not context.sync_self:
			log_action("skip", f"self: {repo_dir} (use --sync-self to update template)", counters)
			return None
		else:
			# Informational status line, not an action - uses CONSOLE.print to avoid log_action SKIP-counter dispatch.
			CONSOLE.print(f"sync_self: processing template {repo_dir}")

	single_repo_mode = context.repo_name is not None
	repo_type = read_repo_type(
		repo_dir,
		single_repo_mode=single_repo_mode,
		write_marker=context.write_marker,
		skip_confirm=context.skip_confirm,
		non_interactive=False,
		counters=counters
	)

	# Capture baseline counters to calculate per-repo deltas for quiet counts
	baseline_unchanged = counters['unchanged']
	baseline_skipped_source = counters['skipped_source']
	baseline_skipped_self = counters['skipped_self']
	baseline_skipped_path = counters['skipped_path']
	baseline_skipped_policy = counters['skipped_policy']
	baseline_merged_count = counters['merged_count']
	baseline_created_count = counters['created_count']

	# Per-repo counters for summary line
	repo_updates = 0
	repo_copies = 0
	repo_skips = 0

	spec = resolve_spec_for_type(repo_type, context.source_dir, counters=counters)

	auto_discovered = []
	if context.auto_discover:
		auto_discovered = auto_discover_test_files(context.source_dir, repo_type)
		if auto_discovered:
			counters['auto_discovered_count'] += len(auto_discovered)
			spec['test_files'].extend(auto_discovered)
			# Informational summary, not an action - bypasses log_action so no counter increments.
			CONSOLE.print(f"auto-discovered {len(auto_discovered)} test files: {', '.join(auto_discovered)}")

	if context.fix_permissions:
		# return value intentionally ignored; chmod side-effect is the purpose
		ensure_git_perms(repo_dir, context.dry_run)

	docs_dir = os.path.join(repo_dir, 'docs')
	if not os.path.isdir(docs_dir):
		make_dir_safe(docs_dir, context.dry_run)

	tests_dir = os.path.join(repo_dir, 'tests')
	if ensure_tests_dir(tests_dir, context.dry_run):
		if context.dry_run:
			log_action("create", tests_dir, counters=counters, dry_run=True)

	conftest_path = os.path.join(tests_dir, 'conftest.py')
	source_conftest = os.path.join(context.source_dir, 'tests', 'conftest.py')
	if os.path.abspath(conftest_path) != os.path.abspath(source_conftest):
		merged_conftest = merge_conftest(source_conftest, conftest_path)
		if merged_conftest is not None:
			dest_existed = os.path.isfile(conftest_path)
			action = 'merge' if dest_existed else 'create'
			write_text(conftest_path, merged_conftest, context.dry_run, action=action)
			if not context.dry_run:
				if dest_existed:
					log_action("merge", f"injected collect_ignore into {conftest_path}", counters=counters)
					counters['merged_count'] += 1
				else:
					log_action("create", conftest_path, counters=counters)
					counters['created_count'] += 1

	remove_deprecated_tests(tests_dir, context.dry_run)

	devel_dir = os.path.join(repo_dir, 'devel')
	if not os.path.isdir(devel_dir):
		make_dir_safe(devel_dir, context.dry_run)

	changelog_path = os.path.join(docs_dir, 'CHANGELOG.md')
	if ensure_changelog_file(changelog_path, context.dry_run):
		if not context.dry_run:
			counters['created_count'] += 1

	# Apply file buckets
	updates, copies, skips = apply_file_bucket('overwrite_files', spec, repo_dir, repo_type, context, counters)
	repo_updates += updates
	repo_copies += copies
	repo_skips += skips

	updates, copies, skips = apply_file_bucket('noexist_files', spec, repo_dir, repo_type, context, counters)
	repo_updates += updates
	repo_copies += copies
	repo_skips += skips

	updates, copies, skips = apply_file_bucket('devel_files', spec, repo_dir, repo_type, context, counters)
	repo_updates += updates
	repo_copies += copies
	repo_skips += skips

	updates, copies, skips = apply_file_bucket('test_files', spec, repo_dir, repo_type, context, counters)
	repo_updates += updates
	repo_copies += copies
	repo_skips += skips

	# Process gitignore blocks, then dedupe across blocks (e.g., dist/ in
	# both python and typescript would otherwise duplicate).
	merge_gitignore_blocks(repo_dir, repo_type, context.source_dir, context, counters=counters)
	gitignore_path = os.path.join(repo_dir, '.gitignore')
	deduplicate_gitignore(gitignore_path, context.dry_run, counters=counters)
	removed_deprecated = remove_gitignore_entries(gitignore_path, DEPRECATED_GITIGNORE_ENTRIES, context.dry_run)
	if not context.dry_run and removed_deprecated > 0:
		counters['merged_count'] += 1

	# Per-repo summary block with quiet counter deltas (only if emit_per_repo_summary is True)
	repo_unchanged = counters['unchanged'] - baseline_unchanged
	repo_skipped_source = counters['skipped_source'] - baseline_skipped_source
	repo_skipped_self = counters['skipped_self'] - baseline_skipped_self
	repo_skipped_path = counters['skipped_path'] - baseline_skipped_path
	repo_skipped_policy = counters['skipped_policy'] - baseline_skipped_policy
	repo_merged = counters['merged_count'] - baseline_merged_count
	repo_created = counters['created_count'] - baseline_created_count

	repo_basename = os.path.basename(repo_dir)
	repo_type_display = repo_type

	if emit_per_repo_summary:
		# Header line: repo=name  type=python
		header = f"repo={repo_basename}  type={repo_type_display}"
		CONSOLE.print(f"[bold]{header}[/]")

		# Counter rows: indented, right-aligned counters
		# Build list of (name, value) tuples in display order
		counter_rows = [
			('updated', repo_updates),
			('copied', repo_copies),
			('merged', repo_merged),
			('created', repo_created),
			('unchanged', repo_unchanged),
			('skipped', repo_skipped_source + repo_skipped_self + repo_skipped_path + repo_skipped_policy),
			('errors', counters['errors']),
		]

		# Compute column width for counter names
		col_width = max(len(name) for name, _ in counter_rows) + 1

		# Print each counter row
		for name, value in counter_rows:
			if name == 'errors' and value > 0:
				CONSOLE.print(f"  {name.ljust(col_width)}[bold red]{value}[/]")
			else:
				CONSOLE.print(f"  {name.ljust(col_width)}{value}")

	# Return repo info for summary aggregation
	return {'name': repo_basename, 'type': repo_type}


#============================================
def main() -> int:
	"""
	Orchestrate propagation: build context, resolve repos, and process each one.
	"""
	args = parse_args()
	context = build_context(args)
	repos = resolve_target_repos(context)
	counters = init_counters()
	repo_results = []
	# Determine whether to emit per-repo summaries (multi-repo mode only)
	is_single_repo = len(repos) == 1
	for repo_dir in repos:
		result = process_repo(repo_dir, context, counters, emit_per_repo_summary=not is_single_repo)
		if result is not None:
			repo_results.append(result)
	validate_counters(counters)
	print_summary(counters, repo_results=repo_results, dry_run=context.dry_run)

	# Final completion line: success (green) or failure (bold red)
	if counters['errors'] == 0:
		CONSOLE.print("[green]done[/]")
	else:
		CONSOLE.print(f"[bold red]failed ({counters['errors']} errors)[/]")

	exit_code = exit_code_for(counters)
	return exit_code


if __name__ == '__main__':
	sys.exit(main())
