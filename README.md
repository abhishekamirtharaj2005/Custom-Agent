<h1 align="center">
  🦀 HermClaw
</h1>

<p align="center">
  <strong>A unified, self-improving personal AI agent with 51+ tools, live screen vision, desktop control, and self-learning.</strong>
</p>

<p align="center">
  <a href="#key-features">Features</a> •
  <a href="#install">Install & Setup</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#tools">51+ Tools</a> •
  <a href="#computer-use--screen-vision">Computer Control</a> •
  <a href="#self-learning--second-brain">Self-Learning</a> •
  <a href="#messaging-channels">14 Channels</a> •
  <a href="#commands">Commands</a>
</p>

---

## What is HermClaw?

HermClaw merges the autonomous ReAct cognitive loop of **Hermes ☤** with the robust multi-channel body and protocol gateway of **OpenClaw 🦞** into a single, production-grade personal AI agent:

- **Body** (from OpenClaw): Local-first gateway, 14 messaging channels, cron scheduler, smart home protocols (Hue, Sonos, Bluetooth, Home Assistant).
- **Brain** (from Hermes): ReAct tool-calling loop, persistent SQLite & vector memory, context compression, self-reflection, auto-skill generation, and multi-agent swarm delegation.

### Key Principles

- 🖥️ **Live Screen Awareness & Computer Control** — autonomous mouse navigation, keyboard input, hotkey macros, and vision-grounded UI element detection.
- 🔓 **Full System Access** — unrestricted shell commands, file operations, background processes, and application launching with configurable risk policies.
- 🧠 **Self-Learning & Second Brain** — automatic reflection loop, SQLite concept graph, auto-generated skills, and bi-directional Obsidian markdown vault synchronization.
- 🛠️ **51+ Built-in Tools** — LSP code intelligence, deep web scraping (Firecrawl/Readability), media generation, audio/music synthesis, system diagnostics, and hardware control.
- 🗣️ **Jarvis Voice Assistant** — hands-free conversational voice mode with live microphone listening, wake-word sensitivity, voice cloning, and spoken responses.
- 🐝 **Multi-Agent Swarms** — coordinated sub-agent teams (Planner, Researcher, Coder, Reviewer, Synthesizer) tackling complex, multi-stage goals.
- 💬 **14+ Messaging Channels** — seamlessly operate across Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Teams, Google Chat, Feishu/Lark, Mattermost, SMS, and Webhooks simultaneously.
- 🏠 **Local-First & Multi-Provider** — runs 100% locally and free with Ollama, or connects to Claude, GPT-4o, Gemini 2.5, Groq, OpenRouter, and AWS Bedrock.

---

## Prerequisites

