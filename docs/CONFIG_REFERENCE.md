# Configuration Reference

Every field in `hermclaw.yaml`, in one table. This file is kept honest by `tests/test_config_reference_coverage.py`, which diffs this table's field list against `HermclawConfig`'s actual pydantic schema and fails the build if they diverge -- so if a field is missing from this table, that's a bug, not a gap you need to work around.

**Source** reflects the architectural mapping in `ARCHITECTURE.md`: which of the two merged projects a field's underlying capability originates from, or whether it's a Hermclaw-original addition needed to unify them. It's an attribution for context, not a claim that the field is byte-for-byte identical to something in either source project.

Every `*_env` field names an **environment variable**, never a literal secret -- see `security/secrets.py`.

## agent

| Field | Type | Default | Source |
|---|---|---|---|
| `agent.name` | string | `"hermclaw"` | Hermclaw-original |
| `agent.default_profile` | string | `"default"` | Hermclaw-original |
| `agent.list` | list of identity entries (`id`, `identity.name`, `identity.emoji`, `profile`) | `[]` | Hermclaw-original -- multi-identity routing to unify Body's channel model with Brain's profile isolation |

## body.gateway

| Field | Type | Default | Source |
|---|---|---|---|
| `body.gateway.bind` | `"loopback"` \| `"all"` | `"loopback"` | Body / OpenClaw |
| `body.gateway.host` | string | `"127.0.0.1"` | Body / OpenClaw |
| `body.gateway.port` | int | `18789` | Body / OpenClaw |
| `body.gateway.auth.mode` | `"token"` | `"token"` | Body / OpenClaw |
| `body.gateway.auth.token_env` | string (env var name) | `"HERMCLAW_GATEWAY_TOKEN"` | Body / OpenClaw |

## body.channels

| Field | Type | Default | Source |
|---|---|---|---|
| `body.channels.telegram.enabled` | bool | `false` | Body / OpenClaw |
| `body.channels.telegram.bot_token_env` | string (env var name) | `"TELEGRAM_BOT_TOKEN"` | Body / OpenClaw |
| `body.channels.telegram.mode` | `"polling"` \| `"webhook"` | `"polling"` | Body / OpenClaw |
| `body.channels.telegram.webhook_url` | string \| null | `null` | Body / OpenClaw |
| `body.channels.discord.enabled` | bool | `false` | Body / OpenClaw |
| `body.channels.discord.bot_token_env` | string (env var name) | `"DISCORD_BOT_TOKEN"` | Body / OpenClaw |
| `body.channels.slack.enabled` | bool | `false` | Body / OpenClaw |
| `body.channels.slack.bot_token_env` | string (env var name) | `"SLACK_BOT_TOKEN"` | Body / OpenClaw |
| `body.channels.slack.app_token_env` | string (env var name) | `"SLACK_APP_TOKEN"` | Body / OpenClaw |
| `body.channels.slack.socket_mode` | bool | `true` | Body / OpenClaw |
| `body.channels.cli.enabled` | bool | `true` | Body / OpenClaw |
| `body.channels.web.enabled` | bool | `false` | Body / OpenClaw |
| `body.channels.whatsapp.enabled` | bool | `false` | Body / OpenClaw (bridged via a Node/Baileys sidecar -- see ARCHITECTURE.md) |
| `body.channels.whatsapp.sidecar_command` | string \| null | `null` (resolves to the bundled sidecar) | Hermclaw-original |

## body.scheduler

| Field | Type | Default | Source |
|---|---|---|---|
| `body.scheduler.heartbeat.enabled` | bool | `true` | Body / OpenClaw |
| `body.scheduler.heartbeat.every` | duration string (`30m`, `2h`, `45s`, `1d`) | `"30m"` | Body / OpenClaw |
| `body.scheduler.heartbeat.show_ok` | bool | `false` | Body / OpenClaw |
| `body.scheduler.heartbeat.show_alerts` | bool | `true` | Body / OpenClaw |
| `body.scheduler.jobs` | list of `{cron, prompt, id?}` | `[]` | Body / OpenClaw |

