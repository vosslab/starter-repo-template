"""File operations, I/O helpers, and merge logic."""

import os
import shutil
import filecmp

import propagate.console
import propagate.model


#============================================
# META leak guard
#============================================

def assert_not_meta(file_rel: str) -> None:
	"""
	Fail loud if a file path would land in any propagation bucket despite being META.

	Called at every plan-construction append site and at the top of the propagator's
	apply_file_bucket dispatcher. Catches both plan-construction leaks (new walker
	branch forgets to filter META) and plan-injection leaks (future feature reads
	a plan from disk or accepts user-supplied paths).

	Args:
		file_rel: Repo-root-relative file path about to be added to a bucket
		          or about to be copied.

	Raises:
		RuntimeError: file_rel matches META_FILES by basename or rel-path,
		              OR any path component matches META_DIRS.
	"""
	basename = os.path.basename(file_rel)
	if file_rel in propagate.model.META_FILES or basename in propagate.model.META_FILES:
		raise RuntimeError(
			f"META leak: {file_rel!r} is in META_FILES and must never ship. "
			"Fix the upstream walker or dispatcher branch that produced this entry."
		)
	parts = file_rel.split(os.sep)
	for part in parts:
		if part in propagate.model.META_DIRS:
			raise RuntimeError(
				f"META leak: {file_rel!r} traverses META_DIRS component {part!r} "
				"and must never ship. Fix the upstream walker or dispatcher branch."
			)


#============================================
# Routing overrides
#============================================

def should_ship_override(file_rel: str, repo_lang: str, repo_dir: str) -> bool | None:
	"""
	Apply routing overrides on top of the walker's default routing.

	Checks ROUTING_OVERRIDES table for language-specific or requirement-based rules.
	Returns None if no override applies (walker's default decision stands).

	Note: this predicate only evaluates the gate fields (`language`, `requires_repo_file`).
	The `bucket` field is NOT consumed here; callers that receive True must re-read the rule
	dict from `propagate.model.ROUTING_OVERRIDES` to apply bucket overrides (see
	compute_propagation_plan in this module for the canonical pattern).

	Args:
		file_rel (str): Repo-root-relative file path.
		repo_lang (str): Repository language type (python, typescript, rust, other, unknown).
		repo_dir (str): Repository directory path.

	Returns:
		bool or None: True if override allows the file to ship, False if override blocks it,
		              None if no override applies.
	"""
	rule = propagate.model.ROUTING_OVERRIDES.get(file_rel)
	if rule is None:
		return None
	rule_lang = rule.get('language')
	if rule_lang is not None and rule_lang != repo_lang:
		return False
	required = rule.get('requires_repo_file')
	if required is not None and not os.path.isfile(os.path.join(repo_dir, required)):
		return False
	return True


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
		propagate.console.log_action(action, message, dry_run=True)
		return False
	shutil.copy2(src, dst)
	return True


def make_dir_safe(path: str, dry_run: bool) -> bool:
	"""
	Create a directory if it does not exist.

	Returns False on dry-run, True on actual mkdir.
	"""
	if dry_run:
		propagate.console.log_action("create", path, dry_run=True)
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
		propagate.console.log_action("skip", f"source: {source} (not found)", counters)
		return 'skipped_source'

	# Check if dest exists and compare
	dest_exists = os.path.isfile(dest)
	is_same = False
	if dest_exists:
		is_same = filecmp.cmp(source, dest, shallow=False)
	if is_same:
		propagate.console.log_action("no change", dest, counters)
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
			propagate.console.log_action("update", formatted_path)
			return 'updated'
		else:
			propagate.console.log_action("copy", formatted_path)
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
		propagate.console.log_action(action, path, dry_run=True)
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
		dirs[:] = [d for d in dirs if d not in propagate.model.SKIP_WALK_DIRS and not d.startswith('.')]
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
def normalize_path(path: str) -> str:
	"""
	Normalize a path for stable filesystem comparisons.
	"""
	return os.path.normcase(os.path.realpath(os.path.abspath(path)))


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
# MERGE bucket: fenced-marker merge (see meta/docs/MERGE_BUCKET_SPEC.md)
#============================================

