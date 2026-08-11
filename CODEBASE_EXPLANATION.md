# Exhaustive Hermclaw Codebase & File Directory Explanation

This document provides an **exhaustive, multi-section analysis of every single file** in the Hermclaw codebase (**119 files total**). No file has been omitted.

## System Architecture Summary

- **Body Layer (`hermclaw/body/`)**: Handles gateway hosting, multi-channel integrations (CLI, WebSockets, Telegram, Discord, Slack, WhatsApp), background task scheduling, and MCP client bridges.
- **Brain Layer (`hermclaw/brain/`)**: Core ReAct tool-calling loop (`HermclawAgent`), SQLite persistent memory (WAL mode, FTS5 search), dynamic context compression, self-reflection, and automated skill growth.
- **Security & Governance (`hermclaw/security/` & `hermclaw/tools/`)**: Enforces single-path tool execution (`ToolDispatcher`), secret redaction, audit logging, rate limiting, and filesystem path confinement.

---

## Root Repository & Configuration Files

### 1. `.gitignore`

- **File Type & Size**: Git Configuration File | 1,089 bytes | 65 lines
- **Architectural Role**: Repository cleanliness and secret protection.
- **Detailed Purpose & Implementation**: Defines exclude patterns for Git source control to prevent committing temporary build artifacts, bytecode, environment secrets, and local databases. Excludes Python cache directories (`__pycache__`, `*.pyc`), virtual environments (`.venv`, `env/`), Pytest artifacts (`.pytest_cache`), local SQLite databases (`*.db`, `state.db`), log files (`*.log`), and sensitive `.env` credential files.
- **Key Safety Rule**: Ensures no developer accidentally commits local profile state databases containing user chat logs or API secrets to remote repositories.

### 2. `ARCHITECTURE.md`

- **File Type & Size**: Technical Specification Document | 8,329 bytes | 192 lines
- **Architectural Role**: Primary architectural design document.
- **Detailed Purpose & Implementation**: Explains the foundational 'Body' vs 'Brain' split derived from merging OpenClaw and Hermes Agent. Describes how the Body layer (`hermclaw/body/`) manages connectivity, channel adapters (CLI, WebSockets, Telegram, Discord, Slack, WhatsApp), background task scheduling, and the gateway control process. Describes how the Brain layer (`hermclaw/brain/`) handles ReAct tool-calling loops, SQLite persistent memory with WAL-mode and FTS5 search, context compression, self-reflection, and skill growth. Also documents shared cross-cutting concerns: `agentskills.io` skill loading, single-path tool security (`ToolDispatcher`), secret resolution, and profile-based isolation.

### 3. `LICENSE`

- **File Type & Size**: Open-Source Legal License | 1,078 bytes | 21 lines
- **Architectural Role**: Open-source licensing compliance.
- **Detailed Purpose & Implementation**: Contains the standard MIT License text for Hermclaw, granting permissions for commercial and non-commercial use, modification, distribution, sublicensing, and private use, provided copyright notices remain intact.

### 4. `MERGE_DECISIONS.md`

- **File Type & Size**: Architectural Rationale Document | 13,746 bytes | 298 lines
- **Architectural Role**: Architectural decision record (ADR).
- **Detailed Purpose & Implementation**: Documents every critical decision where Hermclaw chose between OpenClaw's approach, Hermes Agent's approach, or a unified hybrid design. Key decisions documented include:
  1. *Config System*: Adopted OpenClaw's strict Pydantic validation and anti-clobber protection with ruamel.yaml comment preservation.
  2. *Memory & Storage*: Adopted Hermes Agent's per-profile SQLite database (`state.db`) in WAL mode with FTS5 episodic search instead of OpenClaw's ambient state.
  3. *Single Tool Path*: Forced all tools (including MCP and shell tools) through a single `ToolDispatcher` and approval gate to prevent sandboxed code-exec tools from bypassing approval checks via raw RPCs.
  4. *CLI Subcommands*: Restricted top-level CLI verbs to exactly five (`chat`, `serve`, `doctor`, `reflect`, `skills`) for simplicity.

### 5. `README.md`

- **File Type & Size**: Markdown Project Overview | 11,381 bytes | 285 lines
- **Architectural Role**: Public entry point and quickstart documentation.
- **Detailed Purpose & Implementation**: Provides a feature overview, installation instructions (`pip install hermclaw && hermclaw setup`), usage examples for CLI commands, multi-channel configuration guides, and architecture summary diagrams. Highlights Hermclaw's key capabilities: 28 builtin tools, self-learning reflection, multi-agent identity routing, and local-first execution.

### 6. `clawbert_status.json`

- **File Type & Size**: JSON State File | 202 bytes | 12 lines
- **Architectural Role**: Local state file for the virtual pet companion tool.
- **Detailed Purpose & Implementation**: Stores persistent state parameters for the built-in virtual pet companion (`Clawbert` the Hermit Crab). Tracks metrics including hunger (0-100), happiness (0-100), shell condition ("Shiny"), and ISO timestamps for when the pet was last fed or played with. Read and updated by `hermclaw/tools/virtual_pet.py`.

### 7. `hermclaw.example.yaml`

- **File Type & Size**: YAML Configuration Blueprint | 3,327 bytes | 98 lines
- **Architectural Role**: Default configuration template.
- **Detailed Purpose & Implementation**: Serves as the golden template written to `~/.hermclaw/hermclaw.yaml` upon initial setup. Outlines default settings: local Ollama LLM provider (`llama3.2`), enabled CLI channel, disabled external channels by default, standard approval mode (`manual`), and default memory compression thresholds.

### 8. `hermclaw_complete_features.md`

- **File Type & Size**: Comprehensive Feature Reference Catalog | 41,057 bytes | 985 lines
- **Architectural Role**: Master feature catalog.
- **Detailed Purpose & Implementation**: Provides an exhaustive breakdown of all capabilities merged from Hermes Agent and OpenClaw. Contains detailed sections covering LLM providers, channels, memory architectures, tool catalogs, security parameters, and CLI commands.

### 9. `hermclaw_test_guide.md`

- **File Type & Size**: Interactive Testing Guide | 10,556 bytes | 260 lines
- **Architectural Role**: Quality assurance test guide.
- **Detailed Purpose & Implementation**: Contains copy-paste test prompts and verification instructions for manually testing every feature in `hermclaw chat`.

### 10. `install.py`

- **File Type & Size**: Installation Wizard Script | 24,099 bytes | 715 lines
- **Architectural Role**: Interactive installer and environment setup script.
- **Detailed Purpose & Implementation**: Executes interactive setup (`python install.py`). Prompts user for LLM provider preferences, channel tokens, and default profile settings. Auto-detects local Ollama installations, pulls required models, generates `~/.hermclaw/hermclaw.yaml`, and verifies installation health.

- **Key Classes Defined**:
  - `C`

- **Top-Level Functions**: `banner, ask, ask_yes_no, ask_secret, run_cmd, check_python, check_ollama, get_ollama_models, generate_config, setup_wizard, install, main`

### 11. `pyproject.toml`

- **File Type & Size**: Build System Specification | 3,037 bytes | 85 lines
- **Architectural Role**: Python package setup and dependency definitions.
- **Detailed Purpose & Implementation**: Standard PEP 517/518 build specification using `setuptools`. Defines package dependencies (`pydantic`, `ruamel.yaml`, `fastapi`, `apscheduler`, `structlog`, `typer`), optional extra dependencies (`[bedrock]`, `[browser]`, `[media]`), and CLI console entry point (`hermclaw = hermclaw.cli:main`).

### 12. `requirements.txt`

- **File Type & Size**: Pip Dependency List | 709 bytes | 28 lines
- **Architectural Role**: Core runtime dependency list.
- **Detailed Purpose & Implementation**: Specifies exact version ranges for core third-party dependencies required to run Hermclaw.

## Documentation Subsystem (`docs/`)

### 13. `docs/CONFIG_REFERENCE.md`

- **File Type & Size**: Documentation Manual | 6,808 bytes | 165 lines
- **Architectural Role**: Reference manual for `hermclaw.yaml`.
- **Detailed Purpose & Implementation**: Exhaustively documents every single configuration key in `hermclaw.yaml`. Features detailed tables covering `agent`, `body`, `channels` (CLI, Web, Telegram, Discord, Slack, WhatsApp), `scheduler`, `brain`, `memory`, `reflection`, `skills`, `mcp_servers`, and `tools`. Maintained in sync with `HermclawConfig` Pydantic models via automated coverage tests (`tests/test_config_reference_coverage.py`).

### 14. `docs/SKILL_AUTHORING.md`

- **File Type & Size**: Developer Guide | 6,057 bytes | 148 lines
- **Architectural Role**: Technical guide for authoring skills.
- **Detailed Purpose & Implementation**: Explains the `agentskills.io` standard format adopted by Hermclaw. Details skill folder layouts (`SKILL.md`, `scripts/`, `references/`, `assets/`), mandatory YAML frontmatter fields (`name`, `description`), length constraints (<500 lines for SKILL.md), and progressive disclosure loading tiers (Tier 1 metadata prompt injection, Tier 2 full body activation, Tier 3 on-demand reference reading).

## Core Application & Package Root (`hermclaw/`)

### 15. `hermclaw/__init__.py`

- **File Type & Size**: Python Package Initializer | 264 bytes | 7 lines
- **Architectural Role**: Root module initialization.
- **Detailed Purpose & Implementation**: Defines package-level metadata and docstring for `hermclaw`. Specifies overall library description as a unified, self-improving personal AI agent combining OpenClaw and Hermes Agent.

