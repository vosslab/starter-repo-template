"""Stable contract checks for the TypeScript lint template."""

# Standard Library
import json
import pathlib

# local repo modules
import file_utils


REPO_ROOT = pathlib.Path(file_utils.get_repo_root())
TEMPLATE_ROOT = REPO_ROOT / "templates" / "typescript"


#============================================
def read_jsonc(path: pathlib.Path) -> dict:
	"""Load a template JSONC file whose only comments are whole-line headers."""
	lines = path.read_text(encoding="utf-8").splitlines()
	json_text = "\n".join(line for line in lines if not line.lstrip().startswith("//"))
	return json.loads(json_text)


#============================================
def test_typescript_template_uses_typescript7_and_typed_oxlint() -> None:
	"""The fresh manifest uses the supported TypeScript 7 typed-lint stack."""
	path = TEMPLATE_ROOT / "noexist" / "package.json"
	manifest = json.loads(path.read_text(encoding="utf-8"))
	dependencies = manifest["devDependencies"]
	assert int(dependencies["typescript"].removeprefix(">=").split(".")[0]) >= 7
	assert dependencies["oxlint"].startswith(">=")
	assert dependencies["oxlint-tsgolint"].startswith(">=")
	assert "eslint" not in dependencies
	assert "typescript-eslint" not in dependencies


#============================================
def test_oxlint_uses_shared_base_and_consumer_owned_root_config() -> None:
	"""Fresh consumers extend the canonical rules without overwriting local edits."""
	base_path = TEMPLATE_ROOT / "oxlint.base.json"
	local_path = TEMPLATE_ROOT / "noexist" / ".oxlintrc.json"
	base = read_jsonc(base_path)
	local = read_jsonc(local_path)
	assert local["extends"] == ["./oxlint.base.json"]
	assert local["options"]["typeAware"] is True
	assert base["rules"]["typescript/no-floating-promises"] == "error"
	assert base["rules"]["typescript/no-explicit-any"] == "error"
	assert base["overrides"][1]["rules"]["typescript/no-floating-promises"] == "off"


#============================================
def test_check_codebase_uses_installed_typed_lint_tools() -> None:
	"""The check entrypoint does not download tools during validation."""
	path = TEMPLATE_ROOT / "check_codebase.sh"
	text = path.read_text(encoding="utf-8")
	assert "./node_modules/.bin/tsc --noEmit -p tsconfig.json" in text
	assert "./node_modules/.bin/oxlint --type-aware" in text
	assert "--deny-warnings" not in text
	assert "--ignore-pattern 'node_modules/**'" in text
	assert "./node_modules/.bin/prettier --check" in text
	assert "npx eslint" not in text
