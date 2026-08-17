# Model shutdowns after August 26, 2026: the second outage nobody warns you about

**If you port off the Assistants API onto the model you are currently pinned to, you may be scheduling a second outage for October 23.**

The migration guides do not mention this, and reasonably so: model retirement is a different document's subject. But the two lists intersect, and the intersection lands on people migrating under deadline pressure who pick the target model by copying what is already in their config.

*Every date below was read from [OpenAI's deprecations page](https://developers.openai.com/api/docs/deprecations) on 2026-08-17. Check it yourself before you commit to a target, because these lists move.*

---

## The four dates

| date | what goes |
|---|---|
| **August 26, 2026** | **The Assistants API is removed.** Replacements are the Responses API and the Conversations API. Azure OpenAI retires its Assistants API on the same date. |
| **October 23, 2026** | A large group of legacy models retires. **58 days after the API cliff.** |
| **November 30, 2026** | **The `v1/prompts` API and reusable prompt objects shut down.** |
| **December 1 and 11, 2026** | Image models on December 1. Older GPT-5 and o3 snapshots on December 11. |

## What goes on October 23

This is the list that catches people, because several of these are models a 2024-era or 2025-era Assistants deployment is very likely to be pinned to:

- `gpt-3.5-turbo-0125`, plus the `gpt-3.5-turbo` alias and its completions variants
- `gpt-4-0613`, plus the `gpt-4` alias and its completions variants
- `gpt-4-1106-preview`
- `gpt-4-turbo` and related snapshots
- `gpt-4.1-nano`
- `gpt-4o-2024-05-13`
- `o1-2024-12-17` and the `o1` alias
- `o1-pro-2025-03-19` and the `o1-pro` alias
- `o3-mini-2025-01-31` and the `o3-mini` alias
- `o4-mini-2025-04-16` and related variants
- Fine-tuned models on those bases, including `ft-gpt-3.5-turbo`, `ft-gpt-4`, `ft-gpt-4.1-nano-2025-04-14`, `ft-babbage-002` and `ft-davinci-002`

**If you have fine-tuned models on this list, that is the expensive line.** A fine-tune is not a config value you swap; it is a training run against a base model that will not exist. Plan that separately and plan it now, because it has a lead time the others do not.

## What goes on December 11

`gpt-5-2025-08-07`, `gpt-5-mini-2025-08-07`, `gpt-5-nano-2025-08-07`, `gpt-5-pro-2025-10-06`, `o3-2025-04-16` and `o3-pro-2025-06-10`.

**Note what this means for the obvious defensive move.** Pinning to a specific dated snapshot is normally the right instinct, because it protects you from behaviour changing underneath you. Here, dated GPT-5 snapshots from August and October 2025 are themselves on a shutdown list. **Pinning buys reproducibility and costs you a renewal deadline**, and the renewal deadline is the thing that pages you at night.

## The prompt-objects date, which is a separate trap

**November 30, 2026: the `v1/prompts` API and reusable prompt objects shut down.**

This one matters during an Assistants migration specifically, because reusable Prompt objects look like the natural home for an Assistant's `instructions`. They are the dashboard-shaped thing that most resembles what you are migrating from.

**Rebuild assistants as code configuration instead.** Prompt objects are dashboard-managed, which makes them hard to review, hard to diff and hard to roll back, and they are on a shutdown list three months out.

---

## The practical rule

**Choose your target model against the shutdown lists, not against your current config.** It costs one page-read during a migration you are already doing, and the alternative is doing the whole exercise again in eight weeks with less notice.

If your migration window is tight, the safe move is to port onto a current non-dated model family first and revisit pinning afterward, rather than carrying a soon-to-retire pin through the port because it was already in the file.

---

## Related

- [What to do before August 26, 2026](./what-to-do-before-august-26-2026.md)
- [The silent failures when porting Assistants to the Responses API](./silent-failures-porting-assistants-to-responses-api.md)
- [The export script](../README.md), MIT licensed, no signup