### 16. `hermclaw/banner.py`

- **File Type & Size**: Python Visual Branding Module | 1,349 bytes | 42 lines
- **Architectural Role**: Terminal UI presentation component.
- **Detailed Purpose & Implementation**: Contains functions `get_banner()` and `get_startup_message()` that format Hermclaw ASCII art branding and status summaries using `rich` terminal formatting. Used during CLI startup (`hermclaw chat`, `hermclaw serve`) to present a clean visual identity.

- **Top-Level Functions**: `get_banner, get_startup_message`

### 17. `hermclaw/cli.py`

- **File Type & Size**: Python Module | 35,924 bytes | 1,025 lines
- **Architectural Role**: Primary CLI application entry point.
- **Detailed Purpose & Implementation**: Implements the `hermclaw` CLI application using `typer` and `rich`. Strict constraint: exposes exactly five top-level subcommands:
  1. `hermclaw chat`: Launches local terminal REPL session.
  2. `hermclaw serve`: Starts background HTTP gateway server, channels, and task schedulers.
  3. `hermclaw doctor`: Performs environment diagnostics, config validation, file permission checks, channel status checks, and token cost reporting. Supports `--json`.
  4. `hermclaw reflect`: Triggers manual memory distillation and skill growth pass.
  5. `hermclaw skills`: Manages skills (`list`, `validate`, `show`).

- **Key Classes Defined**:
  - `CleanExit` (inherits from `Exception`) | Methods: `__init__`

- **Top-Level Functions**: `_run, main, _load_env_file, _load_or_die, chat, run, serve, _daemonize_serve, doctor, _check_channel_credentials, _print_checks, reflect`

### 18. `hermclaw/config.py`

- **File Type & Size**: Python Module | 17,246 bytes | 512 lines
- **Architectural Role**: Central configuration management system.
- **Detailed Purpose & Implementation**: Implements `HermclawConfig` using Pydantic v2 schemas and `ruamel.yaml`. Features:
  - Strict schema validation: rejects invalid or misspelled config keys on startup.
  - Last-Known-Good (LKG) backup: automatically saves `hermclaw.lkg.yaml` on successful boot; falls back to LKG if user edits create invalid YAML.
  - Anti-clobber protection: prevents programmatic writes from accidentally wiping user comments or dropping sections.
  - Debounced file watcher (`ConfigWatcher`): hot-reloads configuration changes live.

- **Key Classes Defined**:
  - `GatewayAuthConfig` (inherits from `BaseModel`)
  - `GatewayConfig` (inherits from `BaseModel`)
  - `TelegramChannelConfig` (inherits from `BaseModel`)
  - `DiscordChannelConfig` (inherits from `BaseModel`)
  - `SlackChannelConfig` (inherits from `BaseModel`)
  - `CliChannelConfig` (inherits from `BaseModel`)
  - `WebChannelConfig` (inherits from `BaseModel`)
  - `WhatsappChannelConfig` (inherits from `BaseModel`)
  - `ChannelsConfig` (inherits from `BaseModel`)
  - `HeartbeatConfig` (inherits from `BaseModel`)
  - `SchedulerJobConfig` (inherits from `BaseModel`)
  - `SchedulerConfig` (inherits from `BaseModel`)
  - `BodyConfig` (inherits from `BaseModel`)
  - `FallbackModelConfig` (inherits from `BaseModel`)
  - `ModelConfig` (inherits from `BaseModel`)
  - `MemoryConfig` (inherits from `BaseModel`)
  - `ReflectionConfig` (inherits from `BaseModel`)
  - `BrainConfig` (inherits from `BaseModel`)
  - `McpServerConfig` (inherits from `BaseModel`) | Methods: `_check_transport_fields`
  - `SkillsConfig` (inherits from `BaseModel`)
  - `ToolsApprovalsConfig` (inherits from `BaseModel`)
  - `ToolsConfig` (inherits from `BaseModel`)
  - `AgentIdentity` (inherits from `BaseModel`)
  - `AgentListEntry` (inherits from `BaseModel`)
  - `AgentConfig` (inherits from `BaseModel`)
  - `HermclawConfig` (inherits from `BaseModel`)
  - `ConfigLoadResult`
  - `ConfigWriteRefused` (inherits from `Exception`)
  - `ConfigWatcher` | Methods: `_mtime, stop`

- **Top-Level Functions**: `hermclaw_home, default_config_path, lkg_path, _read_yaml_dict, _validate_dict, write_default_config, _write_lkg, load_config, save_config_text`

### 19. `hermclaw/config_defaults.py`

- **File Type & Size**: Python Module | 3,850 bytes | 115 lines
- **Architectural Role**: Default configuration content constant.
- **Detailed Purpose & Implementation**: Holds the raw string constant for the default `hermclaw.yaml` configuration file. Ensures `install.py`, `config.py`, and `hermclaw.example.yaml` always write identical default configuration settings.

### 20. `hermclaw/i18n.py`

- **File Type & Size**: Python Module | 7,084 bytes | 215 lines
- **Architectural Role**: Internationalization (i18n) translation engine.
- **Detailed Purpose & Implementation**: Implements `t(key, **kwargs)` and language switching across 16 supported languages (English, Spanish, French, German, Japanese, Korean, Chinese, Portuguese, Russian, Hindi, Turkish, Italian, Ukrainian, Afrikaans, Irish, Hungarian). Translates CLI and gateway system messages lazily.

- **Top-Level Functions**: `set_language, get_language, t, available_languages`

### 21. `hermclaw/observability.py`

- **File Type & Size**: Python Module | 3,764 bytes | 118 lines
- **Architectural Role**: Structured logging and log redaction system.
- **Detailed Purpose & Implementation**: Configures `structlog` logging pipelines. Outputs pretty colored logs to terminal standard error and structured JSON lines to rotating log files (`hermclaw.log`). Automatically redacts detected API keys, tokens, and password strings from all log events.

- **Top-Level Functions**: `_redact_event, configure_logging, bind_turn_context, clear_turn_context`

### 22. `hermclaw/runtime.py`

- **File Type & Size**: Python Module | 8,430 bytes | 252 lines
- **Architectural Role**: Agent runtime factory.
- **Detailed Purpose & Implementation**: Implements `AgentRuntime`. Assembles a fully-wired `HermclawAgent` instance for a given profile by linking `HermclawConfig`, `ProfileManager`, `MemoryStore`, `SkillRegistry`, `ToolDispatcher`, and provider transports. Shared by `gateway.py` and `cli.py`.

- **Key Classes Defined**:
  - `AgentRuntime`

- **Top-Level Functions**: `gateway_token`

## Body Subsystem & Channel Adapters (`hermclaw/body/`)

### 23. `hermclaw/body/__init__.py`

- **File Type & Size**: Python Package Initializer | 130 bytes | 4 lines
- **Architectural Role**: Body subsystem root.
- **Detailed Purpose & Implementation**: Package initializer for the Body layer. Summarizes the role of the Body subsystem in handling gateway execution, channel adapters, and background task scheduling.

### 24. `hermclaw/body/agents_registry.py`

- **File Type & Size**: Python Module | 2,318 bytes | 78 lines
- **Architectural Role**: Multi-identity agent routing engine.
- **Detailed Purpose & Implementation**: Defines `AgentsRegistry` and `ResolvedAgent`. Enables a single Hermclaw gateway instance to present multiple distinct identities (e.g. general assistant vs. coding bot) across different channels or incoming user handles. Maps each agent identity to its assigned profile (`SOUL.md`, `MEMORY.md`, `USER.md`, `state.db`), guaranteeing complete isolation of conversation history and personality files.

- **Key Classes Defined**:
  - `ResolvedAgent`
  - `AgentsRegistry` | Methods: `__init__, resolve, resolve_for_message, all_agents, profiles_in_use`

### 25. `hermclaw/body/gateway.py`

- **File Type & Size**: Python Module | 13,682 bytes | 412 lines
- **Architectural Role**: Central control server and HTTP REST/WebSocket API host.
- **Detailed Purpose & Implementation**: Implements `Gateway`, the core server process launched by `hermclaw serve`. Features:
  - Starts FastAPI web application on loopback interface with Bearer token authentication.
  - Exposes REST control endpoints (`GET /status`, `GET /health`, `POST /reload`, `POST /chat`).
  - Manages background channel adapters and task schedulers.
  - Implements intelligent hot-reloading: watches `hermclaw.yaml` changes and reconfigures affected channels or LLM backends live without dropping the process.

- **Key Classes Defined**:
  - `Gateway` | Methods: `__init__, _register_routes, status_snapshot, _apply_scheduler, _default_channel_name, _default_reply_to, _make_on_receive`

- **Top-Level Functions**: `_enabled_channel_names, _channel_config_for`

### 26. `hermclaw/body/mcp_client.py`

- **File Type & Size**: Python Module | 4,227 bytes | 128 lines
- **Architectural Role**: Model Context Protocol (MCP) tool client bridge.
- **Detailed Purpose & Implementation**: Implements `McpClientManager` and `McpToolAdapter`. Connects to external MCP servers defined in `skills.mcp_servers` via stdio or HTTP SSE transports, discovers remote tools, and wraps each remote MCP tool as a native Hermclaw `ToolABC`. Ensures external MCP tools pass through the exact same `ToolDispatcher` security and user approval gates as internal tools.

