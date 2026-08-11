# Beginner-Friendly Guide to the Hermclaw Codebase

Welcome! This guide explains **every single file in the Hermclaw project (119 files total)** in plain English, using real-world analogies so that anyone — even a absolute beginner to programming — can easily understand how everything works.

## Quick Big-Picture Summary

Hermclaw is an **AI Assistant Software** designed around two human-like concepts:

1. **The Body (`hermclaw/body/`)**: The senses and messaging channels (CLI, Web, Telegram, Discord, Slack, WhatsApp). It receives messages from users and sends replies back.
2. **The Brain (`hermclaw/brain/`)**: The thinking mind, memory, and reasoning loop. It decides how to answer, reads past memories, and uses tools.
3. **Tools & Security (`hermclaw/tools/` & `hermclaw/security/`)**: The hands of the AI. Tools let the AI search the web, read files, or run code — but a **Security Dispatcher (Bouncer)** inspects every tool action first to keep your computer safe.


---

## Root Repository & Project Setup Files (12 files)

### 1. `.gitignore`

- 💡 **What is this file?** A checklist file that tells Git (the software that tracks code changes) which files it should ignore and never upload or track.

- 🎯 **Why do we need it?** When code runs, it creates temporary files, private passwords, or local databases. You don't want these uploaded to the internet or shared accidentally.

- 🛠️ **How does it work?** Git reads this list line by line. If a file matches a rule (like `*.log` or `.env`), Git acts like that file doesn't exist for uploading.

- 🔑 **Real-World Analogy**: *Like a shredder bin tag that says 'Do Not Mail These Private Documents'.*

### 2. `ARCHITECTURE.md`

- 💡 **What is this file?** The master blueprint document for Hermclaw.

- 🎯 **Why do we need it?** Helps developers understand how the different parts of the AI agent fit together without having to read thousands of lines of code first.

- 🛠️ **How does it work?** Explains that Hermclaw is split into two big halves: the 'Body' (connecting to apps like Telegram/Discord) and the 'Brain' (thinking and remembering things).

- 🔑 **Real-World Analogy**: *The instruction manual for assembling a complex Lego set.*

### 3. `LICENSE`

- 💡 **What is this file?** The official legal permission slip (MIT License).

- 🎯 **Why do we need it?** Protects the creators legally and lets anyone use, modify, or share the software for free.

- 🛠️ **How does it work?** Standard text that states 'You can use this software however you want, but don't sue us if something breaks.'

- 🔑 **Real-World Analogy**: *A free hall pass given to anyone who wants to use the code.*

### 4. `MERGE_DECISIONS.md`

- 💡 **What is this file?** A diary of major engineering choices made while building Hermclaw.

- 🎯 **Why do we need it?** Hermclaw was created by combining two older AI projects (OpenClaw and Hermes Agent). When those two projects disagreed on how to do something, the creators had to pick a winner.

- 🛠️ **How does it work?** Lists every debate, option A vs option B, and explains why the winning option was chosen.

- 🔑 **Real-World Analogy**: *A judge's written decision explaining why they ruled a certain way.*

### 5. `README.md`

- 💡 **What is this file?** The front door and welcome sign of the project.

- 🎯 **Why do we need it?** When someone opens the project on GitHub, this is the very first webpage they see.

- 🛠️ **How does it work?** Displays pictures, feature lists, quick installation commands, and examples of what the AI can do.

- 🔑 **Real-World Analogy**: *The cover and blurb on the back of a book.*

### 6. `clawbert_status.json`

- 💡 **What is this file?** A mini save-file for Clawbert, the AI's virtual pet crab.

- 🎯 **Why do we need it?** Remembers how happy or hungry Clawbert is even when the computer turns off.

- 🛠️ **How does it work?** Stores numbers like `hunger: 50` and `happiness: 80` in simple text format.

- 🔑 **Real-World Analogy**: *A virtual Tamagotchi save file.*

### 7. `hermclaw.example.yaml`

- 💡 **What is this file?** A sample settings file filled out with safe default values.

- 🎯 **Why do we need it?** Gives new users a working starting point so they don't have to write settings from scratch.

- 🛠️ **How does it work?** When Hermclaw installs for the first time, it copies this file to create your personal settings.

- 🔑 **Real-World Analogy**: *A pre-filled sample job application.*

### 8. `hermclaw_complete_features.md`

- 💡 **What is this file?** Complete feature catalog documentation.

- 🎯 **Why do we need it?** Lists every single feature supported by Hermclaw in one document.

- 🛠️ **How does it work?** Markdown reference catalog.

- 🔑 **Real-World Analogy**: *The full product feature brochure.*

### 9. `hermclaw_test_guide.md`

- 💡 **What is this file?** Hands-on feature testing guide.

- 🎯 **Why do we need it?** Gives you copy-paste prompts to test every feature step by step.

- 🛠️ **How does it work?** Lists test prompts and expected outcomes.

- 🔑 **Real-World Analogy**: *A driving test checklist for a new car.*

### 10. `install.py`

- 💡 **What is this file?** The automatic installer and setup wizard.

- 🎯 **Why do we need it?** Sets up Hermclaw easily by asking simple questions.

- 🛠️ **How does it work?** Checks Python, detects Ollama, asks for your preferences, and creates your config file.

- 🔑 **Real-World Analogy**: *An installation wizard setup program.*

### 11. `pyproject.toml`

- 💡 **What is this file?** Python package build blueprint.

- 🎯 **Why do we need it?** Tells Python build tools how to package and install Hermclaw.

- 🛠️ **How does it work?** Defines project metadata and dependencies.

- 🔑 **Real-World Analogy**: *A factory specification sheet.*

### 12. `requirements.txt`

- 💡 **What is this file?** List of required Python libraries.

- 🎯 **Why do we need it?** Ensures all necessary helper packages are installed.

- 🛠️ **How does it work?** Lists packages like `pydantic`, `fastapi`, and `structlog`.

- 🔑 **Real-World Analogy**: *A required textbook list for a university course.*

## Documentation Files (2 files)

### 13. `docs/CONFIG_REFERENCE.md`

- 💡 **What is this file?** A complete dictionary explaining every setting in the AI's configuration file.

- 🎯 **Why do we need it?** If a user wants to change the AI's name or turn on Discord chat, they can look up the exact setting name here.

- 🛠️ **How does it work?** Organized into tables showing setting names, what they do, and default values.

- 🔑 **Real-World Analogy**: *A car owner's manual explaining what every button on the dashboard does.*

