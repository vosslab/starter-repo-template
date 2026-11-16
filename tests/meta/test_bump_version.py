# Standard Library
import sys
import pathlib
import importlib.util
import json

# PIP3 modules
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


#============================================
def load_bump_version() -> object:
	"""Load the standalone devel command as direct execution would.

	The command intentionally uses permitted flat sibling imports. Keep the
	temporary import path and sibling module cache scoped to this load so this
	test cannot change later tests' import resolution.
	"""
	# ASVS 5.3.2: this path is fixed by the repository-owned test location.
	devel_dir = REPO_ROOT / "devel"
	script_path = devel_dir / "bump_version.py"
	previous_modules = {
		name: sys.modules.pop(name, None)
		for name in ("version_lib", "version_files")
	}
	sys.path.insert(0, str(devel_dir))
	try:
		spec = importlib.util.spec_from_file_location(
			"test_bump_version_module", script_path,
		)
		if spec is None or spec.loader is None:
			raise RuntimeError(f"Cannot load trusted test script: {script_path}")
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
	finally:
		sys.path.pop(0)
		for name in ("version_lib", "version_files"):
			sys.modules.pop(name, None)
		for name, previous_module in previous_modules.items():
			if previous_module is not None:
				sys.modules[name] = previous_module
	return module


BUMP_VERSION = load_bump_version()