- **Key Classes Defined**:
  - `McpToolAdapter` (inherits from `ToolABC`) | Methods: `__init__, spec`
  - `McpClientManager` | Methods: `__init__, session`

### 27. `hermclaw/body/scheduler.py`

- **File Type & Size**: Python Module | 7,800 bytes | 235 lines
- **Architectural Role**: Task scheduler and background heartbeat manager.
- **Detailed Purpose & Implementation**: Implements `HermclawScheduler` using APScheduler's `AsyncIOScheduler`. Runs background tasks:
  1. Periodic Heartbeats: Executes background agent turns in isolated sessions to check system status. Classifies outcomes into `ok` (silent), `background` (silent), or `alert` (relayed to user).
  2. Scheduled Cron Jobs: Runs user-configured cron or one-shot tasks and routes output directly to configured channel adapters.

- **Key Classes Defined**:
  - `ProfileRuntime`
  - `HermclawScheduler` | Methods: `__init__, start, shutdown, register_profile, update_heartbeat_interval, unregister_profile`

- **Top-Level Functions**: `parse_duration, resolve_heartbeat_interval_s, classify_heartbeat_response`

### 28. `hermclaw/body/channels/__init__.py`

- **File Type & Size**: Python Module | 2,380 bytes | 75 lines
- **Architectural Role**: Channel subsystem factory.
- **Detailed Purpose & Implementation**: Defines `build_enabled_channels(config, on_receive_callback)`. Iterates over configured messaging channels (`cli`, `web`, `telegram`, `discord`, `slack`, `whatsapp`), validates their credentials, instantiates their respective `ChannelAdapter` subclasses, and registers the global inbound message callback handler.

- **Top-Level Functions**: `build_enabled_channels`

### 29. `hermclaw/body/channels/base.py`

- **File Type & Size**: Python Module | 2,308 bytes | 79 lines
- **Architectural Role**: Standard abstract interface for all messaging surfaces.
- **Detailed Purpose & Implementation**: Defines `ChannelAdapter` (ABC), `IncomingMessage`, `OutgoingMessage`, and `ChannelHealth`. Every messaging channel (CLI, Web, Telegram, Discord, Slack, WhatsApp) inherits from `ChannelAdapter` and implements `start()`, `stop()`, `send()`, and `health()`. Ensures the `Gateway` and `Scheduler` can interact with any channel uniformly without channel-specific conditionals.

- **Key Classes Defined**:
  - `IncomingMessage`
  - `OutgoingMessage`
  - `ChannelHealth`
  - `ChannelAdapter` (inherits from `ABC`) | Methods: `__init__, health, name`

### 30. `hermclaw/body/channels/cli_channel.py`

- **File Type & Size**: Python Module | 2,641 bytes | 85 lines
- **Architectural Role**: CLI interactive channel adapter.
- **Detailed Purpose & Implementation**: Implements `CliChannel` for local stdin/stdout terminal chat sessions. Supports constructor-injected reader/writer streams, allowing unit tests to simulate terminal user input and output without binding real terminal I/O. Serves as the primary channel for `hermclaw chat`.

- **Key Classes Defined**:
  - `CliChannel` (inherits from `ChannelAdapter`) | Methods: `__init__, health`

### 31. `hermclaw/body/channels/discord.py`

- **File Type & Size**: Python Module | 2,577 bytes | 82 lines
- **Architectural Role**: Discord channel adapter.
- **Detailed Purpose & Implementation**: Implements `DiscordChannel` using `discord.py`'s async client. Connects to Discord gateway WebSockets using `bot_token`, listens for direct messages or channel mentions, converts incoming Discord messages to `IncomingMessage` objects, and dispatches outbound agent responses back to Discord channels.

- **Key Classes Defined**:
  - `DiscordChannel` (inherits from `ChannelAdapter`) | Methods: `__init__, _build_client, _register_handlers, health`

### 32. `hermclaw/body/channels/slack.py`

- **File Type & Size**: Python Module | 2,545 bytes | 80 lines
- **Architectural Role**: Slack channel adapter.
- **Detailed Purpose & Implementation**: Implements `SlackChannel` leveraging `slack_bolt` over Socket Mode. Allows Hermclaw to receive Slack events and send replies securely without needing a public HTTP endpoint or external webhook URL, preserving local-first security.

- **Key Classes Defined**:
  - `SlackChannel` (inherits from `ChannelAdapter`) | Methods: `__init__, _build_app, _register_handlers, health`

### 33. `hermclaw/body/channels/telegram.py`

- **File Type & Size**: Python Module | 2,871 bytes | 88 lines
- **Architectural Role**: Telegram channel adapter.
- **Detailed Purpose & Implementation**: Implements `TelegramChannel` using `python-telegram-bot`'s async `Application`. Receives Telegram messages via long-polling, handles authorized user ID filtering (`allowed_users`), translates Telegram message formats to `IncomingMessage`, and sends agent responses.

- **Key Classes Defined**:
  - `TelegramChannel` (inherits from `ChannelAdapter`) | Methods: `__init__, _build_application, health`

### 34. `hermclaw/body/channels/web.py`

- **File Type & Size**: Python Module | 4,266 bytes | 134 lines
- **Architectural Role**: Embedded Web UI & WebSocket channel adapter.
- **Detailed Purpose & Implementation**: Implements `WebChannel` serving a lightweight HTML/JS web chat client hosted directly by FastAPI. Manages active WebSocket connections per browser tab, enabling real-time streaming chat directly from a browser interface.

- **Key Classes Defined**:
  - `WebChannel` (inherits from `ChannelAdapter`) | Methods: `__init__, _register_routes, health`

### 35. `hermclaw/body/channels/whatsapp.py`

- **File Type & Size**: Python Module | 5,897 bytes | 176 lines
- **Architectural Role**: WhatsApp channel adapter Python bridge.
- **Detailed Purpose & Implementation**: Implements `WhatsAppChannel`, bridging Python to a Node.js sidecar process (`index.js`) running the Baileys WhatsApp Web library. Communicates with the sidecar subprocess over stdin/stdout using a line-delimited JSON-RPC protocol (`send`, `message`, `qr`, `status`).

- **Key Classes Defined**:
  - `WhatsAppChannel` (inherits from `ChannelAdapter`) | Methods: `__init__, health`

### 36. `hermclaw/body/channels/whatsapp_sidecar/index.js`

- **File Type & Size**: JavaScript Node.js Script | 3,765 bytes | 125 lines
- **Architectural Role**: WhatsApp protocol bridge sidecar process.
- **Detailed Purpose & Implementation**: Node.js process utilizing the `@whiskeysockets/baileys` library to establish a WhatsApp Web multi-device connection. Reads JSON-RPC requests from standard input to send messages and emits JSON-RPC notifications to standard output when WhatsApp messages or QR authentication codes arrive.

### 37. `hermclaw/body/channels/whatsapp_sidecar/package.json`

- **File Type & Size**: Node.js Package Manifest | 534 bytes | 22 lines
- **Architectural Role**: Sidecar package metadata.
- **Detailed Purpose & Implementation**: Defines dependencies (`@whiskeysockets/baileys`, `qrcode-terminal`) and startup scripts (`npm start`) for the Node.js WhatsApp sidecar process.

## Brain Subsystem, Memory & LLM Transports (`hermclaw/brain/`)

### 38. `hermclaw/brain/__init__.py`

- **File Type & Size**: Python Package Initializer | 143 bytes | 4 lines
- **Architectural Role**: Brain subsystem root.
- **Detailed Purpose & Implementation**: Package initializer for the Brain subsystem. Summarizes reasoning, memory, context compression, reflection, and model transport components derived from Hermes Agent.

### 39. `hermclaw/brain/agent_loop.py`

- **File Type & Size**: Python Module | 25,821 bytes | 745 lines
- **Architectural Role**: Core ReAct tool-calling agent loop.
- **Detailed Purpose & Implementation**: Implements `HermclawAgent`, the central reasoning loop of Hermclaw. Key mechanics:
  - Accepts incoming user message and retrieves active profile context (`SOUL.md`, `MEMORY.md`, `USER.md`).
  - Formulates system prompt and appends Tier 1 skill metadata and tool definitions.
  - Executes multi-step ReAct loops: sends prompt to provider transport, parses tool call requests, dispatches tools via `ToolDispatcher`, appends tool execution results, and iterates until a final text response is produced.
  - Handles model fallbacks: automatically retries failed requests using configured fallback models (`brain.fallback_models`).
  - Persists every turn and message into SQLite (`MemoryStore`) and checks context compression triggers.

- **Key Classes Defined**:
  - `ToolCallRecord`
  - `AgentTurnResult`
  - `FallbackEntry`
  - `HermclawAgent` | Methods: `__init__, _audit_tool_call`

- **Top-Level Functions**: `text_block, tool_use_block, tool_result_block, assistant_content_from_response, rows_to_canonical_messages, add_usage, approx_token_count, select_tools_for_query`

### 40. `hermclaw/brain/cache.py`

- **File Type & Size**: Python Module | 4,704 bytes | 142 lines
- **Architectural Role**: Prompt and response LRU caching system.
- **Detailed Purpose & Implementation**: Implements `ResponseCache` to cache LLM completions based on SHA-256 hashes of prompt message sequences, tool definitions, and model parameters. Prevents redundant API costs and speeds up repetitive queries.

- **Key Classes Defined**:
  - `ResponseCache` | Methods: `__init__, close, _make_key, get, put, clear, stats`

### 41. `hermclaw/brain/learning_graph.py`

