# Architecture

## The Body/Brain split

Hermclaw is organized around the same split its two source projects each embodied separately:

- **Body** (`hermclaw/body/`) is the part of the system concerned with *being reachable and staying alive*: a gateway process, pluggable channel adapters, a scheduler. This is OpenClaw's territory.
- **Brain** (`hermclaw/brain/`) is the part concerned with *reasoning and remembering*: the tool-calling loop, persistent memory, context compression, reflection, and skill growth. This is Hermes Agent's territory.

Everything under `hermclaw/skills/`, `hermclaw/tools/`, and `hermclaw/security/` is genuinely shared infrastructure that both layers depend on -- the skill format, the tool-execution/approval system, and secret handling aren't "Body" or "Brain" concerns specifically, they're cross-cutting.

The split is deliberately not a service boundary. Body and Brain run in the same process, same Python runtime, sharing the same event loop -- there is no IPC between them. That's what makes `pipx install hermclaw` a one-command install instead of "install two things and wire them together."

## Repo layout

```
hermclaw/
  cli.py                    unified CLI: chat, serve, doctor, reflect, skills
  config.py                 schema, load/save/validate, LKG, hot-reload watcher
  config_defaults.py        single source of truth for the default/example config
  runtime.py                builds one fully-wired HermclawAgent for a profile
  observability.py          structlog setup: JSON to file, pretty to console, redacted

  body/
    gateway.py               owns the HTTP control API + every channel + the scheduler
    scheduler.py              heartbeat + cron jobs via APScheduler
    agents_registry.py        multi-identity routing (agent.list)
    mcp_client.py              wraps remote MCP tools as Hermclaw Tools
    channels/
      base.py                  ChannelAdapter ABC every channel implements
      cli_channel.py, web.py, telegram.py, discord.py, slack.py, whatsapp.py
      whatsapp_sidecar/         Node/Baileys bridge (the one non-Python piece)

  brain/
    agent_loop.py              HermclawAgent: the tool-calling loop
    profiles.py                profile isolation + SOUL.md/MEMORY.md/USER.md
    reflection.py               distills sessions into memory + draft skills
    skill_growth.py             Tier 1 (always-on) + Tier 2 (optional) skill evolution
    memory/
      store.py, schema.sql       SQLite + FTS5, one file per profile
      compressor.py               context compression at a configurable threshold
    transports/
      base.py, fake.py            ProviderTransport ABC + the offline test double
      anthropic.py, openai_compat.py, bedrock.py

  skills/                     agentskills.io SKILL.md parsing + registry
  tools/                      Tool ABC, approvals, shell tool, execution backends
  security/                   secret redaction, filesystem scope, permission checks

tests/                        pytest suite -- see "Testing" below
docs/                         CONFIG_REFERENCE.md, SKILL_AUTHORING.md
```

## Traceability

Every module below maps back to a specific feature prompt in the build specification (`hermclaw_master_build_prompt.md`) it was built from:

| Area | Spec section | Module(s) |
|---|---|---|
| Gateway daemon | C.1.1 | `body/gateway.py` |
| Config system | C.1.2 | `config.py`, `config_defaults.py` |
| Channel adapters | C.1.3 | `body/channels/` |
| Scheduler | C.1.4 | `body/scheduler.py` |
| Multi-agent routing | C.1.5 | `body/agents_registry.py` |
| doctor / serve CLI | C.1.6 | `cli.py` (`doctor`, `serve`) |
| Secrets handling | C.1.7 | `security/secrets.py` |
| MCP client | C.1.8 | `body/mcp_client.py` |
| Agent loop | C.2.1 | `brain/agent_loop.py` |
| Provider transport | C.2.2 | `brain/transports/` |
| SQLite memory | C.2.3 | `brain/memory/store.py`, `schema.sql` |
| Context compressor | C.2.4 | `brain/memory/compressor.py` |
| Identity/fact files | C.2.5 | `brain/profiles.py` (`IdentityFiles`) |
| Reflection loop | C.2.6 | `brain/reflection.py` |
| Profile isolation | C.2.7 | `brain/profiles.py` (`ProfileManager`) |
| Skill growth engine | C.2.8 | `brain/skill_growth.py` |
| chat / reflect CLI | C.2.9 | `cli.py` (`chat`, `reflect`), `runtime.py` |
| Skill system | C.3.1 | `skills/` |
| Unified config schema | C.3.2 | `config.py` (`HermclawConfig`) |
| Unified CLI entrypoint | C.3.3 | `cli.py` |
| Security/tool execution | C.3.4 | `tools/`, `security/permissions.py` |
| Logging | C.3.5 | `observability.py` |
| Packaging | C.3.6 | `pyproject.toml` |

