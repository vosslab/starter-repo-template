"""Data-preservation checks for the removable Graphify Cargo correction."""

# Standard Library
import json
import pathlib

# PIP3 modules
import pytest
import graphify.build
import graphify.export

# local repo modules
import graphify_prune_tests


#============================================


def cargo_graph() -> dict:
	"""Return one Cargo twin, a production node, and parallel dependency links."""
	return {
		"nodes": [
			{"id": "crate:core", "label": "core", "source_file": "core/Cargo.toml"},
			{"id": "pkg_core", "label": "core", "source_file": "core/Cargo.toml",
			 "_origin": "ast", "type": "package", "ecosystem": "cargo", "file_type": "code"},
			{"id": "production", "label": "production", "source_file": "lib.rs",
			 "_origin": "ast", "file_type": "code"},
		],
		"edges": [
			{"source": "production", "target": "crate:core", "relation": "crate_depends_on"},
			{"source": "production", "target": "crate:core", "relation": "references"},
		],
	}


#============================================


def test_cargo_reconciliation_preserves_production_and_parallel_links(tmp_path: pathlib.Path) -> None:
	path = tmp_path / "graph.json"
	path.write_text(json.dumps(cargo_graph()))
	remap = graphify_prune_tests.normalize_cargo_twins(path)
	data = json.loads(path.read_text())
	assert remap == {"crate:core": "pkg_core"}
	assert {node["id"] for node in data["nodes"]} == {"pkg_core", "production"}
	assert data["edges"] == [
		{"source": "production", "target": "pkg_core", "relation": "crate_depends_on"},
		{"source": "production", "target": "pkg_core", "relation": "references"},
	]
	before = path.read_bytes()
	assert graphify_prune_tests.normalize_cargo_twins(path) == {}
	assert path.read_bytes() == before


#============================================


def test_graphify_still_refuses_production_loss_after_reconciliation(tmp_path: pathlib.Path) -> None:
	path = tmp_path / "graph.json"
	path.write_text(json.dumps(cargo_graph()))
	graphify_prune_tests.normalize_cargo_twins(path)
	before = path.read_bytes()
	graph = graphify.build.build_from_json(json.loads(path.read_text()))
	graph.remove_node("production")
	assert graphify.export.to_json(graph, {}, str(path)) is False
	assert path.read_bytes() == before


#============================================


def test_unexplained_normalization_leaves_original_file_untouched(tmp_path: pathlib.Path) -> None:
	data = cargo_graph()
	data["nodes"].extend([
		{"id": "one", "label": "same", "source_file": "concept.md", "source_location": "L1"},
		{"id": "two", "label": "same", "source_file": "concept.md", "source_location": "L1"},
	])
	path = tmp_path / "graph.json"
	path.write_text(json.dumps(data))
	before = path.read_bytes()
	with pytest.raises(RuntimeError, match="Unexplained"):
		graphify_prune_tests.normalize_cargo_twins(path)
	assert path.read_bytes() == before