- **File Type & Size**: Python Module | 11,547 bytes | 338 lines
- **Architectural Role**: Knowledge graph and concept relationship store.
- **Detailed Purpose & Implementation**: Implements `LearningGraph` and `LearningGraphTool`. Tracks concepts learned by the agent, relationship edges between concepts, and confidence scores in SQLite. Exposes tools allowing the agent to query, expand, and visualize concept graphs as ASCII diagrams.

- **Key Classes Defined**:
  - `LearningGraph` | Methods: `__init__, close, add_concept, add_relationship, get_neighbors, stats, visualize_ascii, search`
  - `LearningGraphTool` (inherits from `ToolABC`) | Methods: `__init__, spec`

### 42. `hermclaw/brain/moa.py`

- **File Type & Size**: Python Module | 4,509 bytes | 138 lines
- **Architectural Role**: Mixture-of-Agents parallel reasoning engine.
- **Detailed Purpose & Implementation**: Implements `MoAResult` and MoA orchestration logic. Queries multiple LLM models (e.g. Claude, GPT-4, Llama-3) in parallel with the same prompt, collects candidate responses, and passes them to a synthesizer model to produce a superior combined answer.

- **Key Classes Defined**:
  - `MoAResult`

### 43. `hermclaw/brain/model_catalog.py`

- **File Type & Size**: Python Module | 9,834 bytes | 295 lines
- **Architectural Role**: LLM provider catalog and token cost tracker.
- **Detailed Purpose & Implementation**: Implements `ModelCatalog`, `ModelInfo`, and `CostTracker`. Holds metadata for known LLM models (context window sizes, pricing per 1M tokens, vision/tool support). Resolves model aliases (e.g. `fast` -> `gemma4:12b`), tracks cumulative token usage, and calculates dollar costs per turn and session.

- **Key Classes Defined**:
  - `ModelInfo`
  - `ModelCatalog` | Methods: `__init__, register, resolve, list_all, list_by_provider, format_table`
  - `CostEntry`
  - `CostTracker` | Methods: `__init__, record, total_cost, total_tokens, summary`

### 44. `hermclaw/brain/parallel_exec.py`

- **File Type & Size**: Python Module | 4,798 bytes | 148 lines
- **Architectural Role**: Concurrent tool execution engine.
- **Detailed Purpose & Implementation**: Implements parallel tool execution for turns where the LLM emits multiple tool call requests simultaneously. Executes independent tool calls concurrently using `asyncio.gather()`, drastically reducing multi-tool latency.

- **Key Classes Defined**:
  - `ParallelResult`
  - `PipelineStage`

### 45. `hermclaw/brain/post_processing.py`

- **File Type & Size**: Python Module | 3,028 bytes | 92 lines
- **Architectural Role**: Output sanitizer and reasoning tag scrubber.
- **Detailed Purpose & Implementation**: Contains `scrub_think_tags()`, `extract_thinking()`, and `sanitize_response()`. Strips internal `<think>...</think>` reasoning tags produced by thinking models (DeepSeek R1, QwQ) before presenting final output to users, while storing reasoning content for reflection logs.

- **Top-Level Functions**: `extract_thinking, scrub_think_tags, generate_title_prompt, sanitize_response`

### 46. `hermclaw/brain/profiles.py`

- **File Type & Size**: Python Module | 8,702 bytes | 265 lines
- **Architectural Role**: Profile directory layout & system prompt assembler.
- **Detailed Purpose & Implementation**: Implements `ProfileManager`, `ProfilePaths`, and `IdentityFiles`. Manages profile isolation under `~/.hermclaw/profiles/<profile>/`. Loads and updates identity files:
  - `SOUL.md`: Persona and behavioral rules (human-edited).
  - `MEMORY.md`: Long-term general facts distilled by reflection.
  - `USER.md`: Facts about the user distilled by reflection.
  Assembles the final system prompt by combining identity files, active profile paths, and Tier 1 skill definitions.

- **Key Classes Defined**:
  - `ProfilePaths`
  - `ProfileManager` | Methods: `__init__, profile_root, paths, ensure_profile, list_profiles`
  - `IdentityFiles` | Methods: `__init__, read_soul, read_memory, read_user, append_memory_facts, append_user_facts, assemble_system_prompt`

- **Top-Level Functions**: `_validate_profile_name, _safe_read, _trim_to_limit`

### 47. `hermclaw/brain/reflection.py`

- **File Type & Size**: Python Module | 7,679 bytes | 228 lines
- **Architectural Role**: Autonomous memory distillation engine.
- **Detailed Purpose & Implementation**: Implements `ReflectionDistillation`. Periodically analyzes recent session transcripts to extract durable knowledge:
  1. General facts appended to `MEMORY.md`.
  2. User preference facts appended to `USER.md`.
  3. Repeated procedures (3+ occurrences) sent to `skill_growth.py` to auto-generate draft skills.

- **Key Classes Defined**:
  - `ReflectionDistillation`
  - `ReflectionResult`

- **Top-Level Functions**: `_strip_code_fences, _parse_distillation, _build_transcript`

### 48. `hermclaw/brain/skill_growth.py`

- **File Type & Size**: Python Module | 9,363 bytes | 282 lines
- **Architectural Role**: Automated skill generator and evolution engine.
- **Detailed Purpose & Implementation**: Implements `SkillGrowthEngine` and `SkillEvolutionEngine`. Converts repeated operational steps identified by reflection into new `agentskills.io` skill folders containing valid `SKILL.md` frontmatter and execution instructions. Supports Tier 2 skill evolution to refine auto-generated skills over time.

- **Key Classes Defined**:
  - `EvolutionResult`
  - `SkillGrowthEngine` | Methods: `__init__, generate_draft_skill`
  - `SkillEvolutionEngine` | Methods: `__init__, apply_evolution`

- **Top-Level Functions**: `_slugify, _sanitize_for_frontmatter, _stem, _token_similarity`

### 49. `hermclaw/brain/memory/__init__.py`

- **File Type & Size**: Python Package Initializer | 134 bytes | 4 lines
- **Architectural Role**: Memory package root.
- **Detailed Purpose & Implementation**: Package initializer for persistent memory stores, context compression engines, and SQLite schemas.

### 50. `hermclaw/brain/memory/compressor.py`

- **File Type & Size**: Python Module | 7,312 bytes | 215 lines
- **Architectural Role**: Dynamic context window compressor.
- **Detailed Purpose & Implementation**: Implements `ContextCompressor`. Monitors conversation token counts against `compression_threshold`. When exceeded:
  1. Issues a `save_memory` flush turn allowing the LLM to write crucial facts to memory before context truncation.
  2. Summarizes older message exchanges into a concise continuation recap while preserving the `keep_recent_exchanges` turns verbatim.
  3. Flags older messages as `compressed_away` in SQLite so full-text session search still indexes them without cluttering active LLM context windows.

- **Key Classes Defined**:
  - `CompressionResult`
  - `ContextCompressor` | Methods: `__init__, should_compress`

### 51. `hermclaw/brain/memory/schema.sql`

- **File Type & Size**: SQL Database Schema File | 2,280 bytes | 72 lines
- **Architectural Role**: SQLite database structure definition.
- **Detailed Purpose & Implementation**: SQL DDL creating tables for `sessions`, `messages`, `memories`, `goals`, `schedules`, `kanban_boards`, `todos`, and FTS5 full-text search virtual tables (`messages_fts`). Configures WAL (Write-Ahead Logging) mode and foreign key constraints.

### 52. `hermclaw/brain/memory/store.py`

- **File Type & Size**: Python Module | 10,495 bytes | 312 lines
- **Architectural Role**: Persistent SQLite state manager.
- **Detailed Purpose & Implementation**: Implements `MemoryStore`. Manages thread-safe access to per-profile SQLite databases (`state.db`). Handles creation of sessions, saving incoming/outgoing messages, retrieving session history, updating token consumption stats, and executing FTS5 full-text queries for episodic memory search (`session_search`).

- **Key Classes Defined**:
  - `MessageHit`
  - `SessionRow`
  - `MessageRow`
  - `MemoryStore` | Methods: `__init__, _init_schema, close, create_session, end_session, update_session_usage, get_session, get_recent_sessions, add_message, mark_messages_compressed_away`

- **Top-Level Functions**: `_now_iso, _sanitize_fts_query, _row_to_session, _row_to_message`

### 53. `hermclaw/brain/memory/vector_memory.py`

- **File Type & Size**: Python Module | 15,965 bytes | 468 lines
- **Architectural Role**: Local vector embeddings memory store.
- **Detailed Purpose & Implementation**: Implements `VectorMemory` and `MemoryManageTool`. Performs semantic similarity search over stored long-term memory snippets using cosine distance metrics. Embeddings are generated locally via Ollama or OpenAI APIs, with automatic fallback to FTS5 keyword search if no embedding model is configured.

- **Key Classes Defined**:
  - `VectorMemory` | Methods: `__init__, close, _vector_search, _keyword_search, list_memories, delete, stats`
  - `MemoryManageTool` (inherits from `ToolABC`) | Methods: `__init__, spec`

- **Top-Level Functions**: `_cosine_similarity`

### 54. `hermclaw/brain/transports/__init__.py`

- **File Type & Size**: Python Module | 2,629 bytes | 78 lines
- **Architectural Role**: LLM provider transport factory.
- **Detailed Purpose & Implementation**: Exposes `build_transport(model_config)`. Resolves environment variable secret references (`api_key_env`) at runtime and instantiates the appropriate `ProviderTransport` subclass (Anthropic, Bedrock, OpenAI-compatible).

