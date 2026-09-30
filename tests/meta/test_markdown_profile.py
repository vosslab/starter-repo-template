"""Protect the small content profile and its combination with code families."""

import pathlib

import pytest

import repolib.model
import repolib.plan
import test_markdown_links

ROOT = str(pathlib.Path(__file__).resolve().parents[2])


#============================================
def test_markdown_profile_stays_small() -> None:
	"""Extra code tooling is a profile regression; fix routing, not consumers."""
	plan = repolib.plan.resolve_spec_for_type('markdown', ROOT)
	assert {path for path in plan['test_files'] if '/test_' in path} == {
		'tests/test_markdown_links.py', 'tests/test_ascii_compliance.py',
		'tests/test_whitespace.py',
	}
	assert plan['devel_files'] == []
	assert {'docs/REPO_STYLE.md', 'docs/MARKDOWN_STYLE.md'} <= set(plan['overwrite_files'])
	assert repolib.plan.auto_discover_test_files(ROOT, 'markdown') == []


#============================================
@pytest.mark.parametrize('marker', ['markdown,python', 'python,markdown'])
def test_mixed_profile_retains_python_tooling(marker: str) -> None:
	"""Adding markdown must not shrink Python dependencies or agent guidance."""
	plan = repolib.plan.resolve_spec_for_type(marker, ROOT)
	assert 'docs/PYTHON_STYLE.md' in plan['overwrite_files']
	assert 'tests/test_pyflakes_code_lint.py' in plan['test_files']
	source = repolib.model.find_source_for_bucket(
		ROOT, 'overwrite_files', 'pip_requirements-dev.txt', marker,
	)
	assert source == str(pathlib.Path(ROOT) / 'pip_requirements-dev.txt')


#============================================
def test_djot_local_links_include_references_and_ignore_code(tmp_path: pathlib.Path) -> None:
	"""A broken Djot image/reference must fail just like a broken inline link."""
	(tmp_path / 'lesson.djot').write_text(
		'[chapter](chapter.djot)\n![figure][plot]\n\n[plot]: missing.svg\n'
		'\n```\n[example](ignored.djot)\n```\n', encoding='utf-8',
	)
	issues = test_markdown_links.scan_file(
		str(tmp_path), {'lesson.djot', 'chapter.djot'}, set(), set(), 'lesson.djot',
	)
	assert issues and all('missing.svg' in issue for issue in issues)
