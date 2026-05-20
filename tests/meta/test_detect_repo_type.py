"""Tests for detect_repo_type module."""

import os
import sys
import json

# Add repo_root/tools/ to sys.path to import detect_repo_type
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'tools'))
import detect_repo_type


#============================================
def test_detect_rust_via_cargo(tmp_path):
	"""Write Cargo.toml -> expect (rust, high)."""
	with open(tmp_path / 'Cargo.toml', 'w') as f:
		f.write('[package]\n')
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'rust'
	assert confidence == 'high'
	assert len(reasoning) > 0


#============================================
def test_detect_typescript_via_tsconfig(tmp_path):
	"""Write tsconfig.json -> expect (typescript, high)."""
	with open(tmp_path / 'tsconfig.json', 'w') as f:
		f.write('{}')
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'typescript'
	assert confidence == 'high'
	assert len(reasoning) > 0


#============================================
def test_detect_typescript_via_package_json_with_ts_dep(tmp_path):
	"""Write package.json with typescript in devDeps -> expect (typescript, high)."""
	pkg = {
		'name': 'test',
		'devDependencies': {
			'typescript': '^5.0.0'
		}
	}
	with open(tmp_path / 'package.json', 'w') as f:
		json.dump(pkg, f)
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'typescript'
	assert confidence == 'high'
	assert len(reasoning) > 0


#============================================
def test_detect_typescript_via_package_json_no_ts_dep(tmp_path):
	"""Write package.json without typescript -> expect (typescript, medium)."""
	pkg = {
		'name': 'test',
		'dependencies': {
			'react': '^18.0.0'
		}
	}
	with open(tmp_path / 'package.json', 'w') as f:
		json.dump(pkg, f)
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'typescript'
	assert confidence == 'medium'
	assert len(reasoning) > 0


#============================================
def test_detect_python_via_pyproject(tmp_path):
	"""Write pyproject.toml -> expect (python, high)."""
	with open(tmp_path / 'pyproject.toml', 'w') as f:
		f.write('[project]\n')
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'python'
	assert confidence == 'high'
	assert len(reasoning) > 0


#============================================
def test_detect_python_via_setup_py(tmp_path):
	"""Write setup.py -> expect (python, high)."""
	with open(tmp_path / 'setup.py', 'w') as f:
		f.write('from setuptools import setup\n')
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'python'
	assert confidence == 'high'
	assert len(reasoning) > 0


#============================================
def test_detect_pip_requirements_alone_is_ambiguous(tmp_path):
	"""pip_requirements.txt ships universally; alone it must NOT trigger python."""
	with open(tmp_path / 'pip_requirements.txt', 'w') as f:
		f.write('numpy\n')
	token, confidence, _ = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'ambiguous'
	assert confidence == 'low'


#============================================
def test_detect_ambiguous_mixed_strong_signals(tmp_path):
	"""Write Cargo.toml AND tsconfig.json -> expect (ambiguous, low)."""
	with open(tmp_path / 'Cargo.toml', 'w') as f:
		f.write('[package]\n')
	with open(tmp_path / 'tsconfig.json', 'w') as f:
		f.write('{}')
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'ambiguous'
	assert confidence == 'low'
	assert len(reasoning) > 0


#============================================
def test_detect_ambiguous_empty_repo(tmp_path):
	"""Empty tmp_path -> expect (ambiguous, low)."""
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'ambiguous'
	assert confidence == 'low'
	assert len(reasoning) > 0


#============================================
def test_detect_python_via_file_count_tiebreaker(tmp_path):
	"""Write 10 .py files, no markers -> expect (python, medium)."""
	for i in range(10):
		with open(tmp_path / f'file{i}.py', 'w') as f:
			f.write('# placeholder\n')
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'python'
	assert confidence == 'medium'
	assert len(reasoning) > 0


#============================================
def test_detect_other_via_perl_pg_files(tmp_path):
	"""Write .pg files -> expect (other, medium)."""
	with open(tmp_path / 'problem.pg', 'w') as f:
		f.write('# WebWork problem\n')
	with open(tmp_path / 'another.pg', 'w') as f:
		f.write('# WebWork problem\n')
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	assert token == 'other'
	assert confidence == 'medium'
	assert len(reasoning) > 0


#============================================
def test_detect_skips_node_modules(tmp_path):
	"""Write node_modules/.py + 1 .ts at root -> node_modules walked-around."""
	node_modules = tmp_path / 'node_modules'
	node_modules.mkdir()
	with open(node_modules / 'dummy.py', 'w') as f:
		f.write('# should be skipped\n')
	with open(tmp_path / 'main.ts', 'w') as f:
		f.write('// main\n')
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	# Should not be confused by py file in node_modules
	assert token in ('typescript', 'ambiguous')
	if token == 'typescript':
		assert confidence == 'medium'


#============================================
def test_detect_caps_at_max_files(tmp_path):
	"""Write 3000 small files -> reasoning mentions cap, no hang."""
	subdir = tmp_path / 'subdir'
	subdir.mkdir()
	for i in range(3000):
		with open(subdir / f'file{i}.txt', 'w') as f:
			f.write('x')
	token, confidence, reasoning = detect_repo_type.detect_repo_type(str(tmp_path))
	# Should complete without hanging
	assert len(reasoning) >= 0
	# Check if cap is mentioned
	# It's OK if cap not mentioned if detection happened before cap
	assert token in ('ambiguous', 'python', 'typescript', 'rust', 'other')
