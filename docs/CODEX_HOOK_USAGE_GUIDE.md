# Codex Hook Usage Guide

This project provides a Rust `PreToolUse` policy hook for Codex. It classifies
intercepted Bash commands, `apply_patch` calls, and supported MCP calls as
allow, deny, or passthrough while writing bounded audit records.

The checked-in [Codex hook reference](codex-hook-guide.md) is the source for
the lifecycle protocol used by this implementation. The current online version
is available at <https://learn.chatgpt.com/docs/hooks>.

## Runtime model

Codex sends one JSON object to the hook on standard input. For `PreToolUse`, the
important fields are `session_id`, nullable `transcript_path`, `cwd`,
`hook_event_name`, `tool_name`, and `tool_input`. Codex may also send fields such
as `turn_id`, `tool_use_id`, `model`, and `permission_mode`.

The hook returns one of three outcomes:

| Policy result | Codex behavior |
| --- | --- |
| Deny | Emits a denial with a positive recovery reason. |
| Allow | Emits no output, preserving Codex's normal permission flow. |
| Passthrough | Emits no output, preserving Codex's normal permission flow. |

The active Codex profile evaluates deny rules before allow rules. A compound
Bash command is decomposed into simple commands; any denied component rejects
the entire call, and every component must match an allow rule for the entire
call to be classified as allow. Passthrough is the last-ditch result for a call
that the policy cannot yet justify allowing or denying.

## Build

```bash
cargo build --release
cargo test
```

The binary is `target/release/codex-code-permissions-hook`.

## Choose the policy

The repository keeps two full policy files with the same TOML structure:

- [codex-code-permissions-hook.toml](../codex-code-permissions-hook.toml) uses
  Codex tool names and lifecycle behavior.
- [example.toml](../example.toml) retains the Claude-compatible tool profile
  used to review the intentional semantic differences between the policies.

The policy is intentionally separate from Codex's hook registration. It holds
the command matchers, audit paths, command-chain limit, and protected Git branch
names.

## Register with Codex

Codex discovers hooks in `~/.codex/hooks.json`, `<repo>/.codex/hooks.json`, or
the equivalent inline `[hooks]` section of `config.toml`. Copy the
[config.toml.example](../config.toml.example) content into
`~/.codex/config.toml`, then replace the executable and repository paths when
using a different checkout location.

Codex project hooks run only for trusted project `.codex/` layers. Non-managed
command hooks also require review of the exact hook definition. Use `/hooks` in
Codex CLI to inspect and trust the hook after adding or changing it.

Multiple matching hooks run concurrently. This policy hook therefore cannot
prevent a second matching hook from starting.

## Supported Codex calls

The current Codex hook API exposes these `PreToolUse` categories:

- `Bash`, with the command in `tool_input.command`.
- `apply_patch`, also with patch text in `tool_input.command`.
- MCP tools, with their arguments in `tool_input`.

Codex currently intercepts only simple shell calls. Its richer unified execution
path is not completely covered, and web search plus other non-shell, non-MCP
tools are outside `PreToolUse`. Treat this hook as a useful guardrail, not a
complete security boundary.

## Audit files

The active Codex profile uses `audit_level = "all"` and writes every intercepted
call to `/tmp/codex-tool-use.json` as JSON Lines, independent of whether its
decision is allow, passthrough, or deny. Use `audit_level = "matched"` for
matched calls only or `"off"` to disable the main audit log. The optional
passthrough log is useful for finding allow-policy gaps.

Long strings in audit entries are truncated. Audit write failures are logged as
warnings and do not crash Codex.

## Verification

Run the full policy gate after changing either policy or the decision corpus:

```bash
./config_test.sh
```

This builds the release binary, runs the Rust tests, validates the active Codex
policy, checks the reviewed Codex/Claude semantic difference, and executes every
case in [command_decisions.tsv](../tests/command_decisions.tsv). Any policy and
fixture disagreement makes the command fail.

Validate the policy and exercise a realistic Codex input directly:

```bash
target/release/codex-code-permissions-hook validate \
  --config codex-code-permissions-hook.toml

printf '%s' '{"session_id":"test","transcript_path":null,"cwd":"/tmp","hook_event_name":"PreToolUse","turn_id":"turn","tool_name":"Bash","tool_use_id":"tool","tool_input":{"command":"bash -n script.sh"},"model":"gpt-5","permission_mode":"default"}' \
  | target/release/codex-code-permissions-hook run \
      --config codex-code-permissions-hook.toml
```

The second command should emit a denial reason and write an audit record with
decision `deny`. A command matching no allow or deny rule exits successfully
without standard output and remains available for normal user approval.
