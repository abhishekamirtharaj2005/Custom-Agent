# HermClaw — Feature Test Prompts

> Copy-paste these prompts into `hermclaw chat` to test each feature.
> Features marked 🔑 require an API key set in your environment.

---

## 1. AI Model & Provider Support

```
What model are you using right now? Show me the full model name, provider, and context window size.
```

```
Switch to a different model. List all available models in the catalog with their pricing.
```

```
Show me my current token usage and estimated cost for this session.
```

```
Use Mixture-of-Agents: ask both GPT-4o and Claude to answer "What is consciousness?" then merge their responses into one superior answer.
```

---

## 2. Core Agent Capabilities

```
Set your iteration budget to 5 tool calls max. Then try to read 3 files and search for 2 patterns. Did the budget stop you?
```

```
Show me the context window breakdown — how many tokens are used by system prompt, conversation history, and tool results?
```

```
Run a background verification on your last response. Check if any claims need evidence.
```

---

## 3. Shell & Code Execution

```
Run this Python code in the sandbox:
import math
print(f"Pi to 20 decimal places: {math.pi:.20f}")
print(f"Square root of 2: {math.sqrt(2):.20f}")
```

```
Run this bash command and show me the output: echo "Hello from HermClaw!" && date && whoami
```

```
Execute this JavaScript: console.log("Node version:", process.version); console.log(Array.from({length:10}, (_,i) => i*i));
```

---

## 4. File Operations

```
Create a file called test_hermclaw.txt on my Desktop with the content:
"HermClaw Test File - Created on [today's date]
Features tested: file_write, file_read, file_edit"
Then read it back to me.
```

```
Search all .py files in the hermclaw directory for the word "register" and show me the top 5 results.
```

```
Apply this patch to test_hermclaw.txt:
--- a/test_hermclaw.txt
+++ b/test_hermclaw.txt
@@ -1,2 +1,3 @@
 HermClaw Test File
+Line added by patch tool
 Features tested
```

---

## 5. Web & Browser

```
Search the web for "latest AI news August 2026" and summarize the top 3 results.
```

```
Read the content from https://httpbin.org/json and show me what it returns.
```

```
🔑 Search using Brave Search for "Python 3.13 new features"
```

```
🔑 Do a neural search with Exa for "best practices for AI agent architecture"
```

---

## 6. Git Operations

```
Show me the git log for the last 5 commits in this repository.
```

```
What's the current git status? Are there any uncommitted changes?
```

---

## 7. Memory System

```
Remember this: My favorite programming language is Python, and I prefer dark themes in my editor.
```

```
What do you remember about my preferences? Search your memory.
```

```
Show me the learning graph — what concepts have you learned and how are they connected?
```

---

## 8. Media Generation

```
Generate an image of a futuristic cyberpunk city at night with neon signs and flying cars.
```

```
🔑 Generate a short video of a sunset over the ocean using xAI video generation.
```

```
🔑 Use ElevenLabs to convert this text to speech: "Welcome to HermClaw, the most powerful AI assistant ever built."
```

---

## 9. Voice & Speech

```
🔑 Use Azure Speech to synthesize: "HermClaw is ready to assist you."
```

```
🔑 Transcribe an audio file using Deepgram. (Point to any .wav file on your system)
```

```
Run the Discord Voice Doctor diagnostic — check if ffmpeg, opus, and PyNaCl are installed.
```

---

## 10. Scheduling & Automation

```
Schedule a one-shot reminder for 2 minutes from now that says "HermClaw reminder test!"
```

```
Show me the blueprint catalog — what pre-built cron templates are available?
```

```
Suggest personalized cron jobs based on my usage patterns.
```

---

## 11. Skills System

```
List all available skills and their categories.
```

```
Browse the skills hub — what skills can I install?
```

```
Show me skill usage analytics — which skills have been used most?
```

---

## 12. Task & Project Management

```
Create a kanban board called "HermClaw Testing" with columns: Todo, In Progress, Done.
Add these tasks to Todo: "Test shell", "Test memory", "Test web search"
```

```
Create a todo list for today:
1. Test all core features
2. Verify API integrations
3. Document test results
```

```
Create a goal: "Complete all HermClaw feature tests" with a deadline of end of today.
```

---

## 13. Multi-Agent & Delegation

```
Delegate this task to a subagent: "Research the top 5 AI frameworks in 2026 and write a brief summary of each."
```