### 14. `docs/SKILL_AUTHORING.md`

- 💡 **What is this file?** A step-by-step guide for teaching the AI new skills.

- 🎯 **Why do we need it?** Shows programmers how to write custom skills so the AI can do new jobs (like checking weather or translating languages).

- 🛠️ **How does it work?** Explains how to name skill folders and write instructions in simple markdown format.

- 🔑 **Real-World Analogy**: *A cookbook recipe showing how to teach a apprentice a new dish.*

## Core Application & Package Files (8 files)

### 15. `hermclaw/__init__.py`

- 💡 **What is this file?** A tiny signpost file that marks the `hermclaw` folder as an official Python package.

- 🎯 **Why do we need it?** Python needs this file to understand that the files inside this folder belong together as a single software library.

- 🛠️ **How does it work?** Contains short version information and package description.

- 🔑 **Real-World Analogy**: *A nameplate on a office door saying 'Hermclaw Main Office'.*

### 16. `hermclaw/banner.py`

- 💡 **What is this file?** A visual styling script that draws cool ASCII art text in your terminal window.

- 🎯 **Why do we need it?** Makes starting Hermclaw look professional and fun.

- 🛠️ **How does it work?** Takes letters and converts them into big blocky text with colors.

- 🔑 **Real-World Analogy**: *A glowing neon welcome sign at a store entrance.*

### 17. `hermclaw/cli.py`

- 💡 **What is this file?** The Command Line Interface (CLI) command menu.

- 🎯 **Why do we need it?** This is what runs when you type `hermclaw` in your terminal window.

- 🛠️ **How does it work?** Provides 5 main subcommands: `chat`, `serve`, `doctor`, `reflect`, `skills`.

- 🔑 **Real-World Analogy**: *The main menu screen of a video game.*

### 18. `hermclaw/config.py`

- 💡 **What is this file?** The settings manager.

- 🎯 **Why do we need it?** Loads, validates, and saves `~/.hermclaw/hermclaw.yaml` safely.

- 🛠️ **How does it work?** Uses Pydantic to check for typos. If your settings file gets corrupted, it automatically rolls back to the last working copy (`hermclaw.lkg.yaml`).

- 🔑 **Real-World Analogy**: *A vigilant guard that checks your settings for errors before letting the program start.*

### 19. `hermclaw/config_defaults.py`

- 💡 **What is this file?** The hardcoded backup copy of default settings.

- 🎯 **Why do we need it?** Guarantees that Hermclaw always has a pristine copy of default settings even on brand new computers.

- 🛠️ **How does it work?** Stores raw YAML configuration text as a Python variable.

- 🔑 **Real-World Analogy**: *The factory reset backup stored in a emergency ROM chip.*

### 20. `hermclaw/i18n.py`

- 💡 **What is this file?** The language translator module (Supports 16 languages).

- 🎯 **Why do we need it?** Allows users worldwide to use Hermclaw in their native language (English, Spanish, French, Hindi, Japanese, etc.).

- 🛠️ **How does it work?** Replaces internal message codes with translated words depending on your configured language.

- 🔑 **Real-World Analogy**: *A multi-lingual interpreter at an international conference.*

### 21. `hermclaw/observability.py`

- 💡 **What is this file?** The structured logging and secret blocker system.

- 🎯 **Why do we need it?** Prints helpful progress logs to terminal and disk while making sure passwords or secret keys are NEVER leaked into log files.

- 🛠️ **How does it work?** Scans every log line for tokens/passwords and replaces them with `[REDACTED]` before writing.

- 🔑 **Real-World Analogy**: *A security censor redacting secret names from public police reports.*

### 22. `hermclaw/runtime.py`

- 💡 **What is this file?** The agent assembly factory.

- 🎯 **Why do we need it?** Hooks up settings, memory databases, security rules, and AI connectors into a complete running agent.

- 🛠️ **How does it work?** Combines `HermclawConfig`, `ProfileManager`, `MemoryStore`, and `ToolDispatcher` into an `AgentRuntime` object.

- 🔑 **Real-World Analogy**: *An automotive assembly line putting together a car's engine, wheels, and frame.*

## The 'Body' Layer: Connecting to Users & Chat Platforms (15 files)

### 23. `hermclaw/body/__init__.py`

- 💡 **What is this file?** The folder label for the 'Body' part of the AI.

- 🎯 **Why do we need it?** Tells Python that all files inside `hermclaw/body/` belong to the Body layer.

- 🛠️ **How does it work?** Imports basic Body components when someone imports `hermclaw.body`.

- 🔑 **Real-World Analogy**: *A directory map in a hospital building.*

### 24. `hermclaw/body/agents_registry.py`

- 💡 **What is this file?** The identity router that lets the AI act like different characters depending on who is talking to it.

- 🎯 **Why do we need it?** You might want one assistant to be a formal coding helper and another to be a casual friendly chat companion.

- 🛠️ **How does it work?** Looks at incoming messages, checks which bot identity was requested, and loads that character's memory and rules.

- 🔑 **Real-World Analogy**: *An actor changing masks and costumes depending on which scene they are playing.*

### 25. `hermclaw/body/gateway.py`

- 💡 **What is this file?** The main server engine that keeps Hermclaw running in the background.

- 🎯 **Why do we need it?** Coordinates all chat channels, accepts HTTP requests, and keeps everything alive.

- 🛠️ **How does it work?** Starts a FastAPI web server, loads enabled channels, and automatically reloads settings when `hermclaw.yaml` changes.

- 🔑 **Real-World Analogy**: *The main power plant and control room of a building.*

### 26. `hermclaw/body/mcp_client.py`

- 💡 **What is this file?** The adapter for Model Context Protocol (MCP) servers.

- 🎯 **Why do we need it?** Allows Hermclaw to connect to external tool servers created by third-party developers.

- 🛠️ **How does it work?** Discovers remote tools over MCP standard connections and wraps them so they look like native Hermclaw tools.

- 🔑 **Real-World Analogy**: *A universal USB port that lets Hermclaw plug in external gadgets.*

### 27. `hermclaw/body/scheduler.py`

- 💡 **What is this file?** The alarm clock and task timer.

- 🎯 **Why do we need it?** Allows the AI to perform tasks automatically in the background (like checking emails or sending reminders).

- 🛠️ **How does it work?** Uses APScheduler to trigger background 'heartbeats' or user-defined cron schedules.

- 🔑 **Real-World Analogy**: *A automated alarm clock and planner.*

### 28. `hermclaw/body/channels/__init__.py`