- **Key Classes Defined**:
  - `MissingCredentialsError` (inherits from `Exception`)

- **Top-Level Functions**: `build_transport`

### 55. `hermclaw/brain/transports/anthropic.py`

- **File Type & Size**: Python Module | 4,084 bytes | 125 lines
- **Architectural Role**: Anthropic Claude API network transport.
- **Detailed Purpose & Implementation**: Implements `AnthropicTransport` using `anthropic.AsyncAnthropic`. Normalizes Claude Messages API requests and responses, converting tool specifications into Anthropic schema and handling prompt caching headers (`cache_control`).

- **Key Classes Defined**:
  - `AnthropicTransport` (inherits from `ProviderTransport`) | Methods: `__init__, supports_prompt_cache, _to_anthropic_tools, _parse_response`

### 56. `hermclaw/brain/transports/base.py`

- **File Type & Size**: Python Module | 2,006 bytes | 68 lines
- **Architectural Role**: Abstract base class for LLM network transports.
- **Detailed Purpose & Implementation**: Defines `ProviderTransport` (ABC), `AgentResponse`, `ToolCallRequest`, and `Usage`. Establishes the uniform interface that all LLM provider transports must implement, isolating `HermclawAgent` from provider-specific wire protocol variations.

- **Key Classes Defined**:
  - `ToolCallRequest`
  - `Usage` | Methods: `total_tokens`
  - `AgentResponse`
  - `TransportError` (inherits from `Exception`)
  - `ProviderTransport` (inherits from `ABC`) | Methods: `supports_prompt_cache, name`

### 57. `hermclaw/brain/transports/bedrock.py`

- **File Type & Size**: Python Module | 6,390 bytes | 192 lines
- **Architectural Role**: AWS Bedrock Converse API network transport.
- **Detailed Purpose & Implementation**: Implements `BedrockTransport` using `boto3` Bedrock Runtime Converse API. Translates Hermclaw messages and tool definitions into Amazon Bedrock Converse payload formats for AWS-hosted models (Claude, Llama, Nova).

- **Key Classes Defined**:
  - `BedrockTransport` (inherits from `ProviderTransport`) | Methods: `__init__, _to_converse_messages, _to_converse_tools, _parse_response`

### 58. `hermclaw/brain/transports/fake.py`

- **File Type & Size**: Python Module | 2,466 bytes | 78 lines
- **Architectural Role**: Scriptable mock transport for offline testing.
- **Detailed Purpose & Implementation**: Implements `FakeTransport`. Allows unit tests to script predetermined text responses or tool call sequences without sending real network traffic or consuming LLM API credits.

- **Key Classes Defined**:
  - `FakeTransport` (inherits from `ProviderTransport`) | Methods: `__init__, supports_prompt_cache`

- **Top-Level Functions**: `text_response, tool_call_response`

### 59. `hermclaw/brain/transports/openai_compat.py`

- **File Type & Size**: Python Module | 10,201 bytes | 305 lines
- **Architectural Role**: OpenAI-compatible HTTP transport.
- **Detailed Purpose & Implementation**: Implements `ChatCompletionsTransport` built directly over `httpx.AsyncClient`. Connects to any OpenAI-compatible API endpoint (Ollama, vLLM, OpenRouter, LM Studio, OpenAI). Supports both streaming (Server-Sent Events) and non-streaming responses.

- **Key Classes Defined**:
  - `ChatCompletionsTransport` (inherits from `ProviderTransport`) | Methods: `__init__, _to_openai_messages, _to_openai_tools, _parse_response`

## Plugins Architecture (`hermclaw/plugins/`)

### 60. `hermclaw/plugins/__init__.py`

- **File Type & Size**: Python Module | 7,912 bytes | 242 lines
- **Architectural Role**: Extensible plugin manager.
- **Detailed Purpose & Implementation**: Implements `PluginManager` and `PluginInstance`. Discovers, loads, and manages third-party Hermclaw plugins from `~/.hermclaw/plugins/` or Git repositories. Each plugin directory contains a `plugin.json` manifest and custom Python tools, hooks, or skills.

- **Key Classes Defined**:
  - `PluginManifest` | Methods: `__init__, to_dict`
  - `PluginInstance` | Methods: `__init__`
  - `PluginManager` | Methods: `__init__, discover, load_all, _load_plugin, get, list_plugins, install_from_git, uninstall, create_template`

## Security, Governance & Audit (`hermclaw/security/`)

### 61. `hermclaw/security/__init__.py`

- **File Type & Size**: Python Package Initializer | 0 bytes | 1 line
- **Architectural Role**: Security package root.
- **Detailed Purpose & Implementation**: Package initialization file for security modules.

### 62. `hermclaw/security/audit.py`

- **File Type & Size**: Python Module | 7,259 bytes | 225 lines
- **Architectural Role**: Persistent security auditing and rate limiting logger.
- **Detailed Purpose & Implementation**: Implements `AuditLogger` and `RateLimiter`. Records every tool execution request, parameter payload, timestamp, and user approval outcome into an SQLite audit database (`audit.db`). Implements sliding-window rate limiters per tool and channel.

- **Key Classes Defined**:
  - `AuditLogger` | Methods: `__init__, close, log, query, stats`
  - `RateLimiter` | Methods: `__init__, set_limit, check, stats`

- **Top-Level Functions**: `get_audit_logger, get_rate_limiter`

### 63. `hermclaw/security/permissions.py`

- **File Type & Size**: Python Module | 2,014 bytes | 65 lines
- **Architectural Role**: Filesystem boundary and file permissions enforcement.
- **Detailed Purpose & Implementation**: Implements `ensure_within_scope(path, workspace_root)`. Prevents path traversal attacks (`../`) by ensuring tool file accesses remain strictly within the profile's configured workspace directory. Checks restrictive file permissions (0600) on state databases and config files.

- **Key Classes Defined**:
  - `PathOutsideScopeError` (inherits from `Exception`)

- **Top-Level Functions**: `ensure_within_scope, ensure_dir, check_file_permissions`

### 64. `hermclaw/security/secrets.py`

- **File Type & Size**: Python Module | 2,483 bytes | 78 lines
- **Architectural Role**: Secret reference resolver and redaction engine.
- **Detailed Purpose & Implementation**: Implements `resolve_env_ref(env_var_name)` and `redact(data)`. Ensures configuration files store environment variable *names* (e.g. `bot_token_env: TELEGRAM_BOT_TOKEN`) rather than literal secrets. Redacts sensitive strings from API responses and log outputs.

- **Key Classes Defined**:
  - `MissingSecretError` (inherits from `Exception`)

- **Top-Level Functions**: `resolve_env_ref, redact, redact_copy, scrub_string`

## Skills Loading & Registry (`hermclaw/skills/`)

### 65. `hermclaw/skills/__init__.py`

- **File Type & Size**: Python Package Initializer | 124 bytes | 4 lines
- **Architectural Role**: Skills subsystem root.
- **Detailed Purpose & Implementation**: Package initialization file for skill loaders and registries based on `agentskills.io`.

### 66. `hermclaw/skills/loader.py`

- **File Type & Size**: Python Module | 6,085 bytes | 185 lines
- **Architectural Role**: `agentskills.io` SKILL.md parser and validator.
- **Detailed Purpose & Implementation**: Implements `parse_skill_md(skill_dir)`. Parses YAML frontmatter and Markdown body of `SKILL.md` files. Validates skill metadata (name formatting, description presence, allowed tools list) and returns `SkillMetadata` objects.

- **Key Classes Defined**:
  - `SkillMetadata` | Methods: `auto_generated, compact`
  - `SkillValidationResult` | Methods: `name`

- **Top-Level Functions**: `_split_frontmatter, parse_skill_md, discover_skill_dirs`

### 67. `hermclaw/skills/registry.py`

- **File Type & Size**: Python Module | 3,790 bytes | 122 lines
- **Architectural Role**: Progressive disclosure skill registry.
- **Detailed Purpose & Implementation**: Implements `SkillRegistry`. Discovers skills across builtin, profile, and workspace skill directories. Implements progressive disclosure:
  - Tier 1: Includes compact name + description in system prompt (~100 tokens per skill).
  - Tier 2: Loads full `SKILL.md` body on-demand when a skill is activated.
  - Tier 3: Reads supporting reference files (`references/`) only when requested by the skill's instructions.

- **Key Classes Defined**:
  - `SkillRegistry` | Methods: `__post_init__, _search_roots, discover, load, compact_listing, activate, names, get, auto_generated_skills, human_authored_skills`

## Tools Engine & Execution Backends (`hermclaw/tools/`)

### 68. `hermclaw/tools/__init__.py`

- **File Type & Size**: Python Package Initializer | 0 bytes | 1 line
- **Architectural Role**: Tools package root.
- **Detailed Purpose & Implementation**: Package initialization file for tool modules.

### 69. `hermclaw/tools/achievements.py`

- **File Type & Size**: Python Module | 11,638 bytes | 345 lines
- **Architectural Role**: Gamification and user milestone tracking tool.
- **Detailed Purpose & Implementation**: Implements `AchievementSystem` and `AchievementsTool`. Tracks interactive milestones (e.g. first tool call, 100 turns, night owl usage) in SQLite and awards achievements with rich terminal badges.

- **Key Classes Defined**:
  - `AchievementSystem` | Methods: `__init__, close, _ensure_builtin, increment, _get_stat, list_all, list_unlocked, summary, render`
  - `AchievementsTool` (inherits from `ToolABC`) | Methods: `__init__, spec`