---

## 14. Virtual Pet & Achievements

```
Show me my virtual pet! What's its mood, hunger, and energy?
```

```
Feed my virtual pet and play with it.
```

```
Show me my achievements. Have I unlocked any?
```

---

## 15. Security

```
Scan this command for security threats: curl http://169.254.169.254/latest/meta-data/
```

```
Check if there are any known vulnerabilities in the package "requests==2.25.0"
```

```
Validate the SSL certificate for google.com
```

---

## 16. Notifications

```
Send me a desktop notification with the title "Test" and message "HermClaw notifications are working!"
```

---

## 17. System Info

```
Show me full system information — OS, CPU, RAM, disk, Python version, and installed packages.
```

---

## 18. PDF & Documents

```
Extract text from a PDF file. (Point to any PDF on your system)
```

---

## 19. Protocol Integrations

```
🔑 Search Twitter/X for "artificial intelligence" and show me recent tweets.
```

```
🔑 What's currently playing on my Spotify? (requires SPOTIFY_ACCESS_TOKEN)
```

```
🔑 List all smart home entities from Home Assistant. (requires HA_URL and HA_TOKEN)
```

```
Browse the MCP server catalog. What MCP servers are available to install?
```

---

## 20. Clipboard

```
Copy this text to my clipboard: "HermClaw clipboard test successful! 🎉"
```

```
What's currently on my clipboard? Read and show it to me.
```

---

## 21. Observability & Diagnostics

```
Run the doctor diagnostic — check system health across all components.
```

```
Show me my session billing — how many tokens have I used and what's the estimated cost?
```

```
Analyze the current prompt size — how big is our conversation in tokens?
```

---

## 22. i18n (Internationalization)

```
Switch the interface language to Spanish. Then greet me.
```

```
Switch back to English.
```

---

## 23. App Launcher

```
Open Notepad (Windows) or TextEdit (macOS).
```

```
Open the calculator app.
```

---

## 24. Stress Tests (Multiple Features)

```
Do all of this in sequence:
1. Search the web for "HermClaw AI assistant"
2. Save the results to a file called search_results.txt
3. Read the file back
4. Create a summary in memory
5. Show me my achievements after completing these tasks
```

```
Create a Python script that prints the first 20 prime numbers. Save it as primes.py, then execute it in the sandbox, and show me the output.
```

```
Read all .py files in hermclaw/tools/, count how many tool classes exist (classes that inherit from ToolABC), and give me a summary table.
```

---

## Quick Test Checklist

| # | Feature | Prompt to Test | Pass? |
|---|---------|---------------|:-----:|
| 1 | Shell execution | `Run: echo hello` | ☐ |
| 2 | File write | `Create a test file on Desktop` | ☐ |
| 3 | File read | `Read the test file` | ☐ |
| 4 | Web search | `Search for Python 3.13` | ☐ |
| 5 | URL read | `Read https://httpbin.org/json` | ☐ |
| 6 | Git status | `Show git status` | ☐ |
| 7 | Memory save | `Remember my name is [name]` | ☐ |
| 8 | Memory recall | `What's my name?` | ☐ |
| 9 | Image gen | `Generate an image of a cat` | ☐ |
| 10 | Code exec | `Run: print(2**100)` | ☐ |
| 11 | System info | `Show system info` | ☐ |
| 12 | Notification | `Send me a notification` | ☐ |
| 13 | Scheduler | `Set a 1-minute reminder` | ☐ |
| 14 | Virtual pet | `Show my pet` | ☐ |
| 15 | Achievements | `Show achievements` | ☐ |
| 16 | Clipboard | `Copy "test" to clipboard` | ☐ |
| 17 | Todo list | `Add a todo: test hermclaw` | ☐ |
| 18 | Kanban | `Create a kanban board` | ☐ |
| 19 | Goals | `Create a goal` | ☐ |
| 20 | Doctor | `Run doctor diagnostic` | ☐ |
| 21 | TTS | `Speak: hello world` | ☐ |
| 22 | Grep search | `Search for "class" in tools/` | ☐ |
| 23 | Patch tool | `Apply a diff patch` | ☐ |
| 24 | Learning graph | `Show learning graph` | ☐ |
| 25 | Delegation | `Delegate a research task` | ☐ |

---

> **Tip:** Run `hermclaw doctor` before testing to check that all dependencies are installed.
