# 🧪 Hermclaw Feature Test Guide

> Copy-paste each prompt into `hermclaw chat` to test features one by one.
> Mark each test ✅ or ❌ as you go.

---

## 🔧 Pre-flight

Before testing, make sure:
```bash
hermclaw chat    # should start without errors
```

---

## 1. 💬 Basic Chat & Response

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 1.1 | Basic response | `hello, what can you do?` | Lists capabilities |
| 1.2 | Follow-up context | `tell me a joke` then `explain why it's funny` | References the joke |
| 1.3 | Long response | `write a 500-word essay about AI safety` | Full essay rendered |

---

## 2. 🖥️ Shell / Terminal Commands

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 2.1 | Basic shell | `list all files in my Desktop folder` | Runs `dir` or `ls`, shows files |
| 2.2 | System command | `what's my IP address?` | Runs `ipconfig` / `curl ifconfig.me` |
| 2.3 | Multi-step shell | `create a folder called "hermtest" on my Desktop, then create a file inside it called hello.txt with the text "hermclaw works"` | Creates folder + file |
| 2.4 | Shell output parsing | `how much free disk space do I have?` | Parses disk info |

---

## 3. ℹ️ System Info

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 3.1 | Full system info | `give me my full system information` | CPU, RAM, OS, disk usage |
| 3.2 | Specific info | `what's my CPU and how much RAM do I have?` | Targeted response |
| 3.3 | Running processes | `what are the top 5 processes using the most memory?` | Process list |

---

## 4. 📁 File Operations

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 4.1 | Read file | `read the contents of C:\Users\giant\.hermclaw\hermclaw.yaml` | Shows config |
| 4.2 | Write file | `create a file at C:\Users\giant\Desktop\hermtest\test.py with a Python hello world program` | Creates file |
| 4.3 | Edit file | `add a comment at the top of C:\Users\giant\Desktop\hermtest\test.py saying "Created by Hermclaw"` | Edits file |
| 4.4 | List directory | `list all files in C:\Users\giant\Desktop` | Directory listing |
| 4.5 | Search files | `search for files containing "hermclaw" in C:\Users\giant\Desktop\hermtest` | Grep results |

---

## 5. 🌐 Web Search & URL Reading

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 5.1 | Web search | `search the web for "latest news about AI agents 2025"` | Search results |
| 5.2 | Read URL | `read the contents of https://example.com` | Page content |
| 5.3 | Summarize website | `summarize this webpage: https://en.wikipedia.org/wiki/Artificial_intelligence` | Summary |

---

## 6. 🐍 Code Execution

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 6.1 | Python exec | `run this Python code: print(sum(range(1, 101)))` | Output: 5050 |
| 6.2 | Code with logic | `write and run a Python script that generates the first 20 fibonacci numbers` | Fibonacci output |
| 6.3 | Error handling | `run this Python code: print(1/0)` | Shows ZeroDivisionError |

---

## 7. 📋 Clipboard

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 7.1 | Copy to clipboard | `copy this text to my clipboard: "Hello from Hermclaw!"` | Text copied |
| 7.2 | Read clipboard | `what's currently in my clipboard?` | Shows clipboard content |

---

## 8. 🔀 Git Operations

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 8.1 | Git status | `show me the git status of C:\VS CODE\Hermclaw\hermclaw` | Git status output |
| 8.2 | Git log | `show me the last 5 git commits in C:\VS CODE\Hermclaw\hermclaw` | Commit history |
| 8.3 | Git diff | `show me what changed in the last commit in C:\VS CODE\Hermclaw\hermclaw` | Diff output |

---

## 9. 📝 Task Management (Kanban)

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 9.1 | Create board | `create a kanban board called "My Project"` | Board created |
| 9.2 | Add tasks | `add these tasks to "My Project": "Design UI", "Build API", "Write tests"` | Tasks added |
| 9.3 | Move task | `move "Design UI" to "in_progress" on "My Project"` | Task moved |
| 9.4 | View board | `show me my kanban board "My Project"` | Board displayed |

---

## 10. ✅ Todo List

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 10.1 | Add todo | `add a todo: "Buy groceries"` | Todo added |
| 10.2 | List todos | `show my todo list` | List displayed |
| 10.3 | Complete todo | `mark "Buy groceries" as done` | Marked complete |

---

## 11. 🎯 Goals

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 11.1 | Create goal | `create a goal: "Learn Rust programming" with milestones "Read the book", "Build a CLI tool", "Contribute to open source"` | Goal created |
| 11.2 | View goals | `show my goals` | Goal list |
| 11.3 | Update progress | `mark the first milestone of "Learn Rust programming" as complete` | Progress updated |

---

## 12. 🧠 Persistent Memory

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 12.1 | Store fact | `my favorite programming language is Python and my name is Abhishek` | Acknowledges |
| 12.2 | Recall (same session) | `what is my name and favorite language?` | "Abhishek" + "Python" |
| 12.3 | **Recall (NEW session)** | *Exit chat (Ctrl+C), restart `hermclaw chat`*, then ask: `what is my name?` | Should recall "Abhishek" |

