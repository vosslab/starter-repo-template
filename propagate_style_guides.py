#!/usr/bin/env python3
"""CLI orchestrator for propagating canonical docs and styles to consumer repos."""

import argparse
import os

import propagate.console
import propagate.files
import propagate.model
import propagate.repo


#============================================
def build_context(args) -> propagate.model.PropagateContext:
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

	source_dir = propagate.repo.resolve_source_dir(base_dir, args.source_dir)
	template_root = propagate.files.normalize_path(source_dir)

	return propagate.model.PropagateContext(
		base_dir=base_dir,
		source_dir=source_dir,
		template_root=template_root,
		repo_name=args.repo_name,
		dry_run=args.dry_run,
		bootstrap=args.bootstrap,
		auto_discover=args.auto_discover,
		fix_permissions=args.fix_permissions,
		write_marker=args.write_marker,
		skip_confirm=args.skip_confirm,
		verbose_paths=args.verbose_paths,
	)


#============================================
def resolve_target_repos(context: propagate.model.PropagateContext) -> list[str]:
	"""
	Resolve target repository list from context.

	Returns a single-element list with the resolved target repo if context.repo_name
	is set, otherwise returns discover_repos(context.base_dir).

	Args:
		context (PropagateContext): Orchestration context with base_dir and repo_name.

	Returns:
		list[str]: List of repository paths to process.
	"""
	if context.repo_name:
		target_repo = propagate.repo.resolve_target_repo(context.base_dir, context.repo_name)
		repos = [target_repo]
	else:
		repos = collect_repo_dirs(context.base_dir, target_repo=None)

	return repos


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
				dirs[:] = [d for d in dirs if d not in propagate.model.SKIP_WALK_DIRS and not d.startswith('.')]

	# Apply skip list: drop repos whose basename is in DEFAULT_REPO_SKIP_NAMES
	repo_dirs = [r for r in repo_dirs if os.path.basename(r) not in propagate.model.DEFAULT_REPO_SKIP_NAMES]

	return sorted(repo_dirs)


#============================================
def remove_deprecated_tests(tests_dir: str, dry_run: bool) -> int:
	"""
	Remove deprecated tests scripts from one repo's tests directory.
	"""
	deprecated_tests = propagate.files.load_deprecation_list(
		'meta/propagation/deprecated_tests.txt',
		os.path.dirname(os.path.abspath(__file__))
	)

	removed = 0
	for deprecated_test_file in deprecated_tests:
		deprecated_test_path = os.path.join(tests_dir, deprecated_test_file)
		if not os.path.isfile(deprecated_test_path):
			continue
		if dry_run:
			propagate.console.log_action("removed", deprecated_test_path, dry_run=True)
		else:
			os.remove(deprecated_test_path)
			propagate.console.log_action("removed", deprecated_test_path)
		removed += 1
	return removed


