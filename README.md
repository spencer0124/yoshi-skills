# yoshi-skills

spencer0124's personal Claude skill collection, packaged as a single-plugin marketplace.

| Skill | What it does |
|---|---|
| [`explain-diff`](skills/explain-diff/) | Turns a diff, branch, commit range, or PR into a self-contained interactive HTML explainer with a quiz. [Details](docs/explain-diff.md) |
| [`notion-artifact`](skills/notion-artifact/) | Builds Notion-looking HTML artifacts for decision docs, comparison tables, and notes. |
| [`deep-concrete-explainer`](skills/deep-concrete-explainer/) | Explains a concept background-first and concretely, in Korean, with no hand-waving. |
| [`tone-polish-kr`](skills/tone-polish-kr/) | Polishes Korean messenger/email drafts into concise, natural 존댓말. |

## Install (Claude Code)

```bash
claude plugin marketplace add spencer0124/yoshi-skills
claude plugin install yoshi-skills@yoshi-skills
```

Restart Claude Code once. All four skills load.

### Updating

```bash
claude plugin marketplace update yoshi-skills   # re-fetch manifests from this repo
claude plugin update yoshi-skills               # install the new version (restart to apply)
```

### Migrating from `explain-diff`

This repo was previously the `explain-diff` single-skill marketplace. To switch:

```bash
claude plugin uninstall explain-diff@explain-diff
claude plugin marketplace remove explain-diff
claude plugin marketplace add spencer0124/yoshi-skills
claude plugin install yoshi-skills@yoshi-skills
```

## Install (Claude Desktop / claude.ai)

Plugins are Claude Code only. For Desktop, zip a single skill folder and upload it in Settings → Capabilities → Skills:

```bash
cd skills && zip -r ../tone-polish-kr.zip tone-polish-kr
```

`deep-concrete-explainer` and `tone-polish-kr` are the two written for Desktop.

## License

MIT.
