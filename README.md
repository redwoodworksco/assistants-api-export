# assistants-api-export

**Export your OpenAI Assistants API data to portable JSON before the API is removed on August 26, 2026.**

A single-file, read-only Python script that exports your **assistants, threads, messages, runs, run steps, and attached-file metadata** to well-structured JSON, one file per thread plus a manifest. Works against both **OpenAI** and **Azure OpenAI** endpoints. MIT licensed, one dependency, no account or signup of any kind.

---

## The problem

On **August 26, 2026** the Assistants API is removed. After that date `/v1/assistants` and `/v1/threads` stop answering, and any thread history you did not export is gone. The data lives on OpenAI's side, not yours, and there is no post-shutdown retrieval path.

Two things make this worse than a typical deprecation:

1. **The cliff is hard, not a slow degrade.** The endpoints are removed, not throttled. Code that works on August 25 fails on August 26.
2. **There is no automated migration tool, and OpenAI has said there will not be one.** From the official migration guide: *"We will not provide an automated tool for migrating Threads to Conversations."* What exists is documentation.

**Azure OpenAI retires its Assistants API on the same day.** From Microsoft Learn: *"The Assistants API is deprecated and will be retired on August 26, 2026. Use the generally available Microsoft Foundry Agents service."*

### Official sources

