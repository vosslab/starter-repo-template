"""Tests that the propagator skips the template repo."""

import os
import sys
import tempfile
import pytest


@pytest.fixture(scope='session')
def repo_root():
	"""Get repo root using subprocess and provide it to all tests."""
	# Use absolute path to this file to determine repo root
	# The test file is in tests/meta/, so go up two directories
	test_file = os.path.abspath(__file__)
	# Go up from tests/meta/test_propagate_self_skip.py to root
	test_dir = os.path.dirname(test_file)  # tests/meta/
	tests_dir = os.path.dirname(test_dir)  # tests/
	root = os.path.dirname(tests_dir)  # repo root
	if not os.path.isdir(os.path.join(root, '.git')):
		raise RuntimeError(f"Repository root not found at {root}")
	return root


#============================================
def test_read_repo_type_missing_returns_unknown(repo_root):
	"""Test that read_repo_type returns LANG_UNKNOWN when marker is missing and detection unavailable/ambiguous.

	LANG_UNKNOWN gates language-specific routing via should_ship_override; universal
	walker-routed files still ship to the consumer.
	"""
	sys.path.insert(0, repo_root)
	from propagate.repo import read_repo_type
	from propagate.model import LANG_UNKNOWN

	with tempfile.TemporaryDirectory() as tmp_path:
		repo_type = read_repo_type(tmp_path)
		assert repo_type == LANG_UNKNOWN, f"Expected {LANG_UNKNOWN!r}, got {repo_type!r}"


#============================================
def test_read_repo_type_unknown_token_raises(repo_root):
	"""Test that read_repo_type raises ValueError for unknown tokens."""
	sys.path.insert(0, repo_root)
	from propagate.repo import read_repo_type

	with tempfile.TemporaryDirectory() as tmp_path:
		marker_path = os.path.join(tmp_path, 'REPO_TYPE')
		with open(marker_path, 'w', encoding='utf-8') as f:
			f.write('garbage\n')

		with pytest.raises(ValueError, match='unknown REPO_TYPE token.*garbage'):
			read_repo_type(tmp_path)


#============================================
def test_propagator_self_skips(repo_root):
	"""Test that propagator skips template root unconditionally."""
	# Import the actual list from the propagator to verify the skip
	sys.path.insert(0, repo_root)
	from propagate.model import DEFAULT_REPO_SKIP_NAMES

	# Verify that the template repo is in the skip list
	# The template repo basename should be in DEFAULT_REPO_SKIP_NAMES
	template_basename = os.path.basename(repo_root)
	assert template_basename in DEFAULT_REPO_SKIP_NAMES, (
		f"Expected template repo '{template_basename}' to be in DEFAULT_REPO_SKIP_NAMES: {DEFAULT_REPO_SKIP_NAMES}"
	)
