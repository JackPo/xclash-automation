---
name: skill-creator
description: Creates new Claude Code skills with proper structure, frontmatter, and documentation. Use when creating skills, setting up skill templates, or when user says "create a skill", "make a skill", "new skill for".
allowed-tools: Read, Write, Bash, Glob, Grep
---

# Skill Creator

A meta-skill for creating well-structured Claude Code skills.

## When to Use

- User asks to "create a skill" or "make a skill"
- Setting up reusable automation patterns
- Creating project-specific Claude instructions

## Creating a New Skill

### Step 1: Gather Requirements

Ask the user:
1. **What should the skill do?** (specific capability)
2. **When should it trigger?** (keywords users would say)
3. **What tools does it need?** (Read, Write, Bash, etc.)

### Step 2: Create Directory Structure

```bash
mkdir -p .claude/skills/skill-name
```

### Step 3: Write SKILL.md

```yaml
---
name: skill-name
description: What it does. When to use it. Include trigger keywords.
allowed-tools: Read, Grep, Glob
---

# Skill Title

## Instructions

Clear step-by-step guidance.

## Examples

Show concrete usage.
```

## Best Practices

### Descriptions (Critical!)

**Bad**: "Helps with files"
**Good**: "Extract and analyze log files. Use when debugging errors, searching logs, or when user mentions 'logs', 'errors', or 'stack trace'."

### Keep It Focused

- One skill = one specific capability
- Under 500 lines in SKILL.md
- Put detailed docs in separate files (reference.md, examples.md)

### Tool Restrictions

Use `allowed-tools` to limit permissions:
- Read-only: `allowed-tools: Read, Grep, Glob`
- Full access: omit the field

## Template

When creating a skill, use this template:

```yaml
---
name: [lowercase-with-hyphens]
description: [What it does]. [When to use it]. Use when [trigger keywords].
allowed-tools: [comma-separated tools, or omit for full access]
---

# [Skill Title]

## Purpose

[One sentence explaining what this skill accomplishes]

## Instructions

1. [Step one]
2. [Step two]
3. [Step three]

## Examples

### Example 1: [Scenario]

[Show concrete usage]

## Notes

- [Important consideration]
- [Common pitfall to avoid]
```

## Skill Locations

| Location | Path | Scope |
|----------|------|-------|
| Personal | `~/.claude/skills/` | All your projects |
| Project | `.claude/skills/` | This repo only |

## After Creating

1. Restart Claude Code to load the skill
2. Test by asking a question with keywords from description
3. Iterate on description if skill doesn't trigger
