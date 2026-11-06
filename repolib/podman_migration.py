"""Migrate the formerly universal Podman guard during propagation."""

import os
import fnmatch
import hashlib
import pathlib

import repolib.repo
import repolib.model
import repolib.console

# Fingerprint of the formerly universal guard, before its opt-in docstring update.
LEGACY_GUARD_SHA256 = '86e008a2a4203f644427d2a0fb3c5d2a23c08d43b2faf3ee7270f62a2cbf387d'


#============================================
def find_container_file(repo_dir: str) -> str | None:
	"""Find container build, config, or shell-script filenames outside generated trees."""
	patterns = ('Dockerfile*', '*.Dockerfile', 'Containerfile*', '*.Containerfile',
		'compose*.yml', 'compose*.yaml', 'docker-compose*.yml', 'docker-compose*.yaml',
		'podman*.yml', 'podman*.yaml', '*podman*.sh', '*docker*.sh')
	for root, dirs, files in os.walk(repo_dir, followlinks=False):
		dirs[:] = sorted(name for name in dirs if not name.startswith('.')
			and name not in {'node_modules', 'target', 'build', 'dist', 'venv', '__pycache__',
				'OTHER_REPOS'}
			and not os.path.islink(os.path.join(root, name)))
		for name in sorted(files):
			if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns):
				return os.path.relpath(os.path.join(root, name), repo_dir)
	return None


#============================================
def migrate_podman_guard(repo_dir: str, repo_type: str, template_root: str,
		dry_run: bool) -> tuple[str, int]:
	"""Opt existing guards into Podman, or remove recognized stale copies."""
	if 'podman' in repolib.model.expand_marker_types(repo_type):
		return repo_type, 0
	# ASVS 5.3.2: use fixed trusted paths and refuse symlinked removal targets.
	guard = pathlib.Path(repo_dir, 'tests', 'test_podman_disk_budget.py')
	if not guard.is_file() or guard.is_symlink() or guard.parent.is_symlink():
		return repo_type, 0
	evidence = find_container_file(repo_dir)
	if evidence is not None:
		marker_path = pathlib.Path(repo_dir, 'REPO_TYPE')
		marker = 'other' if repo_type == repolib.model.LANG_UNKNOWN else repo_type
		repo_type = f'{marker},podman'
		repolib.console.log_action('update',
			f'{marker_path}: add podman (found {evidence})', dry_run=dry_run)
		repolib.repo.write_repo_type_marker(str(marker_path), repo_type, dry_run=dry_run)
		return repo_type, 1
	canonical = pathlib.Path(template_root, 'templates/podman/tests/test_podman_disk_budget.py')
	content = guard.read_bytes()
	if content != canonical.read_bytes() and hashlib.sha256(content).hexdigest() != LEGACY_GUARD_SHA256:
		repolib.console.log_action('warn', f'{guard}: locally modified; review removal or add podman')
		return repo_type, 0
	repolib.console.log_action('removed', str(guard), dry_run=dry_run)
	if not dry_run:
		guard.unlink()
	return repo_type, 1
