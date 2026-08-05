# explain-diff

A Claude Code skill that turns a code change (a diff, branch, commit range, or PR) into a single self-contained HTML page that explains it. The page is structured as Background, Glossary, Intuition, a code walkthrough, and a five-question quiz.

Based on Geoffrey Litt's original explain-diff, with a few changes from the community discussion:

- Quiz answer positions are shuffled so the correct one isn't always the longest or in the same slot.
- Added a Glossary section for codebase-specific terms.
- The diff is treated as data, not instructions, so a malicious repo can't inject commands.
- A validation checklist runs before the file is saved.

## Install

Personal skill (available in every project):

```bash
mkdir -p ~/.claude/skills/explain-diff
cp SKILL.md ~/.claude/skills/explain-diff/SKILL.md
```

For a single project, use that project's `.claude/skills/explain-diff/` instead of `~/.claude/`.

Claude Code picks up the new skill without a restart. If you just created the top-level `skills` directory, restart once so it starts watching.

## Usage

```
/explain-diff <target>
```

Targets:

- `/explain-diff working tree` — uncommitted changes
- `/explain-diff my-feature-branch` — a branch compared against its base
- `/explain-diff abc123..def456` — a commit range
- `/explain-diff PR 42` — a pull request (needs the gh CLI)
- `/explain-diff src/auth.ts src/session.ts` — specific files

You can also just ask in plain language, like "explain the changes on this branch," and Claude loads the skill on its own.

The output is written to `/tmp/YYYY-MM-DD-explanation-<slug>.html`, outside the repo. Open it in a browser.

## Notes

- The explanation is generated in English. To switch it, change "Write in **English**" in SKILL.md.
- To output a Notion page instead of HTML, replace the "Final handoff" section with a Notion MCP step.
- If you don't want to regenerate the CSS/JS boilerplate each run, move a renderer into `scripts/render.py` and have SKILL.md pass it a JSON content spec.
