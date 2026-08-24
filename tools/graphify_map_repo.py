#!/usr/bin/env python3
"""Build or update a Graphify repository map and print concise agent guidance."""

# Standard Library
import shutil
import pathlib
import argparse
import subprocess


MODEL = "qwen2.5-coder:7b-instruct"
OUTPUT_DIR_NAME = "graphify-out"
INTERNAL_OUTPUT_NAMES = {
	"cache",
	"manifest.json",
	"needs_update",
}
ARTIFACT_DESCRIPTIONS = {
	"GRAPH_REPORT.md": "architecture, communities, and major relationships",
	"graph.html": "interactive visual repository map",
	"graph.json": "backing graph data used by Graphify queries",
	"wiki/index.md": "generated repository navigation",
}
AUTHORED_AREA_PATTERNS = ("tests/", "devel/", "tools/", "docs/")


#============================================


def parse_args() -> argparse.Namespace:
	"""Accept no modes while preserving standard command-line help."""
	# ASVS 2.2.1: argparse rejects every unsupported command-line value.
	parser = argparse.ArgumentParser(
		description="Build or update Graphify and print concise agent orientation."
	)
	args = parser.parse_args()
	return args


#============================================


def get_repo_root() -> pathlib.Path:
	"""Return the Git repository root for the current working directory."""
	# ASVS 1.2.5: pass arguments directly without a shell interpreter.
	result = subprocess.run(
		["git", "rev-parse", "--show-toplevel"],
		check=True,
		capture_output=True,
		text=True,
	)
	repo_root = pathlib.Path(result.stdout.strip()).resolve()
	return repo_root


#============================================


def require_repo_root(repo_root: pathlib.Path) -> None:
	"""Require the tool to run from the active repository root."""
	current_dir = pathlib.Path.cwd().resolve()
	if current_dir != repo_root:
		raise RuntimeError(f"Run this tool from the repository root: {repo_root}")


#============================================


def require_command(command_name: str) -> str:
	"""Return the resolved executable path or raise a setup error."""
	executable = shutil.which(command_name)
	if executable is None:
		raise RuntimeError(
			f"Required command '{command_name}' is unavailable. "
			"Install the repository's declared development dependencies first."
		)
	return executable


#============================================


def require_ollama_model(ollama_executable: str) -> None:
	"""Require the configured local Ollama model without downloading it."""
	# ASVS 1.2.5: the model and executable are trusted fixed values, passed as argv.
	result = subprocess.run(
		[ollama_executable, "show", MODEL],
		capture_output=True,
		text=True,
	)
	if result.returncode != 0:
		detail = result.stderr.strip()
		raise RuntimeError(
			f"Ollama model '{MODEL}' is unavailable. Run 'ollama pull {MODEL}' first. "
			f"Ollama reported: {detail}"
		)


#============================================


def print_step(label: str) -> None:
	"""Print one prominent runtime phase label."""
	print()
	print(f"============ {label} ============")


#============================================


def run_command(command: list[str], repo_root: pathlib.Path) -> None:
	"""Run one trusted Graphify lifecycle command from the repository root."""
	# ASVS 1.2.5: subprocesses use an argv list and never invoke a shell.
	subprocess.run(command, cwd=repo_root, check=True)


#============================================


def graph_build_command(
	graphify_executable: str,
	repo_root: pathlib.Path,
) -> tuple[str, list[str]]:
	"""Return the correct fresh-extract or incremental-update operation."""
	graph_path = repo_root / OUTPUT_DIR_NAME / "graph.json"
	if graph_path.is_file():
		operation = "UPDATING GRAPHIFY CODE MAP"
		command = [graphify_executable, "update", "."]
	else:
		operation = "EXTRACTING GRAPHIFY CODE MAP"
		command = [graphify_executable, "extract", ".", "--code-only"]
		if (repo_root / "Cargo.toml").is_file():
			command.append("--cargo")
	return operation, command


#============================================


def describe_unknown_artifact(artifact_path: pathlib.Path) -> str:
	"""Return a concise description for an unrecognized Graphify artifact."""
	if artifact_path.is_dir():
		description = "generated Graphify output directory"
	elif artifact_path.suffix == ".html":
		description = "generated visual report"
	elif artifact_path.suffix == ".md":
		description = "generated Markdown report"
	elif artifact_path.suffix == ".json":
		description = "generated Graphify data"
	else:
		description = "generated Graphify artifact"
	return description


#============================================


def visible_output_children(output_dir: pathlib.Path) -> list[pathlib.Path]:
	"""Return visible, user-facing top-level Graphify output paths."""
	children = []
	for child in sorted(output_dir.iterdir(), key=lambda path: path.name.lower()):
		if child.is_dir() or child.name.startswith(".") or child.name in INTERNAL_OUTPUT_NAMES:
			continue
		children.append(child)
	return children


#============================================


