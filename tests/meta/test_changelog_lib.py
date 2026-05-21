"""Tests for devel/changelog_lib.py."""

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


#============================================
# Fixture content builders

SIMPLE_CHANGELOG = (
	"# CHANGELOG\n"
	"\n"
	"Some preamble text.\n"
	"\n"
	"## 2026-05-10\n"
	"\n"
	"### Additions and New Features\n"
	"- Added widget A\n"
	"- Added widget B\n"
	"\n"
	"### Fixes and Maintenance\n"
	"- Fixed bug X\n"
	"\n"
	"## 2026-05-09\n"
	"\n"
	"### Fixes and Maintenance\n"
	"- Fixed bug Y\n"
	"\n"
)


#============================================
# parse_day_blocks round-trip


def test_parse_day_blocks_roundtrip():
	# reassembling preamble + each block's raw_text reproduces input byte-for-byte
	preamble, blocks, warnings = changelog_lib.parse_day_blocks(SIMPLE_CHANGELOG)
	parts = [preamble]
	for block in blocks:
		parts.append(block.raw_text)
	reassembled = "".join(parts)
	assert reassembled == SIMPLE_CHANGELOG
	assert warnings == []


def test_parse_day_blocks_returns_two_blocks_in_order():
	# fixture constructs two day headings; verify order and dates are driven by fixture
	_preamble, blocks, _warnings = changelog_lib.parse_day_blocks(SIMPLE_CHANGELOG)
	dates = [block.date for block in blocks]
	assert dates == ["2026-05-10", "2026-05-09"]


#============================================
# Calendrical tolerance


def test_parse_day_blocks_invalid_date_warns_and_skips():
	# 2026-13-99 matches the regex but is calendrically invalid
	text = (
		"# CHANGELOG\n"
		"\n"
		"## 2026-13-99\n"
		"- this block should be skipped\n"
		"\n"
		"## 2026-05-10\n"
		"- good entry\n"
		"\n"
	)
	_preamble, blocks, warnings = changelog_lib.parse_day_blocks(text)
	# only the valid block survives
	block_dates = [block.date for block in blocks]
	assert block_dates == ["2026-05-10"]
	# at least one warning mentioning the bad date
	bad_warnings = [w for w in warnings if "2026-13-99" in w]
	assert len(bad_warnings) >= 1


#============================================
# Duplicate policies


def test_parse_day_blocks_duplicate_warn_keeps_first():
	text = (
		"## 2026-05-10\n"
		"- first occurrence\n"
		"\n"
		"## 2026-05-10\n"
		"- duplicate, should be skipped\n"
		"\n"
	)
	_preamble, blocks, warnings = changelog_lib.parse_day_blocks(
		text, duplicate_policy="warn",
	)
	# only the first occurrence is kept
	assert len(blocks) == 1
	assert "first occurrence" in blocks[0].raw_text
	assert "duplicate, should be skipped" not in blocks[0].raw_text
	# a duplicate warning is emitted
	dup_warnings = [w for w in warnings if "duplicate" in w and "2026-05-10" in w]
	assert len(dup_warnings) == 1


def test_parse_day_blocks_duplicate_keep_returns_both():
	fixture = (
		"# CHANGELOG\n"
		"\n"
		"## 2026-05-21\n"
		"- first\n"
		"\n"
		"## 2026-05-21\n"
		"- second\n"
	)
	_, blocks, warnings = changelog_lib.parse_day_blocks(
		fixture, source="x.md", duplicate_policy="keep")
	assert len(blocks) == 2
	assert [b.date for b in blocks] == ["2026-05-21", "2026-05-21"]
	assert warnings == []
	dups = changelog_lib.find_duplicate_dates(blocks)
	assert dups == ["2026-05-21"]


def test_parse_day_blocks_unknown_policy_raises_valueerror():
	with pytest.raises(ValueError):
		changelog_lib.parse_day_blocks("## 2026-05-10\n- x\n", duplicate_policy="bogus")


def test_parse_day_blocks_duplicate_raise_raises_valueerror():
	text = (
		"## 2026-05-10\n"
		"- first\n"
		"\n"
		"## 2026-05-10\n"
		"- second\n"
		"\n"
	)
	with pytest.raises(ValueError):
		changelog_lib.parse_day_blocks(text, duplicate_policy="raise")


#============================================
# split_day_block


def test_split_day_block_orphan_bullet_gets_uncategorized_and_warns():
	# bullet appears before any ### heading
	raw_text = (
		"## 2026-05-10\n"
		"- orphan bullet\n"
		"\n"
		"### Additions and New Features\n"
		"- normal bullet\n"
	)
	block = changelog_lib.DayBlock(
		date="2026-05-10",
		raw_text=raw_text,
		source="<test>",
		lineno=1,
	)
	entries, warnings = changelog_lib.split_day_block(block)
	# orphan bullet is classified Uncategorized
	orphan_entries = [e for e in entries if e.title == "orphan bullet"]
	assert len(orphan_entries) == 1
	assert orphan_entries[0].category == "Uncategorized"
	# exactly one orphan warning
	orphan_warnings = [w for w in warnings if "Uncategorized" in w]
	assert len(orphan_warnings) == 1


