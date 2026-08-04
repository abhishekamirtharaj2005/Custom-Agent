# Hermclaw

Hermclaw is a unified, self-improving personal AI agent. It merges two previously-separate frameworks into one coherent, one-command-installable Python package:

- **Body**, derived from OpenClaw: a local-first gateway, pluggable messaging channels, and a heartbeat/cron scheduler.
- **Brain**, derived from Hermes Agent: a ReAct-style tool-calling loop, SQLite-backed memory with full-text recall, context compression, and a reflection loop that distills what it learns into durable memory and new skills over time.

Where the two source projects overlapped, Hermclaw picks one implementation deliberately rather than keeping both -- see [MERGE_DECISIONS.md](MERGE_DECISIONS.md) for every resolution and why. Where they didn't overlap, both capabilities are kept. The full architecture is documented in [ARCHITECTURE.md](ARCHITECTURE.md).

## What it does

Hermclaw runs continuously on your own machine. You talk to it over whichever channels you enable -- a local CLI, a small web widget, Telegram, Discord, Slack, or WhatsApp -- and it remembers what matters across sessions, checks in on a schedule if you want it to, and can safely run shell commands and MCP tools on your behalf, gated by an approval system that's off by default and opt-in when you want it.

It's also designed to get better at your specific use cases over time: a reflection loop periodically reviews recent sessions, distills durable facts into its memory, and notices when you've asked it to do the same multi-step procedure repeatedly -- turning that into a draft skill it can just run next time, instead of you re-explaining it.

## Prerequisites

- **Python 3.11 or later** (`python --version` to check)
- **Git** (to clone the repo)

## Install

Hermclaw is installed from source. Clone the repo and set up a virtual environment:

```bash
git clone https://github.com/hermclaw/hermclaw.git
cd hermclaw

# Create and activate a virtual environment
python -m venv .venv

# Activate (pick your platform):
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows (PowerShell)

# Install Hermclaw in editable mode
pip install -e .
```

Channel support beyond the local CLI and web widget is opt-in, since most people don't want every dependency for every chat platform:

```bash
pip install -e ".[telegram,discord,slack]"   # or any subset
pip install -e ".[bedrock]"                  # AWS Bedrock as a model provider
```

WhatsApp is a special case: it bridges to a small Node.js sidecar (there is no viable pure-Python WhatsApp client), which needs its own one-time setup:

```bash
cd hermclaw/body/channels/whatsapp_sidecar && npm install
```

## First run

### 1. Initialize configuration

```bash
hermclaw doctor --init
```

This writes a default config to `~/.hermclaw/hermclaw.yaml`. By default it's set up for Anthropic (Claude). You can use it as-is or switch providers — see [Model providers](#model-providers) below.

### 2. Set your API key

**Anthropic (default):**

```bash
# Linux / macOS
export ANTHROPIC_API_KEY="your-key-here"

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "your-key-here"
```

### 3. Verify and chat

```bash
hermclaw doctor      # verify everything checks out
hermclaw chat        # start talking to it
```

`hermclaw chat` is a lightweight, local-only conversation -- it doesn't start the gateway or any other channel. When you're ready to run it as a persistent agent across whichever channels you've configured:

```bash
hermclaw serve                # foreground
hermclaw serve --daemonize    # detached, POSIX only
```

## Model providers

Hermclaw supports three model providers: `anthropic` (default), `openai_compat`, and `bedrock`. The provider is configured in `~/.hermclaw/hermclaw.yaml` under `brain.model`.

### Anthropic (default)

Works out of the box after `hermclaw doctor --init`. Just set `ANTHROPIC_API_KEY`.

### Google Gemini (via OpenAI-compatible endpoint)

Edit `~/.hermclaw/hermclaw.yaml` and change the `brain.model` section:

```yaml
brain:
  model:
    provider: "openai_compat"
    model_name: "gemini-2.5-flash"       # or any Gemini model
    api_key_env: "GEMINI_API_KEY"
    api_base_env: "GEMINI_API_BASE"
    context_window: 1048576
```

Then set the environment variables:

```bash
# Linux / macOS
export GEMINI_API_KEY="your-gemini-api-key"
export GEMINI_API_BASE="https://generativelanguage.googleapis.com/v1beta/openai"

# Windows (PowerShell)
$env:GEMINI_API_KEY = "your-gemini-api-key"
$env:GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
```

Get a Gemini API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### Other OpenAI-compatible providers (Ollama, vLLM, LM Studio, OpenRouter, etc.)

The `openai_compat` provider works with any server exposing a `/chat/completions` endpoint:

```yaml
brain:
  model:
    provider: "openai_compat"
    model_name: "your-model-name"
    api_key_env: "OPENAI_COMPAT_API_KEY"
    api_base_env: "OPENAI_COMPAT_API_BASE"
    context_window: 128000
```

### AWS Bedrock

Requires the `bedrock` extra: `pip install -e ".[bedrock]"`. Uses your AWS credentials (environment variables or `~/.aws/credentials`).

```yaml
brain:
  model:
    provider: "bedrock"
    model_name: "anthropic.claude-sonnet-4-6-v1"
```

## The five commands

Hermclaw's CLI is deliberately small:

| Command | Purpose |
|---|---|
| `hermclaw chat` | Interactive local conversation for one profile |
| `hermclaw serve` | Start the gateway: every enabled channel, the scheduler, the HTTP control API |
| `hermclaw doctor` | Diagnostics, a first-run wizard (`--init`), auto-fixes (`--fix`), and a status snapshot |
| `hermclaw reflect` | Manually trigger the reflection loop (it also runs automatically) |
| `hermclaw skills` | `list`, `validate`, and `show` skills for a profile |

Every command accepts `--config`, `--profile`, and `--json` globally. See `hermclaw --help` and `docs/CONFIG_REFERENCE.md` for the full picture.

## Configuration

Everything lives in one file, `~/.hermclaw/hermclaw.yaml`. `hermclaw.example.yaml` in this repo is the fully-commented reference version -- it's the literal file Hermclaw writes on first run. Every field is documented in [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md).

A few defaults worth knowing about up front:

- **`tools.shell_enabled: false`.** Shell access is off until you turn it on. This is a deliberate default -- see ARCHITECTURE.md's security section for why.
- **`tools.approvals.mode: manual`.** When shell access is on, every command asks first, unless you change this.
- **Config edits are safe to make while Hermclaw is running.** It watches its own config file and hot-reloads whatever changed without dropping other channels or losing state.

## Skills

Hermclaw uses the [agentskills.io](https://agentskills.io) open standard for skills -- the same format both source projects already used, so nothing new to learn. A skill is a directory with a `SKILL.md` file (YAML frontmatter plus Markdown instructions), optionally alongside `scripts/`, `references/`, and `assets/`. See [docs/SKILL_AUTHORING.md](docs/SKILL_AUTHORING.md) for how to write one by hand, and how the ones Hermclaw drafts for you automatically differ.

## Development

```bash
# After cloning and creating a venv (see Install above):
pip install -e ".[dev]"
pytest
```

The default test run is fully offline -- every test that would otherwise need a real network connection is exercised against a fake instead (see `tests/conftest.py`), and a session-wide guard fails the run if anything tries to open a real connection outside a test explicitly marked `@pytest.mark.live`.

## License

MIT