# Fence styles by language. First match wins per file; mixing styles is an error.
FENCE_STYLES = (
	('# === TEMPLATE-MANAGED START ===', '# === TEMPLATE-MANAGED END ==='),
	('// === TEMPLATE-MANAGED START ===', '// === TEMPLATE-MANAGED END ==='),
	('<!-- === TEMPLATE-MANAGED START === -->', '<!-- === TEMPLATE-MANAGED END === -->'),
)


def _find_fences(text: str) -> tuple | None:
	"""
	Locate the fenced template-managed region in text.

	Returns (start_idx, end_idx, style_idx, lines) when exactly one valid pair found.
	Returns None when text has no fence markers (plain shape).
	Raises ValueError with an actionable message for malformed fence states:
	missing start, missing end, duplicate markers, mixed styles, or end-before-start.
	"""
	# Use split('\n') not splitlines(): a trailing '\n' produces a final empty element that
	# '\n'.join(...) restores, preserving exact byte-for-byte round-trip on unchanged input.
	lines = text.split('\n')
	style_hits = []
	for style_idx, (start_mark, end_mark) in enumerate(FENCE_STYLES):
		start_count = sum(1 for ln in lines if ln.strip() == start_mark)
		end_count = sum(1 for ln in lines if ln.strip() == end_mark)
		if start_count or end_count:
			style_hits.append((style_idx, start_count, end_count, start_mark, end_mark))

	if not style_hits:
		return None

	if len(style_hits) > 1:
		raise ValueError("fence style mismatch: multiple fence comment styles present")

	style_idx, start_count, end_count, start_mark, end_mark = style_hits[0]
	if start_count > 1:
		raise ValueError("duplicate fence marker: more than one start fence")
	if end_count > 1:
		raise ValueError("duplicate fence marker: more than one end fence")
	if start_count == 0:
		raise ValueError("missing start fence")
	if end_count == 0:
		raise ValueError("missing end fence")

	start_idx = next(i for i, ln in enumerate(lines) if ln.strip() == start_mark)
	end_idx = next(i for i, ln in enumerate(lines) if ln.strip() == end_mark)
	if end_idx < start_idx:
		raise ValueError("fence markers out of order (end before start)")

	return (start_idx, end_idx, style_idx, lines)


