# Merge Decisions

This document explains every point where Hermclaw had to pick one resolution between OpenClaw's approach, Hermes Agent's approach, or something new, and why. It also covers decisions that weren't originally about merging two projects, but that this build pass had to make regardless -- schema gaps, ambiguous acceptance criteria, and internal tensions within the build specification itself.

## A note on methodology

The build specification (`hermclaw_master_build_prompt.md`) instructs implementers to "re-verify current behavior against the live OpenClaw and Hermes Agent repos/docs" before implementing each feature, and provides its own feature-parity matrix (Part B.3) as a starting hypothesis. This build pass implemented the full specification as given -- treating Part B's source grounding as the ground-truth reference material it's explicitly framed as -- rather than re-running independent live verification against the source repos during this pass. Where a decision below reflects that grounding, it's attributed to "OpenClaw" or "Hermes Agent" on that basis, not on a fresh independent check performed during this build. If those projects have since drifted, this document (and the code) may need a follow-up pass against their current state.

## Foundational

**Single Python runtime, not polyglot.** Both source projects' underlying languages (OpenClaw's TypeScript, Hermes Agent's Python) were candidates. Maintaining two runtimes would mean IPC between them, two toolchains, and would undermine the goal of `pipx install hermclaw` being a single command. Full Python was the correct call given that goal, at the cost of the Body layer being a reimplementation rather than a direct port of OpenClaw's TypeScript.

**`tools.shell_enabled` defaults to `false`.** Neither source project defaults to safe shell settings. This is Hermclaw's own, deliberate default -- see ARCHITECTURE.md's security section.

## Config system

**LKG fallback only rescues an *established* install, not a first-ever broken file.** The spec states both that an invalid config should "refuse to start the Brain/Body subsystems... keep only diagnostic commands available" and, separately, that "killing and restarting picks up the last-known-good config." These are only in tension if "invalid" always means the same thing. Resolved as: if there's no last-known-good copy yet (nothing was ever successfully loaded), an invalid file gets the refuse-to-boot treatment exactly as written. If a last-known-good copy exists (this install has booted successfully before), a subsequently-broken live file falls back to it automatically, so a crash mid-write or a bad hand-edit doesn't take down a working install. `ConfigLoadResult.source` reports which happened (`"primary"`, `"lkg"`, or `"defaults"`) so this is never silent.