def test_split_day_block_strict_warns_on_noncanonical_category():
	raw_text = (
		"## 2026-05-10\n"
		"### Made Up Category\n"
		"- a bullet\n"
	)
	block = changelog_lib.DayBlock(
		date="2026-05-10",
		raw_text=raw_text,
		source="<test>",
		lineno=1,
	)
	_entries, warnings = changelog_lib.split_day_block(block, strict=True)
	bad_cat_warnings = [w for w in warnings if "Made Up Category" in w]
	assert len(bad_cat_warnings) == 1


def test_split_day_block_strict_off_does_not_warn_on_noncanonical():
	raw_text = (
		"## 2026-05-10\n"
		"### Made Up Category\n"
		"- a bullet\n"
	)
	block = changelog_lib.DayBlock(
		date="2026-05-10",
		raw_text=raw_text,
		source="<test>",
		lineno=1,
	)
	_entries, warnings = changelog_lib.split_day_block(block, strict=False)
	bad_cat_warnings = [w for w in warnings if "Made Up Category" in w]
	assert bad_cat_warnings == []


#============================================
# write_changelog round-trip


def test_write_changelog_roundtrip(tmp_path):
	# parse, write to disk, re-read, re-parse; block lists must match after
	# accounting for the documented trailing-newline normalization on the
	# very last block (zero-or-many trailing newlines collapse to exactly one).
	preamble, blocks, _warnings = changelog_lib.parse_day_blocks(SIMPLE_CHANGELOG)
	out_path = str(tmp_path / "CHANGELOG.md")
	changelog_lib.write_changelog(out_path, preamble, blocks)
	reread_text = changelog_lib.read_changelog(out_path)
	_preamble2, blocks2, _warnings2 = changelog_lib.parse_day_blocks(reread_text)
	# every block except the last is byte-identical
	assert blocks2[:-1] == blocks[:-1]
	# the last block's raw_text matches after collapsing trailing newlines
	last_in = blocks[-1].raw_text.rstrip("\n") + "\n"
	last_out = blocks2[-1].raw_text.rstrip("\n") + "\n"
	assert last_in == last_out
	# other fields on the last block are unchanged
	assert blocks2[-1].date == blocks[-1].date
	assert blocks2[-1].source == blocks[-1].source
	assert blocks2[-1].lineno == blocks[-1].lineno


#============================================
# Final-newline normalization


def test_write_changelog_normalizes_zero_trailing_newlines(tmp_path):
	# preamble + a single block, with the block's raw_text ending in zero newlines
	block = changelog_lib.DayBlock(
		date="2026-05-10",
		raw_text="## 2026-05-10\n- bullet without trailing newline",
		source="<test>",
		lineno=1,
	)
	out_path = str(tmp_path / "zero.md")
	changelog_lib.write_changelog(out_path, "", [block])
	with open(out_path, "rb") as handle:
		content = handle.read()
	# exactly one trailing newline byte
	assert content.endswith(b"\n")
	assert not content.endswith(b"\n\n")


def test_write_changelog_normalizes_three_trailing_newlines(tmp_path):
	# raw_text ends in three newlines; output should collapse to one
	block = changelog_lib.DayBlock(
		date="2026-05-10",
		raw_text="## 2026-05-10\n- bullet\n\n\n",
		source="<test>",
		lineno=1,
	)
	out_path = str(tmp_path / "three.md")
	changelog_lib.write_changelog(out_path, "", [block])
	with open(out_path, "rb") as handle:
		content = handle.read()
	assert content.endswith(b"\n")
	assert not content.endswith(b"\n\n")


#============================================
# find_duplicate_dates


def test_find_duplicate_dates_empty_for_clean_input():
	blocks = [
		changelog_lib.DayBlock(date="2026-05-10", raw_text="", source="<t>", lineno=1),
		changelog_lib.DayBlock(date="2026-05-09", raw_text="", source="<t>", lineno=2),
	]
	assert changelog_lib.find_duplicate_dates(blocks) == []


def test_find_duplicate_dates_returns_dupes_in_input_order_deduped():
	# build manually so duplicates survive (parse_day_blocks deduplicates by policy)
	blocks = [
		changelog_lib.DayBlock(date="2026-05-10", raw_text="", source="<t>", lineno=1),
		changelog_lib.DayBlock(date="2026-05-09", raw_text="", source="<t>", lineno=2),
		changelog_lib.DayBlock(date="2026-05-10", raw_text="", source="<t>", lineno=3),
		changelog_lib.DayBlock(date="2026-05-10", raw_text="", source="<t>", lineno=4),
		changelog_lib.DayBlock(date="2026-05-09", raw_text="", source="<t>", lineno=5),
	]
	# 2026-05-10 appears three times, 2026-05-09 twice; both reported once,
	# in the order their second occurrence is encountered
	assert changelog_lib.find_duplicate_dates(blocks) == ["2026-05-10", "2026-05-09"]


#============================================
# newest_date


def test_newest_date_returns_first_block_date():
	blocks = [
		changelog_lib.DayBlock(date="2026-05-10", raw_text="", source="<t>", lineno=1),
		changelog_lib.DayBlock(date="2026-05-09", raw_text="", source="<t>", lineno=2),
	]
	assert changelog_lib.newest_date(blocks) == "2026-05-10"


def test_newest_date_returns_none_for_empty_list():
	# direct call with [] confirms no file is read (no path argument exists)
	assert changelog_lib.newest_date([]) is None
