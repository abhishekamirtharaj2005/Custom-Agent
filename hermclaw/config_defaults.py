"""Single source of truth for Hermclaw's default/example config.

This string is written verbatim to ~/.hermclaw/hermclaw.yaml on first run
(config.py's write_default_config) AND to hermclaw.example.yaml at the
repo root (see scripts/generate_example_config.py), so the two can never
drift apart -- the example file the user reads IS the file that gets
written to disk on a fresh install.
"""

from __future__ import annotations

EXAMPLE_CONFIG_YAML = """\
# Hermclaw configuration
# Full reference: docs/CONFIG_REFERENCE.md
# Every *_env field names an ENVIRONMENT VARIABLE to read a secret from --
# never put a literal token/key/password anywhere in this file.

agent:
  name: "hermclaw"
  default_profile: "default"
  list: []                          # multi-identity entries (optional), e.g.:
                                     # - id: support
                                     #   identity: { name: "Helpdesk", emoji: "🎫" }
                                     #   profile: support_profile

body:
  gateway:
    bind: "loopback"                # loopback | all
    host: "127.0.0.1"
    port: 18789
    auth:
      mode: "token"
      token_env: "HERMCLAW_GATEWAY_TOKEN"

  channels:
    telegram:
      enabled: false
      bot_token_env: "TELEGRAM_BOT_TOKEN"
      mode: "polling"                # polling | webhook
    discord:
      enabled: false
      bot_token_env: "DISCORD_BOT_TOKEN"
    slack:
      enabled: false
      bot_token_env: "SLACK_BOT_TOKEN"
      app_token_env: "SLACK_APP_TOKEN"
      socket_mode: true
    cli:
      enabled: true
    web:
      enabled: false
    whatsapp:
      enabled: false                 # backed by the Node/Baileys sidecar

  scheduler:
    heartbeat:
      enabled: true
      every: "30m"
      show_ok: false
      show_alerts: true
    jobs: []                         # - cron: "0 9 * * *"
                                      #   prompt: "Summarize overnight activity"

brain:
  model:
    provider: "openai_compat"        # anthropic | openai_compat | bedrock
    model_name: "gemma4:12b"         # Ollama model
    api_key_env: "OLLAMA_API_KEY"     # not required by Ollama, but the field is needed
    api_base_env: "OLLAMA_API_BASE"   # set to http://localhost:11434/v1
    context_window: 131072
    fallbacks: []                    # - provider: "openai_compat"
                                      #   model_name: "llama-3.1-70b"
                                      #   api_key_env: "OPENAI_COMPAT_API_KEY"
                                      #   api_base_env: "OPENAI_COMPAT_API_BASE"
  memory:
    compression_threshold: 0.5       # fraction of context window that triggers compression
    keep_recent_exchanges: 2
    memory_char_limit: 2200
    user_char_limit: 1375
  reflection:
    enabled: true
    trigger_every_n_turns: 10        # learn faster from conversations

skills:
  directory: "~/.hermclaw/profiles/default/skills"
  extra_directories: []              # shared/team skill folders, read-only
  evolution_enabled: true            # auto-draft skills from repeated patterns
  mcp_servers: []                    # - name: "example"
                                      #   transport: "stdio"
                                      #   command: "npx some-mcp-server"

tools:
  shell_enabled: true                # full shell access enabled
  approvals:
    mode: "off"                      # no approval prompts -- runs everything directly
  backend: "local"                   # local | docker | ssh | singularity | modal | daytona
  docker_image: "python:3.11-slim"
  docker_network: "none"
  ssh_host: null
  ssh_user: null
  ssh_identity_file: null
  network_enabled: true
  filesystem_scope: "~"              # full access to home directory and below

profiles: {}                         # per-profile config overrides, keyed by profile name
"""
