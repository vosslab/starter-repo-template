"""Tests for devel/commit_changelog.py deterministic helpers.

Narrow coverage of pure-function paths where a real bug could plausibly
slip through: the cleaner composition pipeline, and the message-builder
branches (empty, single entry, single-day vs multi-day grouping, body
continuation). The git-touching helpers (`get_last_changelog_commit_date`,
`select_new_entries`) are exercised by interactive smoke runs, not pytest.
"""

# Standard Library
import os
import sys

# pip3 modules
import pytest

# local repo modules
# tests/meta/ is two levels deep, so dirname three times for repo root
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "devel"))
import changelog_lib
import commit_changelog


#============================================
# Helpers

def make_entry(date: str, title: str, body: str = "",
		category: str = "Fixes and Maintenance") -> changelog_lib.Entry:
	"""Build an in-memory Entry record for tests."""
	text = title if not body else f"{title}. {body}"
	return changelog_lib.Entry(
		date=date,
		source="<test>",
		category=category,
		title=title,
		body=body,
		text=text,
		lineno=1,
	)


#============================================
# clean_entry_text composition: the only round-trip that catches a real bug

def test_clean_entry_text_strips_link_bold_and_collapses_whitespace():
	raw = "**Refactor** [devel/foo.py](devel/foo.py)\nadds   a new helper"
	out = commit_changelog.clean_entry_text(raw, max_length=200)
	assert "**" not in out
	assert "[" not in out
	assert "]" not in out
	assert "  " not in out
	assert "devel/foo.py" in out


#============================================
# make_seed_message_from_entries: real branches a future change could break

def test_make_seed_message_empty_returns_none():
	assert commit_changelog.make_seed_message_from_entries([]) is None

def test_make_seed_message_single_entry_uses_title_as_subject():
	entry = make_entry("2026-05-21", "Fix link in docs/FILE.md")
	out = commit_changelog.make_seed_message_from_entries([entry])
	lines = out.splitlines()
	assert lines[0] == "Fix link in docs/FILE.md"
	assert "- Fix link in docs/FILE.md" in lines

def test_make_seed_message_multi_day_emits_date_headings():
	entries = [
		make_entry("2026-05-21", "today bullet"),
		make_entry("2026-05-20", "yesterday bullet"),
	]
	out = commit_changelog.make_seed_message_from_entries(entries)
	assert "## 2026-05-21" in out
	assert "## 2026-05-20" in out

def test_make_seed_message_single_day_omits_heading():
	entries = [
		make_entry("2026-05-21", "first"),
		make_entry("2026-05-21", "second"),
	]
	out = commit_changelog.make_seed_message_from_entries(entries)
	assert "## 2026-05-21" not in out

def test_make_seed_message_emits_indented_continuation_when_body_present():
	entry = make_entry("2026-05-21", "first line of bullet",
			body="continuation text on second line")
	out = commit_changelog.make_seed_message_from_entries([entry])
	lines = out.splitlines()
	bullet_idx = next(i for i, ln in enumerate(lines)
			if ln.startswith("- first line"))
	assert lines[bullet_idx + 1].startswith("  continuation")


if __name__ == "__main__":
	pytest.main([__file__, "-v"])
