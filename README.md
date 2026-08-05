<h1 align="center">
  🦀 HermClaw
</h1>

<p align="center">
  <strong>A unified, self-improving personal AI agent with 28 tools, no guardrails, and self-learning.</strong>
</p>

<p align="center">
  <a href="#install">Install</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#tools">28 Tools</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#model-providers">Model Providers</a> •
  <a href="#commands">Commands</a>
</p>

---

## What is HermClaw?

HermClaw merges two frameworks into one self-improving AI agent:

- **Body** (from OpenClaw): local-first gateway, messaging channels, cron scheduler
- **Brain** (from Hermes Agent): ReAct tool-calling loop, SQLite memory, context compression, skill evolution

**Key principles:**
- 🔓 **No guardrails** — full system access by default (shell, filesystem, apps)
- 🧠 **Self-learning** — reflection loop distills experience into memory and skills
- 🏠 **Local-first** — runs on your machine with Ollama, no cloud API key required
- 🛠️ **28 tools** — file I/O, shell, git, browser, code execution, web search, TTS, vision, PDF, and more
- 🎮 **Fun** — virtual pet, achievements system, learning graph

---

## Prerequisites

| Requirement | How to check |
|---|---|
| **Python 3.11+** | `python --version` |
| **Git** | `git --version` |
| **Ollama** (recommended) | `ollama --version` — [Install Ollama](https://ollama.com/download) |

---

## Install

### Option 1: pip install (recommended)

```bash
# Clone the repo
git clone https://github.com/hermclaw/hermclaw.git
cd hermclaw

# Create virtual environment
python -m venv .venv

# Activate it
# Linux / macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\activate

# Install HermClaw
pip install -e .
```

### Option 2: With all extras

```bash
pip install -e ".[all]"
```

### Option 3: requirements.txt

```bash
pip install -r requirements.txt
pip install -e .
```

### Optional extras

Install only what you need:

```bash
# Model providers
pip install -e ".[anthropic]"        # Claude
pip install -e ".[openai]"           # GPT-4o
pip install -e ".[bedrock]"          # AWS Bedrock

# Features
pip install -e ".[browser]"          # Playwright browser automation
pip install -e ".[voice]"            # Text-to-speech (edge-tts)
pip install -e ".[pdf]"              # PDF text extraction (PyMuPDF)
pip install -e ".[mcp]"              # Model Context Protocol

# Messaging channels
pip install -e ".[telegram]"
pip install -e ".[discord]"
pip install -e ".[slack]"
pip install -e ".[channels]"         # All messaging channels

# Everything
pip install -e ".[all]"
```

---

## Quick Start

### 1. Pull an Ollama model (default)

```bash
ollama pull gemma4:12b
ollama serve                         # start Ollama server (if not running)
```

### 2. Initialize config

```bash
hermclaw doctor --init
```

This creates `~/.hermclaw/hermclaw.yaml` pre-configured for **Ollama** with **no guardrails** and **self-learning enabled**.

### 3. Start chatting

```bash
hermclaw chat
```

That's it. No API keys needed for local models.

### One-shot mode (for scripting)

```bash
hermclaw run "list all Python files in the current directory"
```

### Start the full gateway (multi-channel)

```bash
hermclaw serve                       # foreground
hermclaw serve --daemonize           # detached (POSIX only)
```

---

## Tools

HermClaw comes with **28 built-in tools** the agent can use autonomously:

### File & Code (8 tools)
| Tool | Description |
|---|---|
| `file_read` | Read files with line ranges |
| `file_write` | Create and write files |
| `file_edit` | Targeted search-and-replace editing |
| `list_dir` | List directory contents |
| `grep_search` | Regex search across files |
| `code_exec` | Execute Python/JavaScript in sandbox |
| `shell` | Run any shell command |
| `git` | Git checkpoint, diff, rollback, stash, branch |

### Web & Browser (3 tools)
| Tool | Description |
|---|---|
| `web_search` | DuckDuckGo search |
| `url_read` | Extract content from URLs |
| `browser` | Full Playwright browser automation (click, type, screenshot, JS eval) |

### Media & Documents (4 tools)
| Tool | Description |
|---|---|
| `image_generate` | DALL-E / fal.ai image generation |
| `vision` | Image analysis (GPT-4o / Ollama LLaVA) |
| `tts` | Text-to-speech with 15+ voices |
| `pdf_read` | Extract text from PDF files |

### Memory & Intelligence (3 tools)
| Tool | Description |
|---|---|
| `memory` | Vector semantic search + keyword fallback |
| `goals` | Autonomous long-running goal tracking |
| `learning_graph` | Concept relationships + ASCII visualization |

### Projects & Tasks (3 tools)
| Tool | Description |
|---|---|
| `kanban` | Full project management board |
| `todo` | Quick todo list |
| `delegate` | Spawn sub-agents for parallel work |

### System (5 tools)
| Tool | Description |
|---|---|
| `app_launcher` | Open any app, URL, or file (40+ Windows app shortcuts) |
| `clipboard` | Read/write system clipboard |
| `notify` | System notifications (toast/alert) |
| `system_info` | CPU, RAM, disk, network, GPU metrics |
| `scheduler` | Cron jobs, intervals, one-shot timers |

### Fun & Gamification (2 tools)
| Tool | Description |
|---|---|
| `pet` | ASCII virtual pet (5 evolution stages, mood, hunger/energy) |
| `achievements` | 24 achievements across 6 categories |

---

## Commands

| Command | Purpose |
|---|---|
| `hermclaw chat` | Interactive local conversation |
| `hermclaw run "prompt"` | One-shot mode: send prompt, get response, exit |
| `hermclaw serve` | Start the gateway (all channels + scheduler + HTTP API) |
| `hermclaw doctor` | Diagnostics, first-run wizard (`--init`), auto-fix (`--fix`) |
| `hermclaw reflect` | Manually trigger the self-learning reflection loop |
| `hermclaw models` | List all available models in the catalog |
| `hermclaw skills` | List, validate, and inspect skills |
| `hermclaw sessions` | List, show, export, and delete sessions |
| `hermclaw plugins` | List, install, uninstall, create plugins |

Every command accepts `--config`, `--profile`, and `--json` globally.

---

## Configuration

Everything lives in `~/.hermclaw/hermclaw.yaml`. The defaults are:

| Setting | Default | Description |
|---|---|---|
| Model provider | `openai_compat` (Ollama) | Local model, no API key |
| Model | `gemma4:12b` | Change to any Ollama model |
| Shell access | **Enabled** | Full system access |
| Approvals | **Off** | No confirmation prompts |
| Filesystem scope | **Full** | Unrestricted file access |
| Self-learning | **Enabled** | Reflection + skill evolution |
| Language | `en` | 16 languages available |

See [`hermclaw.example.yaml`](hermclaw.example.yaml) for the fully-commented reference.

---

## Model Providers

### Ollama (default — local, free)

```bash
ollama pull gemma4:12b
ollama serve
hermclaw chat
```

No config changes needed. Works out of the box.

### Other Ollama models

Edit `~/.hermclaw/hermclaw.yaml`:

```yaml
brain:
  model:
    model_name: "llama3.1:8b"        # or qwen2.5:14b, mistral, deepseek-r1, etc.
```

### Anthropic (Claude)

```bash
pip install -e ".[anthropic]"
```

```yaml
brain:
  model:
    provider: "anthropic"
    model_name: "claude-sonnet-4-6"
    api_key_env: "ANTHROPIC_API_KEY"
```

```bash
export ANTHROPIC_API_KEY="your-key-here"          # Linux/macOS
$env:ANTHROPIC_API_KEY = "your-key-here"           # Windows PowerShell
```

### Google Gemini

```yaml
brain:
  model:
    provider: "openai_compat"
    model_name: "gemini-2.5-flash"
    api_key_env: "GEMINI_API_KEY"
    api_base_env: "GEMINI_API_BASE"
```

```bash
export GEMINI_API_KEY="your-key"
export GEMINI_API_BASE="https://generativelanguage.googleapis.com/v1beta/openai"
```

### OpenAI

```bash
pip install -e ".[openai]"
```

```yaml
brain:
  model:
    provider: "openai_compat"
    model_name: "gpt-4o"
    api_key_env: "OPENAI_API_KEY"
    api_base_env: null               # uses default OpenAI endpoint
```

### Any OpenAI-compatible server (vLLM, LM Studio, OpenRouter, etc.)

```yaml
brain:
  model:
    provider: "openai_compat"
    model_name: "your-model"
    api_key_env: "YOUR_API_KEY"
    api_base_env: "YOUR_BASE_URL"    # e.g. http://localhost:8000/v1
```

### AWS Bedrock

```bash
pip install -e ".[bedrock]"
```

```yaml
brain:
  model:
    provider: "bedrock"
    model_name: "anthropic.claude-sonnet-4-6-v1"
```

---

## Infrastructure

HermClaw includes production-grade infrastructure:

| System | Description |
|---|---|
| **Plugin System** | Discover, load, git install, create plugin templates |
| **Audit Logging** | SQLite-backed audit trail of every tool call |
| **Rate Limiting** | Per-tool rate limits (configurable) |
| **Response Cache** | LRU cache with TTL for repeated queries |
| **Parallel Execution** | Concurrent tool dispatch when multiple tools needed |
| **Mixture-of-Agents** | Query multiple models and merge responses |
| **i18n** | 16 languages (en, es, de, fr, ja, ko, zh, pt, ru, hi, tr, it, uk, af, ga, hu) |
| **Model Catalog** | 16 pre-configured models across 7 providers |

---

## Project Structure

```
hermclaw/
├── hermclaw/
│   ├── brain/              # Agent loop, memory, models, cache, learning graph
│   │   ├── agent_loop.py   # ReAct-style tool-calling loop
│   │   ├── memory/         # SQLite store, vector memory, compressor
│   │   ├── cache.py        # Response cache (LRU + TTL)
│   │   ├── learning_graph.py
│   │   ├── model_catalog.py
│   │   ├── moa.py          # Mixture-of-Agents
│   │   ├── parallel_exec.py
│   │   └── transports/     # Provider adapters (Anthropic, OpenAI, Bedrock)
│   ├── body/               # Gateway, channels, scheduler
│   ├── tools/              # All 28 tools
│   ├── plugins/            # Plugin system
│   ├── security/           # Audit logging, rate limiting, secrets
│   ├── skills/             # Skill registry
│   ├── cli.py              # CLI entry point (9 commands)
│   ├── runtime.py          # Agent runtime builder
│   ├── config.py           # Configuration system
│   ├── i18n.py             # 16-language translations
│   └── banner.py           # ASCII art branding
├── tests/
├── docs/
├── hermclaw.example.yaml   # Reference configuration
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

---

## License

MIT
