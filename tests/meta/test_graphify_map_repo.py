"""Behavior tests for the propagated Graphify repository mapping tool."""

# Standard Library
import pathlib

# local repo modules
import tools.graphify_map_repo


#============================================


def test_existing_graph_selects_real_update(tmp_path: pathlib.Path) -> None:
	"""An existing graph uses Graphify's incremental code-map update."""
	output_dir = tmp_path / "graphify-out"
	output_dir.mkdir()
	(output_dir / "graph.json").write_text("{}", encoding="utf-8")
	operation, command = tools.graphify_map_repo.graph_build_command("graphify", tmp_path)
	assert (operation, command) == ("UPDATING GRAPHIFY CODE MAP", ["graphify", "update", "."])


#============================================


def test_missing_graph_selects_code_extraction(tmp_path: pathlib.Path) -> None:
	"""A missing graph performs a fresh code-only extraction."""
	operation, command = tools.graphify_map_repo.graph_build_command("graphify", tmp_path)
	expected = ("EXTRACTING GRAPHIFY CODE MAP", ["graphify", "extract", ".", "--code-only"])
	assert (operation, command) == expected


#============================================


def test_artifact_inventory_uses_existing_user_outputs(tmp_path: pathlib.Path) -> None:
	"""The orientation inventory includes outputs and omits Graphify internals."""
	output_dir = tmp_path / "graphify-out"
	output_dir.mkdir()
	(output_dir / "graph.json").write_text("{}", encoding="utf-8")
	(output_dir / "manifest.json").write_text("{}", encoding="utf-8")
	(output_dir / "2026-08-24").mkdir()
	artifacts = tools.graphify_map_repo.discover_artifacts(tmp_path)
	artifact_paths = {path for path, _description in artifacts}
	assert "graphify-out/graph.json" in artifact_paths
	assert artifact_paths.isdisjoint(
		{"graphify-out/manifest.json", "graphify-out/2026-08-24"}
	)


#============================================


def test_orientation_reports_artifact_and_index_limit() -> None:
	"""The compact message names available evidence and authored exclusions."""
	artifacts = [("graphify-out/GRAPH_REPORT.md", "architecture overview")]
	orientation = tools.graphify_map_repo.format_orientation(artifacts, ["tests/"], True)
	assert "graphify-out/GRAPH_REPORT.md - architecture overview" in orientation
	assert "Graph scope excludes authored areas: tests/" in orientation


#============================================


def test_orientation_warns_when_graph_output_is_visible_to_git() -> None:
	"""A checkout with unignored generated graphs receives a concise warning."""
	artifacts = [("graphify-out/graph.json", "graph data")]
	orientation = tools.graphify_map_repo.format_orientation(artifacts, [], False)
	assert "Graphify output is visible to Git in this checkout." in orientation


# Vendored pytest file. Local changes can and will be overwritten.