### 70. `hermclaw/tools/app_launcher.py`

- **File Type & Size**: Python Module | 7,538 bytes | 225 lines
- **Architectural Role**: Cross-platform desktop application launcher.
- **Detailed Purpose & Implementation**: Implements `AppLauncherTool`. Enables the agent to open, list, and close desktop applications across Windows (`Start-Process`), macOS (`open`), and Linux (`xdg-open`).

- **Key Classes Defined**:
  - `AppLauncherTool` (inherits from `ToolABC`) | Methods: `spec, _open, _list_running, _close`

### 71. `hermclaw/tools/approvals.py`

- **File Type & Size**: Python Module | 1,759 bytes | 58 lines
- **Architectural Role**: Interactive tool approval gate constructor.
- **Detailed Purpose & Implementation**: Implements `build_approval_gate(config)`. Supports three security modes:
  - `manual`: Asks for user confirmation before executing restricted tools.
  - `smart`: Evaluates command risk using an auxiliary classifier.
  - `off`: Disables interactive prompts (logged prominently).
  Always enforces hardline protection against destructive commands regardless of mode.

- **Top-Level Functions**: `build_approval_gate`

### 72. `hermclaw/tools/base.py`

- **File Type & Size**: Python Module | 10,082 bytes | 315 lines
- **Architectural Role**: Core Tool Abstract Base Class and single Dispatcher.
- **Detailed Purpose & Implementation**: Implements `ToolABC` and `ToolDispatcher`. **Highest-priority security module in Hermclaw**. Enforces that ALL tools (built-in tools, shell tool, code-exec, MCP tools) inherit from `ToolABC` and execute exclusively through `ToolDispatcher.dispatch()`. Prevents tools from bypassing approval gates via raw RPCs. Checks dangerous command regex patterns (`rm -rf /`, `:(){ :|:& };:`).

- **Key Classes Defined**:
  - `ToolSpec`
  - `ToolResult`
  - `ToolExecutionDenied` (inherits from `Exception`)
  - `ToolABC` (inherits from `ABC`) | Methods: `spec`
  - `ApprovalsConfig`
  - `ApprovalGate` | Methods: `__init__`
  - `ToolDispatcher` | Methods: `__init__, register, unregister, specs`

- **Top-Level Functions**: `check_dangerous_command`

### 73. `hermclaw/tools/browser_tool.py`

- **File Type & Size**: Python Module | 8,808 bytes | 262 lines
- **Architectural Role**: Playwright browser automation tool.
- **Detailed Purpose & Implementation**: Implements `BrowserTool`. Enables agent to launch headless web browsers, navigate URLs, click DOM elements, fill input fields, take screenshots, and extract rendered webpage HTML/text using Playwright.

- **Key Classes Defined**:
  - `BrowserTool` (inherits from `ToolABC`) | Methods: `__init__, spec`

### 74. `hermclaw/tools/clipboard_tool.py`

- **File Type & Size**: Python Module | 3,687 bytes | 115 lines
- **Architectural Role**: System clipboard access tool.
- **Detailed Purpose & Implementation**: Implements `ClipboardTool`. Enables reading text from and writing text to the host OS clipboard using platform utilities (`pbcopy`/`pbpaste` on macOS, `xclip`/`xsel` on Linux, `powershell.exe` on Windows).

- **Key Classes Defined**:
  - `ClipboardTool` (inherits from `ToolABC`) | Methods: `spec`

### 75. `hermclaw/tools/code_exec.py`

- **File Type & Size**: Python Module | 4,336 bytes | 132 lines
- **Architectural Role**: Subprocess code execution sandbox tool.
- **Detailed Purpose & Implementation**: Implements `CodeExecTool`. Runs arbitrary Python or JavaScript code snippets inside isolated temporary subprocesses with strict execution timeouts.

- **Key Classes Defined**:
  - `CodeExecTool` (inherits from `ToolABC`) | Methods: `__init__, spec`

### 76. `hermclaw/tools/delegate_tool.py`

- **File Type & Size**: Python Module | 6,273 bytes | 185 lines
- **Architectural Role**: Multi-agent delegation tool.
- **Detailed Purpose & Implementation**: Implements `DelegateTool` and `SubagentRegistry`. Allows the primary agent turn to spawn asynchronous background sub-agents to perform parallel subtasks, monitoring their execution status and collecting results.

- **Key Classes Defined**:
  - `SubagentTask`
  - `SubagentRegistry` | Methods: `__init__, register, get, all_tasks, running_count`
  - `DelegateTool` (inherits from `ToolABC`) | Methods: `__init__, spec`

### 77. `hermclaw/tools/file_tools.py`

- **File Type & Size**: Python Module | 14,627 bytes | 442 lines
- **Architectural Role**: Structured file operation tools.
- **Detailed Purpose & Implementation**: Implements `FileReadTool`, `FileWriteTool`, `FileEditTool`, `ListDirTool`, and `GrepSearchTool`. Provides safe structured file operations (reading lines, writing files, multi-chunk editing, directory listing, ripgrep searches) within `filesystem_scope`.

- **Key Classes Defined**:
  - `FileReadTool` (inherits from `ToolABC`) | Methods: `__init__, spec`
  - `FileWriteTool` (inherits from `ToolABC`) | Methods: `__init__, spec`
  - `FileEditTool` (inherits from `ToolABC`) | Methods: `__init__, spec`
  - `ListDirTool` (inherits from `ToolABC`) | Methods: `__init__, spec`
  - `GrepSearchTool` (inherits from `ToolABC`) | Methods: `__init__, spec`

- **Top-Level Functions**: `_resolve_safe`

### 78. `hermclaw/tools/git_tool.py`

- **File Type & Size**: Python Module | 7,100 bytes | 215 lines
- **Architectural Role**: Git repository checkpoint and workflow tool.
- **Detailed Purpose & Implementation**: Implements `GitTool`. Enables the agent to inspect git status, view diffs, create automatic safety commits/checkpoints before complex edits, stash changes, and rollback uncommitted modifications.

- **Key Classes Defined**:
  - `GitTool` (inherits from `ToolABC`) | Methods: `spec, _run_git`

### 79. `hermclaw/tools/goals_tool.py`

- **File Type & Size**: Python Module | 8,880 bytes | 268 lines
- **Architectural Role**: Long-term autonomous goal tracking tool.
- **Detailed Purpose & Implementation**: Implements `GoalsTool` and `GoalsDB`. Allows the agent to set high-level goals, break them down into milestone steps, update progress, and persist goal states in SQLite. Active goals are automatically injected into the system prompt.

- **Key Classes Defined**:
  - `GoalsDB` | Methods: `__init__, close, create, update_progress, complete, list_active, list_all, get, active_summary, abandon`
  - `GoalsTool` (inherits from `ToolABC`) | Methods: `spec`

- **Top-Level Functions**: `_get_db`

### 80. `hermclaw/tools/media_tools.py`

- **File Type & Size**: Python Module | 9,638 bytes | 285 lines
- **Architectural Role**: Multimodal image generation and vision tool.
- **Detailed Purpose & Implementation**: Implements `ImageGenerateTool` and `VisionTool`. Generates images via DALL-E 3 or fal.ai APIs, and analyzes user-provided images using multimodal vision LLMs.

- **Key Classes Defined**:
  - `ImageGenerateTool` (inherits from `ToolABC`) | Methods: `__init__, spec`
  - `VisionTool` (inherits from `ToolABC`) | Methods: `spec`

### 81. `hermclaw/tools/memory_search.py`

- **File Type & Size**: Python Module | 2,664 bytes | 85 lines
- **Architectural Role**: Episodic memory full-text search tool.
- **Detailed Purpose & Implementation**: Implements `SessionSearchTool`. Exposes full-text FTS5 search over past conversation turns as a tool call, enabling the agent to recall past discussions on demand.

- **Key Classes Defined**:
  - `SessionSearchTool` (inherits from `ToolABC`) | Methods: `__init__, spec`

### 82. `hermclaw/tools/notify_tool.py`

- **File Type & Size**: Python Module | 3,551 bytes | 108 lines
- **Architectural Role**: Cross-platform system notification tool.
- **Detailed Purpose & Implementation**: Implements `NotifyTool`. Triggers desktop notifications on Windows (toasts), macOS (Notification Center), and Linux (`notify-send`), or sounds terminal bells.

- **Key Classes Defined**:
  - `NotifyTool` (inherits from `ToolABC`) | Methods: `spec`

### 83. `hermclaw/tools/pdf_tool.py`

- **File Type & Size**: Python Module | 5,552 bytes | 165 lines
- **Architectural Role**: PDF document text extraction tool.
- **Detailed Purpose & Implementation**: Implements `PDFTool`. Extracts readable text content from PDF documents using `PyMuPDF` (`fitz`), falling back to `pdfminer.six` or binary parsing.

- **Key Classes Defined**:
  - `PDFTool` (inherits from `ToolABC`) | Methods: `spec, _extract_pymupdf, _extract_pdfminer, _extract_basic`

### 84. `hermclaw/tools/scheduler_tool.py`

- **File Type & Size**: Python Module | 8,669 bytes | 260 lines
- **Architectural Role**: Task scheduling tool interface.
- **Detailed Purpose & Implementation**: Implements `SchedulerTool` and `ScheduleDB`. Enables the agent to programmatically schedule one-shot timers ("remind me in 30m") or recurring cron tasks stored in SQLite and executed by `HermclawScheduler`.