| Requirement | How to check |
|---|---|
| **Python 3.11+** | `python --version` |
| **Git** | `git --version` |
| **Ollama** (recommended for local use) | `ollama --version` — [Install Ollama](https://ollama.com/download) |

---

## Install

Clone the repository and run the unified interactive setup wizard:

```bash
git clone https://github.com/abhishekamirtharaj2005/Custom-Agent.git
cd Custom-Agent
python install.py
```

### 🧙 8-Step Interactive Setup Wizard

The installer walks you through a comprehensive onboarding experience to configure your entire agent environment:

1. **Identity & Personalization** — Set the agent's name, your name, and system language (16 languages supported).
2. **Primary AI Model Provider** — Select between Ollama (local/free), OpenAI, Anthropic Claude, Google Gemini, Groq, OpenRouter, AWS Bedrock, or custom OpenAI-compatible endpoints.
3. **Fallback & Auxiliary Models** — Configure vision models, ultra-fast reasoning fallback models, and local offline fallbacks.
4. **Messaging Channels Setup** — Connect any of the 14 platforms (Telegram, Discord, Slack, Matrix, Google Chat, Feishu/Lark, Mattermost, Twilio SMS/WhatsApp, Signal, Teams, Webhooks) with guided token and credential entry.
5. **Web Search & Research Keys** — Configure Tavily, Serper, SerpAPI, Brave Search, and Firecrawl API keys for deep web crawling.
6. **Voice, Music & Media Keys** — Configure ElevenLabs TTS, Suno AI music generation, and Fal.ai / DALL-E image models.
7. **Smart Home & Local Hardware** — Enter Philips Hue bridge IP & app keys, Sonos speaker IPs, and Home Assistant endpoints.
8. **Security & Autonomy Mode** — Choose execution mode (Autonomous / No Guardrails vs Interactive Approval Mode for shell commands).

Then it automatically:
- ✅ Installs HermClaw and all required dependencies into your environment
- ✅ Generates your fully-configured `~/.hermclaw/hermclaw.yaml`
- ✅ Safely writes all API keys and tokens to `~/.hermclaw/.env`
- ✅ Pulls your selected Ollama model (e.g. `gemma4:12b`)
- ✅ Runs runtime diagnostics and self-tests

### Re-run setup anytime

```bash
hermclaw setup
```

---

## Manual Install (Alternative)

<details>
<summary>Click to expand manual installation steps</summary>

### Option 1: pip install editable

```bash
git clone https://github.com/abhishekamirtharaj2005/Custom-Agent.git
cd Custom-Agent
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -e .
```

### Option 2: Full installation with all extras

```bash
pip install -e ".[all]"
```

### Option 3: Targeted extras

```bash
# Model providers
pip install -e ".[anthropic]"        # Claude
pip install -e ".[openai]"           # OpenAI GPT-4o
pip install -e ".[gemini]"           # Native Google Gemini
pip install -e ".[bedrock]"          # AWS Bedrock

# Automation & Vision
pip install -e ".[browser]"          # Playwright headless browser
pip install -e ".[vision]"           # PyAutoGUI, OpenCV, Pillow

# Audio & Voice
pip install -e ".[voice]"            # pyttsx3, SpeechRecognition, sounddevice

# Channels
pip install -e ".[telegram,discord,slack]"
```

### Quick Start (manual verification)

```bash
ollama pull gemma4:12b && ollama serve
hermclaw doctor --init
hermclaw chat
```

</details>

---

## Quick Start

### 1. Interactive Terminal Chat
```bash
hermclaw chat
```

### 2. Hands-Free Jarvis Voice Mode
Speak directly to HermClaw through your microphone and hear spoken responses in real-time:
```bash
hermclaw voice
```

### 3. Executive Briefing
Generate your morning agenda, weather, active goals, and unread priority items:
```bash
hermclaw briefing            # Morning executive briefing
hermclaw briefing --debrief   # Evening summary & accomplishments
```

### 4. One-Shot Command Execution
Send a single goal or instruction directly from the command line:
```bash
hermclaw run "Inspect the git status, run pytest, and summarize any failing tests"
```

### 5. Multi-Channel Gateway Daemon
Launch the background server to handle all connected chat bots, webhooks, and cron jobs:
```bash
hermclaw serve                       # Foreground
hermclaw serve --daemonize           # Detached background process (POSIX)
```

---

## 51+ Built-in Tools

HermClaw provides 51 registered tools out of the box, organized into functional suites:

### 📁 File & Code Intelligence (9 tools)
| Tool | Description |
|---|---|
| `file_read` | Read files with selective line ranges and byte offsets |
| `file_write` | Create or overwrite files anywhere on the filesystem |
| `file_edit` | Surgical search-and-replace editing with validation |
| `list_dir` | Recursive directory inspection with file sizes and counts |
| `grep_search` | Fast regex and pattern matching across project files |
| `code_exec` | Execute Python, JavaScript, and Bash in isolated runtimes |
| `shell` | Direct shell command execution (PowerShell, Bash, Cmd) |
| `git` | Complete Git version control (checkpoints, diffs, rollbacks, stashes, logs) |
| `lsp` | **Language Server Protocol client** — diagnostics, definition jumps, hover docstrings, code completions, workspace symbols, and references |

### 🌐 Web & Deep Scraping (5 tools)
| Tool | Description |
|---|---|
| `web_search` | DuckDuckGo web search with snippet extraction |
| `url_read` | Fetch and parse web content into readable markdown |
| `browser` | Full Playwright automation (navigate, click, type, screenshot, evaluate JS) |
| `web_readability` | Clean article extraction removing ads, cookie notices, and navigation noise |
| `firecrawl_scrape` | Deep recursive crawler, sitemap discovery, and structured data extraction |

### 🖱️ Computer Control & Screen Vision (2 tools)
| Tool | Description |
|---|---|
| `computer` | Complete desktop control — mouse clicks, moves, drags, typing, shortcuts, and screenshots |
| `screen_vision` | Multimodal live screen inspection, UI element coordinate grounding, and multi-step desktop macros |

### 🎨 Media & Creative (8 tools)
| Tool | Description |
|---|---|
| `image_generate` | DALL-E 3 and fal.ai high-resolution image generation |
| `vision` | Multimodal image and screenshot comprehension (GPT-4o / Ollama LLaVA) |
| `tts` | Local offline text-to-speech with 15+ selectable system voices |
| `elevenlabs_tts` | Ultra-realistic ElevenLabs cloud voice synthesis |
| `music_generate` | AI music track generation (Suno/ElevenLabs) with local harmonic synthesis fallback |
| `video_generate` | Prompt-to-video generation via creative generative APIs |
| `pdf_read` | High-fidelity text and table extraction from PDF documents |
| `transcribe` | Audio-to-text transcription via Whisper |

### 🎤 Voice & Audio Effects (2 tools)
| Tool | Description |
|---|---|
| `voice_clone` | Clone distinct voices from short reference audio files |
| `voice_effects` | Apply audio transformations (pitch shift, tempo scaling, room reverb) |

### 🏠 Smart Home & Local Hardware (4 tools)
| Tool | Description |
|---|---|
| `home_assistant` | Control Home Assistant entities (lights, climate, switches, automations) |
| `openhue` | Philips Hue control — discover bridges, adjust brightness, colors, and trigger scenes |
| `sonos` | Sonos speaker control — discover devices, play/pause, adjust volume, queue tracks |
| `blucli` | Bluetooth device discovery, pairing, signal strength, and battery telemetry |

### 🧠 Memory & Second Brain (5 tools)
| Tool | Description |
|---|---|
| `memory` | Long-term memory store with semantic vector search and keyword fallback |
| `knowledge_vault` | **Obsidian Second Brain integration** — bi-directional markdown vault sync, daily notes, wikilinks, and automatic indexing |
| `learning_graph` | Dynamic SQLite concept relationship graph with confidence tracking |
| `session_search` | Deep search across historical conversation sessions and decisions |
| `model_catalog` | Model registry with context sizes, parameter counts, and pricing |

### 📋 Projects, Swarm & Executive (5 tools)
| Tool | Description |
|---|---|
| `kanban` | Full project board with columns, cards, labels, and priorities |
| `todo` | Lightweight prioritized task management |
| `goals` | Autonomous long-running goal tracking with milestone breakdown |
| `delegate` | Spawn autonomous sub-agents or coordinate **multi-agent swarms** (Planner, Researcher, Coder, Reviewer) |
| `briefing` | Executive secretary briefings — daily schedules, calendar reminders, weather, and open action items |

### 🖥️ System & Automation (7 tools)
| Tool | Description |
|---|---|
| `app_launcher` | Launch installed desktop applications, URLs, or files (40+ Windows shortcuts) |
| `clipboard` | Read and manipulate the system clipboard |
| `notify` | Send native desktop toast notifications and audio chimes |
| `system_info` | Real-time monitoring of CPU, RAM, disk, network, GPU, and processes |
| `scheduler` | Schedule cron expressions, recurring intervals, and one-shot reminders |
| `patch` | Apply unified diff patches directly to files |
| `process` | Inspect, monitor, and terminate background operating system processes |

### 🔌 Protocol Integrations (2 tools)
| Tool | Description |
|---|---|
| `twitter_search` | Search Twitter/X for live posts, user updates, and trending topics |
| `spotify` | Search tracks, control playback, playlists, and volume on Spotify |

### 🎮 Fun & Gamification (2 tools)
| Tool | Description |
|---|---|
| `pet` | Interactive virtual crab pet with 5 evolution stages, mood, hunger, and energy |
| `achievements` | 24 unlockable achievements across 6 progression categories |

---

## Computer Use & Screen Vision

HermClaw can directly see your screen and control your keyboard and mouse to perform real-world tasks (such as opening applications, sending messages in WhatsApp or Telegram, or clicking desktop buttons):

```
> Open WhatsApp and send "Meeting in 10 minutes" to Alex
```

### How it works:
1. **Live Visual Capture**: Captures screen frame buffers or active application windows.
2. **Vision Element Grounding**: Uses multimodal LLMs to identify pixel coordinates for UI elements, text inputs, buttons, and icons.
3. **Hardware-Level Input**: Dispatches native mouse clicks, drags, smooth scrolling, hotkey combinations (e.g. `Ctrl+Enter`, `Alt+Tab`), and text typing via PyAutoGUI.
4. **Visual Loop Verification**: Inspects subsequent frames to confirm actions succeeded before taking the next step.

---

## Self-Learning & Second Brain

HermClaw continuously improves itself without human intervention through a 3-layer architecture:

### 1. The Learning Graph
A SQLite-backed knowledge graph tracking concepts and semantic connections:
- Stores facts with confidence ratings ($0.0 \to 1.0$) that strengthen with repeated verification.
- Connects concepts using 11 relationship types (`depends_on`, `is_a`, `improves`, `causes`, etc.).
- View your agent's mind at any time with ASCII visualization:
  ```bash
  > Show me your learning graph
  ```

### 2. Auto-Skill Growth Engine
- **Tier 1 (Always On)**: During reflection, when the agent detects a repeated successful procedure, it writes a new `SKILL.md` file.
- **Tier 2 (Evolution)**: Optimizes existing skills over time, refining instructions and parameter usage.
- Deduplication prevents repetitive skills using token similarity analysis.

### 3. Obsidian Second Brain Sync (`knowledge_vault`)
HermClaw can manage your personal Obsidian vault:
- Synchronize notes, research findings, and task summaries into organized markdown files.
- Automatically create bi-directional `[[wikilinks]]` between related concepts.
- Query and retrieve knowledge across your entire second brain.

---

## Messaging Channels

Run HermClaw simultaneously across 14 messaging platforms:

| Channel | Protocol / Adapter | Status | Setup |
|---|---|---|---|
| **Telegram** | `python-telegram-bot` (long-polling) | Native | Set `TELEGRAM_BOT_TOKEN` |
| **Discord** | `discord.py` (WebSocket gateway) | Native | Set `DISCORD_BOT_TOKEN` |
| **Slack** | Slack Bolt API (Socket Mode) | Native | Set `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` |
| **Matrix** | Matrix Client-Server REST API | Native | Set `MATRIX_HOMESERVER` + `MATRIX_ACCESS_TOKEN` |
| **Google Chat** | Google Chat Webhook / Bot API | Native | Set `GOOGLE_CHAT_WEBHOOK_URL` |
| **Feishu / Lark** | Lark Open Platform API | Native | Set `FEISHU_APP_ID` + `FEISHU_APP_SECRET` |
| **Mattermost** | Mattermost REST & WebSocket API | Native | Set `MATTERMOST_URL` + `MATTERMOST_BOT_TOKEN` |
| **Twilio (SMS/WhatsApp)** | Twilio Messaging API | Native | Set `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` |
| **Signal** | `signal-cli` REST daemon | Native | Set `SIGNAL_HTTP_URL` + `SIGNAL_PHONE_NUMBER` |
| **Microsoft Teams** | Bot Framework Webhook | Native | Set `TEAMS_WEBHOOK_URL` |
| **Generic Webhooks** | HTTP POST Inbound / Outbound | Native | Configured in `hermclaw.yaml` |
| **HTTP REST API** | FastAPI / Starlette on port 8080 | Native | Included with `hermclaw serve` |
| **Interactive CLI** | Rich terminal interface | Native | `hermclaw chat` |
| **Jarvis Voice** | Real-time audio stream | Native | `hermclaw voice` |

---

## Commands

### CLI Entry Points

| Command | Purpose |
|---|---|
| `hermclaw chat` | Interactive terminal conversation session |
| `hermclaw voice` | **Hands-free Jarvis voice mode** with live microphone and speaker |
| `hermclaw briefing` | Generate morning executive briefing (use `--debrief` for evening review) |
| `hermclaw run "prompt"` | Run a one-shot command or goal and print output |
| `hermclaw serve` | Start the full gateway (all channels + scheduler + HTTP API) |
| `hermclaw setup` | Interactive 8-step setup wizard (providers, channels, keys, hardware) |
| `hermclaw doctor` | Diagnostics, health checks, first-run wizard (`--init`), auto-fix (`--fix`) |
| `hermclaw reflect` | Manually trigger the self-learning reflection loop |
| `hermclaw models` | List all supported models, context limits, and pricing |
| `hermclaw skills` | List, inspect, validate, and test custom agent skills |
| `hermclaw sessions` | Manage conversation sessions (list, export, inspect, delete) |
| `hermclaw plugins` | Discover, install, validate, and create HermClaw plugins |

### In-Chat Slash Commands

| Command | Action |
|---|---|
| `/models` | List all configured and available models |
| `/model <name>` | Switch active model mid-conversation (e.g. `/model claude-sonnet-4-6`) |
| `/cost` | Display cumulative token usage and estimated API cost |
| `/clear` | Clear the current conversation context window |
| `/save <file>` | Export current conversation session to a JSON/markdown file |
| `/load <file>` | Load and resume a previously saved conversation session |
| `/exit` | Exit the chat session |

---

## Configuration

All agent settings are managed via `~/.hermclaw/hermclaw.yaml`. Core defaults:

```yaml
agent:
  name: "HermClaw"
  language: "en"
  workdir: "."

brain:
  model:
    provider: "openai_compat"
    model_name: "gemma4:12b"
    api_base_env: "OLLAMA_API_BASE"
  memory:
    max_history_turns: 50
    compression_threshold: 0.3
  self_learning:
    enabled: true
    auto_skills: true
    reflection_interval: 10

security:
  allow_shell: true
  require_approval: false
  risk_policy: "permissive"
```

See [`hermclaw.example.yaml`](hermclaw.example.yaml) for a fully-annotated reference file.

---

## Model Providers

### Ollama (Default — Local & 100% Free)
```bash
ollama pull gemma4:12b
ollama serve
hermclaw chat
```

### Anthropic Claude
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```
```yaml
brain:
  model:
    provider: "anthropic"
    model_name: "claude-sonnet-4-6"
```

### Google Gemini
```bash
export GOOGLE_API_KEY="AIza..."
```
```yaml
brain:
  model:
    provider: "gemini"
    model_name: "gemini-2.5-flash"
```

### OpenAI
```bash
export OPENAI_API_KEY="sk-..."
```
```yaml
brain:
  model:
    provider: "openai_compat"
    model_name: "gpt-4o"
```

### Groq (Ultra-Fast Cloud Inference)
```bash
export GROQ_API_KEY="gsk_..."
```
```yaml
brain:
  model:
    provider: "openai_compat"
    model_name: "llama-3.3-70b-versatile"
    api_base: "https://api.groq.com/openai/v1"
```

---

## Project Architecture

```
hermclaw/
├── hermclaw/
│   ├── brain/                        # Agent Cognitive Engine
│   │   ├── agent_loop.py             # ReAct tool-calling loop
│   │   ├── agent_core.py             # Agent abstractions & state
│   │   ├── memory/                   # SQLite memory, vector store, compressor
│   │   ├── learning_graph.py         # SQLite concept relationship graph
│   │   ├── skill_growth.py           # Auto-skill generator & evolution
│   │   ├── reflection.py             # Self-learning reflection loop
│   │   ├── swarm.py                  # Multi-agent swarm orchestrator
│   │   ├── transports/               # Ollama, Anthropic, Gemini, OpenAI, Bedrock
│   │   └── ...
│   ├── body/                         # Gateway, Channels & Protocols
│   │   ├── gateway.py                # Multi-channel unified router
│   │   ├── channels/                 # 14 platform adapters (Discord, Telegram, Slack, Matrix, etc.)
│   │   ├── scheduler.py              # Cron & interval scheduler
│   │   └── voice_mode.py             # Hands-free microphone voice assistant
│   ├── tools/                        # 51+ Built-in Tools
│   │   ├── file_tools.py             # File I/O, search, and editing
│   │   ├── lsp_tool.py               # Language Server Protocol client
│   │   ├── computer_tool.py          # Mouse, keyboard, and screen automation
│   │   ├── protocol_tools.py         # Hue, Sonos, Bluetooth, Home Assistant
│   │   ├── web_tools.py              # Firecrawl, Readability, DuckDuckGo, Playwright
│   │   ├── media_extra.py            # AI music & audio generation
│   │   ├── memory_extra.py           # Obsidian vault & executive briefing
│   │   └── ...
│   ├── security/                     # Audit logging, risk policy, secret management
│   ├── skills/                       # User & auto-evolved skill definitions
│   ├── cli.py                        # Terminal CLI entry point (12 subcommands)
│   ├── runtime.py                    # Runtime builder & dependency injection
│   └── config.py                     # Pydantic configuration schemas
├── tests/                            # Comprehensive unit & integration tests
├── install.py                        # 8-step interactive installer
├── hermclaw.example.yaml             # Master configuration template
└── README.md
```

---

## Development & Testing

Run the full test suite across all tools, channels, and cognitive components:

```bash
pip install -e ".[dev]"
pytest
```

---

## License

MIT © HermClaw Contributors
