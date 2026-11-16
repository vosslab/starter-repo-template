"""Stable policy checks for the TypeScript dependency manifest updater."""

# Standard Library
import importlib.util
import pathlib
import subprocess

# PIP3 modules
import pytest

# local repo modules
import file_utils

REPO_ROOT = pathlib.Path(file_utils.get_repo_root())


#============================================

def load_updater() -> object:
	"""Load the standalone updater without requiring a package import."""
	script_path = REPO_ROOT / "templates/typescript/devel/sync_typescript_package_pins.py"
	spec = importlib.util.spec_from_file_location("typescript_dependency_updater", script_path)
	if spec is None or spec.loader is None:
		raise RuntimeError(f"Cannot load trusted test script: {script_path}")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


UPDATER = load_updater()


#============================================

def test_refresh_manifest_updates_dependencies_and_nested_overrides() -> None:
	"""Published requirements become current minimums, including override leaves."""
	data = {
		"dependencies": {"direct": "^1.0.0", "alias": "npm:actual@^2.0.0"},
		"devDependencies": {"local": "workspace:*"},
		"overrides": {
			"direct": "^1.0.0",
			"parent@^1": {".": "^3.0.0", "child": "^4.0.0"},
		},
	}
	latest = {"actual": "2.5.0", "child": "4.2.0", "direct": "1.4.0", "parent": "3.1.0"}

	changes = UPDATER.refresh_manifest(data, latest)

	assert data["dependencies"] == {"direct": ">=1.4.0", "alias": "npm:actual@>=2.5.0"}
	assert data["devDependencies"] == {"local": "workspace:*"}
	assert data["overrides"] == {
		"direct": ">=1.4.0",
		"parent@^1": {".": ">=3.1.0", "child": ">=4.2.0"},
	}
	assert len(changes) == 5
	UPDATER.validate_direct_overrides(data)


#============================================

def test_registry_collection_keeps_local_specs_out_of_npm_requests() -> None:
	"""Local and reference requirements are not accidentally treated as registry packages."""
	data = {
		"dependencies": {
			"published": ">=1.0.0",
			"local": "file:../local",
			"reference": "$published",
		},
		"overrides": {"published": "$published", "nested": {"child": "git+https://example.test/a"}},
	}

	packages = UPDATER.collect_registry_packages(data)

	assert packages == ["published"]


#============================================

def test_registry_collection_uses_override_alias_target() -> None:
	"""An override alias queries its actual published package, not its selector key."""
	data = {"overrides": {"compat": "npm:actual-package@^2.0.0"}}

	packages = UPDATER.collect_registry_packages(data)

	assert packages == ["actual-package"]


#============================================

def test_direct_override_mismatch_fails_with_repair_instruction() -> None:
	"""npm's direct-override rule fails before an invalid manifest is written."""
	data = {"dependencies": {"minimatch": ">=11.0.8"}, "overrides": {"minimatch": ">=10.0.0"}}

	with pytest.raises(RuntimeError, match="direct override 'minimatch'"):
		UPDATER.validate_direct_overrides(data)


#============================================

def test_direct_nested_override_allows_matching_reference() -> None:
	"""A root ``.`` override may refer to an equivalent direct requirement."""
	data = {
		"dependencies": {"first": ">=11.0.8", "second": ">=11.0.8"},
		"overrides": {"first": {".": "$second"}},
	}

	UPDATER.validate_direct_overrides(data)


#============================================

def test_selector_reports_path_without_registry_access(tmp_path: pathlib.Path) -> None:
	"""Agent selection returns one absolute manifest path before any npm request."""
	manifest = tmp_path / "package.json"
	manifest.write_text("{}\n", encoding="utf-8")

	selected = UPDATER.select_package_json([str(manifest)], None)

	assert selected == str(manifest)


#============================================

def test_discovery_uses_tracked_manifests_and_ignores_generated_snapshots(
	tmp_path: pathlib.Path,
) -> None:
	"""Only a repository's tracked project manifests become updater candidates."""
	(tmp_path / "wasm").mkdir()
	(tmp_path / "output" / "provenance").mkdir(parents=True)
	(tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
	(tmp_path / "wasm/package.json").write_text("{}\n", encoding="utf-8")
	(tmp_path / "output/provenance/package.json").write_text("{}\n", encoding="utf-8")
	subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
	subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)

	paths = UPDATER.iter_package_jsons(str(tmp_path))

	assert paths == [str(tmp_path / "package.json"), str(tmp_path / "wasm/package.json")]
