#!/usr/bin/env bash

set -euo pipefail

MODEL="qwen2.5-coder:7b-instruct"

ollama pull $MODEL

# Require execution from the Git repository root.
GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"

if [[ -z "$GIT_ROOT" ]]; then
	echo "Error: current directory is not inside a Git repository."
	exit 1
fi

if [[ "$PWD" != "$GIT_ROOT" ]]; then
	echo "Error: run this script from the repository root:"
	echo "  $GIT_ROOT"
	exit 1
fi

echo "Building Graphify graph for: $(basename "$GIT_ROOT")"

GRAPHIFY_ARGS=(extract . --code-only)

# Include Cargo workspace information when present.
if [[ -f Cargo.toml ]]; then
	GRAPHIFY_ARGS+=(--cargo)
fi

graphify "${GRAPHIFY_ARGS[@]}"

echo
echo "Labeling Graphify communities with Ollama..."

graphify label . \
	--backend=ollama \
	--model="$MODEL"

echo
graphify benchmark

echo
echo "======================================================================"
echo "GRAPHIFY READY"
echo "======================================================================"
echo
cat <<'EOF'
Give the following instruction to the AI agent manager:

Review the Graphify analysis for this repository before planning or
delegating work. Use graphify-out/GRAPH_REPORT.md and Graphify queries to
understand relevant subsystems, dependencies, and likely impact areas.

Use Graphify to narrow repository context before reading source broadly.
For the current task, identify the relevant communities, files, symbols,
dependency paths, and affected code. Use that information to create
focused task boundaries for subagents. Give each subagent only the
repository context needed for its assigned work.

Useful commands include:
  graphify query "<task or architectural question>" --budget 1500
  graphify explain "<symbol>"
  graphify affected "<symbol>" --depth 2
  graphify path "<symbol A>" "<symbol B>"
  graphify god-nodes --top 20

Treat Graphify as an architectural index and use source code as the final
source of truth when implementation details need confirmation.
EOF
