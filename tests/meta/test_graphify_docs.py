"""Behavior tests for the propagated Graphify repository-map page builder."""

# Standard Library
import re
import sys
import pathlib
import subprocess
import unittest.mock

# PIP3 modules
import pytest

# local repo modules
import file_utils


# OWASP ASVS 5.0.0 V5.3.2: this fixed path uses trusted, internal components.
# pytest.ini is template-meta and never propagates, but this test does, so the
# devel/ directory is placed on sys.path here rather than relying on the
# template's pythonpath setting.
DEVEL_DIR: pathlib.Path = pathlib.Path(file_utils.get_repo_root()) / "devel"
if str(DEVEL_DIR) not in sys.path:
	sys.path.insert(0, str(DEVEL_DIR))

import graphify_docs_lib


MERMAID_NODE_PATTERN = re.compile(r"^    ([A-Za-z0-9_]+)\[", re.MULTILINE)


#============================================


def sample_graph_data() -> dict:
	"""Return a two-community graph with one link crossing between them."""
	graph_data = {
		"nodes": [
			{
				"id": "store",
				"label": "RunStore",
				"community": 0,
				"community_name": "Run Storage",
				"source_file": "src/store.py",
			},
			{
				"id": "writer",
				"label": "write_run()",
				"community": 0,
				"community_name": "Run Storage",
				"source_file": "src/store.py",
			},
			{
				"id": "client",
				"label": "GitHubClient",
				"community": 1,
				"community_name": "GitHub API Client",
				"source_file": "src/github.py",
			},
		],
		"links": [
			{"source": "store", "target": "writer", "relation": "contains"},
			{"source": "writer", "target": "client", "relation": "calls"},
		],
	}
	return graph_data


#============================================


def test_diagram_emits_no_theme_directive() -> None:
	"""GitHub themes Mermaid per reader; a pinned theme breaks light mode."""
	diagram = graphify_docs_lib.format_mermaid_overview(sample_graph_data(), None)
	assert "%%{init" not in diagram


#============================================


@pytest.mark.parametrize(
	"unsafe_text",
	["<br/>", "<small>hidden</small>", "&amp;", '"quoted"', "] ---|9| injected["],
)
def test_diagram_sanitizes_generated_labels(unsafe_text: str) -> None:
	"""Generated community names cannot inject HTML or Mermaid syntax."""
	graph_data = sample_graph_data()
	graph_data["nodes"][2]["community_name"] = f"GitHub {unsafe_text} Client"
	diagram = graphify_docs_lib.format_mermaid_overview(graph_data, None)
	assert unsafe_text not in diagram


#============================================


def test_diagram_node_ids_are_identifier_safe() -> None:
	"""Community names become ids, so punctuation must not reach the diagram."""
	graph_data = sample_graph_data()
	graph_data["nodes"][2]["community_name"] = "Package.json Scripts & Config"
	diagram = graphify_docs_lib.format_mermaid_overview(graph_data, None)
	identifiers = MERMAID_NODE_PATTERN.findall(diagram)
	assert identifiers and all(
		re.fullmatch(r"[A-Za-z0-9_]+", identifier) is not None
		for identifier in identifiers
	)


#============================================


def test_diagram_shows_communities_and_their_crossing_links() -> None:
	"""Boxes carry the community size and edges carry the crossing count."""
	diagram = graphify_docs_lib.format_mermaid_overview(sample_graph_data(), None)
	assert all(
		label in diagram
		for label in ('["Run Storage (2)"]', '["GitHub API Client (1)"]')
	)
	# One link crosses communities; the containment link stays inside one.
	assert "---|1|" in diagram


#============================================


def test_summary_omits_the_benchmark_row_when_unavailable() -> None:
	"""A failed benchmark drops one row rather than failing the page."""
	rows = graphify_docs_lib.format_summary_table(sample_graph_data(), None, None)
	joined = "\n".join(rows)
	assert "Token reduction" not in joined


#============================================


def test_detail_sections_exclude_test_symbols() -> None:
	"""The same predicate that guards orientation also guards the page."""
	graph_data = sample_graph_data()
	graph_data["nodes"].append({
		"id": "case",
		"label": "test_writes_a_run()",
		"community": 0,
		"community_name": "Run Storage",
		"source_file": "tests/test_store.py",
	})
	sections = "\n".join(graphify_docs_lib.format_community_sections(graph_data, None))
	assert "`RunStore`" in sections
	assert "test_writes_a_run" not in sections


#============================================


def test_invalid_svg_export_is_nonfatal(
	tmp_path: pathlib.Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An unparsable optional figure does not prevent page generation."""
	output_dir = tmp_path / graphify_docs_lib.graphify_context_lib.OUTPUT_DIR_NAME
	output_dir.mkdir()
	(output_dir / graphify_docs_lib.EXPORTED_SVG_NAME).write_text("<svg>", encoding="utf-8")
	completed = subprocess.CompletedProcess(["graphify", "export", "svg"], 0)
	mock_run = unittest.mock.Mock(return_value=completed)
	monkeypatch.setattr(graphify_docs_lib.subprocess, "run", mock_run)
	summary = graphify_docs_lib.build_figure("graphify", tmp_path)
	assert summary is None


# Vendored pytest file. Local changes can and will be overwritten.