## brain.model

| Field | Type | Default | Source |
|---|---|---|---|
| `brain.model.provider` | `"anthropic"` \| `"openai_compat"` \| `"bedrock"` | `"anthropic"` | Brain / Hermes Agent |
| `brain.model.model_name` | string | `"claude-sonnet-4-6"` | Brain / Hermes Agent |
| `brain.model.api_key_env` | string (env var name) | `"ANTHROPIC_API_KEY"` | Brain / Hermes Agent |
| `brain.model.api_base_env` | string \| null (env var name) | `null` | Brain / Hermes Agent |
| `brain.model.context_window` | int (tokens) | `200000` | Hermclaw-original -- needed by the context compressor's threshold math |
| `brain.model.fallbacks` | list of model configs, tried in order on transport failure | `[]` | Brain / Hermes Agent |

## brain.memory

| Field | Type | Default | Source |
|---|---|---|---|
| `brain.memory.compression_threshold` | float, `0 < x <= 1` | `0.5` | Brain / Hermes Agent |
| `brain.memory.keep_recent_exchanges` | int | `2` | Brain / Hermes Agent |
| `brain.memory.memory_char_limit` | int | `2200` | Brain / Hermes Agent |
| `brain.memory.user_char_limit` | int | `1375` | Brain / Hermes Agent |

## brain.reflection

| Field | Type | Default | Source |
|---|---|---|---|
| `brain.reflection.enabled` | bool | `true` | Brain / Hermes Agent |
| `brain.reflection.trigger_every_n_turns` | int | `20` | Brain / Hermes Agent |

## skills

| Field | Type | Default | Source |
|---|---|---|---|
| `skills.directory` | path | `"~/.hermclaw/profiles/default/skills"` | Shared standard (agentskills.io), config surface Hermclaw-original |
| `skills.extra_directories` | list of paths (read-only, shared/team skills) | `[]` | Hermclaw-original |
| `skills.evolution_enabled` | bool | `false` | Brain / Hermes Agent (tracks a capability noted in Hermes Agent's own architecture) |
| `skills.mcp_servers` | list of `{name, transport, command?, url?}` | `[]` | Hermclaw-original -- unifies MCP tools with the shared Tool/approval system |

## tools

| Field | Type | Default | Source |
|---|---|---|---|
| `tools.shell_enabled` | bool | `false` | Hermclaw-original default (both source projects default this on) |
| `tools.approvals.mode` | `"manual"` \| `"smart"` \| `"off"` | `"manual"` | Hermclaw-original |
| `tools.backend` | `"local"` \| `"docker"` \| `"ssh"` \| `"singularity"` \| `"modal"` \| `"daytona"` | `"local"` | Hermclaw-original |
| `tools.docker_image` | string | `"python:3.11-slim"` | Hermclaw-original |
| `tools.docker_network` | string \| null | `"none"` | Hermclaw-original |
| `tools.ssh_host` | string \| null | `null` | Hermclaw-original |
| `tools.ssh_user` | string \| null | `null` | Hermclaw-original |
| `tools.ssh_identity_file` | string \| null | `null` | Hermclaw-original |
| `tools.network_enabled` | bool | `true` | Hermclaw-original |
| `tools.filesystem_scope` | path | `"~/.hermclaw/profiles/default/workspace"` | Hermclaw-original |

## profiles

| Field | Type | Default | Source |
|---|---|---|---|
| `profiles` | mapping of profile name -> per-profile config overrides | `{}` | Hermclaw-original |

## Top level

| Field | Type | Default | Source |
|---|---|---|---|
| `$schema` | string \| null | `null` | Hermclaw-original -- the one top-level key allowed alongside the five sections above; every other unknown top-level key is rejected |
