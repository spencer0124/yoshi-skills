# explain-diff

A Claude Code plugin that turns a code change (a diff, branch, commit range, or PR) into a single self-contained HTML page that explains it. The page is structured as Background, Glossary, Intuition, a code walkthrough, and a five-question quiz.

Based on Geoffrey Litt's original explain-diff, with a few changes from the community discussion:

- Quiz answer positions are shuffled, and option lengths are **measured** so the correct one is never reliably the longest.
- Added a Glossary section for codebase-specific terms.
- The diff is treated as data, not instructions, so a malicious repo can't inject commands.
- A validation checklist runs before the file is saved.
- `--lang` picks the explanation language (English by default).
- Output lands in the related project's `explain-diff/` folder and opens in the browser automatically.

Install instructions live in the [repo README](../README.md).

## Usage

```
/explain-diff <target> [--lang <code|name>]
```

Targets:

- `/explain-diff working tree` — uncommitted changes
- `/explain-diff my-feature-branch` — a branch compared against its base
- `/explain-diff abc123..def456` — a commit range
- `/explain-diff PR 42` — a pull request (needs the gh CLI)
- `/explain-diff src/auth.ts src/session.ts` — specific files
- `/explain-diff HEAD --lang ko` — explain in Korean
- `/explain-diff` — with no target, the most recent change is inferred and the assumption is stated at the top of the page

You can also just ask in plain language, like "explain the changes on this branch," and Claude loads the skill on its own.

### Language

Without `--lang` the page is written in English. It accepts a code or a name: `--lang ko`, `--lang Korean`, `--lang ja`.

The language applies to prose only. Code, file paths, symbol names, command output, and quoted source comments stay verbatim — translating a comment you are quoting would make the quote false.

### Where the output goes

`<project>/explain-diff/YYYY-MM-DD-explanation-<slug>.html`, opened in the browser automatically. For a change spanning several repos, it goes in the umbrella repo. The file is left uncommitted, so committing it is your call.

## Developing

When editing this repo:

```bash
claude plugin validate .claude-plugin/plugin.json --strict   # also validates SKILL.md frontmatter
claude plugin tag --push -m 'yoshi-skills %s'                # tag {name}--v{version} and push
```

Don't skip `validate --strict`. If `SKILL.md`'s YAML frontmatter fails to parse, the runtime drops **every** frontmatter field without an error — name, description, argument-hint, allowed-tools, all of it — and the only symptom is a skill that quietly stops behaving. Validation is the only thing that catches it. Watch values starting with `[`, like `argument-hint`: YAML reads them as a flow sequence, so they need quoting.

## Layout

```text
.claude-plugin/
  plugin.json         # plugin manifest — skills path, version
  marketplace.json    # marketplace manifest
skills/
  explain-diff/
    SKILL.md          # the skill itself
```
