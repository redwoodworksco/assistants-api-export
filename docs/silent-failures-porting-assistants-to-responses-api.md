# The silent failures when porting Assistants to the Responses API

Most of the Assistants-to-Responses port fails loudly, and loud failures are cheap: you get a 400, you fix it, you move on. **This page is about the other kind.** These six produce no error at all. The code runs, the response comes back, and the behaviour is wrong.

They are worth knowing about because they are the ones that reach production, and they surface days or weeks later as "the assistant got worse" rather than as a stack trace.

*API shapes described here were checked against OpenAI's published migration documentation. Dates re-verified 2026-08-17.*

---

## 1. `file_search` stops retrieving, and nothing says so

**The trap:** a `thread` carried `tool_resources`, which held your `vector_store_ids`. **A Conversation object has no `tool_resources` field.** There is nowhere for it to go.

Port the thread literally and the resulting conversation has no vector stores attached. The model answers anyway, from its own weights, in a confident tone, having retrieved nothing.

**The fix:** attach `vector_store_ids` to the `file_search` tool **on each request**, not once on the container.

**How to prove it actually works**, which matters more than the fix: request `include: ["file_search_call.results"]` and assert the results array is non-empty. **A test that only checks for a 200 cannot see this failure**, which is precisely why it survives to production.

## 2. `additional_instructions` silently discards your system prompt

**The trap:** the Assistants API had two separate fields. `instructions` was the assistant's base prompt; `additional_instructions` appended per-run context on top of it. **The Responses API has only `instructions`.**

The obvious port maps `additional_instructions` onto `instructions`. That **replaces** the base prompt rather than adding to it. Your assistant's entire personality, its guardrails, its output format rules: gone, replaced by whatever per-run scrap you were appending.

**The fix:** concatenate. Never map.

**Why it hides:** the model still answers, and it answers plausibly. Nothing is missing from the response, only from the prompt.

## 3. The truncation default inverted, so long threads start failing about a week in

**The trap:** under the Assistants API, when a thread outgrew the context window, the default behaviour was to silently trim old messages and keep going. **Under the Responses API the default is to return a hard 400.**

The default flipped from forgiving to strict, and nothing in a straightforward port sets it explicitly.

**Why this one is nastier than it looks:** it is not silent, it is *delayed*. A newly ported deployment works perfectly, because new conversations are short. The failures begin when the first long-lived conversations reach the boundary, which for typical usage is roughly a week after deploy, long after the port was signed off.

**The fix:** set `truncation` explicitly, in code, whatever value you want. Do not inherit a default that changed.

**Related, and it has no clean fix:** `truncation_strategy.last_messages` has no equivalent at all. If you relied on a fixed message window you re-implement it by hand, and `limit` maxes out at 100.

## 4. Your token accounting goes null while your bill keeps working

**The trap:** the usage field names changed. `prompt_tokens` and `completion_tokens` became `input_tokens` and `output_tokens`, and the same for the `*_token_details` breakdowns.

**`total_tokens` survived unchanged.** That is the trap in one line.

Any dashboard, cost allocation job or per-customer billing calculation reading the old names now gets null, while the top-line number it is checked against still looks right. **Nothing alerts, because nothing failed.**

**The fix:** grep for all four names, in your application code **and in your analytics and ETL**, which is usually a different repository owned by a different team.

## 5. Backfilled images vanish, including with OpenAI's own sample code

**The trap:** if you backfill exported threads into Conversations, message content parts come in several types. **The published backfill sample matches on content type with no `image_file` case and no default branch**, so every file-uploaded image is dropped on the floor without comment.

**The fix:** handle `image_file` explicitly, and raise on unknown content types rather than falling through. A backfill that skips content it does not recognise is a backfill that lies about having completed.

**How to prove it:** run an image-bearing conversation through and confirm the images survive. Not a text-only one.

## 6. Bulk backfill quietly exceeds a documented limit

**The trap:** the same published sample posts an entire thread in a single call, against a documented limit of 20 items per call. Short threads work. Long ones do not, and this one at least tends to fail loudly, but the failure arrives mid-migration on your largest and most valuable conversations.

**The fix:** chunk to 20 items or fewer, preserving order.

---

## The pattern underneath all six

**Every one of them is a field that exists in both APIs and means something different, or a field that quietly has no home in the new object.** Neither shows up in a diff of your code, and neither shows up as an error.

**A useful heuristic:** anywhere the port compiles and runs on the first try, look harder. The parts that shout at you are already handled by the shouting.

---

## The loud ones, for completeness

These will find you without help, but here is the list so you can plan for them: function tool definitions flatten from `{type, function:{...}}` to `{type, name, parameters, strict}` · `response_format` becomes `text.format` · the entire run-polling loop is deleted and replaced with an explicit function-call loop · streaming events change from `thread.*` to `response.*` with no shim · on Azure, `create_agent()` becomes `create_version()` and you need two distinct clients.

---

## Getting the data out first

None of this matters if the source data is gone. **The Assistants API is removed on August 26, 2026**, and thread history that was not exported by then is unrecoverable. See [what to do before August 26](./what-to-do-before-august-26-2026.md), and the [export script](../README.md) in this repository, which is MIT licensed and needs no signup.

---

## Related

- [What to do before August 26, 2026](./what-to-do-before-august-26-2026.md)
- [Model shutdowns after August 26, 2026](./model-shutdowns-after-august-26-2026.md)
