#!/usr/bin/env bash
# This file is vendored. Local changes can and will be overwritten by propagation.

# Validate the reviewed Cargo.lock resolution before preparing a source release.
set -euo pipefail

if (( $# != 0 )); then
	if [[ "$1" == "-h" || "$1" == "--help" ]] && (( $# == 1 )); then
		echo "Usage: $0"
		exit 0
	fi
	echo "Usage: $0" >&2
	exit 2
fi

REPOSITORY="$(git rev-parse --show-toplevel)"
readonly REPOSITORY
cd "$REPOSITORY"
source source_me.sh

python3 devel/check_rust_release_metadata.py
cargo fmt --all --check
cargo check --workspace --all-targets --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --all-targets --locked
cargo build --workspace --release --locked
