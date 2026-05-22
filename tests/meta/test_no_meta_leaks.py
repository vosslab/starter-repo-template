"""META leak detector across every bucket of every repo type plan."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

import propagate.files
import propagate.model

TEMPLATE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_TYPES = ('python', 'typescript', 'rust', 'other', 'unknown')

# Buckets that store repo-relative paths verbatim.
PATH_BUCKETS = ('overwrite_files', 'noexist_files', 'merge_files', 'test_files')
# devel_files stores flat basenames (devel/ prefix dropped).
BASENAME_BUCKETS = ('devel_files',)


def _assert_entry_not_meta(entry: str, bucket_name: str, repo_type: str) -> None:
	"""Per-entry check. Fails the test with a useful message on META leak."""
	basename = os.path.basename(entry)
	assert entry not in propagate.model.META_FILES, (
		f"META leak: {entry!r} (full rel-path) in plan[{bucket_name!r}] for repo_type={repo_type!r}"
	)
	assert basename not in propagate.model.META_FILES, (
		f"META leak: {entry!r} (basename={basename!r}) in plan[{bucket_name!r}] for repo_type={repo_type!r}"
	)
	for part in entry.split(os.sep):
		assert part not in propagate.model.META_DIRS, (
			f"META_DIRS leak: {entry!r} traverses {part!r} in plan[{bucket_name!r}] for repo_type={repo_type!r}"
		)


@pytest.mark.parametrize('repo_type', REPO_TYPES)
def test_no_meta_leak_any_bucket(repo_type: str) -> None:
	"""No plan entry across any bucket may match META_FILES or traverse META_DIRS."""
	plan = propagate.files.compute_propagation_plan(TEMPLATE_ROOT, repo_type)
	for bucket in PATH_BUCKETS + BASENAME_BUCKETS:
		for entry in plan.get(bucket, []):
			_assert_entry_not_meta(entry, bucket, repo_type)


def test_assert_not_meta_helper_raises_on_readme() -> None:
	"""The helper that powers in-code dispatcher checks must fail loud on a known META file."""
	with pytest.raises(RuntimeError):
		propagate.files.assert_not_meta('README.md')


def test_assert_not_meta_helper_raises_on_meta_dir() -> None:
	"""The helper must fail when a path traverses any META_DIRS component."""
	with pytest.raises(RuntimeError):
		propagate.files.assert_not_meta(os.path.join('meta', 'something.py'))


def test_assert_not_meta_helper_accepts_legit_path() -> None:
	"""The helper must not raise on a path the propagator legitimately ships."""
	propagate.files.assert_not_meta('docs/REPO_STYLE.md')
	propagate.files.assert_not_meta('CLAUDE.md')
