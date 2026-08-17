# Assistants API shutdown: what to do before August 26, 2026

**The Assistants API is removed on August 26, 2026.** Not throttled, not deprecated-but-working. Removed. Code that runs on August 25 fails on August 26, and any thread history you have not exported by then is gone, because the data lives on OpenAI's side and there is no post-shutdown retrieval path.

**Azure OpenAI retires its Assistants API on the same date.**

*All dates on this page were re-verified against [OpenAI's deprecations page](https://developers.openai.com/api/docs/deprecations) on 2026-08-17.*

This page is the short version: what to do, in what order, if you are reading this with days left rather than months.

---

## The order matters, and most people get it backwards

The instinct is to start porting code. **Do the irreversible thing first.**

Porting can be finished in September. **Exporting cannot.** After August 26 the export is impossible at any price, so every hour spent on the port before the export is an hour spent on the recoverable task while the unrecoverable one sits.

### 1. Harvest your thread IDs (today)

**The API cannot enumerate threads account-wide.** There is no `GET /v1/threads`. If you do not have the IDs, you cannot export the threads, and this surprises almost everyone the first time.

Your thread IDs live in whatever you wrote them to: your own database, your application logs, your traces, your support tickets. Go and get them now, because this step has a research tail and the others do not.

### 2. Run the export and verify it

Use [`export_assistants_api.py`](../export_assistants_api.py) in this repository, or anything else that gets the data out. It is MIT licensed, one dependency, read-only by construction, and needs no signup.

**Then verify it, which is a separate step people skip.** Check that `manifest.json` shows an empty `threads_failed` list, and read the per-thread `errors` arrays rather than assuming they are empty. An export that silently skipped a third of your threads looks exactly like an export that worked.

### 3. Record your vector store and container file IDs

**This is the step that is unrecoverable and almost never on anyone's list.**

Every `vs_...` vector store ID and every code-interpreter `file-...` ID lives inside your assistants' and threads' `tool_resources`. After August 26 you cannot read `tool_resources` from a thread, so if you did not record those IDs, you have file corpora sitting in your account that you can no longer connect to the conversations that used them.

Write them down. A text file is fine.

### 4. Check `expires_after` on every vector store you intend to keep

Vector stores can carry an expiry policy. A store that expires on its own schedule after you have migrated is a failure that arrives weeks later, with no error at migration time.

### 5. Pick your target model against the shutdown lists, not against what you are pinned to now

**Porting onto your currently pinned model can buy you a second outage in under two months.** See [model shutdowns after August 26](./model-shutdowns-after-august-26-2026.md), which lists the October 23 and December 11 dates. No migration guide flags this, because it is a different document's problem.

### 6. Only now, port the code

And before you start, read [the silent failures](./silent-failures-porting-assistants-to-responses-api.md). The loud failures will find you on their own. The silent ones ship to production and surface as quiet wrongness weeks later.

---

## What OpenAI provides, and what it does not

**There is no automated migration tool, and OpenAI has said there will not be one.** From the official migration guide, verbatim: *"We will not provide an automated tool for migrating Threads to Conversations."*

What exists is documentation. That documentation is good and you should read it. It describes the new API well. **What it does not do is tell you which parts of your existing deployment have no equivalent**, and that is where the time goes.

**Azure users have more tooling and a different gap:** Microsoft ships a migration tool that rewrites call shapes. It does not know your bindings, your truncation assumptions, or your downstream ETL, so its output still needs reviewing against every non-Azure gap.

---

## If you have already missed the date

Then the export question is closed and the porting question is not. The pages in this folder still apply to the port, and the checklists are the same. **What you cannot do is recover thread history**, and no vendor, tool or support ticket changes that.

---

## Related

- [The silent failures when porting Assistants to the Responses API](./silent-failures-porting-assistants-to-responses-api.md)
- [Model shutdowns after August 26, 2026](./model-shutdowns-after-august-26-2026.md)
- [The export script itself](../README.md)
