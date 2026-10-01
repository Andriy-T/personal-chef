# 🍳 Personal Chef AI

Experimental cooking assistant built with Deep Agents, LangGraph and Streamlit.
Search recipes, adapt ingredients and plan meals. See [ROADMAP.md](ROADMAP.md)
for the three agreed deliveries: OpenRouter, Deep Agents, then Next.js/Vercel.

## Access modes

- **Probar gratis:** text demo using the project's server-side OpenRouter key.
  Visitors do not enter a key. The owner configures `OPENROUTER_API_KEY`.
- **Mi clave de OpenRouter:** visitor key and configurable model ID.
- **Mi clave de OpenAI:** direct access with the visitor's key, including Whisper voice.

Visitor keys stay in server session memory; the app does not write them to disk.
Conversations go to the selected provider (and upstream provider for OpenRouter);
search queries go to DuckDuckGo. Changing key, provider or model resets the chat.
Conversation memory lasts only for the active session.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and configure your real OPENROUTER_API_KEY.
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://localhost:8501. Edit existing `.env` files rather than overwriting them.
A server `OPENAI_API_KEY` is deliberately not used for anonymous access. Without
an OpenRouter server key, the landing page and visitor-key modes still work.

## Demo configuration and limits

`OPENROUTER_DEMO_MODEL` defaults to `openrouter/free`, which selects available free
models supporting the request's capabilities, including tools. It does not guarantee
a particular model or answer quality. An explicit `provider/model:free` ID is also
accepted. Paid IDs are rejected in demo mode; no paid model fallback is configured.
Check current availability before selecting a fixed model.

- Five attempted user turns per browser session, including failed attempts.
- Forty model starts per UTC day and ten per rolling minute per server process.
- Tool cycles consume additional model calls. Demo SDK retries are disabled.
- Input: 4,000 characters; output: 4,096 tokens per model call.
- Eight main-agent model calls per turn; the last call is reserved for a final
  answer or an honest partial result. A separate 100-step graph ceiling includes
  middleware execution. The shared demo callback also counts internal model calls.
- Starting a new conversation does not reset the session turn counter.

These are small-demo controls, not durable abuse prevention. New browser sessions
reset visitor caps, restarts reset shared counters, and multiple processes have
separate counters. OpenRouter account/provider limits remain authoritative.
Availability and zero infrastructure cost are not guaranteed.

Voice requires the visitor's own OpenAI key; it is not part of the free text demo.

## Architecture

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI, access modes, session state, streaming and voice |
| `agent.py` | Deep Agents, planning middleware, limits, streaming and providers |
| `planning.py` | Shopping quantity consolidation with compatible unit conversions |
| `providers.py` | Explicit settings, demo validation, quotas and public errors |
| `tools.py` | DuckDuckGo search, page reading and instruction scaffolds |
| `tests/` | Offline provider and Streamlit journey tests |
| `test_tools.py` | Original manual search/fetch diagnostic; performs network requests |

Recipe requests are instructed to search, read a page and cite its URL. This is a
prompt instruction, not a programmatic guarantee. Extraction prefers publisher
Recipe JSON-LD, then article/main text, limited to 6,000 characters. Substitution
suggestions remain an instruction scaffold. The old meal-plan scaffold is retained
only for the comparison harness, not exposed by the current chef.

Multi-day planning uses `write_todos`; progress remains available in each reply's
plan expander. `scale_meal_plan` scales original recipe quantities to the diners
per meal before consolidating the shopping. It converts kg/g and l/ml,
keeps incompatible units separate and labels totals containing estimated inputs.
Unspecified quantities stay unspecified; estimated source yields propagate the
estimate label. Arithmetic is deterministic; source accuracy, source yields and
dietary compliance still depend on the model and require review.
Virtual notes live in `StateBackend` and the session checkpointer, not the host
filesystem. Shell execution and delegated subagents are disabled.

The migration is implemented and verified offline. Live five-dinner planning has
not yet met acceptance: free routing/model availability and call budgets prevented
a complete result in the recorded trials. See [evaluation results](evaluations/RESULTS.md).

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Automated tests use fake credentials and responses. Live model/tool checks are separate
and require a configured key and available provider quota.

Chat failures show a reference matching the `personal_chef` server log. Diagnostics
include error category/class, configured model, execution stage and function/line
locations, without exception payloads, keys or conversation content. Interrupted
text remains visible and is explicitly labelled incomplete. The next query starts
with a fresh agent context.

## Hosting

The current UI remains Streamlit. For Streamlit Community Cloud, set server secrets:

```toml
OPENROUTER_API_KEY = "your-real-key"
OPENROUTER_DEMO_MODEL = "openrouter/free"
```

Never commit real secrets. Environment variables take precedence over Streamlit
secrets. Next.js/Vercel is planned, not deployed by this delivery. Before public
rollout, review URL fetching boundaries and use durable quotas for multiple instances.

## References

- [OpenRouter integration](https://openrouter.ai/blog/tutorials/langchain-chatopenrouter-setup/)
- [Free model router](https://openrouter.ai/openrouter/free)
- [Provider limits](https://openrouter.ai/docs/api_reference/limits)

MIT licensed.