Part D (testing strategy, documentation, MERGE_DECISIONS.md) and Part E (final assembly) are addressed by `tests/`, this document plus `docs/`, `MERGE_DECISIONS.md`, and this repo's overall integration respectively.

## Security posture

The single biggest deliberate departure from both source projects: **`tools.shell_enabled` defaults to `false`.** Neither OpenClaw nor Hermes Agent defaults to safe shell settings out of the box. Hermclaw does, on the theory that a personal agent with silent, unscoped shell access by default is the single riskiest thing about this whole category of software, and "secure by default, opt in to power" is a better posture than the reverse.

When shell access is on:

- **Approvals default to `manual`** -- every command asks first, until you explicitly choose `smart` (a lightweight risk classifier decides) or `off` (nothing asks, but see the next point).
- **A hardline pattern set is enforced unconditionally, including in `off` mode.** Catastrophic, essentially-never-legitimate commands (`rm -rf /`, wiping the state database, etc.) are blocked regardless of approval mode. A separate "dangerous" pattern set (e.g. an unscoped `DELETE`/`UPDATE` with no `WHERE`) requires approval in `manual`/`smart` mode but is *not* hardline-blocked, since there are legitimate reasons to want that in `off` mode deliberately.
- **`tools.filesystem_scope` is enforced differently depending on backend.** For `backend: docker`, it's a real boundary -- the container gets exactly one bind mount (the scope directory) and nothing else on the host, which is the strongest guarantee this design can offer. For `backend: local`, it's used as the subprocess's working directory, which is a meaningful signal but not a real sandbox -- arbitrary shell commands can still reference paths outside it. If you need a hard filesystem boundary, use the `docker` backend.
- **Secrets are never held as literal values in config.** Every credential field in `hermclaw.yaml` is a `*_env` reference to an environment variable name, resolved lazily at the point of use and never persisted back to disk. `GET /config` and every log line pass through the same redaction step.

## Known limitations

- **Telegram, Discord, Slack, and WhatsApp adapters are real, complete implementations against their actual client libraries, but were not exercised against live accounts during this build** -- doing so would require real bot tokens/API credentials this environment doesn't have. They're tested by injecting a lightweight fake of each library's underlying client object and verifying the adapter's own wiring (message translation, handler registration, send/receive) end to end; see `tests/contracts/test_channel_adapter.py`.
- **Tier 2 skill evolution ships a working heuristic loop, not the originally-envisioned DSPy+GEPA pipeline.** `SkillEvolutionEngine.evolve_skill()` is real, functional v1 behavior; `evolve_with_gepa()` is an explicitly scoped v2 extension point that raises `NotImplementedError` rather than silently doing nothing. See MERGE_DECISIONS.md.
- **`singularity`, `modal`, and `daytona` tool backends are stubs** that raise `NotImplementedError` with a clear message, per the build spec's explicit allowance for out-of-scope-for-v1 backends. `local` and `docker` are fully implemented.
- **The heartbeat interval precedence chain (per-account > per-channel > profile > global) is implemented as a function, but only the global tier is currently populated by the config schema** -- `body.scheduler.heartbeat` is one setting, not yet broken out per-channel/per-account. The function accepts those tiers as forward-compatible parameters for whenever the schema grows to support them.
