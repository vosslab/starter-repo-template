"""Regression: compute_propagation_plan output matches former TYPED_SPEC behavior."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import propagate_style_guides


def test_python_plan_matches_legacy():
	"""Python type plan matches legacy TYPED_SPEC."""
	template_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
	plan = propagate_style_guides.compute_propagation_plan(template_root, 'python')

	# Expected universal files
	expected_universal_overwrite = {
		'docs/REPO_STYLE.md',
		'docs/MARKDOWN_STYLE.md',
		'docs/CLAUDE_HOOK_USAGE_GUIDE.md',
		'docs/PYTEST_STYLE.md',
		'docs/E2E_TESTS.md',
		'CLAUDE.md',
	}
	# Python-specific
	expected_python_overwrite = {
		'docs/PYTHON_STYLE.md',
	}
	expected_overwrite = expected_universal_overwrite | expected_python_overwrite

	expected_universal_noexist = {
		'docs/AUTHORS.md',
		'AGENTS.md',
		'source_me.sh',
	}
	expected_noexist = expected_universal_noexist | {
		'pip_requirements-dev.txt',
		'pip_requirements.txt',
	}

	expected_universal_devel = {'commit_changelog.py'}
	expected_python_devel = {'submit_to_pypi.py'}
	expected_devel = expected_universal_devel | expected_python_devel

	# Check overwrite_files
	for expected in expected_overwrite:
		assert expected in plan['overwrite_files'], f"Missing {expected} in overwrite_files"

	# Check noexist_files
	for expected in expected_noexist:
		assert expected in plan['noexist_files'], f"Missing {expected} in noexist_files"

	# Check devel_files
	for expected in expected_devel:
		assert expected in plan['devel_files'], f"Missing {expected} in devel_files"


def test_typescript_plan_matches_legacy():
	"""TypeScript type plan matches legacy TYPED_SPEC."""
	template_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
	plan = propagate_style_guides.compute_propagation_plan(template_root, 'typescript')

	expected_universal_overwrite = {
		'docs/REPO_STYLE.md',
		'docs/MARKDOWN_STYLE.md',
		'docs/CLAUDE_HOOK_USAGE_GUIDE.md',
		'docs/PYTEST_STYLE.md',
		'docs/E2E_TESTS.md',
		'CLAUDE.md',
	}
	expected_ts_overwrite = {
		'docs/TYPESCRIPT_STYLE.md',
		'docs/PLAYWRIGHT_USAGE.md',
		'tsconfig.json',
		'eslint.config.js',
		'build_github_pages.sh',
		'run_web_server.sh',
		'check_codebase.sh',
		'dist_clean.sh',
	}
	expected_overwrite = expected_universal_overwrite | expected_ts_overwrite

	expected_universal_noexist = {
		'docs/AUTHORS.md',
		'AGENTS.md',
		'source_me.sh',
	}
	expected_ts_noexist = {'package.json.template'}
	expected_noexist = expected_universal_noexist | expected_ts_noexist

	expected_universal_devel = {'commit_changelog.py'}
	expected_ts_devel = {'setup_playwright.sh'}
	expected_devel = expected_universal_devel | expected_ts_devel

	expected_universal_test = {'tests/TESTS_README.md'}
	expected_test = expected_universal_test

	# Check overwrite_files
	for expected in expected_overwrite:
		assert expected in plan['overwrite_files'], f"Missing {expected} in overwrite_files"

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
	plan = propagate_style_guides.compute_propagation_plan(template_root, 'rust')

	expected_universal_overwrite = {
		'docs/REPO_STYLE.md',
		'docs/MARKDOWN_STYLE.md',
		'docs/CLAUDE_HOOK_USAGE_GUIDE.md',
		'docs/PYTEST_STYLE.md',
		'docs/E2E_TESTS.md',
		'CLAUDE.md',
	}
	expected_overwrite = expected_universal_overwrite

	expected_universal_noexist = {
		'docs/AUTHORS.md',
		'AGENTS.md',
		'source_me.sh',
	}
	expected_noexist = expected_universal_noexist

	expected_universal_devel = {'commit_changelog.py'}
	expected_devel = expected_universal_devel

	# Check overwrite_files
	for expected in expected_overwrite:
		assert expected in plan['overwrite_files'], f"Missing {expected} in overwrite_files"

	# Check noexist_files
	for expected in expected_noexist:
		assert expected in plan['noexist_files'], f"Missing {expected} in noexist_files"

	# Check devel_files
	for expected in expected_devel:
		assert expected in plan['devel_files'], f"Missing {expected} in devel_files"


def test_other_plan_matches_legacy():
	"""Other type plan matches legacy TYPED_SPEC."""
	template_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
	plan = propagate_style_guides.compute_propagation_plan(template_root, 'other')

	expected_universal_overwrite = {
		'docs/REPO_STYLE.md',
		'docs/MARKDOWN_STYLE.md',
		'docs/CLAUDE_HOOK_USAGE_GUIDE.md',
		'docs/PYTEST_STYLE.md',
		'docs/E2E_TESTS.md',
		'CLAUDE.md',
	}
	# 'other' type gets PYTHON_STYLE.md only (per legacy spec)
	expected_other_overwrite = {'docs/PYTHON_STYLE.md'}
	expected_overwrite = expected_universal_overwrite | expected_other_overwrite

	expected_universal_noexist = {
		'docs/AUTHORS.md',
		'AGENTS.md',
		'source_me.sh',
	}
	expected_noexist = expected_universal_noexist

	expected_universal_devel = {'commit_changelog.py'}
	expected_devel = expected_universal_devel

	# Check overwrite_files
	for expected in expected_overwrite:
		assert expected in plan['overwrite_files'], f"Missing {expected} in overwrite_files"

	# Check noexist_files
	for expected in expected_noexist:
		assert expected in plan['noexist_files'], f"Missing {expected} in noexist_files"

	# Check devel_files
	for expected in expected_devel:
		assert expected in plan['devel_files'], f"Missing {expected} in devel_files"