def discover_artifacts(repo_root: pathlib.Path) -> list[tuple[str, str]]:
	"""Inventory only Graphify artifacts that exist in the active checkout."""
	# ASVS 5.3.2: all inspected paths descend from the fixed repository output path.
	output_dir = repo_root / OUTPUT_DIR_NAME
	if not output_dir.is_dir():
		raise RuntimeError(f"Graphify output directory was not created: {output_dir}")

	artifacts = []
	known_top_level_names = {pathlib.Path(path).parts[0] for path in ARTIFACT_DESCRIPTIONS}
	for relative_name, description in ARTIFACT_DESCRIPTIONS.items():
		artifact_path = output_dir / relative_name
		if artifact_path.exists():
			artifacts.append((f"{OUTPUT_DIR_NAME}/{relative_name}", description))

	for artifact_path in visible_output_children(output_dir):
		if artifact_path.name in known_top_level_names:
			continue
		relative_path = artifact_path.relative_to(repo_root)
		description = describe_unknown_artifact(artifact_path)
		artifacts.append((relative_path.as_posix(), description))

	if not artifacts:
		raise RuntimeError(f"No user-facing Graphify artifacts found in {output_dir}")
	return artifacts


#============================================


def read_authored_area_exclusions(repo_root: pathlib.Path) -> list[str]:
	"""Return authored repository areas excluded by the local Graphify policy."""
	ignore_path = repo_root / ".graphifyignore"
	if not ignore_path.is_file():
		return []

	patterns = []
	for raw_line in ignore_path.read_text(encoding="utf-8").splitlines():
		pattern = raw_line.strip()
		if not pattern or pattern.startswith("#"):
			continue
		if pattern in AUTHORED_AREA_PATTERNS:
			patterns.append(pattern)
	return patterns


#============================================


def graph_output_is_ignored(repo_root: pathlib.Path) -> bool:
	"""Return whether Git ignores the canonical generated graph output."""
	# ASVS 1.2.5: use a fixed path and argv list without a shell interpreter.
	result = subprocess.run(
		["git", "check-ignore", "--quiet", f"{OUTPUT_DIR_NAME}/graph.json"],
		cwd=repo_root,
	)
	is_ignored = result.returncode == 0
	return is_ignored


#============================================


def format_orientation(
	artifacts: list[tuple[str, str]],
	exclusions: list[str],
	output_ignored: bool,
) -> str:
	"""Return the concise Graphify orientation for managers and subagents."""
	lines = [
		"GRAPHIFY CONTEXT",
		"",
		f"Graphify mapped this checkout into {OUTPUT_DIR_NAME}/.",
		"",
		"Available artifacts:",
	]
	for artifact_path, description in artifacts:
		lines.append(f"- {artifact_path} - {description}")

	lines.extend(
		[
			"",
			"Use these artifacts before broad repository searches. Use GRAPH_REPORT.md for broad",
			"orientation. For task-specific detail, use as needed:",
			"",
			'  graphify query "<question>" --budget 1500',
			'  graphify explain "<symbol_or_path>"',
			'  graphify affected "<symbol_or_path>" --depth 2',
			'  graphify path "<symbol A>" "<symbol B>"',
			"",
			"Managers use the map to identify logical work slices. Subagents start with the",
			"provided orientation and run focused queries when useful.",
		]
	)
	if exclusions:
		excluded_text = ", ".join(exclusions)
		lines.extend(
			[
				"",
				f"Graph scope excludes authored areas: {excluded_text}",
				"Search excluded areas directly when they matter to the task.",
			]
		)
	if not output_ignored:
		lines.extend(
			[
				"",
				"Graphify output is visible to Git in this checkout.",
				"Review repository ignore policy before committing generated graph files.",
			]
		)
	lines.extend(
		[
			"",
			"Graphify guides investigation; current source, configuration, tests, and runtime",
			"behavior determine what is true.",
		]
	)
	orientation = "\n".join(lines)
	return orientation


#============================================


def validate_core_artifacts(repo_root: pathlib.Path) -> None:
	"""Require the two artifacts needed for reports and targeted graph queries."""
	required_paths = (
		repo_root / OUTPUT_DIR_NAME / "GRAPH_REPORT.md",
		repo_root / OUTPUT_DIR_NAME / "graph.json",
	)
	missing_paths = [path for path in required_paths if not path.is_file()]
	if missing_paths:
		missing_text = ", ".join(str(path) for path in missing_paths)
		raise RuntimeError(f"Graphify did not create required artifacts: {missing_text}")


#============================================


def main() -> None:
	"""Build or update Graphify, then print artifact-driven agent orientation."""
	parse_args()
	repo_root = get_repo_root()
	require_repo_root(repo_root)
	graphify_executable = require_command("graphify")
	ollama_executable = require_command("ollama")
	require_ollama_model(ollama_executable)

	operation, build_command = graph_build_command(graphify_executable, repo_root)
	print_step(operation)
	run_command(build_command, repo_root)

	print_step("LABELING GRAPHIFY COMMUNITIES")
	run_command(
		[
			graphify_executable,
			"label",
			".",
			"--backend=ollama",
			f"--model={MODEL}",
		],
		repo_root,
	)

	print_step("BENCHMARKING GRAPHIFY CODE MAP")
	run_command([graphify_executable, "benchmark"], repo_root)

	validate_core_artifacts(repo_root)
	artifacts = discover_artifacts(repo_root)
	exclusions = read_authored_area_exclusions(repo_root)
	output_ignored = graph_output_is_ignored(repo_root)

	print()
	print("======================================================================")
	print("GRAPHIFY READY")
	print("======================================================================")
	print()
	print(format_orientation(artifacts, exclusions, output_ignored))


if __name__ == "__main__":
	main()
