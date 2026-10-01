# Milestone 2 evaluation — 2026-09-26

## Outcome

Deep Agents migration works in offline integration tests. **Live meal-plan
acceptance is still pending.** The trials do not establish that Deep Agents is
better or faster than the previous agent.

The test asks for five vegetarian dinners for two people, no aubergine, shared
ingredients, cited sources, and a consolidated shopping list for ten portions.
The baseline uses the original prompt and tools, with the original ten-step
ceiling. The new agent uses the new planning prompt and tools. This compares two
application versions, not an isolated framework variable. Only single trials
were made; timings include network search and page fetching.

## Recorded trials

| Model configuration | Engine | Seconds | Model starts | Outcome |
|---|---|---:|---:|---|
| openrouter/free | Previous ReAct | 36.05 | 5 | Whitespace-only streamed answer; not accepted |
| openrouter/free | Deep Agents | 107.56 | 8 | Created plan, searched/read pages; hit call cap before shopping/final answer |
| qwen/qwen3.8-27b:free | Both | <1 each | 1 each | Provider quota rejection |
| google/gemma-4-31b-it:free | Both | <1 each | 1 each | Provider quota rejection; upstream shared-pool limit confirmed |
| inclusionai/ling-3.0-flash-fin:free | Previous ReAct | 16.89 | 5 | Whitespace-only streamed answer; not accepted |
| inclusionai/ling-3.0-flash-fin:free | Deep Agents | 26.00 | 5 | Shared per-minute demo guard stopped the run; incomplete |

The free router resolved to seven different model IDs during the first Deep Agents
run. The fixed-model run removed that confound but hit the evaluation's shared
minute guard after the baseline. This is not evidence of inferior model quality.
The runner now requires separate engine invocations to avoid that experimental flaw.

No complete final menu was available to score source fidelity, all dietary
restrictions, portion counts or shopping totals. Do not mark those criteria passed.
At the last account check, 44 of 50 free daily requests were used; further live
trials were stopped to leave six calls for the owner's testing. This is a dated
snapshot, not the application's current quota.

## Changes driven by the trials

- Prefer Recipe JSON-LD or main article content over page navigation text.
- Reserve the last allowed main model call for a final or explicitly partial answer.
- Keep hard quotas; never fall back to paid models to make an evaluation pass.
- Keep the default free router configurable; no fixed model was promoted on the
  strength of these unsuccessful trials.

## Offline verification

25 tests passed, including actual Deep Agents graph execution with scripted model
messages. Verified: recipe search/read event flow, todo updates and UI persistence,
virtual-note thread isolation, lack of shell/subagent tools, per-turn cap reset,
demo quota propagation, final-call tool restriction, unit conversion and estimated
quantity labels, malformed recipe metadata fallback, and failure recovery.

These tests validate implementation contracts, not real model cooking quality.

## Repeat a live comparison

Use an available free model with tool support. Run separately, at least one minute
apart, and check remaining account quota first. The script rejects paid IDs.

```powershell
.\.venv\Scripts\python.exe evaluations/compare_agents.py --engine baseline --model <provider/model:free>
.\.venv\Scripts\python.exe evaluations/compare_agents.py --engine deepagents --model <provider/model:free>
```

Per-engine JSON includes public test input, answer, model IDs, tool evidence,
elapsed time and error category. Generated `*comparison.json` files are ignored by
Git because they contain verbose scraped page evidence. Earlier raw trials remain
locally in this directory. The first runner did not classify whitespace as an
error; the first baseline's JSON has a null error but its empty answer fails acceptance.

Acceptance requires manual source/constraint review in addition to a completed run.

## Follow-up — 2026-09-28

Live acceptance remains pending. Additional free-only trials exposed both provider
availability failures and semantic failures; no fixed model was promoted:

| Model | Seconds | Calls | Outcome |
|---|---:|---:|---|
| Ling 3.0 Flash Fin, 2048 output tokens | 24.38 | 6 | Incomplete response |
| Ling 3.0 Flash Fin, 4096 output tokens | 34.02 | 8 | Raw tool markup instead of final answer; animal ingredients in shopping |
| Qwen 3.8 27B | <2 | 1 | Provider quota rejection |
| Nemotron 3 Super | 26.51 | 2 | ValueError, cause not captured |
| Gemma 4 31B | 1.03 | 1 | Provider quota rejection |
| Nemotron 3 Ultra | 201.97 | 8 | Raw tool markup rejected; quantities scaled to ten diners per dinner |
| Ling 3.0 Flash Fin, deterministic scaling tool | 30.31 | 8 | Searched/read sources but leaked tool markup; did not reach shopping tool |

Changes responding to these failures:
- Raised output cap to 4096 for structured ingredient arguments, keeping eight
  model calls and free-only selection. This does not guarantee provider availability.
- Reject leaked tool protocol as incomplete output instead of accepting it as an answer.
- Keep tool schemas on the final call with `tool_choice="none"`; providers have
  still leaked markup, so this is not considered a proven provider-level fix.
- Parse fractional amounts and retain unspecified quantities without inventing numbers.
- Replace model-side scaling with `scale_meal_plan`: original source quantities and
  source yield per recipe, plus diners per meal. Code scales each meal and then sums.
  Source transcription, yield accuracy and dietary compliance remain unverified inputs.
- Remove image metadata from recipe instructions and bound search snippets.

29 offline tests pass, including a five-dinners-for-two regression: five recipes
for four people containing 400 g rice each produce 1000 g total, not 5000 g.
The integration test checks the actual shopping tool result, not just scripted
final-answer text. No paid fallback was used.
