"""Round-trip tests for the MERGE bucket helper merge_file_safe.

Covers the four happy-path outcomes: created (dest missing), merged (consumer
fences present, content differs), unchanged (merge produces byte-identical
content), and preservation (consumer additions outside fences survive).
See meta/docs/MERGE_BUCKET_SPEC.md for the contract under test.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import propagate.console
import propagate.files


TEMPLATE_BODY = (
	"<!-- === TEMPLATE-MANAGED START === -->\n"
	"@AGENTS.md\n"
	"@docs/REPO_STYLE.md\n"
	"<!-- === TEMPLATE-MANAGED END === -->\n"
)


def _write(path, content):
	with open(path, 'w', encoding='utf-8') as f:
		f.write(content)


def test_merge_creates_when_dest_missing(tmp_path):
	source = tmp_path / "template.md"
	dest = tmp_path / "consumer" / "consumer.md"
	_write(source, TEMPLATE_BODY)
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	assert outcome == 'created'
	assert dest.exists()
	assert dest.read_text(encoding='utf-8') == TEMPLATE_BODY
	assert counters['created_count'] == 1


def test_merge_replaces_managed_region(tmp_path):
	"""Consumer fenced; template-managed content differs; merge replaces region, preserves outside."""
	source = tmp_path / "template.md"
	dest = tmp_path / "consumer.md"

	template_text = (
		"<!-- === TEMPLATE-MANAGED START === -->\n"
		"@AGENTS.md\n"
		"@docs/REPO_STYLE.md\n"
		"@docs/PYTHON_STYLE.md\n"
		"<!-- === TEMPLATE-MANAGED END === -->\n"
	)
	consumer_text = (
		"# Consumer header\n"
		"<!-- === TEMPLATE-MANAGED START === -->\n"
		"@AGENTS.md\n"
		"<!-- === TEMPLATE-MANAGED END === -->\n"
		"@local/MY_NOTES.md\n"
	)
	_write(source, template_text)
	_write(dest, consumer_text)
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	merged = dest.read_text(encoding='utf-8')
	assert outcome == 'merged'
	assert "@docs/PYTHON_STYLE.md" in merged
	assert merged.startswith("# Consumer header\n"), "consumer header (outside fences) preserved"
	assert "@local/MY_NOTES.md" in merged, "consumer trailing additions preserved"
	assert counters['merged_count'] == 1


def test_merge_unchanged_when_byte_identical(tmp_path):
	"""Merge that would produce identical bytes reports 'unchanged', not 'merged'."""
	source = tmp_path / "template.md"
	dest = tmp_path / "consumer.md"
	_write(source, TEMPLATE_BODY)
	_write(dest, TEMPLATE_BODY)
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	assert outcome == 'unchanged'
	assert counters['merged_count'] == 0
	assert counters['unchanged'] == 1


def test_merge_shell_fence_style(tmp_path):
	"""Shell/Python/YAML files use the '# === TEMPLATE-MANAGED ... ===' fence style."""
	source = tmp_path / "template.sh"
	dest = tmp_path / "consumer.sh"
	template_text = (
		"#!/usr/bin/env bash\n"
		"# === TEMPLATE-MANAGED START ===\n"
		"set -euo pipefail\n"
		"# === TEMPLATE-MANAGED END ===\n"
	)
	consumer_text = (
		"#!/usr/bin/env bash\n"
		"# === TEMPLATE-MANAGED START ===\n"
		"# old content\n"
		"# === TEMPLATE-MANAGED END ===\n"
		"# consumer trailing line\n"
	)
	_write(source, template_text)
	_write(dest, consumer_text)
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	merged = dest.read_text(encoding='utf-8')
	assert outcome == 'merged'
	assert "set -euo pipefail" in merged
	assert "# consumer trailing line" in merged


def test_merge_js_fence_style(tmp_path):
	"""JS/TS files use the '// === TEMPLATE-MANAGED ... ===' fence style."""
	source = tmp_path / "template.ts"
	dest = tmp_path / "consumer.ts"
	template_text = (
		"// === TEMPLATE-MANAGED START ===\n"
		"export const VERSION = '2';\n"
		"// === TEMPLATE-MANAGED END ===\n"
	)
	consumer_text = (
		"// === TEMPLATE-MANAGED START ===\n"
		"export const VERSION = '1';\n"
		"// === TEMPLATE-MANAGED END ===\n"
		"export const LOCAL = 'kept';\n"
	)
	_write(source, template_text)
	_write(dest, consumer_text)
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	merged = dest.read_text(encoding='utf-8')
	assert outcome == 'merged'
	assert "VERSION = '2'" in merged
	assert "LOCAL = 'kept'" in merged


def test_merge_dry_run_does_not_modify(tmp_path):
	"""dry_run=True must not write to the dest file even when a merge would change content."""
	source = tmp_path / "template.md"
	dest = tmp_path / "consumer.md"
	template_text = TEMPLATE_BODY
	consumer_text = (
		"<!-- === TEMPLATE-MANAGED START === -->\n"
		"@stale\n"
		"<!-- === TEMPLATE-MANAGED END === -->\n"
	)
	_write(source, template_text)
	_write(dest, consumer_text)
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=True, counters=counters)

	# Outcome string still reflects what would happen, but the file is untouched.
	assert outcome == 'merged'
	assert dest.read_text(encoding='utf-8') == consumer_text