def merge_file_safe(source: str, dest: str, dry_run: bool, counters: dict) -> str:
	"""
	Merge a template-managed region into a consumer file.

	Outcomes returned:
		'created'   -- dest missing; wrote template verbatim. counters['created_count'] += 1.
		'merged'    -- dest fenced; replaced managed region; consumer additions preserved.
		              counters['merged_count'] += 1.
		'unchanged' -- merge produced byte-identical result. counters['unchanged'] += 1.
		'error'     -- consumer or template in invalid fence state; dest untouched.
		              counters['errors'] += 1.

	Error conditions (dest is NOT modified):
		- template lacks both fences (configuration bug at template side)
		- consumer has fences in invalid state (missing one, duplicates, wrong order,
		  mixed styles, or plain shape with no fences at all)
		- consumer and template use different fence styles
	"""
	if not os.path.isfile(source):
		counters['errors'] += 1
		propagate.console.log_action("error", f"merge source missing: {source}")
		return 'error'

	src_text = read_text(source)
	try:
		src_fences = _find_fences(src_text)
	except ValueError as exc:
		counters['errors'] += 1
		propagate.console.log_action("error", f"merge template fence error in {source}: {exc}")
		return 'error'

	if src_fences is None:
		counters['errors'] += 1
		propagate.console.log_action("error", f"merge template missing fences: {source}")
		return 'error'

	# Dest missing: write template verbatim (template carries both fences + managed content).
	if not os.path.isfile(dest):
		dest_parent = os.path.dirname(dest)
		if dest_parent and not os.path.isdir(dest_parent):
			make_dir_safe(dest_parent, dry_run)
		write_text(dest, src_text, dry_run, action='create')
		if not dry_run:
			propagate.console.log_action("create", dest)
			counters['created_count'] += 1
		return 'created'

	dest_text = read_text(dest)
	try:
		dest_fences = _find_fences(dest_text)
	except ValueError as exc:
		counters['errors'] += 1
		propagate.console.log_action("error", f"{dest}: {exc}")
		return 'error'

	if dest_fences is None:
		counters['errors'] += 1
		propagate.console.log_action("error", f"{dest}: consumer not at fenced shape; add fences once, then re-sync")
		return 'error'

	src_start, src_end, src_style_idx, src_lines = src_fences
	dest_start, dest_end, dest_style_idx, dest_lines = dest_fences

	if src_style_idx != dest_style_idx:
		counters['errors'] += 1
		propagate.console.log_action("error", f"{dest}: fence style mismatch with template")
		return 'error'

	# Build merged: dest content outside fences + template's fenced region (incl. both fences).
	managed_region = src_lines[src_start:src_end + 1]
	new_lines = dest_lines[:dest_start] + managed_region + dest_lines[dest_end + 1:]
	merged = '\n'.join(new_lines)

	# Preserve dest's trailing-newline state.
	if dest_text.endswith('\n') and not merged.endswith('\n'):
		merged += '\n'
	elif not dest_text.endswith('\n') and merged.endswith('\n'):
		merged = merged.rstrip('\n')

	if merged == dest_text:
		propagate.console.log_action("no change", dest, counters)
		return 'unchanged'

	write_text(dest, merged, dry_run, action='merge')
	if not dry_run:
		propagate.console.log_action("merge", dest)
		counters['merged_count'] += 1
	return 'merged'