- 💡 **What is this file?** The master switch for turning chat channels on or off.

- 🎯 **Why do we need it?** Loads all active channels (Telegram, Discord, Web) so the AI can listen on all of them at once.

- 🛠️ **How does it work?** Checks your settings file to see which channels are enabled, builds them, and starts listening.

- 🔑 **Real-World Analogy**: *A multi-line telephone switchboard in an office.*

### 29. `hermclaw/body/channels/base.py`

- 💡 **What is this file?** The universal rules template that EVERY chat channel must follow.

- 🎯 **Why do we need it?** Telegram, Discord, and Slack all work differently. This file creates a single standard format so the AI doesn't care which app the user is typing from.

- 🛠️ **How does it work?** Defines basic functions like `send()` and `start()` that every channel adapter must provide.

- 🔑 **Real-World Analogy**: *A universal adapter plug that lets any international electrical plug fit into a standard wall outlet.*

### 30. `hermclaw/body/channels/cli_channel.py`

- 💡 **What is this file?** The terminal chat window channel.

- 🎯 **Why do we need it?** Allows you to talk directly to the AI inside your computer terminal without needing internet chat apps.

- 🛠️ **How does it work?** Reads lines you type in standard input (keyboard) and prints the AI's answers to standard output (screen).

- 🔑 **Real-World Analogy**: *A walkie-talkie connecting your terminal straight to the AI.*

### 31. `hermclaw/body/channels/discord.py`

- 💡 **What is this file?** The Discord bot connector.

- 🎯 **Why do we need it?** Lets Hermclaw join your Discord server or answer your direct messages on Discord.

- 🛠️ **How does it work?** Connects to Discord's servers using a bot token, listens for messages where the bot is mentioned, and replies back.

- 🔑 **Real-World Analogy**: *A translator standing in a Discord server relaying messages to the AI.*

### 32. `hermclaw/body/channels/slack.py`

- 💡 **What is this file?** The Slack workspace bot connector.

- 🎯 **Why do we need it?** Allows Hermclaw to work inside workplace Slack channels without needing a public IP address.

- 🛠️ **How does it work?** Uses Slack's 'Socket Mode' to establish a private background tunnel to Slack.

- 🔑 **Real-World Analogy**: *A secure private phone line connecting Slack straight to Hermclaw.*

### 33. `hermclaw/body/channels/telegram.py`

- 💡 **What is this file?** The Telegram bot connector.

- 🎯 **Why do we need it?** Allows you to message Hermclaw from your phone or desktop via Telegram.

- 🛠️ **How does it work?** Polls Telegram for new user messages, checks if the sender is authorized, and sends the AI's response.

- 🔑 **Real-World Analogy**: *A dedicated messenger carrying notes back and forth between you on Telegram and the AI.*

### 34. `hermclaw/body/channels/web.py`

- 💡 **What is this file?** The web browser chat widget.

- 🎯 **Why do we need it?** Provides a clean chat interface right inside your internet browser.

- 🛠️ **How does it work?** Hosts a small local web server and uses real-time WebSockets so words pop up instantly as the AI types.

- 🔑 **Real-World Analogy**: *A mini live-chat bubble on a webpage.*

### 35. `hermclaw/body/channels/whatsapp.py`

- 💡 **What is this file?** The WhatsApp connector Python side.

- 🎯 **Why do we need it?** Connects Hermclaw to WhatsApp so you can text your AI assistant.

- 🛠️ **How does it work?** Talks to a background Node.js helper program using JSON messages over stdin/stdout.

- 🔑 **Real-World Analogy**: *A phone operator taking messages from WhatsApp and handing them to the AI.*

### 36. `hermclaw/body/channels/whatsapp_sidecar/index.js`

- 💡 **What is this file?** The JavaScript helper program for WhatsApp.

- 🎯 **Why do we need it?** Python doesn't have a good direct library for WhatsApp Web, but JavaScript does (Baileys).

- 🛠️ **How does it work?** Runs in Node.js, connects to WhatsApp Web, shows a QR code to scan, and passes messages to Python.

- 🔑 **Real-World Analogy**: *A bilingual assistant who speaks JavaScript to WhatsApp and Python to Hermclaw.*

### 37. `hermclaw/body/channels/whatsapp_sidecar/package.json`

- 💡 **What is this file?** The configuration file for the Node.js WhatsApp helper.

- 🎯 **Why do we need it?** Tells Node.js which libraries to download for WhatsApp support.

- 🛠️ **How does it work?** Lists required JavaScript packages like `@whiskeysockets/baileys`.

- 🔑 **Real-World Analogy**: *A shopping list for Node.js software packages.*

## The 'Brain' Layer: AI Thinking, Memory & AI Services (22 files)

### 38. `hermclaw/brain/__init__.py`

- 💡 **What is this file?** The folder label for the 'Brain' part of the AI.

- 🎯 **Why do we need it?** Tells Python that all files inside `hermclaw/brain/` belong to the reasoning and memory engine.

- 🛠️ **How does it work?** Initializes brain package exports.

- 🔑 **Real-World Analogy**: *The entryway door to the AI's thinking room.*

### 39. `hermclaw/brain/agent_loop.py`

