"""Tests for precedence rules in compute_propagation_plan."""

import os
import tempfile

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import propagate.model
import propagate.files


def test_meta_file_never_ships_even_if_in_docs():
	"""META_FILES entries have highest precedence and are excluded from plan."""
	with tempfile.TemporaryDirectory() as tmpdir:
		os.makedirs(os.path.join(tmpdir, 'docs'))
		with open(os.path.join(tmpdir, 'docs', 'README.md'), 'w') as f:
			f.write('test')
		plan = propagate.files.compute_propagation_plan(tmpdir, 'python')
		assert 'docs/README.md' not in plan['overwrite_files']
		assert 'docs/README.md' not in plan['noexist_files']


def test_python_lang_file_excluded_from_typescript():
	"""Language-specific files excluded from non-matching type plans."""
	with tempfile.TemporaryDirectory() as tmpdir:
		os.makedirs(os.path.join(tmpdir, 'docs'))
		os.makedirs(os.path.join(tmpdir, 'devel'))
		with open(os.path.join(tmpdir, 'docs', 'PYTHON_STYLE.md'), 'w') as f:
			f.write('test')
		with open(os.path.join(tmpdir, 'devel', 'submit_to_pypi.py'), 'w') as f:
			f.write('test')
		plan_ts = propagate.files.compute_propagation_plan(tmpdir, 'typescript')
		plan_py = propagate.files.compute_propagation_plan(tmpdir, 'python')
		plan_other = propagate.files.compute_propagation_plan(tmpdir, 'other')
		assert 'docs/PYTHON_STYLE.md' not in plan_ts['overwrite_files']
		assert 'docs/PYTHON_STYLE.md' in plan_py['overwrite_files']
		assert 'docs/PYTHON_STYLE.md' not in plan_other['overwrite_files']
		assert 'submit_to_pypi.py' not in plan_other['devel_files']


def test_universal_noexist_overrides_overwrite():
	"""Universal NOEXIST entries override universal OVERWRITE."""
	with tempfile.TemporaryDirectory() as tmpdir:
		with open(os.path.join(tmpdir, 'AGENTS.md'), 'w') as f:
			f.write('test')
		plan = propagate.files.compute_propagation_plan(tmpdir, 'python')
		assert 'AGENTS.md' not in plan['overwrite_files']
		assert 'AGENTS.md' in plan['noexist_files']


def test_typed_noexist_overrides_typed_overwrite():
	"""Type-specific NOEXIST entries override type-specific OVERWRITE."""
	with tempfile.TemporaryDirectory() as tmpdir:
		type_dir = os.path.join(tmpdir, 'templates', 'typescript')
		os.makedirs(type_dir)
		noexist_dir = os.path.join(type_dir, 'noexist')
		os.makedirs(noexist_dir)
		with open(os.path.join(type_dir, 'foo.ts'), 'w') as f:
			f.write('test')
		with open(os.path.join(noexist_dir, 'foo.ts'), 'w') as f:
			f.write('test')
		plan = propagate.files.compute_propagation_plan(tmpdir, 'typescript')
		assert 'foo.ts' not in plan['overwrite_files']
		assert 'foo.ts' in plan['noexist_files']


def test_typed_overlay_shadows_universal_same_destination():
	"""Type-specific files shadow universal files when destination paths collide."""
	with tempfile.TemporaryDirectory() as tmpdir:
		os.makedirs(os.path.join(tmpdir, 'docs'))
		type_dir = os.path.join(tmpdir, 'templates', 'typescript')
		type_docs_dir = os.path.join(type_dir, 'docs')
		os.makedirs(type_docs_dir)
		with open(os.path.join(tmpdir, 'docs', 'FOO.md'), 'w') as f:
			f.write('universal content')
		with open(os.path.join(type_docs_dir, 'FOO.md'), 'w') as f:
			f.write('typed content')
		plan_ts = propagate.files.compute_propagation_plan(tmpdir, 'typescript')
		plan_py = propagate.files.compute_propagation_plan(tmpdir, 'python')
		source_ts = propagate.model.source_path_for_bucket(tmpdir, 'overwrite_files', 'docs/FOO.md', 'typescript')
		source_py = propagate.model.source_path_for_bucket(tmpdir, 'overwrite_files', 'docs/FOO.md', 'python')
		assert 'docs/FOO.md' in plan_ts['overwrite_files']
		assert 'docs/FOO.md' in plan_py['overwrite_files']
		assert 'templates/typescript' in source_ts
		assert 'templates' not in source_py


def test_pip_requirements_not_in_typescript_plan():
	"""Python-specific files excluded from non-Python type plans."""
	with tempfile.TemporaryDirectory() as tmpdir:
		with open(os.path.join(tmpdir, 'pip_requirements.txt'), 'w') as f:
			f.write('test')
		with open(os.path.join(tmpdir, 'pip_requirements-dev.txt'), 'w') as f:
			f.write('test')
		plan = propagate.files.compute_propagation_plan(tmpdir, 'typescript')
		assert 'pip_requirements.txt' not in plan['overwrite_files']
		assert 'pip_requirements.txt' not in plan['noexist_files']
		assert 'pip_requirements-dev.txt' not in plan['overwrite_files']
		assert 'pip_requirements-dev.txt' not in plan['noexist_files']
