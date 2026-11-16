"""Contract tests for the GitHub Pages template seeds."""

# Standard Library
import pathlib

# PIP3 modules
import yaml

# local repo modules
import file_utils
import repolib.plan


REPO_ROOT = pathlib.Path(file_utils.get_repo_root())
PAGES_ROOT = REPO_ROOT / 'templates' / 'githubpages'


#============================================
def load_yaml(path: pathlib.Path) -> dict:
	"""Load one YAML template mapping."""
	with path.open(encoding='utf-8') as input_file:
		content = yaml.safe_load(input_file)
	return content


#============================================
def test_pages_workflow_installs_builds_and_uploads_artifact() -> None:
	"""The Pages seed installs its lockfile, builds, and publishes dist/."""
	workflow = load_yaml(PAGES_ROOT / 'noexist' / 'deploy-pages.yml')
	steps = workflow['jobs']['build']['steps']
	run_steps = [step['run'] for step in steps if 'run' in step]
	assert 'npm ci --no-audit' in run_steps
	assert './build_github_pages.sh' in run_steps
	upload_step = next(
		step for step in steps
		if step.get('uses', '').startswith('actions/upload-pages-artifact@')
	)
	assert upload_step['with']['path'] == 'dist'
	assert workflow['jobs']['deploy']['needs'] == 'build'
	assert workflow['permissions'] == {'contents': 'read'}
	assert workflow['jobs']['deploy']['permissions'] == {
		'pages': 'write',
		'id-token': 'write',
	}


#============================================
def test_pages_build_uses_installed_tools() -> None:
	"""The Pages build does not download tools outside the committed install."""
	build_text = (PAGES_ROOT / 'noexist' / 'build_github_pages.sh').read_text(encoding='utf-8')
	assert './node_modules/.bin/tsc --noEmit -p tsconfig.json' in build_text
	assert './node_modules/.bin/esbuild "$ENTRY"' in build_text
	assert 'dist/.nojekyll' in build_text


#============================================
def test_pages_seeds_propagate_only_to_pages_repositories() -> None:
	"""Deployment seeds and guidance remain Pages-only files."""
	typescript_plan = repolib.plan.compute_propagation_plan(str(REPO_ROOT), 'typescript')
	pages_plan = repolib.plan.compute_propagation_plan(str(REPO_ROOT), 'githubpages')
	for path_value in ('deploy-pages.yml',):
		assert path_value not in typescript_plan['noexist_files']
		assert path_value in pages_plan['noexist_files']
	assert 'docs/GITHUB_PAGES_STYLE.md' not in typescript_plan['overwrite_files']
	assert 'docs/GITHUB_PAGES_STYLE.md' in pages_plan['overwrite_files']
