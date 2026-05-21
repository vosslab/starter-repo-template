"""
Guardrail test: PYTHON_LANG_FILES must not appear in production code.

This test ensures the deprecated PYTHON_LANG_FILES constant has been
fully removed and replaced with ROUTING_OVERRIDES in WP3.1.
"""

import os
import subprocess
import git_file_utils


def test_python_lang_files_removed_from_production():
	"""
	PYTHON_LANG_FILES must not appear in production code.
	Only changelog history is allowed to mention it.
	"""
	repo_root = git_file_utils.get_repo_root()

	# Get all tracked files
	result = subprocess.run(
		['git', 'ls-files'],
		cwd=repo_root,
		capture_output=True,
		text=True,
		check=True
	)
	tracked = result.stdout.strip().split('\n')

	# Files allowed to mention PYTHON_LANG_FILES (changelog, test file itself, archived docs)
	allowed_substrings = (
		'docs/CHANGELOG',
		'docs/archive',
		'tests/meta/test_python_lang_files_gone.py',
	)

	offenders = []
	for path in tracked:
		if not path.strip():
			continue
		if any(a in path for a in allowed_substrings):
			continue

		full = os.path.join(repo_root, path)
		if not os.path.isfile(full):
			continue

		try:
			with open(full, 'r', encoding='utf-8') as f:
				content = f.read()
		except (UnicodeDecodeError, PermissionError):
			continue

		if 'PYTHON_LANG_FILES' in content:
			offenders.append(path)

	assert not offenders, (
		f"PYTHON_LANG_FILES still referenced in production code: {offenders}. "
		f"Replace with ROUTING_OVERRIDES in propagate/model.py."
	)
