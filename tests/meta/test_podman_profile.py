"""Protect opt-in Podman routing and migration of the former universal guard."""

import pathlib

import pytest

import repolib.repo
import repolib.plan
import repolib.model
import repolib.podman_migration
import repolib.process
import repolib.console

ROOT = str(pathlib.Path(__file__).resolve().parents[2])
GUARD = 'tests/test_podman_disk_budget.py'


@pytest.mark.parametrize('marker', list(repolib.model.REPO_TYPE_ORDER)
	+ ['python,podman', 'podman,python', 'unknown'])
def test_podman_routing(marker: str) -> None:
	"""Only explicit Podman consumers (including all) receive the guard."""
	plan = repolib.plan.resolve_spec_for_type(marker, ROOT)
	expected = 'podman' in repolib.model.expand_marker_types(marker)
	assert (GUARD in plan['test_files']) == expected
	assert GUARD not in repolib.plan.auto_discover_test_files(ROOT, marker)
	if expected:
		source = repolib.model.find_source_for_bucket(ROOT, 'test_files', GUARD, marker)
		assert source == str(pathlib.Path(ROOT, 'templates/podman', GUARD))


def test_podman_choices() -> None:
	"""Reset accepts both standalone and combined Podman markers."""
	assert repolib.repo.parse_repo_type_choice('podman') == 'podman'
	assert repolib.repo.parse_repo_type_choice('python,podman') == 'python,podman'


@pytest.mark.parametrize('dry_run', [True, False])
@pytest.mark.parametrize('container_file', [None, 'deploy/compose.yaml', 'Dockerfile',
	'podman-compose.dev.yml', 'staging.Dockerfile', 'Dockerfile_with_OPL',
	'tools/run_ui_review_podman.sh', 'devel/prune_podman.sh', 'podman-local.example.yml',
	'docker-entrypoint.sh'])
def test_guard_migration(tmp_path: pathlib.Path, dry_run: bool,
		container_file: str | None) -> None:
	"""Evidence opts in; its absence removes a recognized guard; previews write nothing."""
	guard = tmp_path / GUARD
	guard.parent.mkdir()
	guard.write_bytes(pathlib.Path(ROOT, 'templates/podman', GUARD).read_bytes())
	marker = tmp_path / 'REPO_TYPE'
	marker.write_text('python\n')
	if container_file:
		path = tmp_path / container_file
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text('')
	new_type, changes = repolib.podman_migration.migrate_podman_guard(
		str(tmp_path), 'python', ROOT, dry_run,
	)
	assert changes == 1
	assert new_type == ('python,podman' if container_file else 'python')
	assert guard.exists() == (dry_run or container_file is not None)
	assert marker.read_text() == ('python,podman\n' if container_file and not dry_run else 'python\n')


def test_modified_guard_preserved_and_generated_evidence_ignored(tmp_path: pathlib.Path) -> None:
	"""No-container migration cannot discard local edits or trust build output."""
	guard = tmp_path / GUARD
	guard.parent.mkdir()
	guard.write_text('# local check\n')
	generated = tmp_path / 'node_modules/pkg/compose.yml'
	generated.parent.mkdir(parents=True)
	generated.write_text('')
	for name in ['OTHER_REPOS/upstream/Dockerfile',
		'docs/MACOS_PODMAN.md', 'skills/podman-expert/SKILL.md',
		'Vendor/Kate/dockerfile.xml']:
		path = tmp_path / name
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text('')
	assert repolib.podman_migration.find_container_file(str(tmp_path)) is None
	result = repolib.podman_migration.migrate_podman_guard(str(tmp_path), 'python', ROOT, False)
	assert result == ('python', 0)
	assert guard.read_text() == '# local check\n'


@pytest.mark.parametrize('dry_run', [True, False])
def test_process_repo_migrates_before_selecting_overlay(tmp_path: pathlib.Path,
		dry_run: bool) -> None:
	"""Propagation uses the migrated marker in this run and reports the change."""
	(tmp_path / '.git').mkdir()
	(tmp_path / 'REPO_TYPE').write_text('python\n')
	(tmp_path / 'compose.yaml').write_text('')
	guard = tmp_path / GUARD
	guard.parent.mkdir()
	guard.write_text('# old guard\n')
	context = repolib.process.build_context_for_repo(str(tmp_path), dry_run, False, True, False)
	result = repolib.process.process_repo(str(tmp_path), context, repolib.console.init_counters())
	assert result == {'name': tmp_path.name, 'type': 'python,podman', 'changed': True}
	expected = '# old guard\n' if dry_run else pathlib.Path(ROOT, 'templates/podman', GUARD).read_text()
	assert guard.read_text() == expected