**Hot-reload via mtime polling, not an OS file-event API.** inotify/FSEvents/ReadDirectoryChangesW would need an extra dependency, behave differently per platform, and are awkward to unit test without touching a real filesystem-event backend. A short-interval mtime poll with a debounce window gets the same practical behavior (waiting out an editor's temp-write/rename churn before reloading) with no new dependency and a trivially injectable clock for tests.

## Memory schema

**`sessions.parent_session_id` is a schema extension beyond the spec's literal `schema.sql`.** The context compressor's requirement to "start a new continuation session row linked to the prior one for lineage" needs somewhere to put that link; the given schema didn't include one. Added as a nullable, foreign-keyed column -- purely additive, doesn't change any other field's meaning.

**`messages.compressed_away` is a similar addition.** Compressed-away messages are flagged rather than deleted, so `session_search` (FTS5) still finds them after compression -- deleting them would silently make old context unrecoverable via search, which isn't what "compression" should mean.

**`state.db` file permissions are tightened explicitly.** Python's stdlib `sqlite3` creates new files at the process umask (typically `0o644`) -- it doesn't restrict this itself. Since this file holds full conversation history, `MemoryStore` chmods it (and its WAL/SHM sidecars) to `0o600` right after creation, and `hermclaw doctor` checks it on every run.

## Security and tool execution

**Approval gate's "smart" mode ships a heuristic default classifier**, not a live model call, so approvals decisions stay testable offline and don't add a second in-flight model call (with its own latency and cost) to every tool invocation by default. The classifier is a pluggable interface; swapping in a transport-backed classifier for a real per-call risk assessment is a natural extension, not a redesign.

**`tools.filesystem_scope` is a real boundary for `backend: docker`, and a working-directory hint for `backend: local`.** A container can be given exactly one bind mount and nothing else on the host -- that's an actual sandbox. Arbitrary shell commands under the `local` backend cannot be meaningfully confined to a directory without OS-level sandboxing (chroot, namespaces, Landlock), which is out of scope here; setting it as the subprocess's working directory is honest about being a signal, not an enforcement boundary. If a hard filesystem boundary matters for a given use case, use `docker`.

**`singularity`, `modal`, and `daytona` tool backends are stubs.** Each raises `NotImplementedError` with a clear message and a tracking note, per the spec's explicit allowance for backends out of scope for v1. `local` and `docker` are fully implemented; `ssh` is implemented via the CLI's own SSH client rather than a bundled library, for the same "one less dependency" reasoning as the docker backend below.

**The docker tool backend shells out to the `docker` CLI via subprocess, not the `docker` Python SDK.** A subprocess call to `docker run` does the job without adding a dependency; the SDK would be a second way to do the same thing.

## Skill growth (reflection -> draft skills -> optional evolution)

**Semantic dedup uses a stemmed-Jaccard + sequence-match heuristic, not an embedding model.** The acceptance bar ("5 sessions with trivially-reworded procedures still produce exactly one skill, not five") needs *some* notion of semantic similarity beyond exact-text matching, but pulling in an embedding model (and the network call or extra dependency that implies) for one dedup check inside an otherwise fully offline draft-skill flow was a worse tradeoff than a combined heuristic that, in practice, cleanly separates same-procedure restatements (~0.6 similarity in testing) from genuinely different procedures (~0.3). The comparison is against the raw distilled description, not the boilerplate-augmented one written into the skill's frontmatter, since the added boilerplate diluted the signal in early testing. The function signature is a natural place to swap in embedding similarity later without touching call sites.

**Tier 2 skill evolution ships a working heuristic loop as real v1 behavior; DSPy+GEPA is a scoped v2 extension point.** `evolve_skill()` proposes a revised version of a skill's instructions via one model call and a basic sanity gate (non-empty, not wildly larger) -- functional today. `evolve_with_gepa()` exists as the documented home for the originally-envisioned DSPy+GEPA prompt-evolution pipeline and raises `NotImplementedError`; it's a stub with a clear signal, not a silent no-op, and critically, Tier 2 as a *feature* (`skills.evolution_enabled`) is genuinely functional without it.

## CLI

**`hermclaw status` doesn't exist as a sixth top-level command.** C.1.6 of the spec describes status-snapshot behavior (`hermclaw status`, `status --jobs`, `status --json` for token/cost totals) as part of introducing `doctor`/`serve`. C.3.3, the unified CLI entrypoint spec, is explicit that the CLI has "exactly five subcommands... and no others: chat, serve, doctor, reflect, skills," and its own dispatch table doesn't list `status` at all -- read together, C.3.3 supersedes the earlier draft. All status-shaped output (config validity, credentials, file permissions, skills, channel/profile summary) is folded into plain `hermclaw doctor`, with the global `--json` flag covering the machine-readable/scripting use case `status --json` would have served.

## Scheduler

**Heartbeat interval precedence (account > channel > profile > global > built-in default) is implemented as a function that accepts all four tiers, but the current config schema only populates the global one** (`body.scheduler.heartbeat`). Per-channel and per-account heartbeat overrides aren't yet a schema concept. `resolve_heartbeat_interval_s()` accepts the other tiers as optional parameters specifically so adding that schema support later doesn't require touching this function's logic, only its call site.

**Heartbeat delivery target uses "last contact" tracking, not a config field.** Nothing in the schema specifies who a proactive heartbeat alert or scheduled-job result should be sent *to* -- channels have fundamentally different addressing (chat IDs, user IDs, connection handles), so a single config field couldn't express it generically. The gateway tracks, per profile, the most recent `(channel, external_user_id)` that messaged it, and uses that as the delivery target for that profile's next heartbeat/job output. If nobody's talked to a given profile yet, there's nothing to send to, and that's logged rather than guessed at.

**Heartbeat response classification is convention-based (a `HEARTBEAT_OK` sentinel and a `[background]` prefix), not a dedicated tool call.** Giving the heartbeat turn its own extra tool would have meant threading an ad-hoc, single-purpose tool list through `HermclawAgent.run_turn()` for one scheduler feature. The three-way split (nothing to report / did something silently / needs the user) is expressed by asking the model to follow a simple textual convention instead, which the existing agent loop needs no changes to support.

## Multi-agent identity routing

**`agent.list` entries bind to messages via an optional `account` hint on `IncomingMessage`, not an explicit channel-binding field.** The spec's example config shows `id`/`identity`/`profile` per entry but no explicit channel-binding syntax. `AgentsRegistry.resolve_for_message(channel, account)` checks the hint (which a channel adapter can set from whatever platform-specific signal distinguishes multiple bot identities on that channel -- e.g. which bot token received the message) and falls back to the single default identity when absent, which is the common case.

## Transports

**OpenAI-compatible transport is built on raw `httpx`, not the `openai` SDK.** The point of this transport is supporting the wide range of servers that speak an OpenAI-compatible API without actually being OpenAI (vLLM, Ollama, LM Studio, OpenRouter, and others) -- a direct HTTP implementation generalizes better across their inevitable small deviations than a client library built against OpenAI's own service, and avoids a second full SDK dependency alongside `anthropic`.

**Bedrock transport uses the Converse API**, not each model family's bespoke `invoke_model` request body -- it's AWS's own current recommendation for a unified, tool-use-capable interface across model providers on Bedrock, and avoids Hermclaw needing per-model-family request translation.

**Internal messages use one canonical, Anthropic-shaped content-block format** (`{"type": "text"|"tool_use"|"tool_result", ...}`) that `agent_loop.py` and `brain/memory/compressor.py` build and read; every transport is responsible for converting to/from it on its own wire format. This was tightened during the build: the OpenAI-compatible and Bedrock transports initially assumed messages arrived already shaped for their own protocol, which was wrong and has since been fixed with an explicit conversion step in each.

## WhatsApp

**The WhatsApp channel bridges to a small Node.js sidecar over newline-delimited JSON-RPC on stdio**, rather than being pure Python like the rest of Hermclaw. Baileys is the mature, actively-maintained option for the WhatsApp Web protocol, and it's JavaScript-only -- there is no comparable pure-Python client to build against instead. This is a deliberate, narrowly-scoped exception, not a crack in the "one Python runtime" decision above: exactly one channel, isolated to its own subdirectory, communicating over a minimal protocol the Python side owns.

## MCP

**`mcp` is a core dependency, not an optional extra**, even though not every install will configure `skills.mcp_servers`. `body/mcp_client.py` is imported unconditionally by `runtime.py` (used by every profile, whether or not it ends up needing MCP), and the SDK itself is lightweight enough that gating it behind an extra for a marginal install-size savings wasn't worth the added complexity of a deferred-import path.

## Bugs the test suite caught during this build

Worth recording because they'd otherwise look like they were "always correct": the Discord and Slack channel adapters originally registered their message-handling callback only inside their own client/app-construction helper, which is skipped whenever a client or app is injected -- which every test does, and which any future caller supplying a pre-configured client would also do. The contract tests in `tests/contracts/test_channel_adapter.py` caught this (an injected fake client's handler was never wired up), and the fix separates "construct a client" from "register handlers on whatever client we have," with registration always running in `start()` regardless of where the client came from.
