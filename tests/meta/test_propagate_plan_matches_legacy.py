"""Regression: compute_propagation_plan output matches former TYPED_SPEC behavior."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import propagate.model
import propagate.files


def test_python_plan_matches_legacy():
	"""Python type plan matches legacy TYPED_SPEC."""
	template_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
	plan = propagate.files.compute_propagation_plan(template_root, 'python')

	# Expected universal files
	expected_universal_overwrite = {
		'docs/REPO_STYLE.md',
		'docs/MARKDOWN_STYLE.md',
		'docs/CLAUDE_HOOK_USAGE_GUIDE.md',
		'docs/PYTEST_STYLE.md',
		'docs/E2E_TESTS.md',
	}
	# Python-specific
	expected_python_overwrite = {
		'docs/PYTHON_STYLE.md',
	}
	expected_overwrite = expected_universal_overwrite | expected_python_overwrite

	expected_merge = {'CLAUDE.md'}

	expected_universal_noexist = {
		'docs/AUTHORS.md',
		'AGENTS.md',
		'source_me.sh',
		'tests/TESTS_README.md',
	}
	expected_noexist = expected_universal_noexist | {
		'pip_requirements-dev.txt',
		'pip_requirements.txt',
	}

	expected_universal_devel = {'commit_changelog.py', 'dist_clean.sh'}
	expected_python_devel = set()  # submit_to_pypi.py requires pyproject.toml at repo_dir
	expected_devel = expected_universal_devel | expected_python_devel

	# Check overwrite_files
	for expected in expected_overwrite:
		assert expected in plan['overwrite_files'], f"Missing {expected} in overwrite_files"

	# Check merge_files
	for expected in expected_merge:
		assert expected in plan['merge_files'], f"Missing {expected} in merge_files"

	# Check noexist_files
	for expected in expected_noexist:
		assert expected in plan['noexist_files'], f"Missing {expected} in noexist_files"

	# Check devel_files
	for expected in expected_devel:
		assert expected in plan['devel_files'], f"Missing {expected} in devel_files"


def test_typescript_plan_matches_legacy():
	"""TypeScript type plan matches legacy TYPED_SPEC."""
	template_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
	plan = propagate.files.compute_propagation_plan(template_root, 'typescript')

	expected_universal_overwrite = {
		'docs/REPO_STYLE.md',
		'docs/MARKDOWN_STYLE.md',
		'docs/CLAUDE_HOOK_USAGE_GUIDE.md',
		'docs/PYTEST_STYLE.md',
		'docs/E2E_TESTS.md',
	}
	expected_ts_overwrite = {
		'docs/TYPESCRIPT_STYLE.md',
		'docs/PLAYWRIGHT_USAGE.md',
		'eslint.config.js',
		'check_codebase.sh',
		'.prettierrc',
		'.prettierignore',
	}
	expected_overwrite = expected_universal_overwrite | expected_ts_overwrite

	expected_merge = {'CLAUDE.md'}

	expected_universal_noexist = {
		'docs/AUTHORS.md',
		'AGENTS.md',
		'source_me.sh',
		'tests/TESTS_README.md',
	}
	expected_ts_noexist = {'package.json', 'build_github_pages.sh', 'run_web_server.sh', 'tsconfig.json', 'tsconfig.lint.json'}
	expected_noexist = expected_universal_noexist | expected_ts_noexist

	expected_universal_devel = {'commit_changelog.py', 'dist_clean.sh'}
	expected_ts_devel = {'setup_playwright.sh'}
	expected_devel = expected_universal_devel | expected_ts_devel

	# tests/TESTS_README.md moved from test_files to noexist_files in M2/2A; no other universal test_files have explicit expectations.
	expected_test = set()

	# Check overwrite_files
	for expected in expected_overwrite:
		assert expected in plan['overwrite_files'], f"Missing {expected} in overwrite_files"

	# Check merge_files
	for expected in expected_merge:
		assert expected in plan['merge_files'], f"Missing {expected} in merge_files"

	# Check noexist_files
	for expected in expected_noexist:
		assert expected in plan['noexist_files'], f"Missing {expected} in noexist_files"

	# Check devel_files
	for expected in expected_devel:
		assert expected in plan['devel_files'], f"Missing {expected} in devel_files"

	# Check test_files
	for expected in expected_test:
		assert expected in plan['test_files'], f"Missing {expected} in test_files"


def test_rust_plan_matches_legacy():
	"""Rust type plan matches legacy TYPED_SPEC."""
	template_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
	plan = propagate.files.compute_propagation_plan(template_root, 'rust')

	expected_universal_overwrite = {
		'docs/REPO_STYLE.md',
		'docs/MARKDOWN_STYLE.md',
		'docs/CLAUDE_HOOK_USAGE_GUIDE.md',
		'docs/PYTEST_STYLE.md',
		'docs/E2E_TESTS.md',
	}
	expected_overwrite = expected_universal_overwrite

	expected_merge = {'CLAUDE.md'}

	expected_universal_noexist = {
		'docs/AUTHORS.md',
		'AGENTS.md',
		'source_me.sh',
		'tests/TESTS_README.md',
	}
	expected_noexist = expected_universal_noexist

	expected_universal_devel = {'commit_changelog.py', 'dist_clean.sh'}
	expected_devel = expected_universal_devel

	# Check overwrite_files
	for expected in expected_overwrite:
		assert expected in plan['overwrite_files'], f"Missing {expected} in overwrite_files"

	# Check merge_files
	for expected in expected_merge:
		assert expected in plan['merge_files'], f"Missing {expected} in merge_files"

	# Check noexist_files
	for expected in expected_noexist:
		assert expected in plan['noexist_files'], f"Missing {expected} in noexist_files"

	# Check devel_files
	for expected in expected_devel:
		assert expected in plan['devel_files'], f"Missing {expected} in devel_files"


def test_other_plan_matches_legacy():
	"""Other type plan matches legacy TYPED_SPEC."""
	template_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
	plan = propagate.files.compute_propagation_plan(template_root, 'other')

	expected_universal_overwrite = {
		'docs/REPO_STYLE.md',
		'docs/MARKDOWN_STYLE.md',
		'docs/CLAUDE_HOOK_USAGE_GUIDE.md',
		'docs/PYTEST_STYLE.md',
		'docs/E2E_TESTS.md',
	}
	# 'other' type no longer gets PYTHON_STYLE.md (language rule is PYTHON, not 'other')
	expected_other_overwrite = set()
	expected_overwrite = expected_universal_overwrite | expected_other_overwrite

	expected_merge = {'CLAUDE.md'}

	expected_universal_noexist = {
		'docs/AUTHORS.md',
		'AGENTS.md',
		'source_me.sh',
		'tests/TESTS_README.md',
	}
	expected_noexist = expected_universal_noexist

	expected_universal_devel = {'commit_changelog.py', 'dist_clean.sh'}
	expected_devel = expected_universal_devel

	# Check overwrite_files
	for expected in expected_overwrite:
		assert expected in plan['overwrite_files'], f"Missing {expected} in overwrite_files"

	# Check merge_files
	for expected in expected_merge:
		assert expected in plan['merge_files'], f"Missing {expected} in merge_files"

	# Check noexist_files
	for expected in expected_noexist:
		assert expected in plan['noexist_files'], f"Missing {expected} in noexist_files"

	# Check devel_files
	for expected in expected_devel:
		assert expected in plan['devel_files'], f"Missing {expected} in devel_files"
