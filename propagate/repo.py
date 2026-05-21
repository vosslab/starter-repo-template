"""Repository discovery and type detection."""

import os
import sys

import propagate.console
import propagate.model


#============================================
def is_repo_dir(repo_dir: str) -> bool:
	"""Return True if directory contains a .git entry, False otherwise."""
	return os.path.exists(os.path.join(repo_dir, '.git'))


#============================================
def read_repo_type(repo_path: str, single_repo_mode: bool = False, write_marker: bool = False, skip_confirm: bool = False, non_interactive: bool = False, counters: dict | None = None) -> str:
	"""Read REPO_TYPE marker file and return repository language type token.

	In single-repo mode with write_marker, predicts type and writes marker.
	In batch mode with missing marker, attempts detection; falls back to LANG_UNKNOWN.
	LANG_UNKNOWN gates language-specific file routing via should_ship_override;
	universal files still ship via walker.

	Returns token (python, typescript, rust, other, unknown).
	Raises ValueError if marker contains unknown token.

	Fallback to legacy STARTER_REPO_TYPE for backward compatibility.
	"""
	# Optional import: tools/detect_repo_type is present in template, removed at consumer bootstrap.
	detect_repo_type = None
	template_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	tools_dir = os.path.join(template_root, 'tools')
	if os.path.isdir(tools_dir) and os.path.isfile(os.path.join(tools_dir, 'detect_repo_type.py')):
		sys.path.insert(0, tools_dir)
		import detect_repo_type

	marker_path = os.path.join(repo_path, 'REPO_TYPE')
	legacy_marker_path = os.path.join(repo_path, 'STARTER_REPO_TYPE')

	# Check for legacy marker first if new marker doesn't exist
	if not os.path.isfile(marker_path) and os.path.isfile(legacy_marker_path):
		propagate.console.log_action("warn", f"{repo_path}: legacy STARTER_REPO_TYPE marker found; rename to REPO_TYPE")
		with open(legacy_marker_path, 'r', encoding='utf-8') as f:
			token = f.read().strip()
		if token not in ('python', 'typescript', 'rust', 'other'):
			raise ValueError(f"unknown STARTER_REPO_TYPE token {token!r} in {legacy_marker_path}")
		return token

	if not os.path.isfile(marker_path):
		# Missing marker: predict if conditions met, else default to python
		if single_repo_mode and write_marker and detect_repo_type:
			token, confidence, reasoning = detect_repo_type.detect_repo_type(repo_path)

			if confidence == 'high' and token != 'ambiguous':
				# High confidence: write silently
				write_repo_type_marker(marker_path, token, dry_run=False)
				propagate.console.log_action("skip", f"repo={os.path.basename(repo_path)} type={token} confidence=high (auto-wrote marker, predicted)", counters)
				return token

			if confidence == 'medium':
				# Medium confidence: print and ask
				propagate.console.log_action("warn", f"repo={os.path.basename(repo_path)} type={token} (predicted, medium confidence)")
				propagate.console.CONSOLE.print("  reasoning:")
				for bullet in reasoning:
					propagate.console.CONSOLE.print(f"    - {bullet}")

				if skip_confirm or non_interactive:
					# Accept silently
					write_repo_type_marker(marker_path, token, dry_run=False)
					propagate.console.log_action("skip", "wrote marker (medium confidence accepted)", counters)
					return token

				if not non_interactive:
					# Prompt user
					user_input = input(f"Accept predicted type '{token}'? [Y/n]: ").strip()
					if user_input == '' or user_input.lower() == 'y':
						write_repo_type_marker(marker_path, token, dry_run=False)
						return token
					else:
						# User rejected; re-prompt for explicit type
						while True:
							user_type = input(
								"Project type? [p]ython / [t]ypescript / [r]ust / [o]ther [p]: "
							).strip()
							chosen_type = parse_repo_type_choice(user_type, 'python')
							write_repo_type_marker(marker_path, chosen_type, dry_run=False)
							return chosen_type

			# Low confidence or ambiguous: abort if non-interactive, else prompt
			propagate.console.log_action("error", f"repo={os.path.basename(repo_path)} (ambiguous, could not predict)")
			propagate.console.CONSOLE.print("  reasoning:")
			for bullet in reasoning:
				propagate.console.CONSOLE.print(f"    - {bullet}")

			if non_interactive:
				raise ValueError("ambiguous repo type; specify REPO_TYPE manually or use reset_repo.py")

			# Interactive prompt for ambiguous
			while True:
				user_type = input(
					"Project type? [p]ython / [t]ypescript / [r]ust / [o]ther: "
				).strip()
				chosen_type = parse_repo_type_choice(user_type, None)
				if chosen_type is None:
					print("Invalid choice. Try again.")
					continue
				write_repo_type_marker(marker_path, chosen_type, dry_run=False)
				return chosen_type

		# Batch mode with missing marker: try detection, fall back to LANG_UNKNOWN.
		# LANG_UNKNOWN gates language-specific routing via should_ship_override;
		# universal walker-routed files still ship.
		if detect_repo_type:
			token, confidence, _reasoning = detect_repo_type.detect_repo_type(repo_path)
			if confidence == 'high' and token in (propagate.model.LANG_PYTHON, propagate.model.LANG_TYPESCRIPT, propagate.model.LANG_RUST, propagate.model.LANG_OTHER):
				return token
		return propagate.model.LANG_UNKNOWN

	with open(marker_path, 'r', encoding='utf-8') as f:
		token = f.read().strip()
	if token not in ('python', 'typescript', 'rust', 'other'):
		raise ValueError(f"unknown REPO_TYPE token {token!r} in {marker_path}")
	return token