- 💡 **What is this file?** The central thinking and tool-using loop (The AI's Mind).

- 🎯 **Why do we need it?** This is the most important file for reasoning! It decides what tools to use and how to answer your questions.

- 🛠️ **How does it work?** 1. Receives your message -> 2. Loads memories and tools -> 3. Asks the LLM what to do -> 4. Runs tools if requested -> 5. Repeats until done.

- 🔑 **Real-World Analogy**: *A detective looking at clues, picking up tools, thinking, and writing down final conclusions.*

### 40. `hermclaw/brain/cache.py`

- 💡 **What is this file?** A smart memory shortcut that remembers previous answers to identical questions.

- 🎯 **Why do we need it?** Saves money and time by avoiding asking the expensive AI model the exact same question twice.

- 🛠️ **How does it work?** Hashes questions into unique fingerprint keys; if the question was answered recently, returns the cached answer instantly.

- 🔑 **Real-World Analogy**: *A cheat sheet of answered math problems.*

### 41. `hermclaw/brain/learning_graph.py`

- 💡 **What is this file?** A visual web connecting ideas the AI has learned.

- 🎯 **Why do we need it?** Helps the AI understand how concepts connect (e.g. 'Python' -> 'Programming Language' -> 'Software').

- 🛠️ **How does it work?** Stores nodes (concepts) and edges (relationships) in SQLite and can render them as ASCII tree diagrams.

- 🔑 **Real-World Analogy**: *A mind map drawn on a whiteboard.*

### 42. `hermclaw/brain/moa.py`

- 💡 **What is this file?** Mixture-of-Agents (MoA) committee thinker.

- 🎯 **Why do we need it?** Gets higher quality answers by consulting multiple AI models at once.

- 🛠️ **How does it work?** Sends your question to 3 different models simultaneously, then hands all 3 answers to a master model to synthesize the best single response.

- 🔑 **Real-World Analogy**: *A panel of 3 expert doctors conferring together before giving a final medical diagnosis.*

### 43. `hermclaw/brain/model_catalog.py`

- 💡 **What is this file?** The catalog of AI model prices, limits, and capabilities.

- 🎯 **Why do we need it?** Tracks how many tokens were used and calculates how much money was spent on AI API calls.

- 🛠️ **How does it work?** Contains lookup tables for Claude, OpenAI, Ollama, etc., and tracks total dollar expenditure.

- 🔑 **Real-World Analogy**: *A price tag menu and cash register receipt counter.*

### 44. `hermclaw/brain/parallel_exec.py`

- 💡 **What is this file?** The multi-tasking tool executor.

- 🎯 **Why do we need it?** If the AI decides to run 3 tools at once (like reading 3 files), doing them one by one is slow.

- 🛠️ **How does it work?** Runs multiple tools concurrently using Python `asyncio`.

- 🔑 **Real-World Analogy**: *A chef using four stove burners at the same time instead of cooking dishes one after another.*

### 45. `hermclaw/brain/post_processing.py`

- 💡 **What is this file?** The text cleaner and output polished.

- 🎯 **Why do we need it?** Some AI models print raw internal thinking thoughts (`<think>...</think>`). Users usually just want the clean answer.

- 🛠️ **How does it work?** Strips out `<think>` tags and cleans formatting before showing text to the user.

- 🔑 **Real-World Analogy**: *A video editor cutting out bloopers and behind-the-scenes footage before showing the movie.*

### 46. `hermclaw/brain/profiles.py`

- 💡 **What is this file?** The profile and personality folder manager.

- 🎯 **Why do we need it?** Keeps different assistant personas completely separate so their memories and secret files never mix.

- 🛠️ **How does it work?** Manages profile subfolders (`~/.hermclaw/profiles/default/`) holding `SOUL.md`, `MEMORY.md`, and `USER.md`.

- 🔑 **Real-World Analogy**: *Separate locked user profile accounts on a shared laptop.*

### 47. `hermclaw/brain/reflection.py`

- 💡 **What is this file?** The nighttime self-reflection engine.

- 🎯 **Why do we need it?** Allows the AI to learn from experience automatically without being explicitly trained.

- 🛠️ **How does it work?** Reviews past chats, extracts key facts about you (e.g. 'User likes Python'), and saves them to `MEMORY.md`.

- 🔑 **Real-World Analogy**: *A student reviewing their daily class notes before going to sleep.*

### 48. `hermclaw/brain/skill_growth.py`

- 💡 **What is this file?** The automated skill creator.

- 🎯 **Why do we need it?** If the AI notices it does the exact same multi-step task 3 times, it can write a new reusable skill for itself.

- 🛠️ **How does it work?** Drafts a new skill folder with a `SKILL.md` file whenever a repeated procedure is recognized.

- 🔑 **Real-World Analogy**: *An apprentice turning a repeated task into a printed standard operating procedure (SOP).*

### 49. `hermclaw/brain/memory/__init__.py`

- 💡 **What is this file?** The memory package initializer.

- 🎯 **Why do we need it?** Groups memory stores, SQL schemas, and context compressors together.

- 🛠️ **How does it work?** Exposes memory module components.

- 🔑 **Real-World Analogy**: *A file cabinet label.*

### 50. `hermclaw/brain/memory/compressor.py`

- 💡 **What is this file?** The conversation summarizer.

- 🎯 **Why do we need it?** AI models have context limits (a max length of text they can read at once). Long chats would fail if not shortened.

- 🛠️ **How does it work?** When a chat gets too long, it asks the AI to write a summary recap of older turns, keeping recent turns untouched.

- 🔑 **Real-World Analogy**: *An editor turning a long multi-page transcript into a 1-page summary executive report.*

### 51. `hermclaw/brain/memory/schema.sql`

- 💡 **What is this file?** The blueprint for the AI's database tables.

- 🎯 **Why do we need it?** Tells SQLite how to organize stored messages, sessions, goals, and search indexes.

- 🛠️ **How does it work?** Written in standard SQL `CREATE TABLE` statements.

- 🔑 **Real-World Analogy**: *The column layout and headers printed on a blank ledger book.*

### 52. `hermclaw/brain/memory/store.py`

- 💡 **What is this file?** The digital diary file manager.

- 🎯 **Why do we need it?** Saves every message you send and receive so the AI never forgets your chat history.

- 🛠️ **How does it work?** Uses SQLite databases (`state.db`) with WAL-mode (fast background writes) and full-text search.

- 🔑 **Real-World Analogy**: *A librarian writing down every conversation in a giant searchable library catalog.*

### 53. `hermclaw/brain/memory/vector_memory.py`

- 💡 **What is this file?** The semantic memory search engine.

- 🎯 **Why do we need it?** Lets the AI search memories by *meaning* rather than exact word matches (e.g. searching 'dog' finds 'puppy').

- 🛠️ **How does it work?** Converts sentences into mathematical numbers (vectors) and measures how close their meanings are.

- 🔑 **Real-World Analogy**: *A librarian who understands synonyms and concepts rather than just matching letters.*

### 54. `hermclaw/brain/transports/__init__.py`

- 💡 **What is this file?** The AI network connector factory.

- 🎯 **Why do we need it?** Chooses the right network adapter depending on whether you are using Anthropic, AWS Bedrock, or Ollama.

- 🛠️ **How does it work?** Looks up secrets from environment variables and builds the requested transport class.

- 🔑 **Real-World Analogy**: *Selecting the right charger plug for your phone model.*

### 55. `hermclaw/brain/transports/anthropic.py`

- 💡 **What is this file?** The Anthropic Claude connector.

- 🎯 **Why do we need it?** Handles communication with Anthropic's Claude AI models.

- 🛠️ **How does it work?** Sends HTTP messages formatted specifically for Claude's Messages API.

- 🔑 **Real-World Analogy**: *A phone line connecting directly to Anthropic headquarters.*

### 56. `hermclaw/brain/transports/base.py`

- 💡 **What is this file?** The standard network interface blueprint for all AI providers.

- 🎯 **Why do we need it?** Ensures all AI providers (OpenAI, Anthropic, Bedrock) use the exact same input/output format inside Hermclaw.

- 🛠️ **How does it work?** Defines base class `ProviderTransport`.

- 🔑 **Real-World Analogy**: *A standard form that all news reporters must fill out when filing a story.*

### 57. `hermclaw/brain/transports/bedrock.py`

- 💡 **What is this file?** The Amazon Web Services (AWS) Bedrock connector.

- 🎯 **Why do we need it?** Allows Hermclaw to use AI models hosted on Amazon Cloud.

- 🛠️ **How does it work?** Uses AWS `boto3` library to talk to the Bedrock Converse API.

- 🔑 **Real-World Analogy**: *A secure satellite link to Amazon Cloud AI servers.*

### 58. `hermclaw/brain/transports/fake.py`

- 💡 **What is this file?** A pretend AI connector for offline testing.

- 🎯 **Why do we need it?** Allows software tests to run instantly without internet access or spending money on real AI API calls.

- 🛠️ **How does it work?** Returns pre-scripted fake text responses when asked questions.

- 🔑 **Real-World Analogy**: *A practice dummy used by martial artists to practice hits without hurting anyone.*

### 59. `hermclaw/brain/transports/openai_compat.py`

- 💡 **What is this file?** The universal OpenAI-style connector.

- 🎯 **Why do we need it?** Almost all local AI apps (Ollama, LM Studio, vLLM) and OpenRouter use OpenAI's standard format.

- 🛠️ **How does it work?** Uses HTTP calls over `httpx` to send `/v1/chat/completions` requests.

- 🔑 **Real-World Analogy**: *A universal adapter that speaks the standard language understood by 90% of open-source AI servers.*

## Plugins System (1 file)

### 60. `hermclaw/plugins/__init__.py`

- 💡 **What is this file?** The plugin manager.

- 🎯 **Why do we need it?** Lets third-party developers write extension plugins that add new features to Hermclaw.

- 🛠️ **How does it work?** Loads plugins from `~/.hermclaw/plugins/` or installs them from Git repositories.

- 🔑 **Real-World Analogy**: *An app store installed on your smartphone.*

## Security & Safety Systems (4 files)

### 61. `hermclaw/security/__init__.py`

- 💡 **What is this file?** Security folder initializer.

- 🎯 **Why do we need it?** Marks security package root.

- 🛠️ **How does it work?** Package header file.

- 🔑 **Real-World Analogy**: *A security checkpoint sign.*

### 62. `hermclaw/security/audit.py`

- 💡 **What is this file?** The security audit logger and speed limiter.

- 🎯 **Why do we need it?** Keeps an immutable record of every single tool execution for security safety, and prevents runaway tool loops.

- 🛠️ **How does it work?** Saves tool execution details into `audit.db` and enforces maximum call speed limits.

- 🔑 **Real-World Analogy**: *A security camera recording every door opened in a high-security building.*

### 63. `hermclaw/security/permissions.py`

- 💡 **What is this file?** The directory boundary guard.

- 🎯 **Why do we need it?** Prevents malicious or accidental commands from accessing files outside your assigned workspace directory.

- 🛠️ **How does it work?** Checks paths using `ensure_within_scope()` and blocks any path trying to escape with `../`.

- 🔑 **Real-World Analogy**: *A security perimeter fence stopping visitors from wandering into restricted zones.*

### 64. `hermclaw/security/secrets.py`

- 💡 **What is this file?** The password and secret variable manager.

- 🎯 **Why do we need it?** Prevents hardcoding passwords in configuration files.

- 🛠️ **How does it work?** Reads variable references like `bot_token_env: TELEGRAM_TOKEN` and looks up actual secrets from your operating system environment.

- 🔑 **Real-World Analogy**: *A locked key box where passwords are stored safely away from code files.*

## Skills System (3 files)

### 65. `hermclaw/skills/__init__.py`

- 💡 **What is this file?** Skills folder initializer.

- 🎯 **Why do we need it?** Marks skills package root.

- 🛠️ **How does it work?** Package header file.

- 🔑 **Real-World Analogy**: *A skill library entry door.*

### 66. `hermclaw/skills/loader.py`

- 💡 **What is this file?** The skill file reader and checker.

- 🎯 **Why do we need it?** Reads skill files (`SKILL.md`) and verifies that they follow the `agentskills.io` standard format.

- 🛠️ **How does it work?** Parses YAML headers, checks skill names and descriptions, and alerts if anything is missing.

- 🔑 **Real-World Analogy**: *An examiner reviewing student lesson plans for formatting mistakes.*

### 67. `hermclaw/skills/registry.py`

- 💡 **What is this file?** The skill organizer and librarian.

- 🎯 **Why do we need it?** Manages hundreds of skills efficiently without overloading the AI's prompt with heavy text.

- 🛠️ **How does it work?** Uses progressive disclosure: keeps short descriptions in memory initially, and loads full instructions only when the skill is actually invoked.

- 🔑 **Real-World Analogy**: *A library card catalog that shows short book titles first and pulls full books off shelves only when needed.*

## Tools & Hands-On Action Modules (28 files)

### 68. `hermclaw/tools/__init__.py`

- 💡 **What is this file?** Tools package initializer.

- 🎯 **Why do we need it?** Marks tools package root.

- 🛠️ **How does it work?** Package header file.

- 🔑 **Real-World Analogy**: *A toolbox lid.*

### 69. `hermclaw/tools/achievements.py`

- 💡 **What is this file?** The gamification achievement system.

- 🎯 **Why do we need it?** Makes using the AI fun by unlocking fun badges and trophies as you interact with it.

- 🛠️ **How does it work?** Tracks stats (like '100 chat messages sent') and awards colorful badges.

- 🔑 **Real-World Analogy**: *Xbox or PlayStation achievement trophies.*

### 70. `hermclaw/tools/app_launcher.py`

- 💡 **What is this file?** Desktop application launcher tool.

- 🎯 **Why do we need it?** Allows the AI to open software applications on your computer (like Notepad, Chrome, or Spotify).

- 🛠️ **How does it work?** Uses OS commands (`start` on Windows, `open` on Mac, `xdg-open` on Linux).

- 🔑 **Real-World Analogy**: *Double-clicking an application icon on your desktop.*

### 71. `hermclaw/tools/approvals.py`

- 💡 **What is this file?** The safety approval gate builder.

- 🎯 **Why do we need it?** Stops dangerous commands (like deleting files) until you explicitly click 'Approve'.

- 🛠️ **How does it work?** Checks tool risk levels and prompts the user for confirmation when needed.

- 🔑 **Real-World Analogy**: *A pop-up window asking 'Are you sure you want to delete this file?'*

### 72. `hermclaw/tools/base.py`

- 💡 **What is this file?** The master tool controller (`ToolDispatcher`).

- 🎯 **Why do we need it?** THIS IS THE MOST IMPORTANT SECURITY FILE FOR TOOLS! Guarantees that EVERY tool action goes through security checks.

- 🛠️ **How does it work?** Forces all tools to inherit from `ToolABC` and pass through `ToolDispatcher`. Inspects dangerous commands (like `rm -rf /`) and blocks them.

- 🔑 **Real-World Analogy**: *The main security bouncer at a club entrance who inspects everyone's ID and bags before letting them in.*

### 73. `hermclaw/tools/browser_tool.py`

- 💡 **What is this file?** Web browser automation tool.

- 🎯 **Why do we need it?** Lets the AI browse websites, click buttons, fill forms, and take screenshots.

- 🛠️ **How does it work?** Controls a headless web browser using Playwright software.

- 🔑 **Real-World Analogy**: *A robot holding a mouse and keyboard navigating a website for you.*

### 74. `hermclaw/tools/clipboard_tool.py`

- 💡 **What is this file?** System clipboard tool.

- 🎯 **Why do we need it?** Lets the AI copy text to or paste text from your clipboard.

- 🛠️ **How does it work?** Uses native copy/paste tools (`pbcopy`/`pbpaste` on Mac, `powershell` on Windows).

- 🔑 **Real-World Analogy**: *Pressing Ctrl+C and Ctrl+V on your keyboard.*

### 75. `hermclaw/tools/code_exec.py`

- 💡 **What is this file?** Code execution sandbox tool.

- 🎯 **Why do we need it?** Allows the AI to write and test Python or JavaScript code snippets.

- 🛠️ **How does it work?** Runs code in isolated temporary subprocesses with time limits.

- 🔑 **Real-World Analogy**: *A scientist testing a chemical in a isolated test tube.*

### 76. `hermclaw/tools/delegate_tool.py`

- 💡 **What is this file?** Sub-agent delegator tool.

- 🎯 **Why do we need it?** Allows the main AI assistant to spawn helper sub-agents to do subtasks in parallel.

- 🛠️ **How does it work?** Creates independent background sub-agent loops and collects their results.

- 🔑 **Real-World Analogy**: *A project manager delegating subtasks to assistant team members.*

### 77. `hermclaw/tools/file_tools.py`

- 💡 **What is this file?** File system tools (`read`, `write`, `edit`, `list`, `grep`).

- 🎯 **Why do we need it?** Gives the AI structured ways to work with files without using dangerous shell commands.

- 🛠️ **How does it work?** Reads file lines, writes files, performs multi-line replacements, lists directory files, and searches text with ripgrep.

- 🔑 **Real-World Analogy**: *A digital desktop organizer reading, writing, and filing paper folders.*

### 78. `hermclaw/tools/git_tool.py`

- 💡 **What is this file?** Git code version control tool.

- 🎯 **Why do we need it?** Allows the AI to create safety snapshots of your code before making changes, so you can easily undo mistakes.

- 🛠️ **How does it work?** Runs git commands like status, diff, commit, and stash.

- 🔑 **Real-World Analogy**: *Creating a quick save point before a difficult boss fight in a video game.*

### 79. `hermclaw/tools/goals_tool.py`

- 💡 **What is this file?** Long-term goal tracker tool.

- 🎯 **Why do we need it?** Allows the AI to track multi-day projects and remember what steps are finished.

- 🛠️ **How does it work?** Stores goals and milestones in SQLite and displays them in system prompts.

- 🔑 **Real-World Analogy**: *A pin-board displaying project goals and completed checklists.*

### 80. `hermclaw/tools/media_tools.py`

- 💡 **What is this file?** Image generator and vision tool.

- 🎯 **Why do we need it?** Allows the AI to generate new pictures or look at images you upload.

- 🛠️ **How does it work?** Calls DALL-E / fal.ai for image generation and vision AI models for image understanding.

- 🔑 **Real-World Analogy**: *An artist with an easel and a magnifying glass inspecting photos.*

### 81. `hermclaw/tools/memory_search.py`

- 💡 **What is this file?** Past session memory search tool (`session_search`).

- 🎯 **Why do we need it?** Lets the AI search through older conversations to remember things you discussed days or weeks ago.

- 🛠️ **How does it work?** Queries SQLite full-text search indexes.

- 🔑 **Real-World Analogy**: *Flipping back through previous pages of a daily personal diary.*

### 82. `hermclaw/tools/notify_tool.py`

- 💡 **What is this file?** Desktop notification tool.

- 🎯 **Why do we need it?** Sends pop-up alert notifications to your desktop when a task finishes.

- 🛠️ **How does it work?** Triggers Windows toasts, Mac notifications, or Linux alerts.

- 🔑 **Real-World Analogy**: *A phone ringing or popping up a push notification.*

### 83. `hermclaw/tools/pdf_tool.py`

- 💡 **What is this file?** PDF document reader tool.

- 🎯 **Why do we need it?** Allows the AI to read text from PDF documents.

- 🛠️ **How does it work?** Extracts text using PyMuPDF (`fitz`) or pdfminer libraries.

- 🔑 **Real-World Analogy**: *A document scanner turning PDF pages into plain text.*

### 84. `hermclaw/tools/scheduler_tool.py`

- 💡 **What is this file?** Task scheduling tool.

- 🎯 **Why do we need it?** Lets the AI set timers ('Remind me in 30 minutes') or recurring background jobs.

- 🛠️ **How does it work?** Stores schedule items in SQLite and connects to `HermclawScheduler`.

- 🔑 **Real-World Analogy**: *Setting a kitchen timer or smartphone calendar event.*

### 85. `hermclaw/tools/shell.py`

- 💡 **What is this file?** Terminal shell tool.

- 🎯 **Why do we need it?** Allows running command-line commands. **Disabled by default for security**.

- 🛠️ **How does it work?** Passes raw commands to the operating system shell if enabled.

- 🔑 **Real-World Analogy**: *Opening a terminal command prompt window.*

### 86. `hermclaw/tools/system_info.py`

- 💡 **What is this file?** Hardware and system health tool.

- 🎯 **Why do we need it?** Checks how much RAM, CPU, disk space, or battery your computer has left.

- 🛠️ **How does it work?** Queries system hardware using `psutil` library.

- 🔑 **Real-World Analogy**: *The Task Manager or Activity Monitor on your computer.*

### 87. `hermclaw/tools/task_tools.py`

- 💡 **What is this file?** Todo list and Kanban board tools.

- 🎯 **Why do we need it?** Provides structured task lists and Trello-style boards so the AI can organize work.

- 🛠️ **How does it work?** Stores cards, columns, and todo items in SQLite.

- 🔑 **Real-World Analogy**: *Sticky notes organized on a Kanban whiteboard.*

### 88. `hermclaw/tools/tts_tool.py`

- 💡 **What is this file?** Text-To-Speech voice output tool.

- 🎯 **Why do we need it?** Allows the AI to speak answers out loud using high-quality voices.

- 🛠️ **How does it work?** Uses Microsoft Edge TTS engine (`edge-tts`) or native OS speech engines.

- 🔑 **Real-World Analogy**: *A speaker playing spoken audio.*

### 89. `hermclaw/tools/virtual_pet.py`

- 💡 **What is this file?** Clawbert the virtual pet companion.

- 🎯 **Why do we need it?** Adds a fun gamification companion to your coding environment.

- 🛠️ **How does it work?** Manages pet stats (hunger, mood, evolution) and draws ASCII art crabs.

- 🔑 **Real-World Analogy**: *A Tamagotchi virtual pet living inside your terminal.*

### 90. `hermclaw/tools/web_tools.py`

- 💡 **What is this file?** DuckDuckGo web search and webpage reader tools.

- 🎯 **Why do we need it?** Allows the AI to search the internet for current information without needing expensive search API keys.

- 🛠️ **How does it work?** Searches DuckDuckGo and converts webpage HTML into readable markdown text.

- 🔑 **Real-World Analogy**: *Using a search engine and reading web articles.*

### 91. `hermclaw/tools/backends/__init__.py`

- 💡 **What is this file?** Tool backends initializer.

- 🎯 **Why do we need it?** Marks execution backends package root.

- 🛠️ **How does it work?** Package header file.

- 🔑 **Real-World Analogy**: *Execution engine options menu.*

### 92. `hermclaw/tools/backends/docker.py`

- 💡 **What is this file?** The Docker container sandbox backend.

- 🎯 **Why do we need it?** Runs untrusted code inside a disposable isolated container so it can't harm your real computer.

- 🛠️ **How does it work?** Spawns temporary Docker containers with network access disabled by default.

- 🔑 **Real-World Analogy**: *A blast-proof glass isolation chamber.*

### 93. `hermclaw/tools/backends/local.py`

- 💡 **What is this file?** The local command runner backend.

- 🎯 **Why do we need it?** Runs commands directly on your computer inside your workspace folder.

- 🛠️ **How does it work?** Uses Python standard subprocess calls in your local environment.

- 🔑 **Real-World Analogy**: *Running commands in your regular terminal window.*

### 94. `hermclaw/tools/backends/ssh.py`

- 💡 **What is this file?** The remote SSH server backend.

- 🎯 **Why do we need it?** Runs commands on a remote server across the internet.

- 🛠️ **How does it work?** Establishes secure SSH tunnel connections to execute commands.

- 🔑 **Real-World Analogy**: *Using a remote desktop connection to control a server in another city.*

### 95. `hermclaw/tools/backends/stubs.py`

- 💡 **What is this file?** Placeholders for future cloud backends.

- 🎯 **Why do we need it?** Reserves spots for Singularity, Modal, and Daytona backends.

- 🛠️ **How does it work?** Raises clear 'Not Implemented Yet' messages if called.

- 🔑 **Real-World Analogy**: *A 'Under Construction' sign on a future doorway.*

## Helper Scripts (2 files)

### 96. `scripts/__init__.py`

- 💡 **What is this file?** Scripts folder initializer.

- 🎯 **Why do we need it?** Marks scripts package root.

- 🛠️ **How does it work?** Package header file.

- 🔑 **Real-World Analogy**: *Utility folder label.*

### 97. `scripts/list_config_fields.py`

- 💡 **What is this file?** Developer helper script for settings inspection.

- 🎯 **Why do we need it?** Lists all valid settings paths to make sure documentation is never missing fields.

- 🛠️ **How does it work?** Inspects Pydantic model schemas.

- 🔑 **Real-World Analogy**: *An inspector checking that every room in a building is on the floor plan.*

## Testing Suite & Quality Verification (22 files)

### 98. `tests/__init__.py`

- 💡 **What is this file?** Tests folder initializer.

- 🎯 **Why do we need it?** Marks test suite root.

- 🛠️ **How does it work?** Package header file.

- 🔑 **Real-World Analogy**: *Testing department door sign.*

### 99. `tests/conftest.py`

- 💡 **What is this file?** Master test suite configuration and internet socket blocker.

- 🎯 **Why do we need it?** CRITICAL TEST SAFETY RULE! Stops unit tests from secretly calling internet servers or spending real money.

- 🛠️ **How does it work?** Blocks network sockets automatically during test runs unless marked with `@pytest.mark.live`.

- 🔑 **Real-World Analogy**: *Unplugging the internet cable while testing software locally.*

### 100. `tests/test_cli.py`

- 💡 **What is this file?** CLI command unit tests.

- 🎯 **Why do we need it?** Verifies that `hermclaw` terminal commands work without crashing.

- 🛠️ **How does it work?** Executes CLI commands in test environments.

- 🔑 **Real-World Analogy**: *Testing every button on a remote control.*

### 101. `tests/test_config.py`

- 💡 **What is this file?** Configuration system unit tests.

- 🎯 **Why do we need it?** Verifies that bad settings are caught and good settings load properly.

- 🛠️ **How does it work?** Passes valid and broken YAML files to config loaders.

- 🔑 **Real-World Analogy**: *Testing a coin sorter with real coins and fake tokens.*

### 102. `tests/test_config_reference_coverage.py`

- 💡 **What is this file?** Documentation accuracy enforcer test.

- 🎯 **Why do we need it?** Guarantees that `docs/CONFIG_REFERENCE.md` documents EVERY single config field with 0 missed settings.

- 🛠️ **How does it work?** Compares Pydantic code model fields against documentation tables.

- 🔑 **Real-World Analogy**: *A proofreader checking that every word in a contract is defined in the glossary.*

### 103. `tests/test_conftest_guards.py`

- 💡 **What is this file?** Unit tests for test suite network blockers.

- 🎯 **Why do we need it?** Ensures our socket blocker in `tests/conftest.py` is actually blocking real network calls.

- 🛠️ **How does it work?** Tries opening a socket and verifies that it is intercepted.

- 🔑 **Real-World Analogy**: *Testing the circuit breaker by intentionally causing a test short circuit.*

### 104. `tests/test_gateway.py`

- 💡 **What is this file?** Unit tests for Gateway server.

- 🎯 **Why do we need it?** Verifies HTTP endpoints (`/status`, `/health`, `/reload`) and WebSocket chat routes.

- 🛠️ **How does it work?** Sends test HTTP requests to FastAPI in-memory server.

- 🔑 **Real-World Analogy**: *Testing an intercom system in an empty building.*

### 105. `tests/test_mcp_client.py`

- 💡 **What is this file?** Unit tests for MCP client.

- 🎯 **Why do we need it?** Verifies tool discovery and remote tool execution via MCP.

- 🛠️ **How does it work?** Connects to `mcp_test_server.py` and runs tools.

- 🔑 **Real-World Analogy**: *Testing a USB hub with a test flash drive.*

### 106. `tests/test_scheduler.py`

- 💡 **What is this file?** Unit tests for background task scheduler.

- 🎯 **Why do we need it?** Ensures timers, heartbeats, and cron jobs run on schedule.

- 🛠️ **How does it work?** Executes mock scheduler jobs and verifies timing.

- 🔑 **Real-World Analogy**: *Testing an alarm clock to make sure it rings at 7:00 AM.*

### 107. `tests/test_skills.py`

- 💡 **What is this file?** Unit tests for `agentskills.io` skill loading.

- 🎯 **Why do we need it?** Verifies skill validation, frontmatter parsing, and prompt injection protection.

- 🛠️ **How does it work?** Parses sample skill folders and checks output results.

- 🔑 **Real-World Analogy**: *Checking lesson plans to make sure they follow school curriculum guidelines.*

### 108. `tests/brain/__init__.py`

- 💡 **What is this file?** Brain tests initializer.

- 🎯 **Why do we need it?** Marks brain tests subfolder.

- 🛠️ **How does it work?** Package header file.

- 🔑 **Real-World Analogy**: *Brain testing lab sign.*

### 109. `tests/brain/conftest.py`

- 💡 **What is this file?** Pytest setup for brain tests.

- 🎯 **Why do we need it?** Creates temporary test databases so brain tests don't mess up real user data.

- 🛠️ **How does it work?** Defines `wired_profile` fixture.

- 🔑 **Real-World Analogy**: *A clean test lab room set up before an experiment.*

### 110. `tests/brain/test_agent_loop.py`

- 💡 **What is this file?** Unit tests for the AI agent thinking loop.

- 🎯 **Why do we need it?** Verifies that the agent loop handles tool calls and errors properly.

- 🛠️ **How does it work?** Runs synthetic tests against `HermclawAgent`.

- 🔑 **Real-World Analogy**: *Testing a car engine on a test bench.*

### 111. `tests/brain/test_compressor.py`

- 💡 **What is this file?** Unit tests for context compression.

- 🎯 **Why do we need it?** Verifies that long conversations are summarized properly.

- 🛠️ **How does it work?** Simulates long conversations and checks compression triggers.

- 🔑 **Real-World Analogy**: *Testing a trash compactor to make sure it squashes boxes properly.*

### 112. `tests/brain/test_memory_store.py`

- 💡 **What is this file?** Unit tests for SQLite memory database.

- 🎯 **Why do we need it?** Ensures memory saving and searching work accurately and fast.

- 🛠️ **How does it work?** Inserts test messages and runs FTS5 searches.

- 🔑 **Real-World Analogy**: *Testing a filing cabinet lock and search drawer.*

### 113. `tests/brain/test_profiles.py`

- 💡 **What is this file?** Unit tests for profile folder isolation.

- 🎯 **Why do we need it?** Verifies that two different user profiles never leak data into each other.

- 🛠️ **How does it work?** Creates two test profiles and asserts strict boundary separation.

- 🔑 **Real-World Analogy**: *Testing soundproof walls between two separate apartments.*

### 114. `tests/brain/test_reflection_and_skill_growth.py`

- 💡 **What is this file?** Unit tests for reflection and automatic skill creation.

- 🎯 **Why do we need it?** Ensures the AI correctly distills facts and generates draft skills.

- 🛠️ **How does it work?** Runs test reflection cycles on sample conversation transcripts.

- 🔑 **Real-World Analogy**: *Testing a study technique to ensure key notes are remembered.*

### 115. `tests/contracts/__init__.py`

- 💡 **What is this file?** Contracts test package initializer.

- 🎯 **Why do we need it?** Marks contract tests folder.

- 🛠️ **How does it work?** Package header file.

- 🔑 **Real-World Analogy**: *Contract testing sign.*

### 116. `tests/contracts/test_channel_adapter.py`

- 💡 **What is this file?** Universal lifecycle test for all chat channels.

- 🎯 **Why do we need it?** Ensures Telegram, Discord, Slack, and Web channels all follow the exact same rules.

- 🛠️ **How does it work?** Runs standard start/receive/send/stop tests against every channel adapter using fake network connections.

- 🔑 **Real-World Analogy**: *Testing every lightbulb socket with a test meter to make sure they all output 120V.*

### 117. `tests/fixtures/mcp_test_server.py`

- 💡 **What is this file?** A miniature fake Model Context Protocol server for testing.

- 🎯 **Why do we need it?** Allows testing MCP client features locally without needing real external MCP servers.

- 🛠️ **How does it work?** Runs a tiny subprocess over stdio.

- 🔑 **Real-World Analogy**: *A mini toy server used to test connection plugs.*

### 118. `tests/security/__init__.py`

- 💡 **What is this file?** Security tests package initializer.

- 🎯 **Why do we need it?** Marks security test folder.

- 🛠️ **How does it work?** Package header file.

- 🔑 **Real-World Analogy**: *Security lab sign.*

### 119. `tests/security/test_tool_security.py`

- 💡 **What is this file?** Security unit tests.

- 🎯 **Why do we need it?** Ensures dangerous commands are blocked and passwords are redacted.

- 🛠️ **How does it work?** Tries running dangerous commands like `rm -rf /` and asserts that Hermclaw blocks them.

- 🔑 **Real-World Analogy**: *A crash test trying to break security gates to ensure they hold.*
