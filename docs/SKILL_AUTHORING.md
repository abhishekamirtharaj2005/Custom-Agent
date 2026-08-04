# Authoring Skills

Hermclaw uses the [agentskills.io](https://agentskills.io) open standard for skills. This is the same format both OpenClaw and Hermes Agent already used, so this document describes how Hermclaw specifically loads, validates, and surfaces skills -- for the format itself, agentskills.io is the source of truth.

## Anatomy of a skill

A skill is a directory. The directory name **is** the skill's name.

```
my-skill-name/
  SKILL.md        required
  scripts/        optional -- executable helpers the skill's instructions reference
  references/     optional -- longer documents the skill points to on demand
  assets/         optional -- templates, images, anything else the skill needs
```

`SKILL.md` is YAML frontmatter followed by Markdown instructions:

```markdown
---
name: my-skill-name
description: Does the specific thing this skill does. Use when the user asks for that specific thing.
license: MIT
compatibility: Requires the shell tool to be enabled.
allowed-tools: shell read_file
metadata:
  custom_key: any value you want here
---

# My Skill Name

Step-by-step instructions for the agent, in plain Markdown. Reference
files under scripts/ or references/ as needed -- Hermclaw doesn't load
their contents automatically; the agent reads them itself if your
instructions point it there.
```

### Frontmatter fields

| Field | Required | Rules |
|---|---|---|
| `name` | yes | Lowercase letters, numbers, and hyphens only. No leading, trailing, or consecutive hyphens. 64 characters max. **Must exactly match the directory name**, or the skill fails validation. |
| `description` | yes | Non-empty, 1024 characters max. Should describe *what* the skill does and *when* to use it -- this is the only part of the skill loaded into the agent's context by default (see "Progressive disclosure" below), so it's doing a lot of work. |
| `license` | no | Free text. |
| `compatibility` | no | Free text, 500 characters max. Note any prerequisites here (a specific tool needing to be enabled, for instance). |
| `allowed-tools` | no | Space-separated list of tool names this skill is pre-approved to use without an additional approval prompt, when the skill is active. |
| `metadata` | no | Arbitrary key-value mapping. Hermclaw uses `metadata.auto_generated: true` to mark skills it drafted itself (see below) -- don't set this by hand on a skill you wrote. |

One rule worth calling out explicitly: **frontmatter may not contain a literal `<` or `>` character anywhere.** This is the agentskills.io standard's own defense against a skill description trying to smuggle instructions to the agent via HTML/XML-like syntax -- Hermclaw rejects the whole skill, unparsed, if either character appears in the frontmatter block. If you need to describe something like "less than" or "greater than," spell it out instead.

## Progressive disclosure

Hermclaw loads skills in three tiers, and understanding this shapes how you should write `description`:

1. **Always loaded:** every skill's `name` and `description` go into the system prompt at startup -- roughly 100 tokens each. This is the *only* information the agent has when deciding whether a skill might be relevant.
2. **Loaded on activation:** the full `SKILL.md` body (everything after the frontmatter) loads only once the agent decides, from the description alone, that it wants to look at this skill.
3. **Loaded on demand, by the skill's own instructions:** files under `references/` are never read automatically by Hermclaw -- if your `SKILL.md` body tells the agent to consult a reference file for more detail, the agent reads it itself as a normal tool call, at that point.

This means a vague `description` (`"Helps with reports"`) gives the agent nothing to go on when deciding relevance, while an overlong one wastes context on every single turn regardless of whether the skill is ever used. Aim for one or two sentences that name the specific task and the specific trigger.

## Where skills live

- `skills.directory` (default `~/.hermclaw/profiles/<profile>/skills`) -- this profile's own skills, read-write.
- `skills.extra_directories` -- additional folders Hermclaw also reads from, meant for shared/team skill libraries you don't want duplicated per profile. Treated as read-only from Hermclaw's perspective; it will never write here.

Run `hermclaw skills list` to see everything currently loaded for a profile, and `hermclaw skills validate` to run the full checklist above against every skill directory and get a clear pass/fail with reasons.

## Skills Hermclaw writes for you

Separately from anything you author by hand, Hermclaw's reflection loop (`hermclaw reflect`, or automatic every `brain.reflection.trigger_every_n_turns`) watches for procedures you've asked it to repeat three or more times, and drafts a skill for the underlying procedure automatically. These are marked `metadata.auto_generated: true` and start life in the same `skills.directory` as anything you'd write yourself.

A few things worth knowing about auto-drafted skills:

- **They're deliberately conservative about what counts as "the same procedure."** Reflection is asked to recognize the same underlying task even when you phrased it differently each time, and Hermclaw separately re-checks that against similar-looking existing drafts before creating a new one, so you don't end up with five near-duplicate skills for one task described five slightly different ways.
- **They're drafts, not finished skills.** Edit them freely -- there's nothing special protecting an auto-generated `SKILL.md` from a manual edit, and doing so is expected.
- **With `skills.evolution_enabled: true`**, Hermclaw will also periodically propose refinements to its own auto-generated skills' instructions based on how they've been going. This is opt-in and off by default.

## Testing a skill you're writing

```bash
hermclaw skills validate --profile <profile>   # full checklist, every skill
hermclaw skills show <name> --profile <profile>  # see exactly what the agent sees once activated
```