#============================================
def write_repo_type_marker(path: str, token: str, dry_run: bool = False) -> bool:
	"""
	Write REPO_TYPE marker file.

	Args:
		path (str): Path to REPO_TYPE marker file.
		token (str): Canonical type token (python, typescript, rust, other).
		dry_run (bool): If True, do not write changes.

	Returns:
		bool: True if written, False on dry-run.
	"""
	content = token + '\n'
	if dry_run:
		propagate.console.log_action('create', path, dry_run=True)
		return False
	with open(path, 'w', encoding='utf-8') as f:
		f.write(content)
	return True


#============================================
def parse_repo_type_choice(text: str, default: str = None) -> str | None:
	"""
	Parse user input for repo type choice.

	Maps single-letter aliases and full words to canonical tokens.
	Unknown input returns default.

	Args:
		text (str): User input or single-letter choice.
		default (str): Default token if input is unrecognized.

	Returns:
		str: Canonical token (python, typescript, rust, other) or default.
	"""
	if not text:
		return default
	choice = text.strip().lower()
	if choice in ('p', 'python'):
		return 'python'
	if choice in ('t', 'typescript'):
		return 'typescript'
	if choice in ('r', 'rust'):
		return 'rust'
	if choice in ('o', 'other'):
		return 'other'
	return default


#============================================
def repo_is_on_path(repo_dir: str) -> bool:
	"""
	Check whether the repository directory is present in PATH.
	"""
	# Normalize repo_dir for comparison
	target = os.path.normcase(os.path.realpath(os.path.abspath(repo_dir)))
	path_env = os.environ.get('PATH', '')
	for path_entry in path_env.split(os.pathsep):
		if not path_entry:
			continue
		# Normalize path entry for comparison
		normalized_entry = os.path.normcase(os.path.realpath(os.path.abspath(path_entry)))
		if normalized_entry == target:
			return True
	return False


#============================================
def find_repo_root(start_dir: str) -> str | None:
	"""
	Find the nearest ancestor that contains the expected style guides or templates.

	Args:
		start_dir (str): Starting directory.

	Returns:
		str | None: Repo root path when found, otherwise None.
	"""
	current = os.path.abspath(start_dir)
	while True:
		# Check for canonical template overlay (post-WP-F3 architecture)
		if os.path.isdir(os.path.join(current, 'templates', 'typescript')):
			return current
		if os.path.isfile(os.path.join(current, 'docs', 'PYTHON_STYLE.md')):
			return current
		parent = os.path.dirname(current)
		if parent == current:
			return None
		current = parent


#============================================
def resolve_target_repo(base_dir: str, repo_name: str | None) -> str | None:
	"""
	Resolve and validate an optional single target repo under base_dir.

	Args:
		base_dir (str): Base directory that contains repos.
		repo_name (str | None): Optional repo directory name.

	Returns:
		str | None: Absolute repo path if provided, otherwise None.
	"""
	if not repo_name:
		return None
	target_repo = os.path.join(base_dir, repo_name)
	if not os.path.isdir(target_repo):
		raise FileNotFoundError(
			f"Repo not found under {base_dir}: {repo_name}"
		)
	if not is_repo_dir(target_repo):
		raise FileNotFoundError(
			f"Repo missing .git under {base_dir}: {repo_name}"
		)
	return target_repo


#============================================
def resolve_source_dir(base_dir: str, source_dir_arg: str | None) -> str:
	"""
	Resolve the source directory used for propagation.

	Args:
		base_dir (str): Base directory for default lookup.
		source_dir_arg (str | None): Optional user-provided source dir.

	Returns:
		str: Absolute source directory path.
	"""
	source_dir = source_dir_arg
	if source_dir is None:
		preferred_source = os.path.join(base_dir, 'starter_repo_template')
		if os.path.isdir(preferred_source):
			source_dir = preferred_source
		else:
			script_dir = os.path.dirname(os.path.abspath(__file__))
			detected_repo_root = find_repo_root(script_dir)
			if detected_repo_root is None:
				raise FileNotFoundError(
					"Default source dir not found. Provide --source-dir."
				)
			source_dir = detected_repo_root
	return os.path.abspath(os.path.expanduser(source_dir))


#============================================


