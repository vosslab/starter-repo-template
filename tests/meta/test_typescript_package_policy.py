"""Regression checks for the propagated TypeScript package policy helper."""

# Standard Library
import importlib.util
import json
import pathlib

import pytest

import file_utils

REPO_ROOT = pathlib.Path(file_utils.get_repo_root())
CHECKER_PATH = REPO_ROOT / "templates" / "typescript" / "devel" / "check_typescript_package_policy.py"
SPEC = importlib.util.spec_from_file_location("typescript_package_policy", CHECKER_PATH)
PACKAGE_POLICY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PACKAGE_POLICY)


#============================================
def write_manifest(tmp_path: pathlib.Path, data: dict) -> pathlib.Path:
	"""Write one temporary package manifest."""
	path = tmp_path / "package.json"
	path.write_text(json.dumps(data), encoding="utf-8")
	return path


#============================================
def test_open_specs_aliases_and_local_dependencies_pass(tmp_path: pathlib.Path) -> None:
	"""Latest floors, aliases, and local package relationships are intentional."""
	path = write_manifest(tmp_path, {
		"dependencies": {
			"current": ">=1.0.0",
			"alias": "npm:current@>=1.0.0",
			"local": "workspace:*",
		},
		"overrides": {"parent@1": {".": ">=2.0.0", "child": ">=3.0.0"}},
	})
	assert PACKAGE_POLICY.check_manifest(str(path)) == []


#============================================
def test_pinned_specs_and_misaligned_direct_override_fail(tmp_path: pathlib.Path) -> None:
	"""The offline policy catches closed ranges and npm EOVERRIDE hazards."""
	path = write_manifest(tmp_path, {
		"dependencies": {"current": "^1.0.0"},
		"overrides": {"current": ">=2.0.0"},
	})
	violations = PACKAGE_POLICY.check_manifest(str(path))
	assert len(violations) == 2
	assert "not an open >= requirement" in violations[0]
	assert "must equal its dependency requirement" in violations[1]


#============================================
def test_alias_and_missing_override_reference_are_checked(tmp_path: pathlib.Path) -> None:
	"""Aliases retain their target range and references must name direct requirements."""
	path = write_manifest(tmp_path, {
		"dependencies": {"alias": "npm:current@^1.0.0"},
		"overrides": {"nested": {"child": "$missing"}},
	})
	violations = PACKAGE_POLICY.check_manifest(str(path))
	assert len(violations) == 2
	assert "alias" in violations[0]
	assert "does not name a direct dependency" in violations[1]


#============================================
def test_freshness_checks_alias_and_installed_optional_dependency(
	tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""Latest checking uses the alias target and checks optional packages when present."""
	path = write_manifest(tmp_path, {
		"dependencies": {"alias": "npm:target@>=1.0.0"},
		"optionalDependencies": {"optional": ">=1.0.0"},
	})
	monkeypatch.setattr(
		PACKAGE_POLICY.updater, "fetch_latest_versions",
		lambda _packages: {"target": "2.0.0", "optional": "2.0.0"},
	)
	class Result:
		returncode = 0
		stderr = ""
		stdout = json.dumps({"dependencies": {
			"alias": {"version": "1.0.0"}, "optional": {"version": "1.0.0"},
		}})
	monkeypatch.setattr(PACKAGE_POLICY.subprocess, "run", lambda *_args, **_kwargs: Result())
	assert PACKAGE_POLICY.check_resolved_freshness(str(path)) == 1


#============================================
def test_audit_classification_distinguishes_report_from_outage(tmp_path: pathlib.Path) -> None:
	"""A service failure and a confirmed vulnerability receive different statuses."""
	valid = tmp_path / "audit.json"
	valid.write_text(json.dumps({"metadata": {"vulnerabilities": {"total": 1}}}), encoding="utf-8")
	assert PACKAGE_POLICY.check_audit(str(valid)) == 1
	invalid = tmp_path / "outage.json"
	invalid.write_text(json.dumps({"error": "registry unavailable"}), encoding="utf-8")
	assert PACKAGE_POLICY.check_audit(str(invalid)) == 2
	malformed = tmp_path / "malformed.json"
	malformed.write_text("npm registry unavailable", encoding="utf-8")
	assert PACKAGE_POLICY.check_audit(str(malformed)) == 2


#============================================
def test_freshness_resolves_override_alias_target(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
	"""A stale aliased transitive override fails even when no direct dependency is stale."""
	path = write_manifest(tmp_path, {"overrides": {"compat": "npm:actual@>=1.0.0"}})
	monkeypatch.setattr(
		PACKAGE_POLICY.updater, "fetch_latest_versions", lambda _packages: {"actual": "2.0.0"},
	)
	tree = {"dependencies": {"parent": {"dependencies": {"compat": {"version": "1.0.0"}}}}}
	result = PACKAGE_POLICY.subprocess.CompletedProcess([], 0, json.dumps(tree), "")
	monkeypatch.setattr(PACKAGE_POLICY.subprocess, "run", lambda *_args, **_kwargs: result)
	assert PACKAGE_POLICY.check_resolved_freshness(str(path)) == 1
	tree["dependencies"]["parent"]["dependencies"]["compat"]["version"] = "2.0.0"
	result.stdout = json.dumps(tree)
	assert PACKAGE_POLICY.check_resolved_freshness(str(path)) == 0
