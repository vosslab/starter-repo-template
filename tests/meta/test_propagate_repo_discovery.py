"""Test that repo discovery walks .git directories at proper depth and respects skip list."""
import os
import sys


def test_propagate_repo_discovery_depth_and_skip(tmp_path):
	"""Verify depth 1-3 detection, max depth 3 enforcement, and skip-list override behavior."""
	# Create fake repo structure
	# Depth 1
	repo_a = tmp_path / 'repo_a'
	repo_a.mkdir()
	(repo_a / '.git').mkdir()

	repo_b = tmp_path / 'repo_b'
	repo_b.mkdir()
	(repo_b / '.git').mkdir()

	# Depth 2
	group = tmp_path / 'group'
	group.mkdir()

	repo_c = group / 'repo_c'
	repo_c.mkdir()
	(repo_c / '.git').mkdir()

	repo_d = group / 'repo_d'
	repo_d.mkdir()
	(repo_d / '.git').mkdir()

	# Depth 4 (should NOT be detected, exceeds max depth 3)
	deep = tmp_path / 'x' / 'y' / 'z' / 'w'
	deep.mkdir(parents=True)
	(deep / '.git').mkdir()

	# Get propagator script path
	script_dir = os.path.dirname(os.path.abspath(__file__))
	repo_root = os.path.dirname(os.path.dirname(script_dir))

	# Import propagator to test directly
	sys.path.insert(0, repo_root)
	import propagate_style_guides as pg

	# Test discovery
	repos = pg.collect_repo_dirs(str(tmp_path), None)
	repo_names = [os.path.basename(r) for r in repos]

	# Assert depth 1 and 2 repos are found
	assert 'repo_a' in repo_names, f"repo_a at depth 1 should be found; got {repo_names}"
	assert 'repo_b' in repo_names, f"repo_b at depth 1 should be found; got {repo_names}"
	assert 'repo_c' in repo_names, f"repo_c at depth 2 should be found; got {repo_names}"
	assert 'repo_d' in repo_names, f"repo_d at depth 2 should be found; got {repo_names}"

	# Assert depth 4 is NOT found
	assert 'w' not in repo_names, f"depth 4 repo should NOT be found; got {repo_names}"

	# Test skip list
	skip_repo = tmp_path / 'starter-repo-template'
	skip_repo.mkdir()
	(skip_repo / '.git').mkdir()

	repos = pg.collect_repo_dirs(str(tmp_path), None)
	repo_names = [os.path.basename(r) for r in repos]
	assert 'starter-repo-template' not in repo_names, f"starter-repo-template should be skipped; got {repo_names}"

	# Test explicit --repo overrides skip list (resolve_target_repo is in propagate.repo)
	import propagate.repo
	target = propagate.repo.resolve_target_repo(str(tmp_path), 'starter-repo-template')
	assert target == str(skip_repo), f"explicit --repo should override skip list; got {target}"


def test_propagate_repo_discovery_respects_max_depth(tmp_path):
	"""
	Verify that max depth of 3 is enforced: depth 1, 2, 3 repos found; depth 4+ not found.
	"""
	# Create test structure at varying depths
	# Depth 1: a
	a = tmp_path / 'a'
	a.mkdir()
	(a / '.git').mkdir()

	# Depth 2: b/c
	b = tmp_path / 'b'
	b.mkdir()
	c = b / 'c'
	c.mkdir()
	(c / '.git').mkdir()

	# Depth 3: d/e/f
	d = tmp_path / 'd'
	d.mkdir()
	e = d / 'e'
	e.mkdir()
	f = e / 'f'
	f.mkdir()
	(f / '.git').mkdir()

	# Depth 4: g/h/i/j (should not be found)
	g = tmp_path / 'g'
	g.mkdir()
	h = g / 'h'
	h.mkdir()
	i = h / 'i'
	i.mkdir()
	j = i / 'j'
	j.mkdir()
	(j / '.git').mkdir()

	# Import and test
	script_dir = os.path.dirname(os.path.abspath(__file__))
	repo_root = os.path.dirname(os.path.dirname(script_dir))
	sys.path.insert(0, repo_root)
	import propagate_style_guides as pg

	repos = pg.collect_repo_dirs(str(tmp_path), None)
	repo_names = [os.path.basename(r) for r in repos]

	assert 'a' in repo_names, "depth 1 should be found"
	assert 'c' in repo_names, "depth 2 should be found"
	assert 'f' in repo_names, "depth 3 should be found"
	assert 'j' not in repo_names, "depth 4 should NOT be found"
