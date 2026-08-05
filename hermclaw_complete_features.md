# HermClaw — Complete Feature Catalog

> Every feature that **Hermes** ☤ and **OpenClaw** 🦞 can do — combined into one definitive reference.

---

## Table of Contents

1. [AI Model & Provider Support](#1-ai-model--provider-support)
2. [Messaging Platform Support](#2-messaging-platform-support)
3. [Agent Core Capabilities](#3-agent-core-capabilities)
4. [Tool System](#4-tool-system)
5. [Code & Development Tools](#5-code--development-tools)
6. [Web & Browser Automation](#6-web--browser-automation)
7. [File System Operations](#7-file-system-operations)
8. [Media Generation & Understanding](#8-media-generation--understanding)
9. [Voice, Speech & Audio](#9-voice-speech--audio)
10. [Memory & Knowledge Management](#10-memory--knowledge-management)
11. [Skills System](#11-skills-system)
12. [Scheduled Tasks & Automation](#12-scheduled-tasks--automation)
13. [Multi-Agent & Delegation](#13-multi-agent--delegation)
14. [Project Management](#14-project-management)
15. [Session & Conversation Management](#15-session--conversation-management)
16. [Security & Safety](#16-security--safety)
17. [Configuration & Customization](#17-configuration--customization)
18. [Plugin & Extension System](#18-plugin--extension-system)
19. [Gateway & Server Infrastructure](#19-gateway--server-infrastructure)
20. [CLI & Terminal Interface](#20-cli--terminal-interface)
21. [Desktop, Mobile & Web Apps](#21-desktop-mobile--web-apps)
22. [DevOps & Deployment](#22-devops--deployment)
23. [Observability & Diagnostics](#23-observability--diagnostics)
24. [Internationalization](#24-internationalization)
25. [Data Generation & Training](#25-data-generation--training)
26. [Protocols & Interoperability](#26-protocols--interoperability)
27. [Smart Home & IoT](#27-smart-home--iot)
28. [Unique / Fun Features](#28-unique--fun-features)

---

## 1. AI Model & Provider Support

### Cloud Model Providers

| Provider | Hermes ☤ | OpenClaw 🦞 |
|----------|:--------:|:-----------:|
| **OpenAI** (GPT-4, GPT-4o, o1, o3, Codex) | ✅ | ✅ |
| **Anthropic** (Claude 3.5, Claude 4, Opus, Sonnet, Haiku) | ✅ | ✅ |
| **Google Gemini** (Gemini Pro, Ultra, Flash) | ✅ (native adapter) | ✅ |
| **Google Vertex AI** | ✅ | ✅ (Anthropic via Vertex) |
| **AWS Bedrock** | ✅ | ✅ + Bedrock Mantle variant |
| **Azure OpenAI** | ✅ (with Entra ID/AD auth) | ✅ (Microsoft extension) |
| **Azure AI Foundry** | ❌ | ✅ |
| **DeepSeek** | ✅ | ✅ |
| **Mistral AI** | ✅ | ✅ |
| **Groq** (fast inference) | ✅ | ✅ |
| **Fireworks AI** | ✅ | ✅ |
| **Together AI** | ✅ | ✅ |
| **Cerebras** | ❌ | ✅ |
| **NVIDIA NIM** | ✅ (via plugin) | ✅ |
| **Cohere** | ✅ | ✅ |
| **Perplexity AI** | ✅ | ✅ |
| **xAI (Grok)** | ✅ | ✅ |
| **Alibaba Qwen** | ✅ | ✅ |
| **Moonshot (Kimi)** | ✅ (with schema adapter) | ✅ |
| **DeepInfra** | ✅ | ✅ |
| **OpenRouter** (aggregator) | ✅ | ✅ |
| **HuggingFace Inference** | ✅ | ✅ |
| **Nous Research Portal** | ✅ (native) | ❌ |
| **Arcee AI** | ❌ | ✅ |
| **Featherless AI** | ❌ | ✅ |
| **Novita AI** | ❌ | ✅ |
| **Chutes AI** (with OAuth) | ❌ | ✅ |
| **StepFun** | ❌ | ✅ |
| **MiniMax** | ❌ | ✅ |
| **Baidu Qianfan** | ❌ | ✅ |
| **Tencent Cloud AI** | ❌ | ✅ |
| **Alibaba Cloud** | ❌ | ✅ |
| **ByteDance Volcengine** | ❌ | ✅ |
| **BytePlus** | ❌ | ✅ |
| **Venice AI** | ❌ | ✅ |
| **TokenJuice** | ❌ | ✅ |
| **GitHub Copilot** (auth integration) | ✅ (ACP client) | ✅ (extension + proxy) |

### Local / Self-Hosted Model Providers

| Provider | Hermes ☤ | OpenClaw 🦞 |
|----------|:--------:|:-----------:|
| **Ollama** | ✅ | ✅ |
| **LM Studio** | ✅ (with reasoning adapter) | ✅ |
| **llama.cpp** server | ✅ | ✅ |
| **vLLM** server | ❌ | ✅ |
| **SGLang** | ❌ | ✅ |
| **LiteLLM** proxy | ❌ | ✅ |
| Any OpenAI-compatible endpoint | ✅ | ✅ |

### Model Management Features

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| Model catalog with metadata (pricing, context windows) | ✅ (117KB registry) | ✅ (651KB taxonomy) |
| Model switching mid-conversation | ✅ | ✅ |
| Model fallback chains (auto-failover) | ✅ | ✅ (68KB engine) |
| Model aliasing and normalization | ✅ | ✅ |
| API key rotation and pooling | ✅ (112KB credential pool) | ✅ (auth profiles) |
| Rate limit tracking and backoff | ✅ | ✅ |
| Cost tracking and billing view | ✅ (usage pricing calculator) | ✅ (model pricing cache) |
| Reasoning mode support (o1, thinking) | ✅ (with timeouts) | ✅ |
| Prompt caching (Anthropic, Google) | ✅ | ✅ |
| Mixture-of-Agents (MoA) — multi-model merge | ✅ (53KB MoA loop) | ❌ |
| Provider-specific schema adapters | ✅ (Gemini, Moonshot, Codex) | ✅ (per-extension) |
| Auth profile management (multi-key) | ✅ | ✅ (SQLite-backed) |
| Model cost guard (warn on expensive models) | ✅ | ❌ |

---

## 2. Messaging Platform Support

| Platform | Hermes ☤ | OpenClaw 🦞 |
|----------|:--------:|:-----------:|
| **Telegram** | ✅ (via gateway plugin) | ✅ (extension) |
| **Discord** | ✅ (via gateway plugin) | ✅ (extension) |
| **WhatsApp Cloud API** | ✅ (89KB adapter) | ✅ (extension) |
| **WhatsApp Web** (bridge) | ✅ (Node.js bridge) | ❌ |
| **Signal** | ✅ (73KB adapter) | ✅ (extension) |
| **Slack** | ✅ (via gateway plugin) | ✅ (extension) |
| **iMessage** (BlueBubbles) | ✅ (40KB adapter) | ✅ (extension) |
| **Microsoft Teams** | ✅ (MS Graph webhook) | ✅ (extension) |
| **Google Chat** | ❌ | ✅ (extension) |
| **Matrix** | ❌ | ✅ (extension) |
| **IRC** | ❌ | ✅ (extension) |
| **Mattermost** | ❌ | ✅ (extension) |
| **Feishu / Lark** | ❌ | ✅ (extension) |
| **LINE** | ❌ | ✅ (extension) |
| **Nostr** | ❌ | ✅ (extension) |
| **Twitch** | ❌ | ✅ (extension) |
| **Nextcloud Talk** | ❌ | ✅ (extension) |
| **SMS** | ❌ | ✅ (extension) |
| **Synology Chat** | ❌ | ✅ (extension) |
| **Tlon (Urbit)** | ❌ | ✅ (extension) |
| **Xiaomi** | ❌ | ✅ (extension) |
| **WeChat (Weixin)** | ✅ (94KB adapter) | ❌ |
| **QQ Bot** | ✅ (128KB adapter) | ✅ (extension) |
| **Yuanbao (Tencent)** | ✅ (228KB adapter) | ❌ |
| **Zalo** | ❌ | ✅ (extension + personal) |
| **DingTalk** | ✅ (auth integration) | ❌ |
| **Generic Webhook** | ✅ (55KB adapter) | ✅ (extension) |
| **REST API** (self-hosted endpoint) | ✅ (224KB API server) | ✅ (gateway HTTP) |

### Messaging Features

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| Streaming responses to platforms | ✅ (92KB stream consumer) | ✅ (42KB streaming) |
| Message threading | ✅ | ✅ (thread bindings) |
| Typing indicators | ✅ | ✅ |
| Emoji reactions (status) | ✅ | ✅ (status reactions) |
| User/group allowlists | ✅ | ✅ (allowlist matching) |
| Mention-based activation | ✅ | ✅ (mention gating) |
| Message mirroring between platforms | ✅ (7KB mirror) | ❌ |
| Inbound message debouncing | ❌ | ✅ |
| Draft preview and editing | ❌ | ✅ (draft stream) |
| Rich message formatting per platform | ✅ | ✅ |
| Sticker support | ✅ (sticker cache) | ❌ |
| Inline keyboards (QQ) | ✅ | ❌ |
| Platform-specific display configs | ✅ | ✅ |
| Multi-channel simultaneous operation | ✅ (gateway) | ✅ (gateway) |
| Relay connector (bridge protocol) | ✅ (WebSocket relay) | ❌ |

---

## 3. Agent Core Capabilities

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| Conversation loop with tool calling | ✅ (310KB loop) | ✅ (106KB agent-command) |
| Streaming responses (token-by-token) | ✅ | ✅ |
| Context window management | ✅ (161KB compressor) | ✅ (16KB compaction) |
| Conversation compression/summarization | ✅ (69KB strategies) | ✅ (compaction with worker) |
| System prompt builder with context injection | ✅ (98KB prompt builder) | ✅ |
| Context engine (file/symbol retrieval) | ✅ (9.5KB engine) | ✅ (13KB context) |
| Agent identity/personality customization | ✅ (default soul) | ✅ (identity system) |
| Think-tag scrubbing from model outputs | ✅ (15KB scrubber) | ✅ (deepseek filter) |
| Iteration budget control | ✅ | ✅ |
| Tool guardrails (safety checks) | ✅ (18KB guardrails) | ✅ (before-tool-call) |
| Error classification and retry | ✅ (69KB classifier) | ✅ (failover engine) |
| One-shot mode (single prompt, exit) | ✅ | ✅ |
| Background review of outputs | ✅ (49KB) | ❌ |
| Verification evidence collection | ✅ (20KB) | ❌ |
| Verification stop conditions | ✅ (12KB) | ❌ |
| Turn context management | ✅ (26KB) | ✅ |
| Turn finalization (post-processing) | ✅ (26KB) | ✅ |
| Bounded response length enforcement | ✅ | ✅ |
| Code mode (specialized coding behavior) | ❌ | ✅ (53KB code mode) |
| Fast mode (reduced capabilities, faster) | ❌ | ✅ |
| Agent modes (chat, code, headless) | ❌ | ✅ |
| Heartbeat system prompts | ❌ | ✅ |
| Conversation capability profiling | ❌ | ✅ (14KB) |

---

## 4. Tool System

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| Central tool registry | ✅ (37KB registry) | ✅ (54KB agent-tools) |
| Tool grouping into named "toolsets" | ✅ (972-line toolsets.py) | ✅ (via config) |
| Tool availability checking | ✅ | ✅ (availability system) |
| Tool schema generation (JSON Schema) | ✅ | ✅ |
| Tool schema sanitization | ✅ (22KB sanitizer) | ✅ |
| Pre-tool-call approval system | ✅ (149KB approval) | ✅ (72KB before-tool-call) |
| Tool execution with timeout | ✅ (83KB executor) | ✅ |
| Tool result classification | ✅ | ✅ |
| Tool output limits | ✅ | ✅ |
| Tool search/discovery | ✅ (28KB) | ✅ (tool resolution) |
| Tool budget configuration | ✅ | ✅ |
| Tool result storage | ✅ | ✅ |
| Lazy dependency installation for tools | ✅ (42KB lazy_deps) | ❌ |
| Tool planner (multi-step tool planning) | ❌ | ✅ (planner system) |
| Tool policy enforcement | ❌ | ✅ (18KB policy) |

---

## 5. Code & Development Tools

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Shell/Terminal command execution** | ✅ (138KB terminal_tool) | ✅ (70KB bash-tools) |
| **Code execution sandbox** (Python, JS) | ✅ (80KB) | ✅ (sandbox system) |
| **File read/write/edit** | ✅ (104KB file_tools) | ✅ (39KB read tools) |
| **Patch/diff application** | ✅ (24KB parser) | ✅ (21KB apply-patch) |
| **Git checkpoint management** | ✅ (64KB) | ❌ |
| **LSP integration** (diagnostics, completions, hover) | ✅ (full LSP client) | ❌ |
| **LSP server auto-install** (per language) | ✅ (15KB) | ❌ |
| **Coding context analyzer** (file/symbol extraction) | ✅ (39KB) | ✅ (context engine) |
| **Subdirectory hints** (project structure context) | ✅ (10KB) | ✅ |
| **Docker-based sandboxing** | ✅ (64KB Docker env) | ✅ (sandbox system) |
| **SSH remote execution** | ✅ (15KB SSH env) | ❌ |
| **Modal cloud execution** | ✅ (17KB Modal env) | ❌ |
| **Daytona dev environments** | ✅ (10KB) | ❌ |
| **Singularity container execution** | ✅ (10KB) | ❌ |
| **Background process management** | ✅ (102KB process registry) | ✅ (27KB bash-tools.process) |
| **PTY (pseudo-terminal) support** | ✅ | ✅ |
| **File sync between host and environments** | ✅ (20KB) | ❌ |
| **Codex/Responses API runtime** | ✅ (40KB) | ✅ (codex extension) |
| **Computer Use (desktop automation)** | ✅ (100KB CUA backend) | ✅ (via extension) |
| **Process send-keys** (interactive process input) | ❌ | ✅ |
| **Queued file writer** (atomic writes) | ❌ | ✅ |
| **Multiple execution environments** | ✅ (6 environments) | ✅ (Docker sandbox) |

---

## 6. Web & Browser Automation

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Full browser automation** (Playwright) | ✅ (211KB browser_tool) | ✅ (browser extension) |
| **Chrome DevTools Protocol** | ✅ (28KB CDP tool) | ❌ |
| **Anti-detection browser** (Camofox) | ✅ (36KB) | ❌ |
| **Browser session supervisor** | ✅ (65KB) | ❌ |
| **Browser dialog handling** | ✅ (6KB) | ❌ |
| **Web search** (multi-provider) | ✅ (52KB) | ✅ (native web search) |
| **Brave Search** | ✅ | ✅ (extension) |
| **Exa Search** | ✅ | ✅ (extension) |
| **Tavily Search** | ✅ | ✅ (extension) |
| **DuckDuckGo Search** | ❌ | ✅ (extension) |
| **SearXNG** (self-hosted) | ❌ | ✅ (extension) |
| **URL content extraction** | ✅ | ✅ (web readability) |
| **Web content readability** | ❌ | ✅ (extension) |
| **Firecrawl scraping** | ❌ | ✅ (extension) |
| **URL safety validation** | ✅ (21KB) | ✅ |
| **Website access policy** | ✅ (10KB) | ✅ |
| **Live Canvas rendering** | ❌ | ✅ (canvas extension) |

---

## 7. File System Operations

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| Read files (with line ranges) | ✅ | ✅ |
| Write/create files | ✅ | ✅ |
| Edit files (targeted replacement) | ✅ | ✅ |
| List directories | ✅ | ✅ |
| Search files (grep/regex) | ✅ | ✅ |
| Fuzzy file matching | ✅ (39KB) | ✅ |
| File state tracking | ✅ (13KB) | ✅ |
| File safety checks (path traversal prevention) | ✅ (28KB) | ✅ (path policy) |
| Write approval system | ✅ (149KB + 20KB) | ✅ (before-tool-call) |
| Binary file detection | ✅ | ✅ |
| Atomic file writes | ✅ | ✅ |
| Workspace root guard | ❌ | ✅ |
| Tilde expansion | ❌ | ✅ |
| Glob pattern matching | ❌ | ✅ |

---

## 8. Media Generation & Understanding

### Image

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **DALL-E image generation** | ✅ | ✅ |
| **fal.ai image generation** | ✅ | ✅ (extension) |
| **Vision/image analysis** | ✅ (80KB vision_tools) | ✅ (media-understanding) |
| **Image routing** (auto-select provider) | ✅ (31KB) | ✅ (media factory plan) |
| **Image source resolution** | ✅ (15KB) | ✅ |
| **Managed image attachments** | ❌ | ✅ (37KB) |
| **Image sanitization** | ❌ | ✅ |

### Video

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Video generation** | ✅ (22KB) | ✅ (video-generation-core) |
| **Runway video generation** | ❌ | ✅ (extension) |
| **PixVerse video generation** | ❌ | ✅ (extension) |
| **xAI video tools** | ✅ (6.5KB) | ❌ |
| **Video frame extraction** | ❌ | ✅ (skill) |

### Music

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Music generation** | ❌ | ✅ (music generation task) |

### Document

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **PDF extraction** | ✅ | ✅ (document-extract extension) |
| **Content extraction** (read_extract) | ✅ (9KB) | ✅ |

---

## 9. Voice, Speech & Audio

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Text-to-Speech (TTS)** | ✅ (115KB tts_tool) | ✅ (TTS system) |
| **Speech-to-Text (Transcription)** | ✅ (73KB transcription_tools) | ✅ (real-time transcription) |
| **Voice mode** (conversational) | ✅ (48KB voice_mode) | ✅ (Talk mode) |
| **ElevenLabs TTS** | ✅ | ✅ (extension) |
| **Azure Speech Services** | ✅ | ✅ (extension) |
| **Deepgram transcription** | ✅ | ✅ (extension) |
| **OpenAI Whisper (local)** | ✅ | ✅ (skill) |
| **OpenAI Whisper (API)** | ✅ | ✅ (skill) |
| **NeuTTS synthesis** (local) | ✅ (with samples) | ❌ |
| **Sherpa-ONNX TTS** (local) | ❌ | ✅ (skill) |
| **macOS MLX-based local TTS** | ❌ | ✅ (macos-mlx-tts app) |
| **SenseAudio** | ❌ | ✅ (extension) |
| **Real-time voice relay** (Talk mode) | ❌ | ✅ (50KB relay) |
| **Talk handoff** (agent-to-human) | ❌ | ✅ (12KB) |
| **Talk transcription relay** | ❌ | ✅ (15KB) |
| **Local TTS CLI** | ❌ | ✅ (extension) |
| **Discord voice** | ✅ (voice doctor) | ✅ |

---

## 10. Memory & Knowledge Management

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Long-term memory storage** | ✅ (47KB memory_manager) | ✅ (memory system) |
| **Memory tool** (save/recall/search) | ✅ (51KB) | ✅ (18KB memory-search) |
| **Memory provider abstraction** | ✅ (14KB interface) | ✅ (plugin-based) |
| **Honcho memory backend** | ✅ (via plugin) | ❌ |
| **LanceDB vector memory** | ❌ | ✅ (extension) |
| **Wiki-based memory** | ❌ | ✅ (extension) |
| **Active memory** | ❌ | ✅ (extension) |
| **Memory embedding providers** | ❌ | ✅ (OpenAI-compatible) |
| **Voyage embeddings** | ❌ | ✅ (extension) |
| **Memory OAuth** | ✅ | ❌ |
| **Memory curator** (auto-organizes) | ✅ (87KB curator) | ❌ |
| **Memory sanitization** | ✅ | ✅ |
| **Memory backup** | ✅ (28KB curator_backup) | ❌ |
| **Context references tracking** | ✅ (22KB) | ❌ |
| **Learning graph** (concept relationships) | ✅ (12KB) | ❌ |
| **Learning graph visualization** | ✅ (26KB) | ❌ |
| **Self-improvement loop** (learn from experience) | ✅ (9KB learn_prompt) | ❌ |

---

## 11. Skills System

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Skill discovery and loading** | ✅ (31KB utils) | ✅ (skills subsystem) |
| **Skill execution** | ✅ (69KB skills_tool) | ✅ |
| **Skill management tool** | ✅ (61KB) | ✅ |
| **Skills hub** (browse/install) | ✅ (162KB) | ✅ (ClawHub marketplace) |
| **Skill sync** (across devices) | ✅ (49KB) | ❌ |
| **Skill safety guard** | ✅ (45KB) | ✅ (skills security) |
| **Skill AST security audit** | ✅ (5KB) | ❌ |
| **Skill provenance tracking** | ✅ | ✅ |
| **Skill usage analytics** | ✅ (37KB) | ❌ |
| **Skill bundles** (group related skills) | ✅ (15KB) | ❌ |
| **Skill commands** (slash commands) | ✅ (29KB) | ✅ |
| **Skill preprocessing** | ✅ (5KB) | ❌ |
| **Skill creator/workshop** | ✅ | ✅ (workshop, skill-creator) |
| **Skills from experience** (auto-create) | ✅ (curator creates skills) | ❌ |

### Built-in Skill Categories

| Category | Hermes ☤ | OpenClaw 🦞 |
|----------|:--------:|:-----------:|
| Apple ecosystem (Shortcuts, iCloud, Notes, Reminders) | ✅ | ✅ |
| Autonomous AI agents | ✅ | ❌ |
| Computer use / desktop automation | ✅ | ❌ |
| Creative (writing, art) | ✅ | ❌ |
| Data science | ✅ | ❌ |
| Email management | ✅ | ❌ |
| GitHub integration | ✅ | ✅ |
| Media processing | ✅ | ❌ |
| MLOps | ✅ | ❌ |
| Note-taking (Bear, Obsidian, Notion) | ✅ | ✅ |
| Productivity / organization | ✅ | ❌ |
| Research | ✅ | ❌ |
| Smart home / IoT | ✅ | ✅ (openhue) |
| Social media | ✅ | ❌ |
| Software development | ✅ | ✅ (coding-agent) |
| Blockchain/crypto | ✅ (optional) | ❌ |
| Finance | ✅ (optional) | ❌ |
| Gaming | ✅ (optional) | ❌ |
| Health/fitness | ✅ (optional) | ❌ |
| Payments | ✅ (optional) | ❌ |
| Security | ✅ (optional) | ❌ |
| Web development | ✅ (optional) | ❌ |
| Spotify control | ❌ | ✅ |
| Sonos speaker control | ❌ | ✅ |
| Diagram maker | ❌ | ✅ |
| Meme maker | ❌ | ✅ |
| Weather | ❌ | ✅ |
| Trello | ❌ | ✅ |
| tmux session control | ❌ | ✅ |
| Things (macOS todo) | ❌ | ✅ |
| GIF search | ❌ | ✅ |
| Blog watcher (RSS) | ❌ | ✅ |
| 1Password integration | ❌ | ✅ |
| Health monitoring | ❌ | ✅ |
| Model usage tracking | ❌ | ✅ |
| Task workflow engine | ❌ | ✅ |
| Session log viewer | ❌ | ✅ |
| Camera snapshot | ❌ | ✅ |
| Bluetooth CLI | ❌ | ✅ |
| Node.js debugger | ❌ | ✅ |
| Python debugger | ❌ | ✅ |
| Song identification | ❌ | ✅ |
| URL shortening | ❌ | ✅ |
| PDF processing | ❌ | ✅ |

---

## 12. Scheduled Tasks & Automation

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Cron expression scheduling** | ✅ (177KB scheduler) | ✅ (119-file cron system) |
| **Interval-based scheduling** | ✅ | ✅ |
| **One-shot timers** | ✅ | ✅ |
| **Blueprint catalog** (pre-built cron templates) | ✅ (29KB) | ❌ |
| **Job CRUD** (create, read, update, delete) | ✅ (97KB) | ✅ |
| **Job lifecycle guards** | ✅ (7KB) | ✅ |
| **Personalized cron suggestions** | ✅ (10KB + 7KB) | ❌ |
| **Cron output delivery to channels** | ✅ | ✅ (delivery system) |
| **Cron run logging** | ✅ | ✅ (run-log) |
| **Session reaper** (auto-cleanup) | ❌ | ✅ |
| **Trigger scripts** | ❌ | ✅ (15KB) |
| **Stagger scheduling** (avoid thundering herd) | ❌ | ✅ |
| **Heartbeat jobs** | ❌ | ✅ |
| **Cron CLI management** | ✅ | ✅ |

---

## 13. Multi-Agent & Delegation

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Task delegation** (spawn subagents) | ✅ (158KB delegate_tool) | ✅ (subagent system) |
| **Async delegation** | ✅ (24KB) | ✅ |
| **Agent Communication Protocol (ACP)** | ✅ (88KB server) | ✅ (ACP system) |
| **ACP session management** | ✅ (27KB) | ✅ |
| **ACP permission management** | ✅ (6KB) | ✅ |
| **ACP provenance tracking** | ✅ (5KB) | ❌ |
| **Multi-agent directory** | ❌ | ✅ (agent-dir-registry) |
| **Agent binding to channels** | ❌ | ✅ (agent scope) |
| **Agent runtime configuration** | ❌ | ✅ (runtime-config) |
| **Agent settings per-agent** | ❌ | ✅ |
| **Subagent lifecycle management** | ✅ | ✅ |
| **Kanban swarm execution** (parallel agents) | ✅ (10KB) | ❌ |
| **Copilot ACP client** | ✅ (28KB) | ✅ |

---

## 14. Project Management

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Kanban board** (full project mgmt) | ✅ (115KB CLI + 370KB DB) | ❌ |
| **Kanban task decomposition** | ✅ (17KB) | ❌ |
| **Kanban diagnostics** | ✅ (45KB) | ❌ |
| **Kanban tools** (agent-accessible) | ✅ (69KB) | ❌ |
| **Kanban watchers** (notify on changes) | ✅ (67KB) | ❌ |
| **Todo list tool** | ✅ (13KB) | ❌ |
| **Project tools** | ✅ (7KB) | ❌ |
| **Projects database** | ✅ (25KB) | ❌ |
| **Goals system** (autonomous long-running) | ✅ (79KB) | ❌ |
| **Workboard** (project management) | ❌ | ✅ (extension) |

---

## 15. Session & Conversation Management

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **SQLite-backed session store** | ✅ (6,460 lines) | ✅ (90KB session-utils) |
| **FTS5 full-text search** on sessions | ✅ | ✅ (session search) |
| **WAL mode** (concurrent access) | ✅ | ✅ |
| **Session compression** (auto-split long sessions) | ✅ | ✅ (compaction checkpoints) |
| **Session search tool** | ✅ (39KB) | ✅ |
| **Session metadata tracking** | ✅ | ✅ |
| **Session history** | ✅ | ✅ (CLI session history) |
| **Session lifecycle management** | ✅ | ✅ (lifecycle-state) |
| **Conversation title generation** | ✅ (8KB) | ✅ (dashboard-session-title) |
| **Session file repair** | ❌ | ✅ (30KB) |
| **Session compaction checkpoints** | ❌ | ✅ (29KB) |
| **Session transcript recording** | ❌ | ✅ (transcript files) |
| **Session archive** | ❌ | ✅ |
| **Session reset service** | ❌ | ✅ (45KB) |
| **Session slug generation** | ❌ | ✅ |
| **Active session tracking** | ✅ (11KB) | ✅ |
| **Session export** | ✅ (16KB dump) | ✅ (trajectory export) |

---

## 16. Security & Safety

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Secret redaction** (from logs, outputs) | ✅ (37KB) | ✅ (payload redaction) |
| **Secret scope management** | ✅ (9KB) | ✅ |
| **1Password integration** (secret source) | ✅ (25KB) | ✅ (skill) |
| **Bitwarden integration** (secret source) | ✅ (28KB) | ❌ |
| **HashiCorp Vault** | ❌ | ✅ (extension) |
| **Path security validation** | ✅ | ✅ (path-policy) |
| **Threat pattern detection** | ✅ (14KB) | ❌ |
| **Tirith security framework** | ✅ (35KB) | ❌ |
| **URL safety validation** | ✅ (21KB) | ✅ |
| **File write approval** | ✅ (149KB) | ✅ (72KB before-tool-call) |
| **Tool guardrails** | ✅ (18KB) | ✅ (tool policy) |
| **SSL certificate validation** | ✅ (3KB + 2KB) | ✅ |
| **Docker sandbox execution** | ✅ | ✅ (Crabbox) |
| **OSV vulnerability checking** | ✅ (6KB) | ❌ |
| **Semgrep/OpenGrep SAST rules** | ❌ | ✅ (custom rules) |
| **Plugin security scanning** | ❌ | ✅ (44KB install scan) |
| **Credential persistence** (secure) | ✅ (5KB) | ✅ |
| **Agent delete safety** | ❌ | ✅ |
| **Sandbox media paths isolation** | ❌ | ✅ |
| **Exec auto-reviewer** (AI reviews commands) | ❌ | ✅ (12KB) |
| **Provider secret egress control** | ❌ | ✅ (6KB) |
| **Network egress isolation** | ✅ (design doc) | ✅ |

---

## 17. Configuration & Customization

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **YAML configuration** | ✅ (399KB config system) | ✅ (311-file config system) |
| **Zod-based schema validation** | ❌ | ✅ (25KB + 211KB help) |
| **Environment variable configuration** | ✅ | ✅ |
| **Dotenv file loading** | ✅ (17KB env_loader) | ✅ |
| **Config hot-reload** | ❌ | ✅ (18KB config-reload) |
| **Config includes** (file imports) | ❌ | ✅ (16KB includes) |
| **Config backup/rotation** | ✅ | ✅ (backup-rotation) |
| **Config recovery** | ❌ | ✅ (30KB observe-recovery) |
| **Config mutation system** | ❌ | ✅ (39KB mutate) |
| **Config redaction** (for diagnostics) | ❌ | ✅ (28KB) |
| **Config validation** | ✅ | ✅ (72KB validation) |
| **Profile system** (multiple configs) | ✅ (90KB profiles) | ✅ |
| **Environment-specific overrides** | ✅ | ✅ (env-preserve) |
| **Group policy** | ❌ | ✅ (16KB) |
| **Config diff tracking** | ❌ | ✅ |
| **Future version guard** | ❌ | ✅ |
| **Legacy config detection & migration** | ❌ | ✅ |

---

## 18. Plugin & Extension System

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Plugin discovery and loading** | ✅ (plugins system) | ✅ (124KB loader) |
| **Plugin install/uninstall/update** | ✅ (105KB plugins.py) | ✅ (113KB + 93KB) |
| **Plugin marketplace** | ❌ | ✅ (ClawHub, 54KB) |
| **Plugin manifest system** | ❌ | ✅ (78KB manifest) |
| **Plugin registry** | ✅ | ✅ (119KB registry) |
| **Plugin hooks** (lifecycle events) | ✅ | ✅ (56KB hooks) |
| **Plugin SDK** | ❌ | ✅ (full SDK package) |
| **Plugin security scanning** | ❌ | ✅ (44KB) |
| **Plugin git install** | ❌ | ✅ (15KB) |
| **Plugin npm install** | ❌ | ✅ (109KB tests) |
| **Plugin version drift detection** | ❌ | ✅ (5KB) |
| **Plugin peer linking** | ❌ | ✅ (12KB) |
| **Plugin auto-enable** (smart detection) | ❌ | ✅ (37KB) |
| **Plugin control plane** | ❌ | ✅ |
| **Plugin interactive system** | ❌ | ✅ (34KB) |
| **Total extensions/plugins** | 18 plugin directories | 145 extension directories |

---

## 19. Gateway & Server Infrastructure

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Always-on gateway server** | ✅ (1MB run.py) | ✅ (75KB server.impl) |
| **WebSocket connections** | ✅ | ✅ |
| **HTTP REST API** | ✅ (224KB API server) | ✅ (35KB server-http) |
| **OpenAI-compatible HTTP API** | ❌ | ✅ (44KB) |
| **Open Responses API** | ❌ | ✅ (44KB) |
| **Graceful shutdown / drain** | ✅ (13KB drain) | ✅ (38KB server-close) |
| **Hot-reload** (config changes without restart) | ❌ | ✅ (35KB reload handlers) |
| **Channel health monitoring** | ❌ | ✅ (8KB) |
| **Memory monitor** | ✅ (8KB) | ✅ |
| **Scale-to-zero** (hibernate when idle) | ✅ (5KB) | ❌ |
| **Restart loop guard** | ✅ (6KB) | ✅ (restart sentinel) |
| **Message delivery routing** | ✅ (24KB) | ✅ |
| **Control UI** (web dashboard) | ❌ | ✅ (39KB) |
| **Device pairing** | ✅ (28KB) | ✅ |
| **Tailscale integration** | ❌ | ✅ (3KB) |
| **Gateway discovery** (mDNS) | ❌ | ✅ (bonjour extension) |
| **Slash commands** (in platforms) | ✅ (228KB!) | ✅ |
| **Authorization mixin** | ✅ (37KB) | ✅ |
| **Shutdown forensics** | ✅ (18KB) | ❌ |
| **Code version skew detection** | ✅ (2KB) | ❌ |
| **Model pricing cache** | ❌ | ✅ (47KB) |
| **Operator approvals** | ❌ | ✅ |
| **Node registry** (multi-device) | ❌ | ✅ (27KB) |

---

## 20. CLI & Terminal Interface

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Interactive REPL** | ✅ (16,275 lines cli.py) | ✅ (48KB cli-runner) |
| **CLI with 50+ subcommands** | ✅ (617KB main.py) | ✅ (282 CLI files) |
| **ASCII art branding/banner** | ✅ (41KB) | ✅ (banner system) |
| **Multiline editing** | ✅ | ✅ |
| **Slash-command autocomplete** | ✅ | ✅ |
| **Shell completion** (bash/zsh/fish) | ✅ (11KB) | ✅ (19KB) |
| **Curses-based TUI** (alternative) | ✅ (31KB) | ❌ |
| **TUI gateway server** (WebSocket) | ✅ (579KB server!) | ❌ |
| **TUI frontend** (TypeScript) | ✅ (full app) | ❌ |
| **Rich output formatting** (syntax highlight, tables) | ✅ (55KB display) | ✅ (47KB cli-output) |
| **Streaming tool output** | ✅ | ✅ |
| **Interrupt-and-redirect** | ✅ | ✅ |
| **Clipboard integration** | ✅ (18KB) | ❌ |
| **Doctor diagnostic** (system health) | ✅ (111KB) | ✅ (70+ doctor files) |
| **Progress bars** | ✅ | ✅ (7KB) |
| **Setup wizard** (interactive) | ✅ (onboarding) | ✅ (onboard system) |
| **JSON output mode** | ❌ | ✅ |
| **QR code display** | ❌ | ✅ (9KB qr-cli) |
| **One-shot exit** (run command, exit) | ✅ | ✅ |
| **Profile management** | ✅ (90KB) | ✅ (profile) |
| **Device pairing CLI** | ✅ | ✅ (pairing-cli) |

---

## 21. Desktop, Mobile & Web Apps

| App | Hermes ☤ | OpenClaw 🦞 |
|-----|:--------:|:-----------:|
| **Electron Desktop app** | ✅ (full app) | ❌ |
| **Tauri installer app** | ✅ | ❌ |
| **macOS native app** (Swift) | ❌ | ✅ |
| **iOS app** (Swift/SwiftUI) | ❌ | ✅ |
| **Android app** (Kotlin) | ❌ | ✅ |
| **Web dashboard** (React) | ✅ (web/) | ✅ (ui/) |
| **TUI frontend** (TypeScript/Ink) | ✅ (ui-tui/) | ❌ |
| **macOS MLX local TTS** | ❌ | ✅ |
| **Auto-update** (Sparkle appcast) | ❌ | ✅ (61KB appcast) |
| **Docusaurus documentation website** | ✅ (website/) | ❌ |
| **GitHub Pages preview** | ❌ | ✅ (control-ui-github-preview) |

---

## 22. DevOps & Deployment

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Docker multi-stage build** | ✅ | ✅ |
| **Docker Compose** | ✅ (+Windows override) | ✅ |
| **s6-overlay process supervision** | ✅ | ❌ |
| **Fly.io deployment** | ❌ | ✅ |
| **Render.com deployment** | ❌ | ✅ |
| **Kubernetes configs** | ❌ | ✅ (scripts/k8s/) |
| **Podman support** | ❌ | ✅ (scripts/podman/) |
| **systemd service files** | ❌ | ✅ (scripts/systemd/) |
| **NixOS modules** | ✅ (47KB modules) | ❌ |
| **Nix build system** | ✅ (full flake) | ❌ |
| **Homebrew formula** | ✅ | ✅ |
| **npm/pnpm publish** | ❌ | ✅ |
| **pip/PyPI publish** | ✅ | ❌ |
| **PowerShell installer** | ✅ (175KB) | ✅ (56KB) |
| **Bash installer** | ✅ (133KB) | ✅ (110KB) |
| **Android/Termux support** | ✅ | ❌ |
| **Self-update system** | ✅ | ✅ (update-cli) |
| **Release automation** | ✅ (159KB) | ✅ (43KB + 140KB checks) |
| **Container boot** (auto-setup) | ✅ (26KB) | ✅ |
| **Daemon management** | ✅ | ✅ (daemon-cli) |
| **cgroup cleanup** (Linux) | ✅ (2.5KB) | ❌ |

---

## 23. Observability & Diagnostics

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Structured logging** | ✅ (rotating file handler) | ✅ |
| **Secret-redacting log formatter** | ✅ | ✅ |
| **Trace upload** (observability) | ✅ (15KB) | ✅ (trajectory export) |
| **Streaming diagnostics** | ✅ (10KB) | ✅ |
| **OpenTelemetry** | ❌ | ✅ (diagnostics-otel) |
| **Prometheus metrics** | ❌ | ✅ (diagnostics-prometheus) |
| **Doctor command** (full health check) | ✅ (111KB) | ✅ (70+ doctor files) |
| **Status reporting** | ✅ (61KB) | ✅ (status system) |
| **Agent insights/analytics** | ✅ (40KB) | ❌ |
| **Context window breakdown** visualizer | ✅ (6KB) | ❌ |
| **User journey tracking** | ✅ (14KB) | ❌ |
| **Diagnostics upload** | ✅ (5KB) | ❌ |
| **Billing/usage display** | ✅ (11KB) | ✅ (pricing cache) |
| **Prompt size analyzer** | ✅ (7KB) | ❌ |
| **Restart trace** | ❌ | ✅ (12KB) |
| **Startup trace** | ❌ | ✅ |
| **Log viewer CLI** | ✅ (14KB) | ✅ (28KB logs-cli) |

---

## 24. Internationalization

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **i18n system** | ✅ (12KB i18n.py) | ✅ |
| **Supported languages** | 16 (en, es, de, fr, it, ja, ko, pt, ru, tr, uk, zh, zh-hant, af, ga, hu) | Multiple (via i18n tooling) |
| **Translated README** | ✅ (Spanish, Chinese, Urdu) | ❌ |
| **Translated contributing guide** | ✅ (Spanish) | ❌ |
| **Translated security policy** | ✅ (Spanish) | ❌ |
| **Native app i18n** | ❌ | ✅ (63KB i18n tooling) |
| **Control UI i18n** | ❌ | ✅ |
| **Documentation i18n** | ❌ | ✅ (docs-i18n scripts) |

---

## 25. Data Generation & Training

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Batch runner** (parallel prompt processing) | ✅ (1,322 lines) | ❌ |
| **Trajectory compression** (for training data) | ✅ (1,575 lines) | ❌ |
| **SWE benchmark runner** | ✅ (733 lines) | ❌ |
| **Toolset probability distributions** | ✅ (359 lines) | ❌ |
| **Data generation configs** | ✅ (examples directory) | ❌ |
| **Sample and compress** trajectories | ✅ (14KB script) | ❌ |

> **Note:** Data generation/training is unique to Hermes — it was designed by Nous Research for creating training data to improve AI models.

---

## 26. Protocols & Interoperability

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **MCP Server** (expose tools to external clients) | ✅ (10 tools, stdio) | ✅ (MCP subsystem) |
| **MCP Client** (connect to external MCP servers) | ✅ (251KB mcp_tool) | ✅ |
| **MCP OAuth flows** | ✅ (40KB + 33KB) | ✅ (10KB) |
| **MCP catalog** (browse/install) | ✅ (30KB) | ✅ (mcp-cli) |
| **MCP security** | ✅ (7KB) | ✅ |
| **Agent Communication Protocol (ACP)** | ✅ (full adapter, 88KB server) | ✅ (ACP system) |
| **OpenAI-compatible API** (serve as endpoint) | ✅ (API server) | ✅ (openai-http) |
| **Open Responses API** | ❌ | ✅ (44KB) |
| **Relay connector protocol** | ✅ (WS transport) | ❌ |
| **Microsoft Graph API** | ✅ (14KB client) | ❌ |
| **Feishu/Lark API** | ✅ (docs + drive tools) | ✅ (extension) |
| **X/Twitter API** | ✅ (20KB search tool) | ❌ |
| **Spotify API** | ✅ (plugin) | ✅ (skill) |
| **Home Assistant API** | ✅ (19KB tool) | ❌ |

---

## 27. Smart Home & IoT

| Feature | Hermes ☤ | OpenClaw 🦞 |
|---------|:--------:|:-----------:|
| **Home Assistant integration** | ✅ (19KB) | ❌ |
| **Philips Hue control** | ❌ | ✅ (openhue skill) |
| **Google Meet integration** | ✅ (plugin) | ❌ |
| **Sonos speaker control** | ❌ | ✅ (skill) |
| **Bluetooth CLI control** | ❌ | ✅ (blucli skill) |

---

## 28. Unique / Fun Features

### Hermes-Only ☤

| Feature | Description |
|---------|-------------|
| **Virtual Pet System** 🐣 | ASCII art virtual pet companion with mood states, evolution, hunger/energy, animations, and AI-generated appearances. |
| **Achievement/Gamification System** 🏆 | Unlock achievements as you use Hermes — gamifies the AI experience. |
| **Learning Graph** 🧠 | Builds a visual graph of concepts the agent has learned, with relationships and visualization. |
| **Self-Improvement Loop** 🔄 | Agent creates skills from experience, improves them during use — a genuine learning system. |
| **Memory Curator** 📚 | Autonomously organizes and curates long-term memory — creates skills from patterns. |
| **Kanban Board** (full project management) 📋 | Built-in kanban with task decomposition, diagnostics, swarm execution, and watchers. |
| **Mixture-of-Agents (MoA)** 🤖 | Queries multiple models and merges their responses for higher quality answers. |
| **Goals System** 🎯 | Autonomous, long-running goal pursuit — the agent works towards goals over time. |
| **Data Generation Pipeline** 📊 | Purpose-built for creating AI training data — batch processing, trajectory compression, SWE benchmarks. |
| **Anti-Detection Browser** (Camofox) 🦊 | Browser automation that avoids bot detection. |
| **6 Execution Environments** 🌍 | Local, Docker, SSH, Modal, Daytona, Singularity — run tools anywhere. |
| **LSP Integration** 📝 | Full Language Server Protocol support with auto-install for diagnostics and completions. |
| **NixOS Modules** ❄️ | First-class NixOS service definitions for declarative deployment. |
| **WhatsApp Web Bridge** 📱 | Direct WhatsApp Web integration (not just Cloud API). |
| **WeChat (Weixin) Adapter** 🇨🇳 | Full WeChat integration (94KB). |
| **QQ Bot Adapter** 🇨🇳 | Full QQ messaging integration (128KB). |
| **Yuanbao Adapter** 🇨🇳 | Tencent Yuanbao integration with stickers and media (228KB). |
| **Nous Research Account/Billing** 💳 | Native integration with Nous Research platform and subscriptions. |
| **Keystroke Diagnostics** ⌨️ | Debug keyboard input issues in the TUI. |
| **Discord Voice Doctor** 🎤 | Diagnose Discord voice connection issues. |

### OpenClaw-Only 🦞

| Feature | Description |
|---------|-------------|
| **Native iOS App** 📱 | Full Swift/SwiftUI iOS companion app. |
| **Native Android App** 📱 | Full Kotlin Android companion app. |
| **Native macOS App** 🖥️ | Swift macOS native app with auto-updates. |
| **Live Canvas** 🎨 | Real-time interactive canvas rendering in the browser. |
| **Talk Mode** (voice relay) 🗣️ | Real-time voice conversation with agent handoff capability. |
| **ClawHub Marketplace** 🏪 | Full plugin marketplace (like npm for AI plugins). |
| **145 Extensions** 🧩 | Massive extension ecosystem — 40+ AI providers, 24+ platforms. |
| **Plugin SDK** 🛠️ | Full SDK for building third-party plugins. |
| **Config Hot-Reload** 🔄 | Change configuration without restarting the gateway. |
| **OpenAI-Compatible HTTP API** 🔌 | Serve as a drop-in OpenAI replacement endpoint. |
| **Open Responses API** 📡 | Standard Responses API endpoint. |
| **Kubernetes Deployment** ☸️ | K8s configs for cloud-native deployment. |
| **OpenTelemetry & Prometheus** 📊 | Production-grade observability. |
| **Fly.io / Render.com Deployment** ☁️ | One-click cloud deployment configs. |
| **QR Code Pairing** 📲 | QR code-based device pairing. |
| **Tailscale Integration** 🔒 | Secure networking via Tailscale. |
| **mDNS/Bonjour Discovery** 📡 | Automatic gateway discovery on local network. |
| **Music Generation** 🎵 | AI music generation capability. |
| **Diffs Viewer** (with language pack) 📝 | Visual diff viewer extension. |
| **Parallel Execution** ⚡ | Parallel tool execution extension. |
| **Logbook** 📓 | Session logbook extension. |
| **51 Bundled Skills** 🎯 | Spotify, Sonos, diagrams, memes, weather, Trello, tmux, debuggers, and more. |
| **Exec Auto-Reviewer** 🛡️ | AI reviews shell commands before execution for safety. |
| **macOS MLX Local TTS** 🎤 | On-device TTS using Apple's MLX framework. |
| **ClickClack** 🔊 | Keyboard sounds extension (fun!). |
| **Lobster** 🦞 | Mascot features and branding. |

---

## Summary Statistics

| Metric | Hermes ☤ | OpenClaw 🦞 | Combined |
|--------|:--------:|:-----------:|:--------:|
| **AI Model Providers** | 20+ | 40+ | 45+ unique |
| **Local Model Providers** | 3 | 6 | 6 |
| **Messaging Platforms** | 12+ | 24+ | 30+ unique |
| **Built-in Skills** | 18 categories + 19 optional | 51 bundled | 85+ categories |
| **Extensions/Plugins** | 18 plugins | 145 extensions | 160+ |
| **CLI Subcommands** | 50+ | 50+ | 80+ unique |
| **Execution Environments** | 6 | 2 (local + Docker) | 7 unique |
| **Native Apps** | 1 (Electron desktop) | 4 (iOS, Android, macOS, Web) | 5 |
| **Languages (i18n)** | 16 | Multiple | 16+ |
| **Programming Language** | Python | TypeScript | Both |
| **Source Files** | ~500+ Python | ~2,500+ TypeScript | ~3,000+ |
| **Test Coverage** | 116 test files + 29 dirs | Extensive (per-file tests) | Comprehensive |

---

> **Key Insight:** Hermes excels in **self-improvement, learning, data generation, project management (kanban), Chinese platform support (WeChat/QQ/Yuanbao), and execution environment diversity**. OpenClaw excels in **massive provider/platform coverage, native mobile apps, plugin marketplace, production infrastructure (K8s, observability), hot-reload, and media generation**. Together, they form an extraordinarily comprehensive AI assistant ecosystem.
