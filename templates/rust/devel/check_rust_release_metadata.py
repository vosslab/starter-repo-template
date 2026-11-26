#!/usr/bin/env python3
# This file is vendored. Local changes can and will be overwritten by propagation.

"""Validate the Cargo metadata that must agree before a Rust release."""

# Standard Library
import json
import pathlib
import subprocess
import sys
import tomllib

# local repo modules
import version_lib


#============================================
def repository_root() -> pathlib.Path:
	"""Return the checked repository root."""
	result = subprocess.run(
		["git", "rev-parse", "--show-toplevel"],
		check=True,
		capture_output=True,
		text=True,
	)
	return pathlib.Path(result.stdout.strip())


#============================================
def workspace_metadata(repository: pathlib.Path) -> dict:
	"""Read Cargo's complete locked workspace metadata."""
	if not (repository / "Cargo.lock").is_file():
		raise RuntimeError("Cargo.lock is required for a reproducible source release")
	result = subprocess.run(
		["cargo", "metadata", "--locked", "--format-version", "1"],
		cwd=repository,
		check=True,
		stdout=subprocess.PIPE,
		text=True,
	)
	metadata = json.loads(result.stdout)
	return metadata


#============================================
def workspace_package_names(metadata: dict) -> list[str]:
	"""Return the sorted names of workspace members from Cargo metadata."""
	workspace_members = set(metadata["workspace_members"])
	names = [
		package["name"]
		for package in metadata["packages"]
		if package["id"] in workspace_members
	]
	if not names:
		raise RuntimeError("Cargo metadata contains no workspace packages")
	if len(names) != len(set(names)):
		raise RuntimeError("Cargo metadata contains duplicate workspace package names")
	names.sort()
	return names


#============================================
def root_release_version(repository: pathlib.Path, metadata: dict) -> str | None:
	"""Return a root package or virtual-workspace release version when declared."""
	manifest_path = str(repository / "Cargo.toml")
	workspace_members = set(metadata["workspace_members"])
	for package in metadata["packages"]:
		if package["id"] in workspace_members and package["manifest_path"] == manifest_path:
			return package["version"]
	with pathlib.Path(manifest_path).open("rb") as manifest_file:
		manifest = tomllib.load(manifest_file)
	workspace = manifest.get("workspace")
	if not isinstance(workspace, dict):
		return None
	workspace_package = workspace.get("package")
	if not isinstance(workspace_package, dict):
		return None
	version = workspace_package.get("version")
	if version is not None and not isinstance(version, str):
		raise RuntimeError("workspace.package.version must be a string")
	return version


#============================================
def verify_root_version(repository: pathlib.Path, metadata: dict) -> str | None:
	"""Check root VERSION when Cargo declares one shared release version."""
	version_path = repository / "VERSION"
	if not version_path.is_file():
		return None
	cargo_version = root_release_version(repository, metadata)
	if cargo_version is None:
		return None
	file_version = version_lib.normalize_cargo_version(
		version_lib.read_version_file(str(repository))
	)
	version_lib.verify_version_sync(cargo_version, file_version)
	return cargo_version


def main() -> None:
	"""Verify the locked Cargo metadata for this repository's workspace."""
	repository = repository_root()
	metadata = workspace_metadata(repository)
	package_names = workspace_package_names(metadata)
	cargo_version = verify_root_version(repository, metadata)
	version_note = f" (VERSION matches {cargo_version})" if cargo_version else ""
	print(
		f"release metadata: {len(package_names)} workspace package(s): "
		f"{', '.join(package_names)}{version_note}"
	)


if __name__ == "__main__":
	try:
		main()
	except (
		KeyError,
		OSError,
		RuntimeError,
		subprocess.CalledProcessError,
		ValueError,
	) as error:
		print(f"release metadata check failed: {error}", file=sys.stderr)
		raise SystemExit(2) from error
