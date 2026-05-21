"""Test that every propagation plan entry has a corresponding source file."""
import os
import sys


def test_propagate_spec_all_entries_resolve_to_source():
	"""Every propagation plan entry across all buckets resolves to an existing source file."""
	script_dir = os.path.dirname(os.path.abspath(__file__))
	repo_root = os.path.dirname(os.path.dirname(script_dir))

	# Import the propagator modules
	sys.path.insert(0, repo_root)
	import propagate.model
	import propagate.files

	for repo_type in ('python', 'typescript', 'rust', 'other'):
		plan = propagate.files.compute_propagation_plan(repo_root, repo_type)
		for bucket, entries in plan.items():
			if bucket == 'gitignore_block':
				continue
			for entry in entries:
				source_path = propagate.model.source_path_for_bucket(repo_root, bucket, entry, repo_type=repo_type)
				assert os.path.isfile(source_path), f"[{repo_type}] {bucket} {entry!r}: {source_path}"
