"""Tests for devel/commit_changelog.py deterministic helpers.

Narrow coverage of pure-function paths where a real bug could plausibly
slip through: the cleaner composition pipeline, the message-builder
branches (empty, single entry, single-day vs multi-day grouping, body
continuation), and the entry-selection set-difference (driven against
fabricated prior/current changelog strings, no git, no filesystem).
The git-touching wrappers (`get_last_changelog_commit_sha`,
`get_changelog_text_at`) are exercised by interactive smoke runs.
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
	# single entry with no body: subject is the title and there is no
	# body block (the title bullet would just duplicate the subject)
	entry = make_entry("2026-05-21", "Fix link in docs/FILE.md")
	out = commit_changelog.make_seed_message_from_entries([entry])
	lines = out.splitlines()
	assert lines[0] == "Fix link in docs/FILE.md"
	assert "- Fix link in docs/FILE.md" not in lines

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

def test_make_seed_message_single_entry_emits_body_as_paragraph():
	# single entry with a body: subject is the title; body is rendered as
	# a plain paragraph after the blank line (no `- title` repetition,
	# no two-space indent -- that shape is reserved for multi-entry lists)
	entry = make_entry("2026-05-21", "first line of bullet",
			body="continuation text on second line")
	out = commit_changelog.make_seed_message_from_entries([entry])
	lines = out.splitlines()
	assert lines[0] == "first line of bullet"
	assert lines[1] == ""
	assert lines[2].startswith("continuation text")
	assert not any(ln.startswith("- first line") for ln in lines)

def test_make_seed_message_multi_entry_keeps_bulleted_body():
	# multi-entry seeds keep the `- title` bullet list (each entry must
	# be individually scannable in the editor buffer)
	entries = [
		make_entry("2026-05-21", "alpha"),
		make_entry("2026-05-21", "beta"),
	]
	out = commit_changelog.make_seed_message_from_entries(entries)
	lines = out.splitlines()
	assert "- alpha" in lines
	assert "- beta" in lines


#============================================
# compute_new_entries: set-difference identity logic (the bug fix)

def test_compute_new_entries_empty_prior_returns_all():
	current = [make_entry("2026-05-21", "a"), make_entry("2026-05-21", "b")]
	out = commit_changelog.compute_new_entries(current, [])
	assert [e.title for e in out] == ["a", "b"]

def test_compute_new_entries_same_day_second_commit():
	# bug repro: prior commit shipped a + b under today; user added c.
	# the old date-window filter returned a, b, c; the fix returns only c.
	prior = [make_entry("2026-05-21", "a"), make_entry("2026-05-21", "b")]
	current = [
		make_entry("2026-05-21", "a"),
		make_entry("2026-05-21", "b"),
		make_entry("2026-05-21", "c"),
	]
	out = commit_changelog.compute_new_entries(current, prior)
	assert [e.title for e in out] == ["c"]

def test_compute_new_entries_no_changes_returns_empty():
	entries = [make_entry("2026-05-21", "a")]
	out = commit_changelog.compute_new_entries(entries, entries)
	assert out == []

def test_compute_new_entries_title_rephrase_treated_as_new():
	# documented behavior: a rephrased title is a new key.
	prior = [make_entry("2026-05-21", "original phrasing")]
	current = [make_entry("2026-05-21", "revised phrasing")]
	out = commit_changelog.compute_new_entries(current, prior)
	assert [e.title for e in out] == ["revised phrasing"]

def test_compute_new_entries_preserves_current_order():
	prior = [make_entry("2026-05-21", "b")]
	current = [
		make_entry("2026-05-21", "c"),
		make_entry("2026-05-21", "b"),
		make_entry("2026-05-21", "a"),
	]
	out = commit_changelog.compute_new_entries(current, prior)
	assert [e.title for e in out] == ["c", "a"]


#============================================
# parse_text: in-memory parse entry point used by the SHA-anchored selection

def test_parse_text_round_trip_drives_compute_new_entries():
	# Bug-fix integration: feed prior + current changelog strings through
	# parse_text and verify the (date, title) set-difference picks only
	# the newly-added bullet. This is the actual end-to-end path that
	# select_new_entries follows for non-first-time commits.
	prior_text = (
		"## 2026-05-21\n\n"
		"### Fixes and Maintenance\n\n"
		"- morning bullet\n"
	)
	current_text = (
		"## 2026-05-21\n\n"
		"### Fixes and Maintenance\n\n"
		"- morning bullet\n"
		"- afternoon bullet\n"
	)
	_pb, prior_entries, _pw = changelog_lib.parse_text(
		prior_text, source="<prior>"
	)
	_cb, current_entries, _cw = changelog_lib.parse_text(
		current_text, source="<current>"
	)
	new = commit_changelog.compute_new_entries(current_entries, prior_entries)
	assert [e.title for e in new] == ["afternoon bullet"]


if __name__ == "__main__":
	pytest.main([__file__, "-v"])
