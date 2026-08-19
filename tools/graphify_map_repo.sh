#!/usr/bin/env bash

set -euo pipefail

MODEL="qwen2.5-coder:7b-instruct"
MODE="${1:-update}"

if [[ "$MODE" != "fresh" && "$MODE" != "update" && "$MODE" != "context" ]]; then
	echo "Usage: $0 [fresh|update|context]"
	echo "  fresh  - rebuild the Graphify graph from scratch"
	echo "  update - reuse existing graphify-out when available, then refresh labels/benchmarks"
	echo "  context - print AI-manager dispatch context only (no graphify work)"
	exit 1
fi

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

print_manager_context() {
echo "MANAGER CONTEXT (copy/paste for subagent dispatch):"
echo
echo "Repository root: $GIT_ROOT"
echo "Repository type token (REPO_TYPE): $(cat REPO_TYPE 2>/dev/null || echo '<missing>')"
echo "Git remote:"
git remote get-url origin 2>/dev/null || echo "  <no origin configured>"
echo
echo "Primary repo rules to preserve in every brief:"
echo "  - AGENTS.md"
echo "  - docs/REPO_STYLE.md"
echo "  - docs/PYTHON_STYLE.md"
echo "  - docs/MARKDOWN_STYLE.md"
echo "  - docs/PYTEST_STYLE.md"
echo
echo "Subagent-relevant manifests:"
echo "  - meta/propagation/manifests.yaml"
echo "  - meta/docs/REPO_TYPE.md"
echo "  - meta/propagation/deprecated_gitignore.txt"
echo "  - meta/propagation/deprecated_claude_md.txt"
echo "  - meta/propagation/deprecated_tests.txt"
echo
if [[ -d docs/active_plans ]]; then
	echo "Open plans:"
	ls docs/active_plans/{active,audits,reports,decisions,workstreams} 2>/dev/null | sed 's#^#  - #' || true
else
	echo "Open plans: docs/active_plans directory not present"
fi
echo
echo "Suggested delegation command list:"
echo "  graphify query \"what are the main risk areas and impacted files?\" --budget 1800"
echo "  graphify explain \"<symbol>\""
echo "  graphify affected \"<symbol>\" --depth 2"
echo
echo "Suggested task boundary template:"
cat <<'EOF'
{
  "plan_path": "<optional>",
  "task_text": "<exact scope text>",
  "evidence_gate": [
    "graphify-out/GRAPH_REPORT.md",
    "graphify query results",
    "graphify path/explain outputs"
  ],
  "owned_files": [],
  "verification": []
}
EOF
}

if [[ "$MODE" == "context" ]]; then
	print_manager_context
	exit 0
fi

ollama pull $MODEL

echo "Building Graphify graph for: $(basename "$GIT_ROOT") ($MODE)"

GRAPHIFY_ARGS=(extract . --code-only)
DO_FULL_EXTRACT=0
if [[ "$MODE" == "fresh" ]]; then
	DO_FULL_EXTRACT=1
elif [[ "$MODE" == "update" ]] && [[ ! -d graphify-out || ! -f graphify-out/GRAPH_REPORT.md ]]; then
	echo "No prior graphify output found; performing a fresh run."
	DO_FULL_EXTRACT=1
else
	echo "Existing graphify output found; updating labels and benchmarks."
fi

# Include Cargo workspace information when present.
if [[ -f Cargo.toml ]]; then
	GRAPHIFY_ARGS+=(--cargo)
fi

if (( DO_FULL_EXTRACT )); then
	graphify "${GRAPHIFY_ARGS[@]}"
fi

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

print_manager_context
