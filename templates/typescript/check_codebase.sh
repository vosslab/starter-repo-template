#!/usr/bin/env bash
# This file is vendored. Local changes can and will be overwritten by propagation.

# Run TypeScript type checks, lint, formatting, and Node unit tests (no build).
set -euo pipefail

usage() {
	printf '%s\n' "Usage: check_codebase.sh [-h|--help]" "" \
		"  -h, --help  Print this help and exit 0."
}

while [ "$#" -gt 0 ]; do
	case "$1" in
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "ERROR: unknown flag: $1" >&2
			usage >&2
			exit 2
			;;
	esac
done

cd "$(git rev-parse --show-toplevel)"

if ! command -v node >/dev/null 2>&1; then
	echo "ERROR: node not found on PATH." >&2
	exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
	echo "ERROR: npm not found on PATH." >&2
	exit 1
fi

echo "node $(node --version), npm $(npm --version)"

if [ ! -f package.json ]; then
	echo "ERROR: package.json missing." >&2
	exit 1
fi

if [ ! -d node_modules ]; then
	echo "ERROR: node_modules missing. Run 'npm install' first." >&2
	exit 1
fi

if [ ! -f .prettierignore.local ]; then
	echo "ERROR: .prettierignore.local missing." >&2
	exit 1
fi

if [ ! -f package-lock.json ]; then
	echo "WARN: package-lock.json missing; npm install will not produce a reproducible install." >&2
fi

echo "==> typecheck"
./node_modules/.bin/tsc --noEmit -p tsconfig.json

# tsconfig.lint.json covers TypeScript in tests/ and tools/.
lint_dirs=()
[ -d tests ] && lint_dirs+=(tests)
[ -d tools ] && lint_dirs+=(tools)
if [ "${#lint_dirs[@]}" -gt 0 ] && \
	find "${lint_dirs[@]}" -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.mts' -o -name '*.cts' \) \
	-print -quit | grep -q .; then
	echo "==> typecheck:lint"
	./node_modules/.bin/tsc --noEmit -p tsconfig.lint.json
else
	echo "==> SKIP typecheck:lint (no TypeScript under tests/ or tools/)"
fi
echo "==> lint"
./node_modules/.bin/oxlint --type-aware \
	--ignore-pattern 'node_modules/**' \
	--ignore-pattern 'dist/**' \
	--ignore-pattern 'dist_*/**' \
	--ignore-pattern '**/dist_*/**' \
	--ignore-pattern 'OTHER_REPOS/**' \
	--ignore-pattern '_temp*' \
	--ignore-pattern '**/_temp*' .
echo "==> format:check"
	./node_modules/.bin/prettier --check --ignore-path .gitignore --ignore-path .prettierignore \
	--ignore-path .prettierignore.local '**/*.{ts,tsx,mts,cts,js,mjs,cjs}'
if compgen -G 'tests/test_*.mjs' >/dev/null; then
	echo "==> test:node"
	node --import tsx --test 'tests/test_*.mjs'
else
	echo "==> SKIP test:node (no tests/test_*.mjs files present)"
fi
echo "PASS: codebase checks passed."
