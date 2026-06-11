"""Tests for folder-convention propagation routing."""

import os
import tempfile

import repolib.model
import repolib.files


def test_universal_doc_routes_overwrite() -> None:
	"""Docs/ file routes to overwrite_files for all repo types."""
	with tempfile.TemporaryDirectory() as tmpdir:
		os.makedirs(os.path.join(tmpdir, 'docs'))
		with open(os.path.join(tmpdir, 'docs', 'FOO.md'), 'w') as f:
			f.write('test')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'python')
		assert 'docs/FOO.md' in plan['overwrite_files']


def test_meta_file_excluded_basename_form() -> None:
	"""META_FILES entry by basename (e.g. README.md) excludes the file."""
	with tempfile.TemporaryDirectory() as tmpdir:
		with open(os.path.join(tmpdir, 'README.md'), 'w') as f:
			f.write('test')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'python')
		assert 'README.md' not in plan['overwrite_files']


def test_meta_dir_excludes_nested_files() -> None:
	"""Files under meta/ (META_DIRS entry) never ship, regardless of depth."""
	with tempfile.TemporaryDirectory() as tmpdir:
		os.makedirs(os.path.join(tmpdir, 'meta', 'docs'))
		with open(os.path.join(tmpdir, 'meta', 'docs', 'PROPAGATION_RULES.md'), 'w') as f:
			f.write('test')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'python')
		assert 'meta/docs/PROPAGATION_RULES.md' not in plan['overwrite_files']


def test_meta_dir_excludes_tools_nested() -> None:
	"""Files under tools/ (META_DIRS entry) never ship, regardless of file name."""
	with tempfile.TemporaryDirectory() as tmpdir:
		os.makedirs(os.path.join(tmpdir, 'tools'))
		with open(os.path.join(tmpdir, 'tools', 'detect_repo_type.py'), 'w') as f:
			f.write('test')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'python')
		assert 'tools/detect_repo_type.py' not in plan['overwrite_files']


def test_meta_test_prefix_excluded() -> None:
	"""test_propagate_* files excluded."""
	with tempfile.TemporaryDirectory() as tmpdir:
		os.makedirs(os.path.join(tmpdir, 'tests'))
		with open(os.path.join(tmpdir, 'tests', 'test_propagate_x.py'), 'w') as f:
			f.write('test')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'python')
		assert 'test_propagate_x.py' not in plan['test_files']


def test_typescript_overlay_routes_to_overwrite() -> None:
	"""templates/typescript/foo.ts routes to overwrite_files for typescript type."""
	with tempfile.TemporaryDirectory() as tmpdir:
		type_dir = os.path.join(tmpdir, 'templates', 'typescript')
		os.makedirs(type_dir)
		with open(os.path.join(type_dir, 'foo.ts'), 'w') as f:
			f.write('test')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'typescript')
		assert 'foo.ts' in plan['overwrite_files']


def test_typescript_noexist_routes_to_noexist() -> None:
	"""templates/typescript/noexist/package.json routes to noexist_files."""
	with tempfile.TemporaryDirectory() as tmpdir:
		noexist_dir = os.path.join(tmpdir, 'templates', 'typescript', 'noexist')
		os.makedirs(noexist_dir)
		with open(os.path.join(noexist_dir, 'package.json'), 'w') as f:
			f.write('test')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'typescript')
		assert 'package.json' in plan['noexist_files']


def test_python_lang_files_only_for_python() -> None:
	"""docs/PYTHON_STYLE.md only ships to python repos."""
	with tempfile.TemporaryDirectory() as tmpdir:
		os.makedirs(os.path.join(tmpdir, 'docs'))
		with open(os.path.join(tmpdir, 'docs', 'PYTHON_STYLE.md'), 'w') as f:
			f.write('test')
		plan_py = repolib.files.compute_propagation_plan(tmpdir, 'python')
		plan_ts = repolib.files.compute_propagation_plan(tmpdir, 'typescript')
		plan_other = repolib.files.compute_propagation_plan(tmpdir, 'other')
		assert 'docs/PYTHON_STYLE.md' in plan_py['overwrite_files']
		assert 'docs/PYTHON_STYLE.md' not in plan_ts['overwrite_files']
		assert 'docs/PYTHON_STYLE.md' not in plan_other['overwrite_files']


def test_other_gets_python_style_only() -> None:
	"""'other' repo type does not get Python-specific files."""
	with tempfile.TemporaryDirectory() as tmpdir:
		os.makedirs(os.path.join(tmpdir, 'docs'))
		os.makedirs(os.path.join(tmpdir, 'devel'))
		with open(os.path.join(tmpdir, 'docs', 'PYTHON_STYLE.md'), 'w') as f:
			f.write('test')
		with open(os.path.join(tmpdir, 'devel', 'submit_to_pypi.py'), 'w') as f:
			f.write('test')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'other')
		assert 'docs/PYTHON_STYLE.md' not in plan['overwrite_files']
		assert 'submit_to_pypi.py' not in plan['devel_files']


def test_universal_noexist_overrides_overwrite() -> None:
	"""AGENTS.md in UNIVERSAL_NOEXIST moves to noexist_files, not overwrite."""
	with tempfile.TemporaryDirectory() as tmpdir:
		with open(os.path.join(tmpdir, 'AGENTS.md'), 'w') as f:
			f.write('test')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'python')
		assert 'AGENTS.md' not in plan['overwrite_files']
		assert 'AGENTS.md' in plan['noexist_files']


def test_root_file_not_in_allowlist_excluded() -> None:
	"""Root file outside allowlist not in plan."""
	with tempfile.TemporaryDirectory() as tmpdir:
		with open(os.path.join(tmpdir, 'random_root.md'), 'w') as f:
			f.write('test')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'python')
		assert 'random_root.md' not in plan['overwrite_files']


def test_gitignore_blocks_loaded_from_files() -> None:
	"""Gitignore blocks loaded from gitignore.universal and templates/<type>/gitignore.<type>."""
	with tempfile.TemporaryDirectory() as tmpdir:
		# Universal lives under templates/, not at template root
		templates_dir = os.path.join(tmpdir, 'templates')
		os.makedirs(templates_dir)
		with open(os.path.join(templates_dir, 'gitignore.universal'), 'w') as f:
			f.write('report_*.txt\n.DS_Store\n')
		# Typed
		ts_dir = os.path.join(tmpdir, 'templates', 'typescript')
		os.makedirs(ts_dir)
		with open(os.path.join(ts_dir, 'gitignore.typescript'), 'w') as f:
			f.write('node_modules/\ndist/\n')
		plan = repolib.files.compute_propagation_plan(tmpdir, 'typescript')
		assert 'report_*.txt' in plan['gitignore_block']
		assert '.DS_Store' in plan['gitignore_block']
		assert 'node_modules/' in plan['gitignore_block']
		assert 'dist/' in plan['gitignore_block']
