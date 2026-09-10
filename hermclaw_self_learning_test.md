# HermClaw — Self-Learning Test Prompts

> Paste these into `hermclaw chat` **in order**. Each step builds on the previous one.

---

## Phase 1: Learning Graph — Teaching Concepts

### Step 1: Teach the agent a concept
```
Learn this concept: "Python" is a programming language used for AI, web development, and scripting. Category: programming.
```

### Step 2: Teach a related concept
```
Learn this concept: "FastAPI" is a Python web framework for building APIs. Category: programming.
```

### Step 3: Connect them
```
Connect these in your learning graph: "FastAPI" depends_on "Python"
```

### Step 4: Teach more concepts and connect them
```
Learn these concepts and connect them:
1. "Docker" - containerization tool. Category: devops.
2. "Kubernetes" - container orchestration. Category: devops.
3. Connect: Kubernetes depends_on Docker
4. Connect: Docker related_to Python
```

### Step 5: Visualize the graph
```
Show me your learning graph. Visualize all the concepts you've learned so far.
```

### Step 6: Explore a specific concept
```
Explore the concept "Python" in your learning graph. Show all its connections.
```

### Step 7: Check stats
```
Show me your learning graph stats. How many concepts and relationships do you have?
```

### Step 8: Search the graph
```
Search your learning graph for anything related to "programming"
```

---

## Phase 2: Confidence Growth — Verify Learning Strengthens

### Step 9: Repeat a concept (confidence should increase)
```
Learn this again: "Python" is a programming language. It's the most popular language for AI.
```

### Step 10: Check if confidence grew
```
Explore "Python" in your learning graph. Has its confidence score increased from the first time?
```

### Step 11: Repeat multiple times and verify
```
Learn "Python" again - used for data science and machine learning.
Now show me the learning graph stats. Python's usage_count should be 3+ now.
```

---

## Phase 3: Memory — Persistent Recall

### Step 12: Save facts to memory
```
Remember this: I am working on a project called "HermClaw" which is an AI agent. My preferred coding language is Python and I use VS Code.
```

### Step 13: Test recall
```
What project am I working on? What's my preferred language?
```

### Step 14: Save more context
```
Remember: My deployment target is Docker containers on a Linux server. I prefer YAML for configuration files.
```

### Step 15: Test cross-session recall
> **Exit hermclaw chat (Ctrl+C), then start it again with `hermclaw chat`**
```
What do you remember about me and my project?
```

---

## Phase 4: Skill Growth — Auto-Generated Skills

### Step 16: Do a repeated procedure (1st time)
```
Help me create a Python FastAPI project: create a file called app.py with a basic FastAPI hello world endpoint with health check.
```

### Step 17: Do the same procedure again (2nd time)
```
Help me create another Python FastAPI project: create a file called api.py with a basic FastAPI hello world endpoint with health check.
```

### Step 18: Trigger reflection
```
22
```

### Step 19: Check if a skill was auto-generated
```
List all available skills. Are there any auto-generated ones?
```

---

## Phase 5: Combined Test — Full Self-Learning Loop

### Step 20: Complex learning chain
```
I want you to learn and remember everything about this workflow:
1. We write Python code using FastAPI
2. We test it locally with pytest
3. We containerize with Docker
4. We deploy to Kubernetes
5. We monitor with Prometheus

Learn each tool as a concept, connect them in order (each depends_on or prerequisite_for the next), and remember this as my standard deployment workflow.
```

### Step 21: Verify the full chain
```
Visualize my deployment workflow in the learning graph. Show all 5 tools and their connections.
```

### Step 22: Test applied learning
```
I need to deploy a new service. Based on what you've learned about my workflow, what steps should I follow?
```

---

## Verification Checklist

| # | What to Check | How to Verify | Pass? |
|---|--------------|---------------|:-----:|
| 1 | Concepts are stored | `Show learning graph stats` → concepts > 0 | ☐ |
| 2 | Relationships work | `Explore "Python"` → shows connections | ☐ |
| 3 | Confidence grows | Repeat a concept → confidence increases from 0.5 | ☐ |
| 4 | Usage count increments | Repeat a concept → usage_count goes up | ☐ |
| 5 | Graph visualization | `Visualize learning graph` → shows ASCII graph | ☐ |
| 6 | Search works | `Search for "programming"` → finds results | ☐ |
| 7 | Memory saves facts | `Remember X` → confirmed saved | ☐ |
| 8 | Memory recalls facts | Ask about saved facts → correct answer | ☐ |
| 9 | Cross-session memory | Restart chat → still remembers | ☐ |
| 10 | Skill auto-generation | Repeat a procedure → new skill created | ☐ |

---

> **Key insight:** Self-learning in HermClaw is NOT model fine-tuning. It builds a persistent knowledge base (graph + memory + skills) that gets injected into context each session.
