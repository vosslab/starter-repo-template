"""Error-case tests for merge_file_safe.

Every error case must:
  - return 'error'
  - increment counters['errors']
  - leave the dest file UNTOUCHED (the propagator refuses to guess; user fixes the fence
    state, then re-runs)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import propagate.console
import propagate.files


TEMPLATE_BODY = (
	"<!-- === TEMPLATE-MANAGED START === -->\n"
	"@AGENTS.md\n"
	"<!-- === TEMPLATE-MANAGED END === -->\n"
)


def _write(path, content):
	with open(path, 'w', encoding='utf-8') as f:
		f.write(content)


def _setup(tmp_path, template_text, consumer_text):
	source = tmp_path / "template.md"
	dest = tmp_path / "consumer.md"
	_write(source, template_text)
	_write(dest, consumer_text)
	return source, dest


def test_error_consumer_missing_end_fence(tmp_path):
	source, dest = _setup(
		tmp_path,
		TEMPLATE_BODY,
		"<!-- === TEMPLATE-MANAGED START === -->\n@AGENTS.md\nno end fence below\n",
	)
	before = dest.read_text(encoding='utf-8')
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	assert outcome == 'error'
	assert counters['errors'] == 1
	assert dest.read_text(encoding='utf-8') == before


def test_error_consumer_missing_start_fence(tmp_path):
	source, dest = _setup(
		tmp_path,
		TEMPLATE_BODY,
		"no start fence above\n@AGENTS.md\n<!-- === TEMPLATE-MANAGED END === -->\n",
	)
	before = dest.read_text(encoding='utf-8')
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	assert outcome == 'error'
	assert counters['errors'] == 1
	assert dest.read_text(encoding='utf-8') == before


def test_error_consumer_fences_reversed(tmp_path):
	source, dest = _setup(
		tmp_path,
		TEMPLATE_BODY,
		"<!-- === TEMPLATE-MANAGED END === -->\n@AGENTS.md\n<!-- === TEMPLATE-MANAGED START === -->\n",
	)
	before = dest.read_text(encoding='utf-8')
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	assert outcome == 'error'
	assert counters['errors'] == 1
	assert dest.read_text(encoding='utf-8') == before


def test_error_consumer_duplicate_start_fence(tmp_path):
	source, dest = _setup(
		tmp_path,
		TEMPLATE_BODY,
		"<!-- === TEMPLATE-MANAGED START === -->\n"
		"first\n"
		"<!-- === TEMPLATE-MANAGED START === -->\n"
		"second\n"
		"<!-- === TEMPLATE-MANAGED END === -->\n",
	)
	before = dest.read_text(encoding='utf-8')
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	assert outcome == 'error'
	assert counters['errors'] == 1
	assert dest.read_text(encoding='utf-8') == before


def test_error_consumer_mixed_fence_styles(tmp_path):
	"""Consumer mixes markdown start with shell end -- fence-style mismatch."""
	source, dest = _setup(
		tmp_path,
		TEMPLATE_BODY,
		"<!-- === TEMPLATE-MANAGED START === -->\n"
		"@AGENTS.md\n"
		"# === TEMPLATE-MANAGED END ===\n",
	)
	before = dest.read_text(encoding='utf-8')
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	assert outcome == 'error'
	assert counters['errors'] == 1
	assert dest.read_text(encoding='utf-8') == before


def test_error_consumer_plain_shape_no_fences(tmp_path):
	"""Consumer at pre-MERGE shape (no fences at all) is an error; user must migrate once."""
	source, dest = _setup(
		tmp_path,
		TEMPLATE_BODY,
		"@AGENTS.md\n@docs/REPO_STYLE.md\n",
	)
	before = dest.read_text(encoding='utf-8')
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	assert outcome == 'error'
	assert counters['errors'] == 1
	assert dest.read_text(encoding='utf-8') == before


def test_error_template_missing_fences(tmp_path):
	"""Template without fences is a configuration bug; dispatcher must refuse to merge."""
	source = tmp_path / "template.md"
	dest = tmp_path / "consumer.md"
	_write(source, "plain template body, no fences\n")
	_write(dest, "<!-- === TEMPLATE-MANAGED START === -->\nx\n<!-- === TEMPLATE-MANAGED END === -->\n")
	before = dest.read_text(encoding='utf-8')
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	assert outcome == 'error'
	assert counters['errors'] == 1
	assert dest.read_text(encoding='utf-8') == before


def test_error_source_missing(tmp_path):
	source = tmp_path / "missing_template.md"
	dest = tmp_path / "consumer.md"
	_write(dest, TEMPLATE_BODY)
	before = dest.read_text(encoding='utf-8')
	counters = propagate.console.init_counters()

	outcome = propagate.files.merge_file_safe(str(source), str(dest), dry_run=False, counters=counters)

	assert outcome == 'error'
	assert counters['errors'] == 1
	assert dest.read_text(encoding='utf-8') == before