#============================================
def merge_conftest(source_file: str, dest_file: str) -> str | None:
	"""
	Inject the canonical collect_ignore block into a destination conftest.py.

	Source is canonical for the collect_ignore line; any other consumer content
	(imports, fixtures, etc.) is preserved. Returns merged text when an update
	is needed, or None when no change is needed.

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
def merge_gitignore_blocks(repo_dir: str, repo_type: str, template_root: str, context: 'propagate.model.PropagateContext', counters: dict | None = None) -> None:
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
		display_path = propagate.model.format_path_pair(gitignore_path, gitignore_path, repo_dir, context)
		if context.dry_run:
			propagate.console.log_action("create", display_path, dry_run=True)
		else:
			with open(gitignore_path, 'w', encoding='utf-8') as f:
				f.write(content)
			propagate.console.log_action("create", display_path)
			if counters is not None:
				counters['created_count'] += 1
	elif content != existing_content:
		display_path = propagate.model.format_path_pair(gitignore_path, gitignore_path, repo_dir, context)
		if context.dry_run:
			propagate.console.log_action("update", display_path, dry_run=True)
		else:
			with open(gitignore_path, 'w', encoding='utf-8') as f:
				f.write(content)
			propagate.console.log_action("update", display_path)
			if counters is not None:
				counters['merged_count'] += 1


#============================================
def ensure_git_perms(repo_dir: str, dry_run: bool) -> bool:
	"""
	Make .git group-writable so Git can create .git/index.lock and update the index.

	Note: This only helps if the user is in the repo group.
	"""
	import stat

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
			propagate.console.log_action("create", path, dry_run=True)
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
def load_deprecation_list(rel_path: str, template_root: str) -> list[str]:
	"""Read newline-delimited deprecation entries from meta/propagation/.

	Skips blank lines and comment lines (those starting with '#').
	Raises FileNotFoundError if the file is missing; loud failure beats
	silent missing-deprecation scrub.
	"""
	full_path = os.path.join(template_root, rel_path)
	with open(full_path) as f:
		return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith('#')]


#============================================
# Module-level constants for testing
#============================================
def _get_template_root() -> str:
	"""Compute template root directory lazily."""
	return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_deprecated_test_scripts() -> list[str]:
	"""Load deprecated test scripts list lazily."""
	return load_deprecation_list('meta/propagation/deprecated_tests.txt', _get_template_root())


def _get_deprecated_gitignore_entries() -> list[str]:
	"""Load deprecated gitignore entries list lazily."""
	return load_deprecation_list('meta/propagation/deprecated_gitignore.txt', _get_template_root())


# Lazy-loaded module-level exports for test access
TEMPLATE_ROOT = None
DEPRECATED_TEST_SCRIPTS = None
DEPRECATED_GITIGNORE_ENTRIES = None


def _init_module_constants() -> None:
	"""Initialize module-level constants once on first access."""
	global TEMPLATE_ROOT, DEPRECATED_TEST_SCRIPTS, DEPRECATED_GITIGNORE_ENTRIES
	if TEMPLATE_ROOT is not None:
		return  # Already initialized
	TEMPLATE_ROOT = _get_template_root()
	DEPRECATED_TEST_SCRIPTS = _get_deprecated_test_scripts()
	DEPRECATED_GITIGNORE_ENTRIES = _get_deprecated_gitignore_entries()


# Initialize on first import
_init_module_constants()


#============================================
def resolve_spec_for_type(repo_type: str, template_root: str = None, counters: dict | None = None, repo_dir: str | None = None) -> dict:
	"""
	Return the five-bucket propagation spec for the given repo_type.
	Uses compute_propagation_plan with template_root (defaults to script directory).
	"""
	if repo_type not in ('universal', 'python', 'typescript', 'rust', 'other', 'unknown'):
		raise ValueError(f"unknown repo type {repo_type!r}")
	if template_root is None:
		template_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	if repo_type == 'universal':
		repo_type = 'python'  # 'universal' is an alias for python in the fold scheme
	return compute_propagation_plan(template_root, repo_type, counters=counters, repo_dir=repo_dir)


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
		# Filter walk dirs in-place to skip unwanted directories
		dirs[:] = [d for d in dirs if d not in propagate.model.SKIP_WALK_DIRS and not d.startswith('.')]

		for name in files:
			if not (name.startswith('test_') and (name.endswith('.py') or name.endswith('.mjs'))):
				continue
			# Exclude template-meta tests (propagate/reset_repo/detect_repo_type self-tests)
			if any(name.startswith(p) for p in propagate.model.META_TEST_PREFIXES):
				continue
			rel_path = os.path.relpath(os.path.join(root, name), test_dir)
			# Prepend 'tests/' to make it an absolute path from template_root
			full_rel_path = os.path.join('tests', rel_path)
			if full_rel_path not in spec_test_files and full_rel_path not in discovered:
				discovered.append(full_rel_path)

	return discovered


#============================================
def compute_propagation_plan(template_root: str, repo_type: str, counters: dict | None = None, repo_dir: str | None = None) -> dict:
	"""
	Compute the five-bucket propagation plan by walking the filesystem.

	Walks template_root and returns a dict with:
	- 'overwrite_files': repo-root-relative paths that overwrite at consumer
	- 'noexist_files': repo-root-relative paths that ship only when missing
	- 'devel_files': bare filenames under devel/ at consumer
	- 'test_files': paths under tests/ at consumer
	- 'gitignore_block': pattern lines for .gitignore

	Args:
		template_root (str): Root directory of template files to scan.
		repo_type (str): Repository type (python, typescript, rust, other, unknown).
		counters (dict | None): Optional counter dict for progress tracking.
		repo_dir (str | None): Optional repository directory for requirement checks.
			Falls back to template_root for requirement predicate evaluation.

	Precedence (apply in this order; earlier rules win on conflict):
	  1. META_FILES / META_DIRS              -> never ship (drop from all buckets)
	  2. ROUTING_OVERRIDES (via should_ship_override) -> language/requirement-based rules
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
	- ROUTING_OVERRIDES (via should_ship_override) applies to routing decisions
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
		'merge_files': [],
		'devel_files': [],
		'test_files': [],
		'gitignore_block': [],
	}

	# Default repo_dir to template_root if not provided (for requirement checks)
	if repo_dir is None:
		repo_dir = template_root

	# Helper: check if a path is under a meta directory
	def is_in_meta_dir(rel_path: str) -> bool:
		parts = rel_path.split(os.sep)
		for part in parts:
			if part in propagate.model.META_DIRS:
				return True
		return False

	# 1. Walk universal files at template root
	if repo_type in ('python', 'other', 'typescript', 'rust', 'unknown'):
		for root, dirs, files in os.walk(template_root, topdown=True, followlinks=False):
			# Skip directories: meta, templates (we walk it separately)
			dirs[:] = [d for d in dirs if d not in propagate.model.META_DIRS]

			rel_root = os.path.relpath(root, template_root)
			if rel_root == '.':
				rel_root = ''

			# Process files in this directory
			for name in files:
				if name.startswith('.'):
					continue

				file_rel = os.path.join(rel_root, name) if rel_root else name

				# Skip META_FILES (matches by full rel-path OR bare basename for
				# entries that may appear at any depth). docs/active_plans and
				# docs/archive are caught by is_in_meta_dir().
				if file_rel in propagate.model.META_FILES or name in propagate.model.META_FILES:
					continue

				# Skip if under a meta directory
				if is_in_meta_dir(file_rel):
					continue

				# Apply routing overrides (language and requirement-based gates)
				override = should_ship_override(file_rel, repo_type, repo_dir)
				if override is False:
					continue

				# Check for override bucket assignment (e.g., pip_requirements -> noexist)
				rule = propagate.model.ROUTING_OVERRIDES.get(file_rel)
				if rule is not None and 'bucket' in rule:
					bucket_name = rule['bucket'] + '_files'
					if file_rel not in plan[bucket_name]:
						assert_not_meta(file_rel)
						plan[bucket_name].append(file_rel)
					continue

				# Route by prefix/location
				if file_rel.startswith('docs/'):
					assert_not_meta(file_rel)
					plan['overwrite_files'].append(file_rel)
				elif file_rel.startswith('devel/'):
					bare_name = os.path.basename(file_rel)
					if bare_name not in plan['devel_files']:
						assert_not_meta(bare_name)
						plan['devel_files'].append(bare_name)
				elif file_rel.startswith('tests/'):
					bare_name = os.path.basename(file_rel)
					# Skip template-meta test prefixes
					if any(bare_name.startswith(p) for p in propagate.model.META_TEST_PREFIXES):
						continue
					# Include test files and helpers
					if (bare_name.startswith('test_') and (bare_name.endswith('.py') or bare_name.endswith('.mjs'))) or \
						bare_name in ('TESTS_README.md',) or \
						bare_name.startswith(('check_', 'fix_')) or \
						bare_name in ('git_file_utils.py',):
						if file_rel not in plan['test_files']:
							assert_not_meta(file_rel)
							plan['test_files'].append(file_rel)
				elif file_rel in propagate.model.ROOT_PROPAGATE_ALLOWLIST:
					assert_not_meta(file_rel)
					plan['overwrite_files'].append(file_rel)



	# 2. Walk typed overlay under templates/<repo_type>/
	type_overlay_root = os.path.join(template_root, 'templates', repo_type)
	if os.path.isdir(type_overlay_root):
		for root, dirs, files in os.walk(type_overlay_root, topdown=True, followlinks=False):
			dirs[:] = [d for d in dirs if d not in propagate.model.SKIP_WALK_DIRS and not d.startswith('.')]

			rel_root = os.path.relpath(root, type_overlay_root)
			if rel_root == '.':
				rel_root = ''

			for name in files:
				# Ship every file under the typed overlay; META filter below handles exclusions.
				# No .gitkeep filter needed -- the repo deliberately holds zero .gitkeep files
				# (verified via `find templates -name '.gitkeep'`); add one back here only if
				# .gitkeep placeholders are reintroduced.
				file_rel = os.path.join(rel_root, name) if rel_root else name

				# META guard: typed overlays must filter template-internal files so a stray
				# templates/<type>/README.md (or any META name) cannot ship to consumers.
				if name in propagate.model.META_FILES or file_rel in propagate.model.META_FILES:
					continue
				if is_in_meta_dir(file_rel):
					continue

				# Route by subdirectory
				if file_rel.startswith('noexist/'):
					# Strip 'noexist/' prefix for the consumer path
					consumer_path = file_rel[8:]  # len('noexist/') = 8
					# META filter on consumer_path so a typed-noexist entry whose
					# stripped path collides with a META name cannot ship.
					if not consumer_path:
						continue
					consumer_basename = os.path.basename(consumer_path)
					if consumer_path in propagate.model.META_FILES or consumer_basename in propagate.model.META_FILES:
						continue
					if is_in_meta_dir(consumer_path):
						continue
					if consumer_path not in plan['noexist_files']:
						assert_not_meta(consumer_path)
						plan['noexist_files'].append(consumer_path)
				elif file_rel.startswith('devel/'):
					bare_name = os.path.basename(file_rel)
					if bare_name not in plan['devel_files']:
						assert_not_meta(bare_name)
						plan['devel_files'].append(bare_name)
				elif file_rel.startswith('tests/'):
					if file_rel not in plan['test_files']:
						assert_not_meta(file_rel)
						plan['test_files'].append(file_rel)
				elif name.startswith('gitignore.'):
					# Skip; will be loaded separately
					pass
				else:
					# Top-level files in templates/<type>/
					# rule 5: typed overlay shadows universal
					if file_rel in plan['overwrite_files']:
						plan['overwrite_files'].remove(file_rel)
					assert_not_meta(file_rel)
					plan['overwrite_files'].append(file_rel)

	# 3. Load gitignore blocks from files
	gitignore_block = []

	# Load universal gitignore block
	universal_gitignore_path = os.path.join(template_root, 'templates', 'gitignore.universal')
	gitignore_block.extend(load_gitignore_block(universal_gitignore_path))

	# Load typed gitignore block
	typed_gitignore_path = os.path.join(template_root, 'templates', repo_type, f'gitignore.{repo_type}')
	gitignore_block.extend(load_gitignore_block(typed_gitignore_path))

	# Deduplicate gitignore block
	plan['gitignore_block'] = list(dict.fromkeys(gitignore_block))

	# 4. Apply UNIVERSAL_NOEXIST overrides
	# Any path in UNIVERSAL_NOEXIST must move from overwrite/test buckets to noexist.
	# Covers tests/TESTS_README.md, which the tests-walker routes to test_files by default.
	for path in propagate.model.UNIVERSAL_NOEXIST:
		if path in plan['overwrite_files']:
			plan['overwrite_files'].remove(path)
		if path in plan['test_files']:
			plan['test_files'].remove(path)
		if path not in plan['noexist_files']:
			plan['noexist_files'].append(path)

	# 5. Apply typed noexist overrides (rule 4: typed noexist shadows typed overwrite)
	# Any path in plan['noexist_files'] that is also in plan['overwrite_files'] must be removed from overwrite
	for path in list(plan['noexist_files']):
		if path in plan['overwrite_files']:
			plan['overwrite_files'].remove(path)

	# 6. Apply MERGE_FILES routing. MERGE wins over OVERWRITE and NOEXIST for the same path.
	# META still wins over MERGE: assert_not_meta() fails loud if a MERGE-tagged file is META.
	for path in propagate.model.MERGE_FILES:
		if path in plan['overwrite_files']:
			plan['overwrite_files'].remove(path)
		if path in plan['noexist_files']:
			plan['noexist_files'].remove(path)
		if path not in plan['merge_files']:
			assert_not_meta(path)
			plan['merge_files'].append(path)

	return plan
