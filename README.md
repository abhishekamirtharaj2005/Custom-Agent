<h1 align="center">
  🦀 HermClaw
</h1>

<p align="center">
  <strong>A unified, self-improving personal AI agent with 40+ tools, no guardrails, and self-learning.</strong>
</p>

<p align="center">
  <a href="#install">Install</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#tools">40+ Tools</a> •
  <a href="#self-learning">Self-Learning</a> •
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
- 🧠 **Self-learning** — reflection loop distills experience into memory, skills, and a concept graph
- 🏠 **Local-first** — runs on your machine with Ollama, no cloud API key required
- 🛠️ **40+ tools** — file I/O, shell, git, browser, code execution, web search, TTS, vision, PDF, voice cloning, and more
- 🎮 **Fun** — virtual pet (5 evolution stages), achievements system, learning graph
- 🌐 **Multi-provider** — Ollama, OpenAI, Anthropic, Google Gemini, Groq, OpenRouter, AWS Bedrock
- 🔌 **Extensible** — plugin system, custom skills, protocol integrations (Twitter, Spotify, Home Assistant)

---

## Prerequisites

| Requirement | How to check |
|---|---|
| **Python 3.11+** | `python --version` |
| **Git** | `git --version` |
| **Ollama** (recommended) | `ollama --version` — [Install Ollama](https://ollama.com/download) |

---

## Install

```bash
git clone https://github.com/abhishekamirtharaj2005/Custom-Agent.git
cd Custom-Agent
python install.py
```

The setup wizard will interactively ask you:

1. **Model Provider** — Ollama (local/free), OpenAI, Anthropic, Groq, OpenRouter, or custom
2. **Model** — Pick from available models for your chosen provider
3. **API Key** — Enter your API key (or skip for Ollama)
4. **Chat Platforms** — Enable Telegram, Discord, Slack bots (optional)
5. **Security** — Shell access and approval mode

Then it automatically:
- ✅ Installs hermclaw + required extras
- ✅ Generates `~/.hermclaw/hermclaw.yaml`
- ✅ Saves API keys to `~/.hermclaw/.env`
- ✅ Pulls Ollama model (if applicable)
- ✅ Verifies the installation

### Re-run setup anytime

```bash
hermclaw setup
```

---

## Manual Install (Alternative)

<details>
<summary>Click to expand manual installation steps</summary>

### Option 1: pip install

```bash
git clone https://github.com/abhishekamirtharaj2005/Custom-Agent.git
cd Custom-Agent
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
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

```bash
# Model providers
pip install -e ".[anthropic]"        # Claude
pip install -e ".[openai]"           # GPT-4o

# Features
pip install -e ".[browser]"          # Playwright browser
pip install -e ".[voice]"            # Text-to-speech
pip install -e ".[pdf]"              # PDF extraction

# Messaging channels
pip install -e ".[telegram,discord,slack]"

# Everything
pip install -e ".[all]"
```

### Quick Start (manual)

```bash
ollama pull gemma4:12b && ollama serve
hermclaw doctor --init
hermclaw chat
```

</details>

---

## Quick Start

After installation (either method), just run:

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

HermClaw comes with **40+ built-in tools** the agent can use autonomously:

### 📁 File & Code (8 tools)
| Tool | Description |
|---|---|
| `file_read` | Read files with line ranges |
| `file_write` | Create and write files |
| `file_edit` | Targeted search-and-replace editing |
| `list_dir` | List directory contents |
| `grep_search` | Regex search across files |
| `code_exec` | Execute Python/JavaScript/Bash in sandboxed environments |
| `shell` | Run any shell command (PowerShell, Bash, Cmd) |
| `git` | Git checkpoint, diff, rollback, stash, branch, log |

### 🌐 Web & Browser (3 tools)
| Tool | Description |
|---|---|
| `web_search` | DuckDuckGo search with result extraction |
| `url_read` | Extract and parse content from URLs |
| `browser` | Full Playwright browser automation (click, type, screenshot, JS eval, navigate) |

### 🎨 Media & Documents (7 tools)
| Tool | Description |
|---|---|
| `image_generate` | DALL-E 3 / fal.ai image generation |
| `vision` | Image analysis (GPT-4o / Ollama LLaVA) |
| `tts` | Text-to-speech with 15+ voices (pyttsx3) |
| `elevenlabs_tts` | Premium ElevenLabs TTS with voice selection |
| `video_generate` | Video generation from text prompts |
| `pdf_read` | Extract text from PDF files |
| `transcribe` | Audio transcription (Whisper) |

### 🎤 Voice (2 tools)
| Tool | Description |
|---|---|
| `voice_clone` | Clone voices from audio samples |
| `voice_effects` | Apply audio effects (pitch, speed, reverb) |

### 🧠 Memory & Intelligence (4 tools)
| Tool | Description |
|---|---|
| `memory` | Persistent memory with semantic search + keyword fallback |
| `learning_graph` | Concept relationship graph with confidence tracking + ASCII visualization |
| `session_search` | Search across conversation history |
| `model_catalog` | List models, check current model, view pricing/context info |

### 📋 Projects & Tasks (4 tools)
| Tool | Description |
|---|---|
| `kanban` | Full project management board (columns, cards, labels, priorities) |
| `todo` | Quick todo list with categories and priorities |
| `goals` | Autonomous long-running goal tracking with sub-goals |
| `delegate` | Spawn sub-agents for parallel work |

### 🖥️ System (7 tools)
| Tool | Description |
|---|---|
| `app_launcher` | Open any app, URL, or file (40+ Windows app shortcuts) |
| `clipboard` | Read/write system clipboard |
| `notify` | System notifications (Windows toast/sound alerts) |
| `system_info` | CPU, RAM, disk, network, GPU, process metrics |
| `scheduler` | Cron jobs, intervals, one-shot timers |
| `patch` | Apply unified diff patches to files |
| `process` | Manage background processes (list, kill, monitor) |

### 🔌 Protocol Integrations (3 tools)
| Tool | Description |
|---|---|
| `twitter_search` | Search Twitter/X for tweets and trends |
| `spotify` | Control Spotify playback and search music |
| `home_assistant` | Control smart home devices (lights, thermostat, switches) |

### 🎮 Fun & Gamification (2 tools)
| Tool | Description |
|---|---|
| `pet` | ASCII virtual pet with 5 evolution stages, mood, hunger/energy tracking |
| `achievements` | 24 achievements across 6 categories (unlock by using features) |

### 🖱️ Computer Use (1 tool)
| Tool | Description |
|---|---|
| `computer` | Desktop automation — screenshots, mouse clicks, keyboard input |

---

## Self-Learning

HermClaw has a **3-layer self-learning system** that builds knowledge over time:

### 1. Learning Graph
A **SQLite-backed concept graph** that tracks what the agent has learned:
- Store concepts with name, category, description, and confidence score (0→1)
- Create relationships between concepts (11 types: `is_a`, `depends_on`, `prerequisite_for`, etc.)
- Confidence grows automatically with repeated encounters
- ASCII visualization of the knowledge graph

### 2. Skill Growth Engine
**Automatically creates new skills from repeated patterns:**
- **Tier 1 (always on):** During reflection, if the agent notices repeated procedures, it auto-generates a draft SKILL.md file
- **Tier 2 (opt-in):** `SkillEvolutionEngine` takes existing auto-generated skills and proposes improved/tighter steps
- Deduplication prevents creating duplicate skills using token similarity matching

### 3. Persistent Memory
Long-term semantic memory across sessions:
- Facts are stored and recalled via semantic search
- The agent auto-recalls relevant memories at the start of each conversation
- Cross-session persistence — restart the chat and it still remembers

### How to test self-learning

```
# Teach concepts
> Learn this concept: "Python" is a programming language. Category: programming.

# Connect concepts
> Connect: "FastAPI" depends_on "Python"

# Visualize the graph
> Show me your learning graph

# Save facts to memory
> Remember: I prefer YAML for configuration files.

# Trigger reflection
> hermclaw reflect
```

---

## Commands

| Command | Purpose |
|---|---|
| `hermclaw chat` | Interactive local conversation |
| `hermclaw run "prompt"` | One-shot mode: send prompt, get response, exit |
| `hermclaw serve` | Start the gateway (all channels + scheduler + HTTP API) |
| `hermclaw setup` | Interactive setup wizard (model, provider, API keys, channels) |
| `hermclaw doctor` | Diagnostics, first-run wizard (`--init`), auto-fix (`--fix`) |
| `hermclaw reflect` | Manually trigger the self-learning reflection loop |
| `hermclaw models` | List all available models in the catalog |
| `hermclaw skills` | List, validate, and inspect skills |
| `hermclaw sessions` | List, show, export, and delete sessions |
| `hermclaw plugins` | List, install, uninstall, create plugins |

### Chat commands (inside `hermclaw chat`)

| Command | Purpose |
|---|---|
| `/models` | List available models |
| `/model <name>` | Switch model mid-conversation |
| `/cost` | Show token usage and estimated cost |
| `/clear` | Clear conversation history |
| `/save <file>` | Export conversation to file |
| `/load <file>` | Load conversation from file |
| `/exit` or `Ctrl+C` | Exit chat |

Every CLI command accepts `--config`, `--profile`, and `--json` globally.

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
| Context compression | **0.3** | Compress at 30% of context window |
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

**Recommended local models:**

| Model | Size | Best for |
|---|---|---|
| `gemma4:12b` | 7.6 GB | Default, great balance |
| `gemma4:27b` | 17 GB | Better reasoning (needs 24GB+ RAM) |
| `qwen3:8b` | 6.6 GB | Fast, multilingual |
| `llama3.1:8b` | 4.7 GB | Lightweight |

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
    provider: "gemini"
    model_name: "gemini-2.5-flash"
    api_key_env: "GOOGLE_API_KEY"
```

```bash
export GOOGLE_API_KEY="your-key"
```

### OpenAI

```yaml
brain:
  model:
    provider: "openai_compat"
    model_name: "gpt-4o"
    api_key_env: "OPENAI_API_KEY"
    api_base_env: null               # uses default OpenAI endpoint
```

### Groq (fast cloud inference)

```yaml
brain:
  model:
    provider: "openai_compat"
    model_name: "llama-3.3-70b-versatile"
    api_key_env: "GROQ_API_KEY"
    api_base_env: "GROQ_API_BASE"    # https://api.groq.com/openai/v1
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
| **Skill Registry** | Auto-generated + user-defined skills with YAML frontmatter |
| **Audit Logging** | SQLite-backed audit trail of every tool call |
| **Rate Limiting** | Per-tool rate limits (configurable) |
| **Response Cache** | LRU cache with TTL for repeated queries |
| **Context Compression** | Auto-summarizes long conversations to stay within model limits |
| **Parallel Execution** | Concurrent tool dispatch when multiple tools needed |
| **Mixture-of-Agents (MoA)** | Query multiple models and merge responses |
| **Multi-Agent Delegation** | Spawn sub-agents for parallel workstreams |
| **Smart Tool Selection** | Only sends relevant tools to the model based on query keywords |
| **i18n** | 16 languages (en, es, de, fr, ja, ko, zh, pt, ru, hi, tr, it, uk, af, ga, hu) |
| **Model Catalog** | 16+ pre-configured models across 7 providers |
| **Security Scanner** | Code pattern analysis + dependency audit |
| **Verification Engine** | Automated testing with pass/fail assertion |

---

## Messaging Channels

HermClaw can run as a bot on multiple platforms simultaneously:

| Channel | Extra | How to enable |
|---|---|---|
| **Telegram** | `pip install -e ".[telegram]"` | Set `TELEGRAM_BOT_TOKEN` |
| **Discord** | `pip install -e ".[discord]"` | Set `DISCORD_BOT_TOKEN` |
| **Slack** | `pip install -e ".[slack]"` | Set `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` |
| **HTTP API** | Built-in | `hermclaw serve` (runs on port 8080) |

---

## Project Structure

```
hermclaw/
├── hermclaw/
│   ├── brain/                  # Agent intelligence
│   │   ├── agent_loop.py       # ReAct-style tool-calling loop
│   │   ├── agent_core.py       # Core agent abstractions
│   │   ├── memory/             # SQLite store, vector memory, compressor
│   │   ├── cache.py            # Response cache (LRU + TTL)
│   │   ├── learning_graph.py   # Concept relationship graph
│   │   ├── skill_growth.py     # Auto-skill generation + evolution
│   │   ├── reflection.py       # Self-learning reflection loop
│   │   ├── model_catalog.py    # 16+ model definitions
│   │   ├── model_manager.py    # Dynamic model switching
│   │   ├── moa.py              # Mixture-of-Agents
│   │   ├── multi_agent.py      # Multi-agent delegation
│   │   ├── parallel_exec.py    # Concurrent tool execution
│   │   ├── verification.py     # Automated testing
│   │   ├── post_processing.py  # Response formatting
│   │   ├── profiles.py         # User profiles + identity files
│   │   └── transports/         # Provider adapters
│   │       ├── openai_compat.py  # Ollama, OpenAI, Groq, OpenRouter
│   │       ├── anthropic.py      # Claude
│   │       ├── gemini.py         # Google Gemini (native)
│   │       └── bedrock.py        # AWS Bedrock
│   ├── body/                   # Gateway, channels, scheduler
│   ├── tools/                  # All 40+ tools
│   ├── plugins/                # Plugin system
│   ├── security/               # Audit logging, rate limiting, secrets
│   ├── skills/                 # Skill registry + loader
│   ├── cli.py                  # CLI entry point (10 commands)
│   ├── runtime.py              # Agent runtime builder
│   ├── config.py               # Configuration system (Pydantic)
│   ├── i18n.py                 # 16-language translations
│   └── banner.py               # ASCII art branding
├── tests/
├── docs/
├── install.py                  # Interactive setup wizard
├── hermclaw.example.yaml       # Reference configuration
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
