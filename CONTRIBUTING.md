# Contributing

This repo has a deadline: **August 26, 2026**, when the Assistants API is removed. After that date the script cannot be tested against a live API by anyone, so useful contributions are the ones that arrive *before* then.

## The most valuable thing you can send

**A run/run-step export from live data.** That path is fixture-verified but not live-verified (verifying it requires executing a model run, which costs money — see the README's "Verification status"). If you export a thread that has real runs in it and something looks wrong — missing steps, an unexpected `step_details` shape, a tool call the script doesn't harvest file IDs from — please open an issue.

Also very useful:

- **Azure `api-version` results.** Which versions work, which return errors, and what the error said.
- **Unusual object shapes** the script mishandles — older threads, unusual annotations, vector-store attachments.
- **Scale reports.** How it behaved over hundreds or thousands of threads: rate limiting, runtime, memory.

## Redact before you paste

Thread contents are usually real user data. Before pasting anything into an issue:

- Replace IDs (`thread_...`, `msg_...`, `asst_...`, `file-...`, `run_...`) with placeholders.
- Strip message text — the **shape** of the object is what matters, not its content.
- Never paste an API key. If you post one by accident, revoke it immediately at platform.openai.com.

## Pull requests

Keep the script **a single file with one dependency** (`requests`). That constraint is deliberate: the people who most need this tool are maintaining a codebase nobody has touched in a year, and "download one file, `pip install requests`" is the whole install story. PRs that add packaging, a config format, a CLI framework, or extra dependencies will be declined on that basis, however clean they are.

Run the tests before opening a PR:

```bash
python3 test_export_fixtures.py
```

New behavior should come with a fixture test. Fixtures are built from the official API reference object shapes rather than from captured live data, so no real data ever enters the repo.

## Scope

This is an **exporter**. Getting data out losslessly is the job. Conversion into Responses/Conversations API or Foundry Agents format is deliberately out of scope for this repo — the raw objects are preserved verbatim precisely so that conversion can happen separately, on your terms.
