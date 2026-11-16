"""Behavior checks for the propagated dependency-maintenance front door."""

# Standard Library
import os
import pathlib
import shutil
import stat
import subprocess

import file_utils


REPO_ROOT = pathlib.Path(file_utils.get_repo_root())
WRAPPER_SOURCE = REPO_ROOT / "templates" / "typescript" / "update_dependencies.sh"


#============================================
def make_executable(path: pathlib.Path) -> None:
	"""Add executable permission to one temporary shell file."""
	path.chmod(path.stat().st_mode | stat.S_IXUSR)


#============================================
def test_refresh_failure_skips_npm_stages(tmp_path: pathlib.Path) -> None:
	"""A failed refresh retains evidence and never audits or installs an old tree."""
	work = tmp_path / "project"
	(work / "devel").mkdir(parents=True)
	(work / "bin").mkdir()
	shutil.copy2(WRAPPER_SOURCE, work / "update_dependencies.sh")
	make_executable(work / "update_dependencies.sh")
	(work / "source_me.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
	(work / "package.json").write_text("{}\n", encoding="utf-8")
	updater = work / "devel" / "sync_typescript_package_pins.py"
	updater.write_text(
		"import pathlib, sys\n"
		"if '--select-only' in sys.argv:\n"
		" print(pathlib.Path('package.json').resolve())\n"
		"else:\n"
		" pathlib.Path('package.json').write_text('updated evidence')\n"
		" raise SystemExit(1)\n", encoding="utf-8",
	)
	checker = work / "devel" / "check_typescript_package_policy.py"
	checker.write_text("#!/usr/bin/env python3\nraise SystemExit(0)\n", encoding="utf-8")
	fake_npm = work / "bin" / "npm"
	fake_npm.write_text("#!/usr/bin/env bash\necho npm-called >&2\nexit 99\n", encoding="utf-8")
	make_executable(fake_npm)
	assert subprocess.run(["git", "init", "-q", str(work)], check=True).returncode == 0
	environment = dict(os.environ)
	environment["PATH"] = f"{work / 'bin'}:{environment['PATH']}"
	result = subprocess.run(
		["bash", "./update_dependencies.sh"], cwd=work, env=environment,
		capture_output=True, text=True,
	)
	assert result.returncode == 1
	assert "FAIL: refresh direct dependencies and overrides" in result.stderr
	assert (work / "package.json").read_text() == "updated evidence"
	assert "npm-called" not in result.stderr