#============================================
def test_patch_updates_repo_and_cargo_versions(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The patch action recognizes equivalent repo and Cargo versions."""
	cargo_toml = tmp_path / "Cargo.toml"
	version_file = tmp_path / "VERSION"
	cargo_toml.write_text(
		'[package]\nname = "demo"\nversion = "26.8.0"\nedition = "2024"\n',
		encoding="utf-8",
	)
	version_file.write_text("26.08\n", encoding="utf-8")
	monkeypatch.setattr(
		sys,
		"argv",
		[
			"bump_version.py",
			"patch",
			"--apply",
			"--base-dir",
			str(tmp_path),
		],
	)

	BUMP_VERSION.main()

	assert version_file.read_text(encoding="utf-8") == "26.08.1\n"
	assert 'version = "26.8.1"' in cargo_toml.read_text(encoding="utf-8")


#============================================
def test_set_version_synchronizes_rust_versions(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An explicit CalVer synchronizes repo and Cargo representations."""
	cargo_toml = tmp_path / "Cargo.toml"
	cargo_lock = tmp_path / "Cargo.lock"
	version_file = tmp_path / "VERSION"
	cargo_toml.write_text(
		'[package]\nname = "demo"\nversion = "26.5.0"\nedition = "2024"\n',
		encoding="utf-8",
	)
	cargo_lock.write_text(
		'version = 4\n\n'
		'[[package]]\n'
		'name = "demo"\n'
		'version = "26.5.0"\n\n'
		'[[package]]\n'
		'name = "dependency"\n'
		'version = "1.2.3"\n',
		encoding="utf-8",
	)
	version_file.write_text("26.06\n", encoding="utf-8")
	monkeypatch.setattr(
		sys,
		"argv",
		[
			"bump_version.py",
			"-A",
			"--set-version",
			"26.07",
			"--base-dir",
			str(tmp_path),
		],
	)

	BUMP_VERSION.main()

	cargo_outputs = (
		cargo_toml.read_text(encoding="utf-8"),
		cargo_lock.read_text(encoding="utf-8"),
	)
	assert cargo_outputs == (
		'[package]\nname = "demo"\nversion = "26.7.0"\nedition = "2024"\n',
		'version = 4\n\n'
		'[[package]]\n'
		'name = "demo"\n'
		'version = "26.7.0"\n\n'
		'[[package]]\n'
		'name = "dependency"\n'
		'version = "1.2.3"\n',
	)
	assert version_file.read_text(encoding="utf-8") == "26.07\n"


#============================================
def test_set_version_updates_workspace_package_only(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Workspace members inheriting a version keep version.workspace = true."""
	workspace_toml = tmp_path / "Cargo.toml"
	cargo_lock = tmp_path / "Cargo.lock"
	member_dir = tmp_path / "crates" / "demo"
	member_dir.mkdir(parents=True)
	member_toml = member_dir / "Cargo.toml"
	workspace_toml.write_text(
		'[workspace]\nmembers = ["crates/demo"]\n\n'
		'[workspace.package]\nversion = "26.5.0"\nedition = "2024"\n',
		encoding="utf-8",
	)
	member_toml.write_text(
		'[package]\nname = "demo"\nversion.workspace = true\n',
		encoding="utf-8",
	)
	cargo_lock.write_text(
		'version = 4\n\n'
		'[[package]]\n'
		'name = "demo"\n'
		'version = "26.5.0"\n',
		encoding="utf-8",
	)
	monkeypatch.setattr(
		sys,
		"argv",
		[
			"bump_version.py",
			"-A",
			"--set-version",
			"26.07",
			"--base-dir",
			str(tmp_path),
		],
	)

	BUMP_VERSION.main()

	workspace_outputs = (
		workspace_toml.read_text(encoding="utf-8"),
		cargo_lock.read_text(encoding="utf-8"),
	)
	assert workspace_outputs == (
		'[workspace]\nmembers = ["crates/demo"]\n\n'
		'[workspace.package]\nversion = "26.7.0"\nedition = "2024"\n',
		'version = 4\n\n'
		'[[package]]\n'
		'name = "demo"\n'
		'version = "26.7.0"\n',
	)
	assert member_toml.read_text(encoding="utf-8") == (
		'[package]\nname = "demo"\nversion.workspace = true\n'
	)


#============================================
def test_set_version_synchronizes_root_package_metadata(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An explicit version repairs root package and lockfile metadata only."""
	manifest = tmp_path / "package.json"
	lockfile = tmp_path / "package-lock.json"
	manifest.write_text(
		'{\n\t"name": "demo",\n\t"version": "26.5.0",\n\t"private": true\n}\n',
		encoding="utf-8",
	)
	lockfile.write_text(
		'{\n\t"name": "demo",\n\t"version": "26.5.0",\n'
		'\t"lockfileVersion": 3,\n\t"packages": {\n\t\t"": {\n'
		'\t\t\t"name": "demo",\n\t\t\t"version": "0.0.0"\n\t\t},\n'
		'\t\t"node_modules/example": {\n\t\t\t"version": "1.2.3"\n\t\t}\n'
		'\t}\n}\n',
		encoding="utf-8",
	)
	monkeypatch.setattr(
		sys,
		"argv",
		[
			"bump_version.py", "-A", "--set-version", "26.07",
			"--base-dir", str(tmp_path),
		],
	)

	BUMP_VERSION.main()

	assert '"version": "26.7.0"' in manifest.read_text(encoding="utf-8")
	lock_text = lockfile.read_text(encoding="utf-8")
	assert lock_text.count('"version": "26.7.0"') == 2
	assert '"node_modules/example": {\n\t\t\t"version": "1.2.3"' in lock_text


#============================================
def test_nested_package_manifest_is_not_a_version_source(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Only the selected repository root package manifest is synchronized."""
	(tmp_path / "package.json").write_text(
		'{"name": "root", "version": "26.5.0"}\n', encoding="utf-8",
	)
	nested_dir = tmp_path / "wasm"
	nested_dir.mkdir()
	nested = nested_dir / "package.json"
	nested.write_text(
		'{"name": "wasm", "version": "1.0.0"}\n', encoding="utf-8",
	)
	monkeypatch.setattr(
		sys,
		"argv",
		[
			"bump_version.py", "-A", "--set-version", "26.07",
			"--base-dir", str(tmp_path),
		],
	)

	BUMP_VERSION.main()

	assert json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))["version"] == "26.7.0"
	assert nested.read_text(encoding="utf-8") == '{"name": "wasm", "version": "1.0.0"}\n'


#============================================
def test_set_version_repairs_stale_lock_root_metadata(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An explicit current version still repairs stale root lock metadata."""
	(tmp_path / "package.json").write_text(
		'{"name":"demo","version":"26.7.0"}\n', encoding="utf-8",
	)
	lockfile = tmp_path / "package-lock.json"
	lockfile.write_text(
		'{"name":"demo","version":"26.7.0","packages":{"":{"version":"0.0.0"}}}\n',
		encoding="utf-8",
	)
	monkeypatch.setattr(
		sys,
		"argv",
		[
			"bump_version.py", "-A", "--set-version", "26.07",
			"--base-dir", str(tmp_path),
		],
	)

	BUMP_VERSION.main()

	assert lockfile.read_text(encoding="utf-8") == (
		'{"name":"demo","version":"26.7.0","packages":{"":{"version":"26.7.0"}}}\n'
	)


#============================================
def test_set_version_supports_lockfile_root_metadata_without_top_version(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A valid lockfile can derive its project version from packages[\"\"]."""
	(tmp_path / "package.json").write_text(
		'{"name":"demo","version":"26.5.0"}\n', encoding="utf-8",
	)
	lockfile = tmp_path / "package-lock.json"
	lockfile.write_text(
		'{"name":"demo","lockfileVersion":3,"packages":{"":{"version":"26.5.0"}}}\n',
		encoding="utf-8",
	)
	monkeypatch.setattr(
		sys,
		"argv",
		[
			"bump_version.py", "-A", "--set-version", "26.07",
			"--base-dir", str(tmp_path),
		],
	)

	BUMP_VERSION.main()

	assert '"version":"26.7.0"' in lockfile.read_text(encoding="utf-8")