---

## 13. 🔍 Session Search

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 13.1 | Search history | `search our conversation for "python"` | Finds messages mentioning python |

---

## 14. 📊 Model Info

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 14.1 | Current model | `what model are you using right now?` | gemma4:12b |
| 14.2 | Model catalog | Run in terminal: `hermclaw models` | Model table |

---

## 15. 🚀 App Launcher

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 15.1 | Open app | `open Notepad` | Notepad launches |
| 15.2 | Open URL | `open https://github.com in my browser` | Browser opens |
| 15.3 | List apps | `what apps can you launch?` | App categories listed |

---

## 16. 🔔 Notifications

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 16.1 | Desktop notification | `send me a desktop notification saying "Test from Hermclaw"` | Toast notification |
| 16.2 | Reminder (if supported) | `remind me in 1 minute to drink water` | Notification after 1 min |

---

## 17. ⏰ Scheduler

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 17.1 | Create job | `schedule a job to remind me to stretch every 30 minutes` | Job scheduled |
| 17.2 | List jobs | `show my scheduled jobs` | Job list |
| 17.3 | Cancel job | `cancel the stretch reminder` | Job removed |

---

## 18. 🏆 Achievements & Gamification

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 18.1 | View achievements | `show my achievements` | Achievement list/stats |
| 18.2 | Check progress | `how many commands have I used so far?` | Usage stats |

---

## 19. 🐾 Virtual Pet

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 19.1 | Check pet | `how is my virtual pet doing?` | Pet status with emoji |
| 19.2 | Feed pet | `feed my pet` | Pet fed, happiness up |
| 19.3 | Play with pet | `play with my pet` | Pet played, stats change |

---

## 20. 🗣️ Text-to-Speech

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 20.1 | Generate speech | `convert this text to speech: "Hello, I am Hermclaw, your personal AI agent"` | Audio file created |
| 20.2 | List voices | `what TTS voices are available?` | Voice list |

---

## 21. 📄 PDF (if installed)

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 21.1 | Read PDF | `read the contents of [path-to-any-pdf-file]` | PDF text extracted |
| 21.2 | Summarize PDF | `summarize [path-to-any-pdf-file]` | Summary of PDF |

> Skip if no PDF files available.

---

## 22. 🩺 Doctor & Diagnostics

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 22.1 | System health | Run in terminal: `hermclaw doctor` | Health report |
| 22.2 | JSON output | Run in terminal: `hermclaw doctor --json` | Machine-readable JSON |

---

## 23. 🌍 Internationalization

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 23.1 | Hindi | `mujhe Hindi mein jawab do: aaj ka din kaisa hai?` | Hindi response |
| 23.2 | Tamil | `enakku Tamil la pathil kudu: nee enna seyya mudiyum?` | Tamil response |

---

## 24. 🔒 Security

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 24.1 | Dangerous command | `run: rm -rf /` or `format C:` | Should execute if shell_enabled (no guardrails as designed) |
| 24.2 | Audit log | Check `~/.hermclaw/profiles/default/` for audit entries | Logged commands |

---

## 25. ⚙️ Configuration

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 25.1 | View config | `show me my current hermclaw configuration` | Config displayed |
| 25.2 | Re-run setup | Run in terminal: `hermclaw setup` | Setup wizard starts |

---

## 26. 🔄 Multi-turn Stress Test

| # | Test | Prompt | Expected |
|---|------|--------|----------|
| 26.1 | Complex chain | `create a Python file that calculates prime numbers up to 1000, save it to my Desktop, run it, and tell me how many primes there are` | File created → executed → count reported |
| 26.2 | Research task | `search the web for "Python 3.13 new features", summarize the top 3 results, and save the summary to a file on my Desktop` | Search → summarize → file saved |

---

## 📊 Test Summary

| Category | Tests | Passed | Failed |
|----------|:-----:|:------:|:------:|
| Basic Chat | 3 | | |
| Shell | 4 | | |
| System Info | 3 | | |
| File Ops | 5 | | |
| Web | 3 | | |
| Code Exec | 3 | | |
| Clipboard | 2 | | |
| Git | 3 | | |
| Kanban | 4 | | |
| Todo | 3 | | |
| Goals | 3 | | |
| Memory | 3 | | |
| Session Search | 1 | | |
| Model Info | 2 | | |
| App Launcher | 3 | | |
| Notifications | 2 | | |
| Scheduler | 3 | | |
| Achievements | 2 | | |
| Virtual Pet | 3 | | |
| TTS | 2 | | |
| PDF | 2 | | |
| Doctor | 2 | | |
| i18n | 2 | | |
| Security | 2 | | |
| Config | 2 | | |
| Stress Tests | 2 | | |
| **TOTAL** | **68** | | |

---

> 💡 **Tip:** After running all tests, restart `hermclaw chat` and ask `what is my name?` — this is the ultimate memory persistence test.