- **Key Classes Defined**:
  - `ScheduleDB` | Methods: `__init__, close, create, list_active, list_all, mark_run, cancel, pause, resume`
  - `SchedulerTool` (inherits from `ToolABC`) | Methods: `spec`

- **Top-Level Functions**: `_get_db`

### 85. `hermclaw/tools/shell.py`

- **File Type & Size**: Python Module | 4,085 bytes | 125 lines
- **Architectural Role**: Terminal command execution tool.
- **Detailed Purpose & Implementation**: Implements `ShellTool`. Exposes command-line execution capabilities. **Disabled by default in configuration (`tools.shell_enabled: false`)**; when disabled, it is completely unregistered from `ToolDispatcher`.

- **Key Classes Defined**:
  - `ShellTool` (inherits from `ToolABC`) | Methods: `__init__, spec`

### 86. `hermclaw/tools/system_info.py`

- **File Type & Size**: Python Module | 8,238 bytes | 248 lines
- **Architectural Role**: Hardware and OS metrics diagnostics tool.
- **Detailed Purpose & Implementation**: Implements `SystemInfoTool`. Queries host metrics (CPU utilization, RAM usage, disk space, GPU stats, active network interfaces, running processes, battery status) via `psutil`.

- **Key Classes Defined**:
  - `SystemInfoTool` (inherits from `ToolABC`) | Methods: `spec, _overview, _processes, _network, _gpu, _battery, _env_vars`

### 87. `hermclaw/tools/task_tools.py`

- **File Type & Size**: Python Module | 13,833 bytes | 415 lines
- **Architectural Role**: Todo list and Kanban board project management tools.
- **Detailed Purpose & Implementation**: Implements `KanbanTool`, `TodoTool`, and `_KanbanDB`. Provides persistent todo items and multi-column Kanban boards stored in SQLite for structured project management.

- **Key Classes Defined**:
  - `_KanbanDB` | Methods: `__init__, close, create_board, list_boards, get_board, add_task, move_task, add_todo, complete_todo, list_todos`
  - `KanbanTool` (inherits from `ToolABC`) | Methods: `spec`
  - `TodoTool` (inherits from `ToolABC`) | Methods: `spec`

- **Top-Level Functions**: `_get_db`

### 88. `hermclaw/tools/tts_tool.py`

- **File Type & Size**: Python Module | 5,091 bytes | 152 lines
- **Architectural Role**: Text-To-Speech audio synthesis tool.
- **Detailed Purpose & Implementation**: Implements `TTSTool`. Synthesizes audio speech from text using `edge-tts` (free, high-quality Microsoft Edge speech API) or OS native speech engines (`SAPI5`, `say`, `espeak`).

- **Key Classes Defined**:
  - `TTSTool` (inherits from `ToolABC`) | Methods: `spec, _platform_tts`

### 89. `hermclaw/tools/virtual_pet.py`

- **File Type & Size**: Python Module | 12,351 bytes | 375 lines
- **Architectural Role**: Gamified virtual pet companion tool.
- **Detailed Purpose & Implementation**: Implements `VirtualPetTool` and `VirtualPet`. Maintains state for `Clawbert` the Hermit Crab. Features mood mechanics (happiness, hunger, energy), evolution stages (Egg -> Baby -> Juvenile -> Adult -> Legendary), and renders dynamic ASCII art.

- **Key Classes Defined**:
  - `VirtualPet` | Methods: `__init__, close, _get_pet, adopt, status, feed, play, rest, rename, _apply_time_decay`
  - `VirtualPetTool` (inherits from `ToolABC`) | Methods: `__init__, spec`

### 90. `hermclaw/tools/web_tools.py`

- **File Type & Size**: Python Module | 10,663 bytes | 318 lines
- **Architectural Role**: Web search and HTTP webpage reading tools.
- **Detailed Purpose & Implementation**: Implements `WebSearchTool` (DuckDuckGo search without API keys) and `UrlReadTool` (fetches web pages and converts HTML to Markdown).

- **Key Classes Defined**:
  - `WebSearchTool` (inherits from `ToolABC`) | Methods: `spec, _format_results`
  - `UrlReadTool` (inherits from `ToolABC`) | Methods: `spec`

### 91. `hermclaw/tools/backends/__init__.py`

- **File Type & Size**: Python Package Initializer | 0 bytes | 1 line
- **Architectural Role**: Backends package root.
- **Detailed Purpose & Implementation**: Package initialization file for tool execution backends.

### 92. `hermclaw/tools/backends/docker.py`

- **File Type & Size**: Python Module | 2,649 bytes | 82 lines
- **Architectural Role**: Docker container isolated execution backend.
- **Detailed Purpose & Implementation**: Implements Docker execution backend. Runs shell commands inside disposable Docker containers with network access disabled by default (`tools.docker_network: none`) to eliminate SSRF risks.

### 93. `hermclaw/tools/backends/local.py`

- **File Type & Size**: Python Module | 2,376 bytes | 75 lines
- **Architectural Role**: Local subprocess execution backend.
- **Detailed Purpose & Implementation**: Implements local subprocess backend. Executes shell commands using `asyncio.create_subprocess_exec` within the confined profile workspace directory.

- **Top-Level Functions**: `scoped_env`

### 94. `hermclaw/tools/backends/ssh.py`

- **File Type & Size**: Python Module | 1,590 bytes | 52 lines
- **Architectural Role**: Remote SSH execution backend.
- **Detailed Purpose & Implementation**: Implements SSH execution backend for executing commands on remote servers via SSH connections.

### 95. `hermclaw/tools/backends/stubs.py`

- **File Type & Size**: Python Module | 1,419 bytes | 48 lines
- **Architectural Role**: Placeholder stubs for out-of-scope execution backends.
- **Detailed Purpose & Implementation**: Defines stubs for Singularity, Modal, and Daytona backends. Raises explicit `NotImplementedError` with tracking messages if invoked.

## Development & Configuration Scripts (`scripts/`)

### 96. `scripts/__init__.py`

- **File Type & Size**: Python Package Initializer | 0 bytes | 1 line
- **Architectural Role**: Scripts package root.
- **Detailed Purpose & Implementation**: Package initialization file for development scripts.

### 97. `scripts/list_config_fields.py`

- **File Type & Size**: Python Utility Script | 1,575 bytes | 52 lines
- **Architectural Role**: Pydantic schema inspection utility.
- **Detailed Purpose & Implementation**: Recursively inspects `HermclawConfig` Pydantic models to extract and list all valid dot-notation config paths. Used to verify documentation completeness in `tests/test_config_reference_coverage.py`.

- **Top-Level Functions**: `_is_model, leaf_field_paths`

## Comprehensive Test Suite & Harness (`tests/`)

### 98. `tests/__init__.py`

- **File Type & Size**: Python Package Initializer | 0 bytes | 1 line
- **Architectural Role**: Test package root.
- **Detailed Purpose & Implementation**: Initializer for the Pytest test suite.

### 99. `tests/conftest.py`

- **File Type & Size**: Root Pytest Configuration | 2,922 bytes | 92 lines
- **Architectural Role**: Root Pytest configuration and network socket guard.
- **Detailed Purpose & Implementation**: Implements `block_real_sockets` (autouse fixture). Intercepts and blocks all external network socket creation during test runs unless marked with `@pytest.mark.live`, ensuring tests run 100% offline by default.

- **Top-Level Functions**: `pytest_configure, isolated_hermclaw_home, block_real_sockets, anthropic_key_env, profile_manager`

### 100. `tests/test_cli.py`

- **File Type & Size**: Pytest CLI Test File | 3,698 bytes | 118 lines
- **Architectural Role**: Unit tests for CLI subcommands.
- **Detailed Purpose & Implementation**: Validates CLI commands (`chat`, `serve`, `doctor`, `reflect`, `skills`). Asserts that CLI exposes exactly five top-level subcommands and tests `--json` output formatting.

- **Top-Level Functions**: `_fake_api_key, test_help_lists_exactly_five_subcommands, test_doctor_init_writes_config_and_is_idempotent, test_doctor_reports_missing_gateway_token_as_failure, test_doctor_json_output_is_valid_json, test_doctor_fix_creates_state_db, test_skills_list_empty, test_skills_validate_empty_passes, test_skills_show_unknown_skill_gives_clean_error, test_reflect_on_profile_with_zero_sessions, test_reflect_all_profiles_with_no_profiles_yet, test_invalid_config_gives_clean_error_not_traceback`

### 101. `tests/test_config.py`

- **File Type & Size**: Pytest Config Test File | 5,189 bytes | 158 lines
- **Architectural Role**: Unit tests for configuration management.
- **Detailed Purpose & Implementation**: Tests Pydantic schema validation, unknown key rejection, LKG fallback mechanics, anti-clobber protection against section deletion, and file watching.

- **Top-Level Functions**: `test_missing_config_writes_safe_defaults, test_valid_config_round_trips, test_unknown_top_level_key_rejected, test_unknown_nested_key_rejected, test_schema_passthrough_allowed, test_invalid_config_falls_back_to_lkg, test_invalid_config_with_no_lkg_reports_invalid, test_malformed_yaml_falls_back_to_lkg, test_save_config_text_refuses_large_shrink, test_save_config_text_refuses_dropped_agent_block, test_save_config_text_force_overrides_protection, test_save_config_text_normal_edit_succeeds`

### 102. `tests/test_config_reference_coverage.py`