| source | what it says |
|---|---|
| [OpenAI API Deprecations](https://developers.openai.com/api/docs/deprecations) | *"On August 26th, 2025, we notified developers using the Assistants API of its deprecation and removal from the API one year later, on August 26, 2026."* |
| [OpenAI: Assistants → Conversations migration guide](https://developers.openai.com/api/docs/assistants/migration) | *"It will shut down on August 26, 2026."* · *"We will not provide an automated tool for migrating Threads to Conversations."* |
| [OpenAI developer community announcement](https://community.openai.com/t/assistants-api-beta-deprecation-august-26-2026-sunset/1354666) | "Assistants API beta deprecation — August 26, 2026 sunset" |
| [Azure OpenAI Assistants concepts (retirement notice)](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/concepts/assistants) | *"deprecated and will be retired on August 26, 2026"* → migrate to Microsoft Foundry Agents |
| [Microsoft Q&A confirmation](https://learn.microsoft.com/en-us/answers/questions/5790094/will-azure-openai-assistants-api-specifically-be-d) | same date, same migration path |

*All five links re-verified against the live pages on 2026-08-07.*

This script does one job: **get your data out, losslessly, before the date.** What you migrate *to* (Responses API, Conversations API, Foundry Agents, your own store, or nothing) is your call.

---

## Install

Python 3.8+ and one dependency:

```bash
pip install requests
```

Then download `export_assistants_api.py`. It is deliberately a single file with no package, no config, and no install step, so you can vendor it straight into a repo that has been untouched for a year.

```bash
curl -O https://raw.githubusercontent.com/redwoodworksco/assistants-api-export/main/export_assistants_api.py
```

## Usage

```bash
export OPENAI_API_KEY=sk-...

# Export all assistants + specific threads
python3 export_assistants_api.py --out ./export \
    --thread-ids thread_abc123,thread_def456

# Thread IDs from a file (one per line, '#' comments allowed)
python3 export_assistants_api.py --out ./export --thread-file my_threads.txt

# Just the assistant definitions (no thread IDs supplied)
python3 export_assistants_api.py --out ./export
```

### Azure OpenAI

```bash
export AZURE_OPENAI_API_KEY=...   # falls back to OPENAI_API_KEY if unset

python3 export_assistants_api.py --out ./export \
    --azure-endpoint https://YOUR-RESOURCE.openai.azure.com \
    --api-version 2024-05-01-preview \
    --thread-file my_threads.txt
```

Azure uses the `api-key` header and requires an explicit `--api-version`; the script handles both differences for you. Everything else (output layout, pagination, retries) is identical.

### Flags

| flag | meaning |
|---|---|
| `--out DIR` | output directory (default `./assistants-export`) |
| `--thread-ids a,b,c` | comma-separated thread IDs |
| `--thread-file FILE` | file of thread IDs, one per line (`#` comments allowed) |
| `--no-assistants` | skip exporting assistant objects |
| `--no-runs` | skip runs/run-steps (much faster; messages only) |
| `--azure-endpoint URL` | use an Azure OpenAI resource |
| `--api-version VER` | Azure `api-version` (**required** with `--azure-endpoint`) |
| `--base-url URL` | override the OpenAI base URL (proxies, gateways) |

## Output layout

```
export/
  manifest.json          # counts, endpoint, failures, export timestamp
  assistants.json        # every assistant in the project (fully paginated)
  threads/
    <thread_id>.json     # thread object + messages (ascending) + runs
                         #   (each run carries its "steps") + file metadata
```

Each thread file is self-contained (`export_schema: assistants-thread-export/v1`) and preserves the **raw API objects verbatim**: nothing is normalized away, so you can reshape into any target format later without re-fetching. Which matters, because after August 26 you cannot re-fetch.

---

## The honest limitation: thread IDs cannot be enumerated

**The Assistants API has no endpoint that lists all threads in an account.** Threads are retrievable only by ID. That is an API limitation, not a limitation of this script. **No export tool can "find all your threads,"** and you should be skeptical of any that claims to.

Where your thread IDs actually live:

- **Your own application database or logs**: wherever your app persisted the `thread_...` ID when it called `POST /v1/threads`. This is the normal source and usually the only complete one.
- **Application traces / observability tooling**: request logs of thread-creation responses.
- **The OpenAI dashboard's Threads page**: if your organization enabled thread visibility, you can browse and copy IDs by hand.

If a thread's ID exists nowhere in your systems, that thread cannot be retrieved by anyone. That is itself the best argument for running this export **while your logs are still around**.

Two smaller limitations, stated plainly:

- **File metadata only, not file bytes.** Files with `purpose: assistants` cannot have their content downloaded through the API. The export records filename, size, created-at and the file IDs, so you know exactly what was attached, but the bytes are not retrievable.
- **Run steps can age out.** Very old runs may return incomplete step data. The script records this as a warning in that thread's `errors` array rather than failing the export.

## Behavior you can rely on

- **Read-only by construction.** The script issues only `GET` requests. It never creates, modifies or deletes anything, and it never invokes a model. **Running the export costs $0 in model usage.**
- **Full pagination.** Every list endpoint is followed to exhaustion (100/page, cursor-based).
- **Rate limits handled.** 429s and 5xxs retry with exponential backoff, honoring `Retry-After`, up to 6 attempts.
- **Partial failure is survivable.** A deleted thread is recorded in the manifest and skipped; a missing file or aged-out run steps are recorded in that thread's `errors` array. One bad object never aborts a long export.
- **Auth failures are loud.** Clear message on stderr, exit code 2, not a silent empty export.

## Verification status

Stated precisely, because "it works" is not a claim you should take on faith from a stranger's repo:

- **Live-verified against the real OpenAI API**: assistant export, thread export, message export (ordering, unicode, metadata), pagination cursor-following, the missing-thread path, and the auth-failure path were all exercised against `api.openai.com` using real objects that were created, exported, inspected, then deleted.
- **Fixture-verified, pending a live run**: the run / run-step export path is covered by unit tests (`test_export_fixtures.py`) whose fixtures are built from the official API reference object shapes ([runs](https://developers.openai.com/api/docs/api-reference/runs/object), [run steps](https://developers.openai.com/api/docs/api-reference/run-steps/step-object)), including `tool_calls` and `message_creation` steps and file-ID harvesting from code-interpreter image outputs. Verifying this path against live data requires **executing a model run**, which costs money; that was not done. If you hit a run-export problem on real data, please [open an issue](../../issues) with the (redacted) object shape, that is the single most useful contribution to this repo.

```bash
python3 test_export_fixtures.py
```

## Contributing / issues

Bug reports are welcome and useful, especially anything from a **live run export**, an **Azure `api-version` mismatch**, or an unusual object shape the script mishandles. See [CONTRIBUTING.md](CONTRIBUTING.md). Please redact IDs and content before pasting.

---

## Need the port done, not just the export?


This exporter is the free half, and it is deliberately complete on its own. If you can do the migration yourself, take it and go. That is what it is for.

If you'd rather not, we do the port itself at a **fixed price**:

- **Porting kit (self-serve), $249.** Migration playbook for Assistants to Responses / Conversations API and Agents SDK, plus the Azure Assistants to Foundry Agents variant, the mapping scripts, and a checklist of the mappings that are *not* 1:1 (where most of the lost time goes). 23 pages, 20 documented non-1:1 gaps, every API shape cited to the live vendor page it was read from.
- **Done-for-you port, $400 to $600 fixed.** We perform the migration against your repo, async, no calendar tag. Email stan@redwoodworks.co.

👉 **[The Assistants API Porting Kit](https://redwoodworks.gumroad.com/l/rpiqx)**

We wrote the export tool you just ran.

## License

[MIT](LICENSE). Do whatever you want with it, including using it commercially. Copyright (c) 2026 Redwood Works.