#============================================
def apply_file_bucket(bucket_name: str, spec: dict, repo_dir: str, repo_type: str, context: propagate.model.PropagateContext, counters: dict) -> tuple:
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

	# Defense in depth: assert no dispatcher entry is META even if the walker
	# was bypassed (plan read from disk, user-supplied paths, etc.).
	for entry in spec.get(bucket_name, []):
		propagate.files.assert_not_meta(entry)

	if bucket_name == 'overwrite_files':
		# ============ OVERWRITE BUCKET ============
		# Overwrite: copy to repo at exact path.
		for file_rel in spec['overwrite_files']:
			source_file = propagate.model.find_source_for_bucket(context.source_dir, 'overwrite_files', file_rel, repo_type)
			if source_file is None:
				counters['errors'] += 1
				propagate.console.log_action("error", f"source missing for {file_rel}")
				continue

			dest_file = os.path.join(repo_dir, file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				propagate.console.log_action("skip", f"self: {dest_file}", counters)
				continue

			# Regular overwrite: use copy_if_changed
			def _format_overwrite_path(s: str, d: str) -> str:
				"""Format path for overwrite bucket with context."""
				return propagate.model.format_path_pair(s, d, repo_dir, context)
			result = propagate.files.copy_if_changed(source_file, dest_file, context.dry_run, counters, action_label='update', format_path=_format_overwrite_path)
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
			source_file = propagate.model.find_source_for_bucket(context.source_dir, 'noexist_files', file_rel, repo_type)
			if source_file is None:
				counters['errors'] += 1
				propagate.console.log_action("error", f"source missing for {file_rel}")
				continue

			dest_file = os.path.join(repo_dir, file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				propagate.console.log_action("skip", f"self: {dest_file}", counters)
				continue

			if file_rel == 'source_me.sh' and propagate.repo.repo_is_on_path(repo_dir):
				propagate.console.log_action("skip", f"path: {dest_file} (repo is already on PATH)", counters)
				continue

			if os.path.exists(dest_file) and not context.bootstrap:
				propagate.console.log_action("skip", f"{dest_file} (exists, use --bootstrap to override)", counters)
				bucket_skips += 1
				continue

			dest_parent = os.path.dirname(dest_file)
			if dest_parent and not os.path.isdir(dest_parent):
				propagate.files.make_dir_safe(dest_parent, context.dry_run)

			formatted_path = propagate.model.format_path_pair(source_file, dest_file, repo_dir, context)
			propagate.files.copy_file_safe(source_file, dest_file, context.dry_run, action='copy', message=formatted_path if context.dry_run else None)
			if not context.dry_run:
				propagate.console.log_action("copy", formatted_path)
				counters['copied_count'] += 1
			bucket_copies += 1

	elif bucket_name == 'devel_files':
		# ============ DEVEL BUCKET ============
		# Devel: copy to repo/devel/<basename>; flat namespace, not subdirectory-preserved.
		for file_rel in spec['devel_files']:
			source_file = propagate.model.find_source_for_bucket(context.source_dir, 'devel_files', file_rel, repo_type)
			if source_file is None:
				counters['errors'] += 1
				propagate.console.log_action("error", f"source missing for devel_files:{file_rel}")
				continue

			dest_file = propagate.model.target_path_for_bucket(repo_dir, 'devel_files', file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				propagate.console.log_action("skip", f"self: {dest_file}", counters)
				continue

			# Use copy_if_changed for standard overwrite semantics
			path_formatter = lambda s, d: propagate.model.format_path_pair(s, d, repo_dir, context)
			result = propagate.files.copy_if_changed(source_file, dest_file, context.dry_run, counters, action_label='update', format_path=path_formatter)
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

	elif bucket_name == 'merge_files':
		# ============ MERGE BUCKET ============
		# Merge: replace template-managed fenced region in consumer file; preserve consumer
		# additions outside the fences. See meta/docs/MERGE_BUCKET_SPEC.md.
		for file_rel in spec['merge_files']:
			# Merge sources live at template_root paths (same lookup shape as overwrite_files).
			source_file = propagate.model.find_source_for_bucket(context.source_dir, 'overwrite_files', file_rel, repo_type)
			if source_file is None:
				counters['errors'] += 1
				propagate.console.log_action("error", f"source missing for merge_files:{file_rel}")
				continue

			dest_file = os.path.join(repo_dir, file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				propagate.console.log_action("skip", f"self: {dest_file}", counters)
				continue

			outcome = propagate.files.merge_file_safe(source_file, dest_file, context.dry_run, counters)
			if outcome == 'merged':
				bucket_updates += 1
			elif outcome == 'created':
				bucket_copies += 1

	elif bucket_name == 'test_files':
		# ============ TEST BUCKET ============
		# Test: copy to tests/<file_rel> preserving tests/ prefix; auto-discovered files merge here.
		for file_rel in spec['test_files']:
			source_file = propagate.model.find_source_for_bucket(context.source_dir, 'test_files', file_rel, repo_type)
			if source_file is None:
				counters['errors'] += 1
				propagate.console.log_action("error", f"source missing for test_files:{file_rel}")
				continue

			dest_file = propagate.model.target_path_for_bucket(repo_dir, 'test_files', file_rel)

			if os.path.abspath(dest_file) == os.path.abspath(source_file):
				propagate.console.log_action("skip", f"self: {dest_file}", counters)
				continue

			# Use copy_if_changed for standard overwrite semantics
			def _format_test_path(s: str, d: str) -> str:
				"""Format path for test bucket with context."""
				return propagate.model.format_path_pair(s, d, repo_dir, context)
			result = propagate.files.copy_if_changed(source_file, dest_file, context.dry_run, counters, action_label='update', format_path=_format_test_path)
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
def parse_args():
	"""Parse CLI flags and return the argparse Namespace."""
	parser = argparse.ArgumentParser(
		description=(
			"Copy shared style/docs/scripts into each repo under ~/nsh/"
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
	parser.set_defaults(dry_run=False, bootstrap=False, fix_permissions=False, auto_discover=True, write_marker=False, skip_confirm=False, verbose_paths=False)
	args = parser.parse_args()
	return args


#============================================
def process_repo(repo_dir: str, context: 'propagate.model.PropagateContext', counters: dict, emit_per_repo_summary: bool = True) -> dict | None:
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
	if not propagate.repo.is_repo_dir(repo_dir):
		return None

	repo_normalized = propagate.files.normalize_path(repo_dir)
	if repo_normalized == context.template_root:
		propagate.console.log_action("skip", f"self: {repo_dir}", counters)
		return None

	single_repo_mode = context.repo_name is not None
	repo_type = propagate.repo.read_repo_type(
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

	spec = propagate.files.resolve_spec_for_type(repo_type, context.source_dir, counters=counters, repo_dir=repo_dir)

	auto_discovered = []
	if context.auto_discover:
		auto_discovered = propagate.files.auto_discover_test_files(context.source_dir, repo_type)
		if auto_discovered:
			counters['auto_discovered_count'] += len(auto_discovered)
			spec['test_files'].extend(auto_discovered)
			# Informational summary, not an action - bypasses log_action so no counter increments.
			propagate.console.CONSOLE.print(f"auto-discovered {len(auto_discovered)} test files: {', '.join(auto_discovered)}")

	if context.fix_permissions:
		# return value intentionally ignored; chmod side-effect is the purpose
		propagate.files.ensure_git_perms(repo_dir, context.dry_run)

	docs_dir = os.path.join(repo_dir, 'docs')
	if not os.path.isdir(docs_dir):
		propagate.files.make_dir_safe(docs_dir, context.dry_run)

	tests_dir = os.path.join(repo_dir, 'tests')
	if propagate.files.ensure_tests_dir(tests_dir, context.dry_run):
		if context.dry_run:
			propagate.console.log_action("create", tests_dir, counters=counters, dry_run=True)

	conftest_path = os.path.join(tests_dir, 'conftest.py')
	source_conftest = os.path.join(context.source_dir, 'tests', 'conftest.py')
	if os.path.abspath(conftest_path) != os.path.abspath(source_conftest):
		merged_conftest = propagate.files.merge_conftest(source_conftest, conftest_path)
		if merged_conftest is not None:
			dest_existed = os.path.isfile(conftest_path)
			action = 'merge' if dest_existed else 'create'
			propagate.files.write_text(conftest_path, merged_conftest, context.dry_run, action=action)
			if not context.dry_run:
				if dest_existed:
					propagate.console.log_action("merge", f"injected collect_ignore into {conftest_path}", counters=counters)
					counters['merged_count'] += 1
				else:
					propagate.console.log_action("create", conftest_path, counters=counters)
					counters['created_count'] += 1

	remove_deprecated_tests(tests_dir, context.dry_run)

	devel_dir = os.path.join(repo_dir, 'devel')
	if not os.path.isdir(devel_dir):
		propagate.files.make_dir_safe(devel_dir, context.dry_run)

	changelog_path = os.path.join(docs_dir, 'CHANGELOG.md')
	if propagate.files.ensure_changelog_file(changelog_path, context.dry_run):
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

	updates, copies, skips = apply_file_bucket('merge_files', spec, repo_dir, repo_type, context, counters)
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
	propagate.files.merge_gitignore_blocks(repo_dir, repo_type, context.source_dir, context, counters=counters)
	gitignore_path = os.path.join(repo_dir, '.gitignore')
	propagate.files.deduplicate_gitignore(gitignore_path, context.dry_run, counters=counters)
	deprecated_tests = propagate.files.load_deprecation_list(
		'meta/propagation/deprecated_gitignore.txt',
		context.source_dir
	)
	removed_deprecated = propagate.files.remove_gitignore_entries(gitignore_path, deprecated_tests, context.dry_run)
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
		propagate.console.CONSOLE.print(f"[bold]{header}[/]")

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
				propagate.console.CONSOLE.print(f"  {name.ljust(col_width)}[bold red]{value}[/]")
			else:
				propagate.console.CONSOLE.print(f"  {name.ljust(col_width)}{value}")

	# Return repo info for summary aggregation
	return {'name': repo_basename, 'type': repo_type}


#============================================
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
def main() -> int:
	"""
	Orchestrate propagation: build context, resolve repos, and process each one.
	"""
	args = parse_args()
	context = build_context(args)
	repos = resolve_target_repos(context)
	counters = propagate.console.init_counters()
	repo_results = []
	# Determine whether to emit per-repo summaries (multi-repo mode only)
	is_single_repo = len(repos) == 1
	for repo_dir in repos:
		result = process_repo(repo_dir, context, counters, emit_per_repo_summary=not is_single_repo)
		if result is not None:
			repo_results.append(result)
	propagate.console.validate_counters(counters)
	propagate.console.print_summary(counters, repo_results=repo_results, dry_run=context.dry_run)

	# Final completion line: success (green) or failure (bold red)
	if counters['errors'] == 0:
		propagate.console.CONSOLE.print("[green]done[/]")
	else:
		propagate.console.CONSOLE.print(f"[bold red]failed ({counters['errors']} errors)[/]")

	exit_code = exit_code_for(counters)
	return exit_code


if __name__ == '__main__':
	raise SystemExit(main())