- **File Type & Size**: Pytest Coverage Test File | 1,466 bytes | 45 lines
- **Architectural Role**: Automated documentation sync test.
- **Detailed Purpose & Implementation**: Compares leaf field paths in `HermclawConfig` Pydantic models against tables in `docs/CONFIG_REFERENCE.md`. Fails the build if any config field is undocumented or obsolete.

- **Top-Level Functions**: `_documented_field_paths, test_every_schema_field_is_documented, test_doc_does_not_document_nonexistent_fields`

### 103. `tests/test_conftest_guards.py`

- **File Type & Size**: Pytest Guard Test File | 558 bytes | 22 lines
- **Architectural Role**: Tests for test runner network guards.
- **Detailed Purpose & Implementation**: Verifies that `block_real_sockets` correctly blocks real network connections and that `@pytest.mark.live` properly bypasses the block.

- **Top-Level Functions**: `test_real_connection_is_actually_blocked, test_live_marker_bypasses_guard`

### 104. `tests/test_gateway.py`

- **File Type & Size**: Pytest Gateway Test File | 4,443 bytes | 138 lines
- **Architectural Role**: Unit tests for `Gateway` HTTP API.
- **Detailed Purpose & Implementation**: Tests FastAPI gateway routes (`/status`, `/health`, `/reload`, `/chat`), authentication token checks, and WebSocket messaging channels.

- **Key Classes Defined**:
  - `SyntheticChannel` (inherits from `ChannelAdapter`) | Methods: `__init__, health`

- **Top-Level Functions**: `gateway_config_no_cli`

### 105. `tests/test_mcp_client.py`

- **File Type & Size**: Pytest MCP Client Test File | 1,481 bytes | 48 lines
- **Architectural Role**: Integration tests for MCP client.
- **Detailed Purpose & Implementation**: Tests `McpClientManager` tool discovery and execution against `mcp_test_server.py`.

- **Key Classes Defined**:
  - `_FakeMcpServerConfig` | Methods: `__init__`

### 106. `tests/test_scheduler.py`

- **File Type & Size**: Pytest Scheduler Test File | 5,619 bytes | 175 lines
- **Architectural Role**: Unit tests for `HermclawScheduler`.
- **Detailed Purpose & Implementation**: Tests APScheduler integration, cron expression parsing, heartbeat classification (`ok`, `background`, `alert`), and message routing to channel adapters.

- **Key Classes Defined**:
  - `RecordingChannel` (inherits from `ChannelAdapter`) | Methods: `__init__, health`

- **Top-Level Functions**: `_build_runtime, test_classify_heartbeat_response, test_parse_duration, test_heartbeat_interval_precedence`

### 107. `tests/test_skills.py`

- **File Type & Size**: Pytest Skills Test File | 5,245 bytes | 162 lines
- **Architectural Role**: Unit tests for `agentskills.io` skill loading.
- **Detailed Purpose & Implementation**: Validates `SKILL.md` frontmatter parsing, metadata validation (name formatting, description checks), prompt injection character rejection, and Tier 1 progressive disclosure compact listing.

- **Top-Level Functions**: `_write_skill, test_valid_skill_passes, test_missing_skill_md, test_name_mismatch_rejected, test_name_too_long_rejected, test_name_invalid_characters_rejected, test_missing_description_rejected, test_prompt_injection_chars_rejected, test_missing_frontmatter_rejected, test_allowed_tools_parsed, test_auto_generated_flag_read_from_metadata, test_registry_loads_only_valid_skills`

### 108. `tests/brain/__init__.py`

- **File Type & Size**: Python Package Initializer | 0 bytes | 1 line
- **Architectural Role**: Brain tests subpackage root.
- **Detailed Purpose & Implementation**: Initializer for brain unit tests.

### 109. `tests/brain/conftest.py`

- **File Type & Size**: Pytest Fixtures File | 1,228 bytes | 42 lines
- **Architectural Role**: Pytest fixtures for brain testing.
- **Detailed Purpose & Implementation**: Defines `wired_profile` fixture. Sets up isolated temporary profile directories with mock databases and memory stores for testing brain components.

- **Top-Level Functions**: `wired_profile`

### 110. `tests/brain/test_agent_loop.py`

- **File Type & Size**: Pytest Unit Test File | 5,135 bytes | 155 lines
- **Architectural Role**: Unit tests for `HermclawAgent`.
- **Detailed Purpose & Implementation**: Exercises `HermclawAgent` ReAct loop, tool call dispatching, multi-turn message assembly, model fallback logic, and error handling using `AlwaysFailsTransport` and `FakeTransport`.

### 111. `tests/brain/test_compressor.py`

- **File Type & Size**: Pytest Unit Test File | 3,678 bytes | 115 lines
- **Architectural Role**: Unit tests for context window compression.
- **Detailed Purpose & Implementation**: Tests `ContextCompressor` trigger conditions, memory flush turns, summary recap creation, and lineage tracking across parent session IDs.

- **Top-Level Functions**: `_make_agent`

### 112. `tests/brain/test_memory_store.py`

- **File Type & Size**: Pytest Unit Test File | 5,032 bytes | 148 lines
- **Architectural Role**: Unit tests for `MemoryStore`.
- **Detailed Purpose & Implementation**: Validates SQLite `MemoryStore` operations, WAL mode concurrency, strict permissions (0600), message serialization, and FTS5 full-text search query sanitization.

- **Top-Level Functions**: `test_session_and_message_round_trip, test_wal_mode_enabled, test_state_db_permissions_are_owner_only, test_session_search_finds_matches, test_session_search_handles_special_characters_safely, test_session_search_performance_under_500_messages, test_compressed_away_messages_excluded_when_requested, test_compressed_away_messages_still_searchable, test_parent_session_id_lineage`

### 113. `tests/brain/test_profiles.py`

- **File Type & Size**: Pytest Unit Test File | 4,234 bytes | 132 lines
- **Architectural Role**: Unit tests for profile isolation.
- **Detailed Purpose & Implementation**: Asserts profile directory isolation, path traversal prevention (`../../`), identity file persistence, and system prompt composition.

- **Top-Level Functions**: `test_ensure_profile_creates_expected_layout, test_two_profiles_get_distinct_roots, test_path_traversal_rejected, test_list_profiles, test_soul_md_never_auto_written, test_memory_facts_appended_and_trimmed_to_limit, test_assemble_system_prompt_includes_all_sections`

### 114. `tests/brain/test_reflection_and_skill_growth.py`

- **File Type & Size**: Pytest Unit Test File | 5,974 bytes | 175 lines
- **Architectural Role**: Unit tests for reflection and skill growth.
- **Detailed Purpose & Implementation**: Tests automated memory distillation, token similarity metrics, and draft skill creation from repeated procedures.

- **Top-Level Functions**: `test_token_similarity_separates_same_from_different_procedures`

### 115. `tests/contracts/__init__.py`

- **File Type & Size**: Python Package Initializer | 0 bytes | 1 line
- **Architectural Role**: Contracts tests package root.
- **Detailed Purpose & Implementation**: Initializer for channel adapter contract tests.

### 116. `tests/contracts/test_channel_adapter.py`

- **File Type & Size**: Pytest Shared Lifecycle Test File | 9,431 bytes | 285 lines
- **Architectural Role**: Shared contract test suite for channel adapters.
- **Detailed Purpose & Implementation**: Exercises standard lifecycle (`start()` -> inbound message -> outbound reply -> `stop()`) against every channel adapter (CLI, Web, Telegram, Discord, Slack, WhatsApp) using in-memory fakes to verify contract compliance without network calls.

- **Key Classes Defined**:
  - `_FakeUpdater` | Methods: `__init__`
  - `_FakeBot` | Methods: `__init__`
  - `_FakeTelegramApp` | Methods: `__init__, add_handler`
  - `_FakeDiscordChannelObj` | Methods: `__init__`
  - `_FakeDiscordClient` | Methods: `__init__, event, get_channel`
  - `_FakeSlackClient` | Methods: `__init__`
  - `_FakeSlackApp` | Methods: `__init__, event`
  - `_FakeSocketHandler` | Methods: `__init__`
  - `_FakeStreamWriter` | Methods: `__init__, write`
  - `_FakeStreamReader` | Methods: `__init__, push`
  - `_FakeWhatsAppProcess` | Methods: `__init__, terminate`

### 117. `tests/fixtures/mcp_test_server.py`

- **File Type & Size**: Subprocess MCP Server Test Fixture | 1,708 bytes | 55 lines
- **Architectural Role**: Real MCP server subprocess fixture.
- **Detailed Purpose & Implementation**: Implements a minimal real MCP server communicating over stdio. Used by `test_mcp_client.py` to test end-to-end MCP tool discovery and invocation.

### 118. `tests/security/__init__.py`

- **File Type & Size**: Python Package Initializer | 0 bytes | 1 line
- **Architectural Role**: Security tests package root.
- **Detailed Purpose & Implementation**: Initializer for security tests.

### 119. `tests/security/test_tool_security.py`

- **File Type & Size**: Pytest Security Test File | 3,898 bytes | 122 lines
- **Architectural Role**: Unit tests for security enforcement.
- **Detailed Purpose & Implementation**: Tests dangerous command regex pattern detection (`rm -rf /`), secret redaction from logs, environment variable reference resolution, and workspace directory scope confinement.

- **Top-Level Functions**: `test_dangerous_command_detection, test_redact_hides_secret_looking_values, test_resolve_env_ref_reads_actual_environment, test_filesystem_scope_sets_working_directory, test_shell_tool_rejects_unknown_backend`
