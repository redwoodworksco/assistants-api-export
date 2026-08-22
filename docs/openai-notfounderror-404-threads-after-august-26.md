# `openai.NotFoundError` / HTTP 404 on `/v1/threads` and `/v1/assistants` after August 26, 2026

If you landed here from a stack trace, the short version: **the Assistants API was removed on August 26, 2026.** Your code did not break. The endpoint it calls no longer exists.

This page covers what you will see, why nothing warned you, and what is still recoverable.

*Removal date re-verified against [OpenAI's deprecations page](https://developers.openai.com/api/docs/deprecations). SDK behaviour below was read from the `openai-python` source, not from documentation. Page written 2026-08-22.*

---

## What the failure looks like

**At the HTTP layer, a removed OpenAI route returns `404`.** Verified directly against `api.openai.com`: a request to a route that does not exist returns status `404` rather than a `400` or a structured deprecation notice.

**In the Python SDK, that surfaces as `openai.NotFoundError`.** This is a hard mapping in the client, not a guess: `_client.py` converts `response.status_code == 404` into `_exceptions.NotFoundError`, and `_exceptions.py` declares `class NotFoundError(APIStatusError)` with `status_code: Literal[404] = 404`.

So the calls that stop working are the ones you would expect:

```python
client.beta.assistants.create(...)   # -> openai.NotFoundError
client.beta.threads.create(...)      # -> openai.NotFoundError
client.beta.threads.messages.list(thread_id)   # -> openai.NotFoundError
client.beta.threads.runs.create(...)           # -> openai.NotFoundError
```

In the Node SDK the same status maps to `NotFoundError` from the `openai` package.

## Why nothing warned you, which is the part worth understanding

**The SDK still ships the methods.** `client.beta.assistants` and `client.beta.threads` are still present in the `openai-python` source. They still typecheck. Your editor still autocompletes them. Your CI still passes, because most suites mock the client rather than call it.

**The removal happened on the server, not in the library.** There is no import error, no deprecation warning at call time, and no version bump that would have failed your build. Pinning your SDK version protected you from nothing, because the thing that changed was not in the package.

This is why the failure arrives as a production incident rather than as a failed deploy.

## What is recoverable, stated honestly

### Your thread data

**If you did not export your threads before August 26, there is no API left to read them with.** The endpoints that list messages on a thread are the same ones that were removed. This is the part that is genuinely gone from a programmatic point of view, and no tool can work around it, including ours.

If your threads still matter to you, your remaining routes are your own application database (many deployments stored a copy of every message alongside the thread ID and forgot), your logs, and OpenAI support. Check the first of those before assuming the data is lost. A surprising number of Assistants deployments were already writing messages to their own store for display purposes.

### Your code

**The code half is straightforward and well covered by free material.** OpenAI publishes a migration guide to the Responses API, and Azure publishes a tool that converts code constructs for Azure OpenAI Assistants, which retired on the same date. Microsoft states plainly that their tool "doesn't migrate state data like past runs, threads, or messages." Both vendors move code. Neither moves data.

Start with the vendor guide. It is free, it is current, and for a straightforward deployment it is enough.

### The failures that do not announce themselves

The 404 is the easy one. The porting failures that reach production are the quiet ones: `file_search` that silently retrieves nothing, `additional_instructions` that replaces your system prompt instead of appending to it, a truncation default that flipped from trimming to a hard 400 about a week after you deploy, and token accounting that goes null while `total_tokens` keeps looking right.

Those are written up separately in [the silent failures page](./silent-failures-porting-assistants-to-responses-api.md).

## What else retires, so you fix it once

August 26 is not the only date. The same deprecations page lists `gpt-4-turbo`, `gpt-4o-2024-05-13`, `o1`, `o3-mini` and `o4-mini` retiring **October 23**, along with five fine-tune base models. Fine-tunes on a retiring base go with the base, and a fine-tune is a training run rather than a config value, so it carries a lead time nothing else on the list does. `v1/prompts` shuts down **November 30**.

If you are already in the code, check those now. The [model shutdown page](./model-shutdowns-after-august-26-2026.md) has the full list.

---

## The tools on this repo

**The exporter in this repository reads threads out of the Assistants API into JSON.** It is free and MIT licensed. Be clear about its limits after the cliff: it calls the same removed endpoints, so **it cannot recover threads once the API is gone**, and it never could list threads for you, because the Assistants API had no endpoint that enumerates them. It works when you hold your own thread IDs and the API is still up.

**If your port is stuck on the behaviour differences rather than the syntax**, there is a paid kit covering the gaps that produce wrong output rather than errors, and a fixed-price porting service. Both are linked from the [repository README](../README.md).

If the vendor guide gets you there, use the vendor guide. It is free and it is good.
