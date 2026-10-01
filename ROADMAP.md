# Personal Chef: evolution plan

Three independently reviewable deliveries, agreed on 2026-09-26. Work can continue
in this task or another session using this file as the handoff.

## 1. OpenRouter and a keyless visitor demo

Implemented locally:
- Explicit OpenRouter/OpenAI selection with the dedicated OpenRouter integration.
- Server-owned OpenRouter key for a text demo, defaulting to `openrouter/free`.
- Optional visitor keys; no automatic use of the server's OpenAI credentials.
- Free-only demo model validation, session turn cap, process-wide model-call quota,
  bounded input/output and agent steps, safe public errors.
- Offline provider and Streamlit journey tests.

Acceptance: a real recipe request searches, reads a source and returns a cited
answer; key switching resets the conversation; quota exhaustion fails gracefully.
Free model quality and availability must be evaluated before choosing a fixed model.
The router can select different free models; it is not a reproducible benchmark.

Validation on 2026-09-26:
- 10 offline tests passed (`python -m unittest discover -s tests -v`).
- `pip check` and `git diff --check` passed.
- Real `openrouter/free` recipe smoke test executed `web_search`, then `fetch_page`,
  and returned gazpacho ingredients with a Directo al Paladar source URL.
  This verifies a successful journey, not general recipe accuracy or model quality.
- Local browser reviewed; sidebar opens/closes on a narrow viewport.
- SDK retries explicitly disabled with `OpenRouter(retry_config=None)`; the wrapper's
  `max_retries=0` alone retains SDK defaults. Timeout is 45,000 milliseconds.
- No public deployment, push or commit performed. Next delivery: Deep Agents.

Follow-up: a visitor reported a generic error for `hamburguesa`. The original
exception was not logged, so its cause cannot be established retrospectively.
An isolated live repeat completed search, page reading and a cited Canal Cocina
answer. Added classified public errors, safe reference-based server diagnostics,
partial-answer preservation and detection of truncated model output. Four new
regression tests cover timeout classification, safe logs, truncation and recovery;
all 14 offline tests pass. This does not establish that intermittent provider
failures are eliminated.
The same query also completed in the local Streamlit browser after applying the
changes. The router produced a different answer/source there; source fidelity was
not independently verified in this diagnostic run.

## 2. Deep Agents with a useful planning task

Implemented locally with `deepagents==0.7.19`, `langchain==1.4.2` and
`langgraph==1.2.12`. Added TodoListMiddleware, session-local StateBackend notes,
arithmetic shopping consolidation, recipe metadata extraction and streamed plan
progress. Shell and delegated subagents are disabled. Preserved provider selection,
visitor/demo quotas and safe errors; eight main model calls per turn with the last
reserved for a final/partial answer, plus a 100-node graph ceiling.

Validation: 29 offline tests cover the real graph's tools, memory isolation, quota
propagation, call limits, plan events, recipe extraction, shopping arithmetic and UI
recovery. Live comparison attempted five vegetarian dinners for two, without
aubergine. Neither engine delivered a complete accepted result in those trials.
Detailed evidence and timings: [evaluations/RESULTS.md](evaluations/RESULTS.md).

Still pending before declaring this milestone fully accepted: a complete live
five-dinner menu, checked against source content and restrictions, with a correctly
consolidated list. Repeat with an available fixed model and enough free quota;
do not infer quality improvement from migration or synthetic tests alone.

## 3. Next.js interface and Vercel

Pending. Show a concrete visual direction before implementation. Target recipe
cards, visible sources, starter suggestions and a useful shopping list.
Prefer preserving the Python agent behind an API; evaluate Vercel Python execution
limits, streaming and durable conversation storage before settling backend hosting.
Replace process-local quotas with shared durable enforcement for multiple instances.
Review URL fetching boundaries before public deployment. Deploy and verify the
public visitor journey separately from local implementation.

## Scope and continuity

- Keep changes as separate deliveries; no need to create three sidebar tasks.
- Voice currently requires a visitor OpenAI key. Free speech input is a later decision.
- Do not publish LinkedIn posts automatically. Each delivery can supply a factual demo
  and lessons learned for a later post.
- `CLAUDE.md` was already untracked and contains outdated architecture notes; left intact.
